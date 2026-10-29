"""Offline library replay entrypoint (issue #29).

Iterates the frozen manifests and replays each one through the same
in-process orchestrator gate as ``evals/replay.py``. Credential-free:
no network, no subprocess, no model calls — safe under ``QED_OFFLINE=1``
with no keys. Exit 0 iff every verdict matches ``expected_verdict``.
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
    from evals.replay import main as replay_main

    # Default to the full frozen library: evals.replay uses argparse,
    # and a bare None would make it parse the host process's sys.argv
    # (e.g. pytest's) instead of replaying everything.
    return replay_main([] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
