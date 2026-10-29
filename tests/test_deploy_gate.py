"""Final deploy-gate acceptance tests (issue #29).

Credential-free: scrubbed env with ``QED_OFFLINE=1`` and a forbidden
``subprocess`` prove the Makefile targets exist, the README/LICENSE
contract holds, the Modal entrypoint is shaped correctly, and the
offline scripts each exit 0. Scripts run in-process via ``runpy`` (no
subprocess) mirroring ``tests/test_replay.py`` style.
"""
import runpy
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _scrubbed_env(monkeypatch, **overrides):
    for key in (
        "META_API_KEY",
        "META_API_URL",
        "MODAL_TOKEN",
        "QED_OFFLINE",
        "QED_CODEGEN_BACKEND",
        "OPENCODE_INVOKED_BY",
        "QED_AGENT_DEPTH",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def _forbid_subprocess(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not run offline")

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _boom)


def _run_script(path: Path) -> int:
    """Execute a ``scripts/*.py`` entry point in-process; return exit code."""
    try:
        runpy.run_path(str(path), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        return 0 if code is None else int(code)
    return 0


def test_makefile_has_deploy_targets():
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("dev:", "test:", "replay:", "eval:", "demo-offline:"):
        assert target in text, "Makefile missing %s target" % target


def test_readme_deploy_contract():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for required in (
        "QED_OFFLINE",
        "muse-spark",
        "Modal",
        "make replay",
        "it never executes the authors' scripts",
    ):
        assert required in text, "README missing %r" % required


def test_license_is_mit():
    first = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").splitlines()[0]
    assert "MIT" in first


def test_modal_entrypoint_shape(monkeypatch):
    # NOTE: modal_app is imported BEFORE the subprocess ban — modal's own
    # annotations evaluate ``subprocess.Popen`` at import time, so the
    # import needs the real stdlib (it spawns nothing and touches no
    # network). Offline script probes below still run fully subprocess-free.
    # The import is scrubbed from sys.modules afterwards so the offline
    # suite's "never imports modal" contract (test_sandbox) holds
    # regardless of test order.
    import sys

    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    before = set(sys.modules)
    try:
        import modal_app

        assert modal_app.APP_NAME == "qed"
        assert getattr(modal_app.app, "name", "") == "qed"
    finally:
        for key in [k for k in sys.modules if k not in before]:
            del sys.modules[key]
    source = (REPO_ROOT / "modal_app.py").read_text(encoding="utf-8")
    assert "modal.App(" in source
    assert '"qed"' in source
    assert "asgi_app" in source
    assert "app.main" in source


@pytest.mark.parametrize(
    "script", ["scripts/replay.py", "scripts/eval.py", "scripts/demo_offline.py"]
)
def test_offline_scripts_exit_zero(monkeypatch, script):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    _forbid_subprocess(monkeypatch)
    assert _run_script(REPO_ROOT / script) == 0
