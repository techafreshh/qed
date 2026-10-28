import importlib
import os
from pathlib import Path

from fastapi.testclient import TestClient


def _scrubbed_env(monkeypatch, **overrides):
    for key in (
        "META_API_KEY",
        "MODAL_TOKEN",
        "QED_OFFLINE",
        "QED_CODEGEN_BACKEND",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def _fresh_settings():
    import app.config

    return importlib.reload(app.config)


def test_defaults_with_clean_env(monkeypatch):
    _scrubbed_env(monkeypatch)
    config = _fresh_settings()
    try:
        s = config.get_settings()
        assert s.offline is True
        assert s.codegen_backend == "llama_direct"
        assert s.meta_api_key == ""
        assert s.modal_token == ""
    finally:
        importlib.reload(config)


def test_offline_explicit_1_is_true(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    config = _fresh_settings()
    try:
        assert config.get_settings().offline is True
    finally:
        importlib.reload(config)


def test_offline_explicit_0_is_false(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="0")
    config = _fresh_settings()
    try:
        assert config.get_settings().offline is False
    finally:
        importlib.reload(config)


def test_offline_falsy_words_opt_out(monkeypatch):
    for word in ("false", "no", "off", "FALSE", "No", "OFF"):
        _scrubbed_env(monkeypatch, QED_OFFLINE=word)
        config = _fresh_settings()
        try:
            assert config.get_settings().offline is False, word
        finally:
            importlib.reload(config)


def test_env_example_contains_all_keys():
    example = Path(__file__).resolve().parent.parent / ".env.example"
    content = example.read_text(encoding="utf-8")
    for key in (
        "META_API_KEY",
        "MODAL_TOKEN",
        "QED_OFFLINE",
        "QED_CODEGEN_BACKEND",
    ):
        assert key in content


def test_repr_never_leaks_secrets(monkeypatch):
    _scrubbed_env(
        monkeypatch,
        META_API_KEY="super-secret-meta",
        MODAL_TOKEN="super-secret-modal",
    )
    config = _fresh_settings()
    try:
        rendered = repr(config.get_settings())
        assert "super-secret-meta" not in rendered
        assert "super-secret-modal" not in rendered
    finally:
        importlib.reload(config)


def test_health_boots_with_defaults(monkeypatch):
    _scrubbed_env(monkeypatch)
    config = _fresh_settings()
    try:
        import app.main

        importlib.reload(app.main)
        client = TestClient(app.main.app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    finally:
        importlib.reload(config)
        import app.main

        importlib.reload(app.main)


def test_dotenv_does_not_override_environment(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text('QED_OFFLINE=0\nQED_CODEGEN_BACKEND="custom"\n', encoding="utf-8")
    monkeypatch.setenv("QED_OFFLINE", "1")
    import app.config as config_mod

    config_mod.load_dotenv(dotenv)
    try:
        assert os.environ["QED_OFFLINE"] == "1"
        assert os.environ["QED_CODEGEN_BACKEND"] == "custom"
    finally:
        monkeypatch.delenv("QED_CODEGEN_BACKEND", raising=False)
