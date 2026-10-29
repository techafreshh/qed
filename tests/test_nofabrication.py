"""No-fabrication checker acceptance tests (issue #28).

Credential-free: scrubbed env with ``QED_OFFLINE=1``. Subprocess is
allowed here on purpose: the checker proves numbers by executing
notebook cells via ``runner.notebook.execute_notebook``.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from evals.nofabrication import (
    build_card_text,
    check,
    extract_card_numbers,
    main,
    match_numbers,
)
from runner.offline import NotFound

CHECKER = Path(__file__).resolve().parent.parent / "evals" / "nofabrication.py"


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


def _run_cli(monkeypatch, *args):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    proc = subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc


def test_genuine_run_zero_untraced(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    for run_id in ("demo_replicated", "demo_failed"):
        untraced, card_numbers, cell_numbers = check(run_id)
        assert untraced == []
        assert cell_numbers, "executed cells must yield numbers for %s" % run_id
    proc = _run_cli(monkeypatch, "demo_replicated")
    assert proc.returncode == 0
    assert "0 untraced" in proc.stdout


def test_doctored_card_999_untraced(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    untraced, card_numbers, _ = check(
        "demo_replicated", card_text="estimate 2.05 doctored 999.99"
    )
    assert 999.99 in untraced
    assert 2.05 in card_numbers
    proc = _run_cli(
        monkeypatch, "demo_replicated", "--card-text", "estimate 999.99"
    )
    assert proc.returncode == 1
    assert "untraced" in proc.stdout
    assert "999.99" in proc.stdout


def test_doctored_card_file_untraced(monkeypatch, tmp_path, capsys):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    card = tmp_path / "card.txt"
    card.write_text("estimate 999.99\n", encoding="utf-8")
    assert main(["--run-id", "demo_replicated", "--card-file", str(card)]) == 1
    out = capsys.readouterr().out
    assert "untraced" in out
    assert "999.99" in out


def test_rounding_normalization(monkeypatch):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    assert match_numbers([2.05], [2.05001]) == []
    assert match_numbers([2.05], [2.05]) == []
    assert match_numbers([999.99], [2.05]) == [999.99]
    assert match_numbers([], [2.05]) == []
    assert match_numbers([2.05], []) == [2.05]


def test_years_skipped_and_unknown_id_errors(monkeypatch, capsys):
    _scrubbed_env(monkeypatch, QED_OFFLINE="1")
    assert 2020.0 not in extract_card_numbers("in 2020 the estimate was 2.05")
    assert extract_card_numbers("in 2020 the estimate was 2.05") == [2.05]
    assert 999.99 in extract_card_numbers("doctored 999.99 in 2020")
    card = build_card_text(
        {"verdict": "REPLICATED", "fragile_choice": "picked in 2020"}
    )
    assert extract_card_numbers(card) == []
    with pytest.raises(NotFound):
        check("no_such_paper_xyz")
    assert main(["no_such_paper_xyz"]) == 2
    out = capsys.readouterr().out
    assert "error" in out
    assert main([]) == 2
