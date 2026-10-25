from __future__ import annotations
from dataclasses import replace
import pytest
from market_os.paper_venue import SyntheticMarketEvent, VenueConfig, VirtualPaperVenue
from market_os.b34_strategy import NormalizedNumericalSignal, StrategyConfig, StrategyError, SyntheticStrategyAdapter, decide

def ev(t=1000): return SyntheticMarketEvent("synthetic-event", "BTCUSDT", t, 100.0, 101.0, 100.5, 1.0, "a"*64)
def snap(btc=0.0): return VirtualPaperVenue(VenueConfig(initial_btc_quantity=btc, initial_average_entry_price=90.0 if btc else 0.0)).snapshot()
def sig(p=0.6, status="usable", kind="calibrated_probability", t=1000): return NormalizedNumericalSignal("synthetic-signal", "BTCUSDT", t, kind, p, status, "b"*64)

def test_buy_hold_sell_to_flat_path():
    d=decide(sig(0.6), ev(), snap()); assert d.action=="buy" and d.order is not None
    assert decide(sig(0.6), ev(), snap(1.0)).action=="hold"
    d=decide(sig(0.4), ev(), snap(1.0)); assert d.action=="sell" and d.order.quantity==1.0

@pytest.mark.parametrize("status", ["unavailable","stale","abstained","contradictory","schema_invalid","unsupported"])
def test_bad_status_abstains(status): assert decide(sig(status=status), ev(), snap()).action=="abstain"

def test_threshold_boundary_and_hold_band():
    c=StrategyConfig(buy_threshold=.6, sell_threshold=.4)
    assert decide(sig(.6),ev(),snap(),c).action=="buy"
    assert decide(sig(.4),ev(),snap(1),c).action=="sell"
    assert decide(sig(.5),ev(),snap(),c).action=="hold"

def test_score_stale_cash_and_fingerprint_guards():
    assert decide(sig(kind="uncalibrated_score"),ev(),snap()).action=="abstain"
    assert decide(sig(t=0),ev(400001),snap()).action=="abstain"
    assert decide(sig(.9),ev(),snap(),StrategyConfig(max_order_notional_usdt=1)).action=="buy"
    with pytest.raises(StrategyError,match="mismatch"): replace(sig(), fingerprint="0"*64)
    with pytest.raises(StrategyError,match="fingerprint"): NormalizedNumericalSignal("x","BTCUSDT",1,"calibrated_probability",.5,"usable","provider")

def test_deterministic_decisions_and_timestamp_guard():
    a=decide(sig(),ev(),snap()); b=decide(sig(),ev(),snap()); assert a.to_dict()==b.to_dict()
    assert decide(sig(t=2000),ev(1000),snap()).action=="reject"

def test_finite_and_no_derivative_fields():
    with pytest.raises(StrategyError): sig(float("nan"))
    d=decide(sig(),ev(),snap()); assert not hasattr(d,"leverage") and not hasattr(d,"futures")

def test_adapter_duplicate_and_chronology_guards():
    adapter = SyntheticStrategyAdapter()
    assert adapter.decide(sig(), ev(), snap()).action == "buy"
    assert adapter.decide(sig(), ev(), snap()).action == "reject"
    older = NormalizedNumericalSignal("synthetic-older", "BTCUSDT", 999, "calibrated_probability", .6, "usable", "b" * 64)
    assert adapter.decide(older, ev(999), snap()).action == "reject"

def test_sell_to_flat_rejects_excess_notional():
    assert decide(sig(.4), ev(), snap(1), StrategyConfig(max_order_notional_usdt=50)).action == "reject"
