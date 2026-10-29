"""Frozen-paper replay gate (issue #26).

Iterates ``library/papers/*.yaml`` (excluding the ``example.yaml``
placeholder), runs the orchestrator in-process per manifest, and compares
each verdict to ``expected_verdict``. Exit 0 iff all match, 1 on any
mismatch, 2 on loader/usage errors. Offline-first and credential-free:
no network, no subprocess.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_PAPERS_DIR = Path(__file__).resolve().parent.parent / "library" / "papers"
FIXTURES = {"example.yaml"}


def _clean_id(paper_id: str) -> str:
    """Mirror ``runner.offline._check_id`` traversal guard; raises ValueError."""
    if not isinstance(paper_id, str):
        raise ValueError("unknown paper %r" % (paper_id,))
    cleaned = paper_id.strip()
    if not cleaned:
        raise ValueError("unknown paper %r" % (paper_id,))
    for bad in ("/", "\\", "."):
        if bad in cleaned:
            raise ValueError("unknown paper %r" % (paper_id,))
    if "\x00" in cleaned:
        raise ValueError("unknown paper %r" % (paper_id,))
    return cleaned


def _load_manifests(papers_dir: Path):
    """Load and validate manifests, excluding placeholder fixtures."""
    from library.schema import load_library, load_manifest

    manifests = load_library(papers_dir)
    fixture_ids: set[str] = set()
    for name in FIXTURES:
        try:
            fixture_ids.add(load_manifest(Path(papers_dir) / name).id)
        except Exception:
            continue
    return [m for m in manifests if m.id not in fixture_ids]


def replay_paper(manifest) -> tuple[str, str, bool]:
    """Run the orchestrator for one manifest; return (id, verdict, matched)."""
    from agent.orchestrate import run_claim

    result = run_claim(manifest.id, manifest.claim)
    verdict = result.get("verdict")
    if not isinstance(verdict, str) or not verdict:
        verdict = "FAILED"
    return manifest.id, verdict, verdict == manifest.expected_verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay frozen papers and compare verdicts to expectations."
    )
    parser.add_argument(
        "--paper",
        action="append",
        default=None,
        help="Replay only this paper id (repeatable).",
    )
    parser.add_argument(
        "--papers-dir",
        default=str(DEFAULT_PAPERS_DIR),
        help="Directory holding paper manifests (default: library/papers).",
    )
    args = parser.parse_args(argv)

    papers_dir = Path(args.papers_dir)
    try:
        manifests = _load_manifests(papers_dir)
    except Exception as exc:
        print("replay error: cannot load manifests: %s" % exc, file=sys.stderr)
        return 2

    wanted: list[str] | None = None
    if args.paper:
        wanted = []
        for raw in args.paper:
            try:
                wanted.append(_clean_id(raw))
            except ValueError as exc:
                print("replay error: %s" % exc, file=sys.stderr)
                return 2
        by_id = {m.id: m for m in manifests}
        unknown = [pid for pid in wanted if pid not in by_id]
        if unknown:
            print(
                "replay error: unknown paper %r" % unknown[0], file=sys.stderr
            )
            return 2
        manifests = [by_id[pid] for pid in wanted]

    if not manifests:
        print("replay error: no papers to replay", file=sys.stderr)
        return 2

    matched = 0
    for manifest in manifests:
        try:
            paper_id, verdict, ok = replay_paper(manifest)
        except Exception as exc:
            print(
                "MISMATCH %s: error %s, expected %s"
                % (manifest.id, exc, manifest.expected_verdict)
            )
            continue
        if ok:
            matched += 1
            print("ok %s: %s" % (paper_id, verdict))
        else:
            print(
                "MISMATCH %s: got %s, expected %s"
                % (paper_id, verdict, manifest.expected_verdict)
            )
    print("%d/%d match" % (matched, len(manifests)))
    return 0 if matched == len(manifests) else 1


if __name__ == "__main__":
    sys.exit(main())
