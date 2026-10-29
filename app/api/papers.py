"""GET /api/papers over the frozen YAML library (offline, credential-free)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from library import schema as library_schema

router = APIRouter(prefix="/api/papers", tags=["papers"])

# The placeholder fixture is not a real frozen paper; never list it.
_FIXTURE_FILENAME = "example.yaml"

# Offline fallback so the endpoint degrades instead of raising (never 500).
_FALLBACK_PAPERS = [
    {
        "id": "demo_replicated",
        "title": "Demo replicated finding (offline fallback)",
        "citation": "Demo et al. (2024). Offline fallback finding. Journal of Demos.",
        "claim": "The demo effect replicates offline.",
        "expected_verdict": "REPLICATED",
        "source": "offline fallback",
    },
    {
        "id": "demo_failed",
        "title": "Demo failed finding (offline fallback)",
        "citation": "Demo et al. (2024). Offline fallback finding. Journal of Demos.",
        "claim": "The demo effect fails to replicate offline.",
        "expected_verdict": "FAILED",
        "source": "offline fallback",
    },
    {
        "id": "example_replication",
        "title": "Example replication (offline fallback)",
        "citation": "Smith, J. et al. (2015). Example finding. Journal of Example Studies.",
        "claim": "Smaller class sizes raise average test scores.",
        "expected_verdict": "REPLICATED",
        "source": "offline fallback",
    },
    {
        "id": "card_krueger_1994_minwage",
        "title": (
            "Card, D., & Krueger, A. B. (1994). Minimum wages and employment. "
            "American Economic Review (offline fallback)."
        ),
        "citation": (
            "Card, D., & Krueger, A. B. (1994). Minimum wages and employment: "
            "A case study of the fast-food industry in New Jersey and "
            "Pennsylvania. American Economic Review, 84(4), 772-793."
        ),
        "claim": "Raising the minimum wage did not reduce fast-food employment.",
        "expected_verdict": "REPLICATED",
        "source": "offline fallback",
    },
]


def _papers_dir() -> Path:
    return Path(library_schema.__file__).resolve().parent / "papers"


def _manifest_to_paper(manifest: library_schema.PaperManifest) -> dict:
    return {
        "id": manifest.id,
        "title": manifest.citation,
        "citation": manifest.citation,
        "claim": manifest.claim,
        "expected_verdict": manifest.expected_verdict,
        "source": manifest.source,
    }


def list_paper_dicts() -> list[dict]:
    """Read frozen manifests from disk; fall back to demo ids, never raise."""
    try:
        items = [
            _manifest_to_paper(library_schema.load_manifest(path))
            for path in sorted(_papers_dir().glob("*.yaml"))
            if path.is_file() and path.name != _FIXTURE_FILENAME
        ]
    except Exception:
        items = []
    if len(items) >= 4:
        return items
    seen = {item["id"] for item in items}
    for fallback in _FALLBACK_PAPERS:
        if fallback["id"] not in seen:
            items.append(dict(fallback))
            seen.add(fallback["id"])
        if len(items) >= 4:
            break
    return items


@router.get("", include_in_schema=False)
def list_papers_no_slash() -> list[dict]:
    return list_paper_dicts()


@router.get("/")
def list_papers() -> list[dict]:
    return list_paper_dicts()
