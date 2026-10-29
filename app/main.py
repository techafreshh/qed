from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings  # noqa: F401  (loads env with safe defaults)

app = FastAPI(title="QED")

# API routers are optional: the UI shell lap works with or without them.
try:
    from app.api.events import router as events_router

    app.include_router(events_router)
except Exception:
    pass
try:
    from app.api.papers import router as papers_router

    app.include_router(papers_router)
except Exception:
    pass
try:
    from app.api.runs import router as runs_router

    app.include_router(runs_router)
except Exception:
    pass

STATIC_DIR = Path(__file__).resolve().parent / "static"

_PLACEHOLDER_HTML = (
    "<html><head><title>QED</title></head>"
    "<body><h1>QED</h1>"
    "<p>A second opinion for published science. Walking skeleton.</p>"
    "</body></html>"
)


def _index_path() -> Path:
    return STATIC_DIR / "index.html"


def _safe_static_child(name: str) -> Path | None:
    """Resolve a static file without escaping STATIC_DIR; None if unsafe."""
    try:
        candidate = (STATIC_DIR / name).resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(STATIC_DIR.resolve())
    except ValueError:
        return None
    return candidate


if (STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def root():
    index = _index_path()
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse(_PLACEHOLDER_HTML)


@app.get("/{full_path:path}", response_class=HTMLResponse)
def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "not found"}, status_code=404)
    candidate = _safe_static_child(full_path)
    if candidate is not None and candidate.is_file():
        return FileResponse(candidate)
    index = _index_path()
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse(_PLACEHOLDER_HTML)
