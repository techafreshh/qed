"""Application configuration with offline-first safe defaults.

Secrets live in `.env` (see `.env.example`) and are never logged.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

_OFFLINE_FALSE_VALUES = frozenset({"0", "false", "no", "off"})

_DEFAULT_CODEGEN_BACKEND = "llama_direct"


def parse_offline(value: str | None) -> bool:
    """Unset or empty means offline; only explicit falsy strings opt out."""
    if value is None:
        return True
    if value.strip() == "":
        return True
    return value.strip().lower() not in _OFFLINE_FALSE_VALUES


def load_dotenv(path: str | Path | None = None) -> None:
    """Minimal `.env` parser: KEY=VALUE, `#` comments, optional quotes.

    Never overrides real environment variables; silently no-ops when
    no `.env` file exists.
    """
    dotenv_path = Path(path) if path is not None else Path.cwd() / ".env"
    try:
        content = dotenv_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_dotenv()


@dataclass
class Settings:
    meta_api_key: str = field(default="", repr=False)
    modal_token: str = field(default="", repr=False)
    offline: bool = True
    codegen_backend: str = _DEFAULT_CODEGEN_BACKEND

    def __repr__(self) -> str:
        return (
            f"Settings(meta_api_key='***', modal_token='***', "
            f"offline={self.offline!r}, "
            f"codegen_backend={self.codegen_backend!r})"
        )


def get_settings() -> Settings:
    return Settings(
        meta_api_key=os.environ.get("META_API_KEY", ""),
        modal_token=os.environ.get("MODAL_TOKEN", ""),
        offline=parse_offline(os.environ.get("QED_OFFLINE")),
        codegen_backend=os.environ.get(
            "QED_CODEGEN_BACKEND", _DEFAULT_CODEGEN_BACKEND
        ),
    )


settings = get_settings()
