"""Offline eval gate entrypoint (issue #29).

Replays every frozen (non-fixture) manifest in-process and compares each
verdict to the manifest's ``expected_verdict``, printing a PASS/FAIL
table. Credential-free: no network, no subprocess, no model calls —
safe under ``QED_OFFLINE=1`` with no keys. Exit 0 iff all match.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("QED_OFFLINE", "1")


def main(argv: list[str] | None = None) -> int:
    from evals.replay import _load_manifests, replay_paper

    del argv  # the eval gate always covers the full frozen library
    papers_dir = _REPO_ROOT / "library" / "papers"
    try:
        manifests = _load_manifests(papers_dir)
    except Exception as exc:
        print("eval error: cannot load manifests: %s" % exc, file=sys.stderr)
        return 2
    if not manifests:
        print("eval error: no papers to evaluate", file=sys.stderr)
        return 2
    failures = 0
    for manifest in manifests:
        try:
            paper_id, verdict, ok = replay_paper(manifest)
        except Exception as exc:
            print("FAIL %-32s error %s" % (manifest.id, exc))
            failures += 1
            continue
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(
            "%s %-32s got %-10s expected %s"
            % (mark, paper_id, verdict, manifest.expected_verdict)
        )
    print("eval: %d/%d pass" % (len(manifests) - failures, len(manifests)))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
