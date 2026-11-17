import math
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.strategy.candles import Candle, H1_SECONDS
from app.strategy.engine import run_backtest, scan_latest
from app.strategy.risk import RISK_FRACTION, SymbolSpec, floor_to_step, size_position
from app.strategy.sample import BASE, SAMPLE_SPEC, run_sample, sample_candles

client = TestClient(app)


def test_sample_backtest_wins_one_loses_one_and_skips_the_third_same_day():
    report = run_sample()
    summary = report["summary"]
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["resolved_trades"] == 2
    assert summary["unresolved"] == 0
    assert summary["net_r"] == 2.5
    assert summary["profit_factor_r"] == 3.5
    assert summary["skipped"] == 1
    assert report["skipped"][0]["reason"] == "daily_limit"
    assert [trade["lot_size"] for trade in report["trades"]] == [2.85, 5.34]
    assert report["trades"][0]["r_multiple"] == 3.5
    assert report["trades"][1]["r_multiple"] == -1
    assert report["trades"][1]["exit_reason"] == "stop_loss"
    assert report["ending_equity"] == 10484.65
    shot = report["trades"][0]["shot"]
    assert len(shot["candles"]) >= 2
    assert {level["name"] for level in shot["levels"]} >= {"H4 high", "H4 low", "Retest", "Breakout high", "Breakout low", "Entry", "Stop", "Target"}
    assert report["summary"]["win_rate"] == 0.5
    days = {
        datetime.fromtimestamp(trade["signal_time"], timezone.utc).date()
        for trade in report["trades"]
    }
    assert len(days) == 1
    equity = 10_000
    for trade in report["trades"]:
        assert trade["estimated_risk_cash"] <= equity * RISK_FRACTION + 1e-6
        equity += trade["cash_pnl"]


def test_take_profit_is_three_and_a_half_times_the_stop_distance():
    report = run_sample()
    for trade in report["trades"]:
        distance = abs(trade["entry"] - trade["stop_loss"])
        assert abs(abs(trade["take_profit"] - trade["entry"]) - 3.5 * distance) < 1e-9


def test_lot_size_floors_and_never_rounds_up():
    assert floor_to_step(0.029, 0.01) == 0.02
    spec = SymbolSpec(0.01, 0.01, 1, 0.01, 0.05, 0.01, 2)
    sized = size_position(10_000, 24, spec, require_lots=True)
    assert sized.capped is True
    assert sized.lots == 0.05
    assert sized.cash_risk <= 10_000 * RISK_FRACTION
    too_small = size_position(10, 24, SAMPLE_SPEC, require_lots=True)
    assert too_small.error == "below_min_lot"
    assert too_small.lots is None


def _scan(higher, lower, bid, ask, **overrides):
    values = dict(
        symbol="XAUUSD", h4=higher, h1=lower, bid=bid, ask=ask, equity=10_000,
        spec=SAMPLE_SPEC, trades_today=0, position_open=False, now=lower[-1].time + H1_SECONDS,
    )
    values.update(overrides)
    return scan_latest(**values)


def test_same_candle_stop_and_target_counts_as_a_loss():
    higher, lower = sample_candles()
    fill = Candle(lower[3].time, 110.7, 113.0, 109.0, 111.0)
    report = run_backtest(
        higher, lower[:3] + [fill], symbol="XAUUSD", spec=SAMPLE_SPEC, spread=0,
        spread_source="test", starting_equity=10_000, source="test",
    )
    assert len(report.trades) == 1
    assert report.trades[0].exit_reason == "both_hit_stop_first"
    assert report.trades[0].r_multiple == -1


def _pending_window():
    higher, lower = sample_candles()
    saved = lower[:9]
    return higher, saved, saved[-1].time + H1_SECONDS + 10


def test_open_position_blocks_a_valid_setup():
    higher, saved, now = _pending_window()
    evaluation = _scan(higher, saved, 113.4, 113.6, position_open=True, now=now)
    assert evaluation.proposal is None
    assert evaluation.skip_reason == "position_open"


def test_a_later_h4_bar_does_not_change_the_stop():
    higher, saved, now = _pending_window()
    evaluation = _scan(higher, saved, 113.0, 113.2, now=now)
    assert evaluation.bias == "long"
    assert evaluation.proposal is not None
    assert evaluation.proposal.stop_loss == 112.8


def test_forming_bar_is_ignored():
    higher, lower = sample_candles()
    last = lower[-1]
    forming = Candle(last.time + H1_SECONDS, 1, 2, 0.5, 1.9)
    closed_now = last.time + H1_SECONDS
    ignored = run_backtest(
        higher, lower + [forming], symbol="XAUUSD", spec=SAMPLE_SPEC, spread=0,
        spread_source="test", starting_equity=10_000, source="test", now=closed_now + 10,
    )
    included = run_backtest(
        higher, lower, symbol="XAUUSD", spec=SAMPLE_SPEC, spread=0,
        spread_source="test", starting_equity=10_000, source="test", now=closed_now,
    )
    assert [trade.signal_time for trade in ignored.trades] == [trade.signal_time for trade in included.trades]


def test_neutral_bias_has_no_trade():
    base = int(BASE.timestamp())
    higher = [
        Candle(base, 100, 120, 90, 110),
        Candle(base + 4 * H1_SECONDS, 110, 115, 100, 108),
    ]
    bars = [Candle(base + hour * H1_SECONDS, 105, 112, 100, 108) for hour in range(5, 10)]
    evaluation = _scan(higher, bars, 108, 108.2)
    assert evaluation.bias == "neutral"
    assert evaluation.proposal is None
    assert evaluation.skip_reason == "neutral_bias"


def test_rules_and_sample_backtest_report_execution_flag_from_gate():
    from app.execution_gate import is_execution_enabled

    enabled = is_execution_enabled()
    rules = client.get("/api/v1/strategy/rules")
    assert rules.status_code == 200
    assert rules.json()["execution_enabled"] is enabled
    backtest = client.post("/api/v1/strategy/backtest", json={"source": "sample"})
    assert backtest.status_code == 200
    body = backtest.json()
    assert body["execution_enabled"] is enabled
    assert body["order_submitted"] is False
    assert body["summary"]["resolved_trades"] == 2
    health = client.get("/health")
    assert health.json()["execution_enabled"] is enabled


def test_order_send_exists_only_behind_the_account_guard():
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = [path.name for path in root.rglob("*.py") if "order_send(" in path.read_text(encoding="utf-8")]
    assert offenders == ["adapter.py"]
    adapter = (root / "mt5" / "adapter.py").read_text(encoding="utf-8")
    assert adapter.index('not in {"demo", "live"}') < adapter.index("order_send(")


def test_candle_request_rejects_an_unknown_timeframe():
    response = client.get("/api/v1/mt5/candles?timeframe=M5")
    assert response.status_code == 422


def test_mt5_backtest_requires_an_ordered_date_range():
    missing = client.post("/api/v1/strategy/backtest", json={"source": "mt5", "symbol": "XAUUSD"})
    assert missing.status_code == 422
    backwards = client.post("/api/v1/strategy/backtest", json={"source": "mt5", "symbol": "XAUUSD", "from_date": "2024-03-01", "to_date": "2024-01-01"})
    assert backwards.status_code == 422
    malformed = client.post("/api/v1/strategy/backtest", json={"source": "mt5", "symbol": "XAUUSD", "from_date": "March", "to_date": "2024-01-02"})
    assert malformed.status_code == 422


def test_invalid_symbol_is_rejected():
    response = client.post("/api/v1/strategy/backtest", json={"source": "sample", "symbol": "../etc"})
    assert response.status_code == 422


def test_price_above_the_retest_is_not_an_entry():
    higher, saved, now = _pending_window()
    evaluation = _scan(higher, saved, 113.5, 113.7, now=now)
    assert evaluation.proposal is None
    assert evaluation.skip_reason == "waiting_retest"
    assert evaluation.checks["h4_bias"] is True
    assert evaluation.checks["h1_setup"] is True
    assert evaluation.checks["retest"] is False


def test_a_wide_stop_stays_a_pending_setup():
    base = int(BASE.timestamp())
    higher = [
        Candle(base, 100, 108, 90, 104),
        Candle(base + 4 * H1_SECONDS, 104, 110, 100, 108),
        Candle(base + 8 * H1_SECONDS, 108, 120, 100, 118),
    ]
    candle1 = Candle(base + 8 * H1_SECONDS, 109, 111, 108, 110.5)
    candle2 = Candle(base + 9 * H1_SECONDS, 110.5, 116, 100, 115)
    evaluation = _scan(higher, [candle1, candle2], 114, 114.2, now=base + 10 * H1_SECONDS + 10)
    assert evaluation.proposal is None
    assert evaluation.skip_reason == "waiting_retest"
    assert evaluation.checks["h1_setup"] is True


def test_prices_stay_finite():
    report = run_sample()
    for trade in report["trades"]:
        assert all(math.isfinite(trade[key]) for key in ("entry", "stop_loss", "take_profit", "r_multiple"))


def test_agent_reclaim_enters_on_the_next_open_and_a_bare_sweep_does_not():
    from app.strategy.agent import AGENT_RULES_SOURCE, evaluate_agent
    from app.strategy.engine import run_backtest

    base = 1_700_000_000
    higher = []
    for index in range(30):
        close = 100 + index
        higher.append(Candle(base + index * 4 * H1_SECONDS, close - 1, close + 1, close - 2, close))
    signal_time = higher[-1].time + 4 * H1_SECONDS
    previous = Candle(signal_time - H1_SECONDS, 130, 132, 128, 131)
    reclaim = Candle(signal_time, 129, 136, 127, 135)
    fill = Candle(signal_time + H1_SECONDS, 135, 160, 134, 150)
    report = run_backtest(
        higher, [previous, previous, reclaim, fill], symbol="XAUUSD", spec=SAMPLE_SPEC, spread=0,
        spread_source="test", starting_equity=10_000, source="test", evaluate=evaluate_agent, rules_source=AGENT_RULES_SOURCE,
    )
    assert report.rules_source == AGENT_RULES_SOURCE
    assert len(report.trades) == 1
    assert report.trades[0].direction == "buy"
    assert report.trades[0].entry == 135
    assert report.trades[0].status == "win"
    missed = Candle(signal_time, 129, 131, 127, 130)
    quiet = run_backtest(
        higher, [previous, previous, missed, fill], symbol="XAUUSD", spec=SAMPLE_SPEC, spread=0,
        spread_source="test", starting_equity=10_000, source="test", evaluate=evaluate_agent, rules_source=AGENT_RULES_SOURCE,
    )
    assert quiet.trades == []


def test_unknown_backtest_rules_are_rejected():
    response = client.post("/api/v1/strategy/backtest", json={"source": "sample", "rules": "martingale"})
    assert response.status_code == 422
