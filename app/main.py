from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.papers import router as papers_router
from app.api.runs import router as runs_router
from app.config import settings  # noqa: F401  (loads env with safe defaults)

app = FastAPI(title="QED")
app.include_router(papers_router)
app.include_router(runs_router)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def root():
    return (
        "<html><head><title>QED</title></head>"
        "<body><h1>QED</h1>"
        "<p>A second opinion for published science. Walking skeleton.</p>"
        "</body></html>"
    )
