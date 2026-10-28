"""Single-shot structured codegen via the Meta Model API (issue #11).

Offline default: return a deterministic pandas/statsmodels analysis script
as a string. The caller writes it to disk; this module never writes files,
never executes code, and never logs secrets. A live Meta Model API call is
attempted only when ``QED_OFFLINE`` explicitly opts out AND a non-empty
``META_API_KEY`` is set; any live failure silently falls back to the
offline template.
"""
from __future__ import annotations

import os

try:
    from codegen.base import RecursionGuardError as _BaseGuardError
except ImportError:
    _BaseGuardError = None

if _BaseGuardError is not None:
    RecursionGuardError = _BaseGuardError
else:

    class RecursionGuardError(RuntimeError):
        """Raised when codegen runs inside an agent invocation."""

try:
    from codegen.base import check_recursion_guard as _base_guard
except ImportError:
    _base_guard = None

try:
    from codegen.base import CodegenBackend as _CodegenBackend
except ImportError:
    _CodegenBackend = None

_GUARD_VARS = ("OPENCODE_INVOKED_BY", "QED_AGENT_DEPTH")
_OFFLINE_FALSE_VALUES = frozenset({"0", "false", "no", "off"})

_LIVE_MAX_TOKENS = 256
_LIVE_TIMEOUT = 10.0
_META_API_URL = "https://api.llama.com/v1/chat/completions"
_META_MODEL = "Llama-4-Maverick-17B-128E-Instruct-FP8"

_LABEL_KEYS = ("id", "claim", "estimator")

__all__ = ["LlamaBackend", "RecursionGuardError"]


def _guard() -> None:
    """Refuse recursive agent invocation before any other work."""
    if _base_guard is not None:
        _base_guard()
        return
    for var in _GUARD_VARS:
        value = os.environ.get(var)
        if value is not None and value.strip() != "":
            raise RecursionGuardError(
                "recursive agent invocation refused: %s is set" % var
            )


def _is_offline() -> bool:
    """True unless explicitly online with a usable key.

    Mirrors ``app.config.parse_offline``: unset/empty ``QED_OFFLINE`` means
    offline; only explicit falsy words opt out. Even then, an empty
    ``META_API_KEY`` forces the offline template.
    """
    try:
        from app.config import parse_offline
    except ImportError:

        def parse_offline(value):
            if value is None:
                return True
            if value.strip() == "":
                return True
            return value.strip().lower() not in _OFFLINE_FALSE_VALUES

    if parse_offline(os.environ.get("QED_OFFLINE")):
        return True
    return not os.environ.get("META_API_KEY", "").strip()


def _coerce_label(value) -> str:
    """Coerce ragged spec/profile input to a short single-line label.

    Never raises: dicts prefer ``id``/``claim``/``estimator`` keys,
    ``None`` maps to ``""``, everything else goes through ``str()``.
    """
    try:
        if value is None:
            return ""
        if isinstance(value, dict):
            for key in _LABEL_KEYS:
                item = value.get(key)
                if item is not None and str(item).strip() != "":
                    return _coerce_label(item)
            return _coerce_label(str(value))
        collapsed = " ".join(str(value).split())
        return collapsed[:200]
    except Exception:
        return ""


def _offline_template(spec, dataset_profile, prior_traceback=None) -> str:
    """Build the deterministic offline pandas/statsmodels script."""
    spec_label = _coerce_label(spec)
    profile_label = _coerce_label(dataset_profile)
    header = [
        "# llama_direct offline codegen: deterministic template (no network, no keys).",
        "# spec: %s" % spec_label,
        "# dataset_profile: %s" % profile_label,
    ]
    try:
        tb_text = str(prior_traceback).strip() if prior_traceback is not None else ""
    except Exception:
        tb_text = ""
    if tb_text != "":
        header.append("# prior traceback context (repair hint only, not executed):")
        for line in tb_text.splitlines()[:20]:
            header.append("# " + line[:200])
    body = (
        "import sys\n"
        "\n"
        "import pandas as pd\n"
        "import statsmodels.api as sm\n"
        "\n"
        'CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "data.csv"\n'
        "\n"
        "\n"
        "def main(path=CSV_PATH):\n"
        '    """Load CSV and fit OLS (Logit fallback for binary outcomes)."""\n'
        "    df = pd.read_csv(path)\n"
        "    outcome = df.columns[-1]\n"
        "    predictors = list(df.columns[:-1])\n"
        "    y = df[outcome]\n"
        '    X = sm.add_constant(df[predictors], has_constant="add")\n'
        '    ols_result = sm.OLS(y, X, missing="drop").fit()\n'
        "    print(ols_result.summary())\n"
        "    print(ols_result.params)\n"
        "    # Logit fallback: uncomment when the outcome is binary (0/1).\n"
        '    # logit_result = sm.Logit(y, X, missing="drop").fit(disp=False)\n'
        "    # print(logit_result.summary())\n"
        "    # print(logit_result.params)\n"
        "    return ols_result\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    main()\n"
    )
    return "\n".join(header) + "\n" + body


def _looks_valid(code) -> bool:
    """Check a live reply is a usable pandas/statsmodels script."""
    return (
        isinstance(code, str)
        and "import pandas" in code
        and "statsmodels" in code
        and len(code) > 200
    )


def _live_prompt(spec_label: str, profile_label: str) -> str:
    return (
        "Write a single Python analysis script using pandas and statsmodels. "
        "Return Python code only, no prose. "
        "The script must load its CSV path from sys.argv[1] "
        '(default "data.csv"), fit an OLS model with statsmodels, '
        "print the summary and params, and include a Logit fallback. "
        "Spec: %s. Dataset profile: %s."
        % (spec_label, profile_label)
    )


def _live_author(prompt: str):
    """Attempt one live Meta Model API call; return reply or None."""
    try:
        from agent.llm import complete
    except ImportError:
        complete = None
    if complete is not None:
        try:
            return complete(prompt, max_tokens=_LIVE_MAX_TOKENS)
        except Exception:
            return None
    try:
        import httpx
    except ImportError:
        return None
    try:
        key = os.environ.get("META_API_KEY", "")
        url = os.environ.get("META_API_URL", "") or _META_API_URL
        response = httpx.post(
            url,
            headers={"Authorization": "Bearer %s" % key},
            json={
                "model": _META_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": _LIVE_MAX_TOKENS,
            },
            timeout=_LIVE_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    message = first.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, str) and content:
                            return content
                    text = first.get("text")
                    if isinstance(text, str) and text:
                        return text
        return None
    except Exception:
        return None


_Base = _CodegenBackend if _CodegenBackend is not None else object


class LlamaBackend(_Base):
    """Direct Llama code author: live API when online, template otherwise."""

    def author(self, spec, dataset_profile=None, prior_traceback=None, **kwargs):
        """Author a pandas/statsmodels script string for ``spec``."""
        if dataset_profile is None and "profile" in kwargs:
            dataset_profile = kwargs["profile"]
        if prior_traceback is None and "prior_traceback" in kwargs:
            prior_traceback = kwargs["prior_traceback"]
        _guard()
        if _is_offline():
            return _offline_template(spec, dataset_profile, prior_traceback)
        try:
            reply = _live_author(
                _live_prompt(_coerce_label(spec), _coerce_label(dataset_profile))
            )
        except Exception:
            reply = None
        if _looks_valid(reply):
            return reply
        return _offline_template(spec, dataset_profile, prior_traceback)
