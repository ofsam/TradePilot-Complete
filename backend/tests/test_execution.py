from app.mt5.execution import filling_type, plan_demo_order
from app.strategy.risk import SymbolSpec

SPEC = SymbolSpec(0.01, 0.01, 0.1, 0.01, 100, 0.01, 2)


def _plan(**overrides):
    values = dict(
        environment="demo",
        trade_allowed=True,
        direction="buy",
        price=4045.66,
        stop=4040.00,
        scanned_entry=4045.66,
        scanned_distance=5.66,
        equity=100_000,
        spec=SPEC,
        trades_today=0,
        position_open=False,
        now=1_000,
        expires_at=10_000,
    )
    values.update(overrides)
    return plan_demo_order(**values)


def test_contest_and_unknown_accounts_are_refused():
    for environment in ("contest", "unknown"):
        _plan_result, reason = _plan(environment=environment)
        assert reason == "Orders are sent only on a demo or live account."


def test_live_plan_uses_the_same_risk_limits():
    plan, reason = _plan(environment="live")
    assert reason is None
    assert plan is not None
    assert plan.cash_risk <= 100_000 * 0.02 + 0.01


def test_demo_plan_stays_within_two_percent_and_three_and_a_half():
    plan, reason = _plan()
    assert reason is None
    assert plan is not None
    assert plan.cash_risk <= 100_000 * 0.02 + 0.01
    assert abs((plan.target - plan.price) - 3.5 * (plan.price - plan.stop)) < 0.02
    assert plan.lots >= 0.01


def test_open_position_daily_limit_and_drift_are_refused():
    assert _plan(position_open=True)[1] == "This symbol already has an open position."
    assert _plan(trades_today=2)[1] == "The Ghana day already has two sent trades."
    assert _plan(price=4060, stop=4055, scanned_entry=4045.66, scanned_distance=5)[1].startswith("The live price has moved")
    assert _plan(trade_allowed=False)[1].startswith("The terminal is not allowing")
    assert _plan(now=20_000, expires_at=10_000)[1].startswith("This signal has expired")


def test_a_buy_below_the_stop_is_refused_and_live_distance_is_not_recapped():
    _plan_result, reason = _plan(direction="buy", price=4020, stop=4030, scanned_entry=4020, scanned_distance=10)
    assert reason == "The ask is not above the stop, so this buy cannot be sent."
    plan, reason = _plan(stop=3900, scanned_distance=145.66)
    assert reason is None
    assert plan is not None
    assert abs((plan.target - plan.price) - 3.5 * (plan.price - plan.stop)) < 0.02


def test_filling_mode_prefers_fok_then_ioc():
    assert filling_type(1) == 0
    assert filling_type(2) == 1
    assert filling_type(0) == 2
