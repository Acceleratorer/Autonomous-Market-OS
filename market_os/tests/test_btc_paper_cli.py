from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_os.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "btc_paper" / "replay.json"


def test_btc_paper_cli_replay_is_read_only_inspection(capsys) -> None:
    assert main(["btc-paper", "replay", "--fixture", str(FIXTURE)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["manifest"]["symbol"] == "BTCUSDT"
    assert result["manifest"]["candle_count"] == 12


def test_btc_paper_cli_reports_fixture_read_errors() -> None:
    with pytest.raises(SystemExit, match="cannot read BTC replay fixture"):
        main(["btc-paper", "replay", "--fixture", str(FIXTURE.with_suffix(".missing"))])
