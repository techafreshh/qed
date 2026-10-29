"""Modal deployment entrypoint: QED FastAPI app at a stable URL (issue #29).

Deploy with::

    modal deploy modal_app.py

which serves the existing FastAPI app (``app.main:app`` — UI bundle
included) at the stable ``https://<workspace>--qed-....modal.run`` URL.
Keep the deployment live through Nov 8 (re-deploy to extend). Preview
without deploying via ``modal serve modal_app.py``.

Operator keys (``META_API_KEY``, ``MODAL_TOKEN``) are inserted at deploy
time via ``modal secret`` / ``modal deploy`` env only — never committed.
Without keys the app serves the offline demo path (``QED_OFFLINE=1``
default); the run endpoints degrade to cached demo verdicts instead of
500s.

``modal`` is imported lazily so credential-free runs (``QED_OFFLINE=1``
tests, offline replay/eval) never touch it; without ``modal``
installed, importing this module still succeeds and only building the
function raises.
"""

from __future__ import annotations

APP_NAME = "qed"

try:
    import modal
except ImportError:  # pragma: no cover - modal is a deploy-time dep only
    modal = None  # type: ignore[assignment]


if modal is not None:
    # Pure builder objects — no network, no credentials at import time.
    image = (
        modal.Image.debian_slim()
        .pip_install_from_requirements("requirements.txt")
        .add_local_python_source(
            "app", "agent", "codegen", "db", "library", "rubric", "runner"
        )
        # ``add_local_python_source`` ships ``.py`` files only, so the UI
        # bundle, frozen manifests, and cached fixtures ride along as
        # explicit dirs, landing where the code resolves them:
        # ``app/main.py:STATIC_DIR`` (``.../app/static``),
        # ``runner/offline.py:CACHE_ROOT`` (``.../library/cache``), and
        # ``library/schema.py`` papers dir (``.../library/papers``).
        .add_local_dir("app/static", remote_path="/root/app/static")
        .add_local_dir("library/cache", remote_path="/root/library/cache")
        .add_local_dir("library/papers", remote_path="/root/library/papers")
    )

    app = modal.App(APP_NAME)

    @app.function(image=image)
    @modal.asgi_app()
    def qed_asgi():
        """Return the existing FastAPI app; Modal serves it as ASGI."""
        from app.main import app as web_app

        return web_app
else:  # pragma: no cover - local runs without the modal package

    def qed_asgi():  # type: ignore[misc]
        """Fail loudly only when the Modal entrypoint is actually built."""
        raise RuntimeError(
            "modal package is required to serve qed_asgi: "
            "pip install 'modal>=1.0'"
        )
