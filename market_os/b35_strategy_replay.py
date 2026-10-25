"""Synthetic strategy/replay composition; no fitting or performance claims.

Each event settles earlier commands before its signal is consumed. Orders
created from that observation can only be considered by a later event.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any, Sequence

from .b34_strategy import (
    NormalizedNumericalSignal,
    StrategyConfig,
    StrategyDecision,
    SyntheticStrategyAdapter,
)
from .paper_venue import SyntheticMarketEvent, VenueConfig, VenueSnapshot
from .synthetic_replay import ReplayCommand, ReplaySession, ReplayStep


SESSION_SCHEMA = "market-os.b3-5.synthetic-strategy-session@v1"
INTERPRETATION = (
    "synthetic contract and accounting replay only; "
    "no predictive evidence, profitability claim, or promotion approval"
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StrategySignalFixture:
    """One explicit event binding; no nearest-time matching or signal reuse."""

    event_id: str
    signal: NormalizedNumericalSignal

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id:
            raise ValueError("fixture requires an event_id")
        if not isinstance(self.signal, NormalizedNumericalSignal):
            raise ValueError("fixture requires a typed numerical signal")
        replace(self.signal)  # Revalidate the producer's fingerprint and fields.

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "signal": self.signal.to_dict()}


@dataclass(frozen=True)
class StrategyReplayObservation:
    event_id: str
    replay_step: ReplayStep
    snapshot: VenueSnapshot
    decision: StrategyDecision | None
    command: ReplayCommand | None
    command_state: str

    def __post_init__(self) -> None:
        if self.replay_step.event_id != self.event_id:
            raise ValueError("observation event does not match replay step")
        if self.replay_step.venue_snapshot_fingerprint != self.snapshot.fingerprint:
            raise ValueError("observation snapshot does not match replay step")
        if self.decision is None:
            if self.command is not None or self.command_state != "missing_signal":
                raise ValueError("missing signal cannot create a command")
        elif self.decision.event_id != self.event_id:
            raise ValueError("decision event mismatch")
        elif self.decision.order is None:
            if self.command is not None or self.command_state != "no_order":
                raise ValueError("non-order decision cannot create a command")
        else:
            if self.command_state not in {"queued", "unexecuted_end_of_stream"}:
                raise ValueError("order decision requires an explicit command state")
            if self.command is None or self.command.order != self.decision.order:
                raise ValueError("command must preserve the strategy order")
            if self.command.submitted_at_ms <= self.replay_step.event_time_ms:
                raise ValueError("command cannot execute on its decision event")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "replay_step": self.replay_step.to_dict(),
            "snapshot": self.snapshot.to_dict(),
            "decision": self.decision.to_dict() if self.decision else None,
            "command": self.command.to_dict() if self.command else None,
            "command_state": self.command_state,
        }


@dataclass(frozen=True)
class StrategyReplayReport:
    """Immutable canonical report; callers receive independent dictionary copies."""

    canonical_payload: str
    fingerprint: str

    def __post_init__(self) -> None:
        payload = json.loads(self.canonical_payload)
        if not isinstance(payload, dict) or payload.get("schema") != SESSION_SCHEMA:
            raise ValueError("unsupported strategy session schema")
        if payload.get("synthetic_only") is not True or payload.get("interpretation") != INTERPRETATION:
            raise ValueError("strategy session must preserve the synthetic boundary")
        if "fingerprint" in payload:
            raise ValueError("report projection cannot contain its own fingerprint")
        if self.canonical_payload != _canonical(payload) or self.fingerprint != _fingerprint(payload):
            raise ValueError("strategy session fingerprint mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**json.loads(self.canonical_payload), "fingerprint": self.fingerprint}

    def verify_replay(self, other: StrategyReplayReport) -> bool:
        return isinstance(other, StrategyReplayReport) and self == other


def run_strategy_replay(
    events: Sequence[SyntheticMarketEvent],
    fixtures: Sequence[StrategySignalFixture],
    *,
    strategy_config: StrategyConfig | None = None,
    venue_config: VenueConfig | None = None,
) -> StrategyReplayReport:
    """Compose existing policy and matching without rewriting their decisions.

    Missing signals generate no decision or order. Signals are consumed once
    at their explicitly bound event; future or stale signals retain B3.4's
    reject/abstain result. End-of-stream orders are retained, never auto-filled.
    """
    strategy_config = StrategyConfig() if strategy_config is None else strategy_config
    venue_config = VenueConfig() if venue_config is None else venue_config
    if not isinstance(strategy_config, StrategyConfig) or not isinstance(venue_config, VenueConfig):
        raise ValueError("strategy and venue configurations must be typed")
    replace(strategy_config)
    replace(venue_config)
    events = tuple(events)
    for event in events:
        if not isinstance(event, SyntheticMarketEvent):
            raise ValueError("events must be typed synthetic events")
        replace(event)
    replay = ReplaySession(events, (), venue_config)
    adapter = SyntheticStrategyAdapter(strategy_config)
    event_ids = {event.event_id for event in events}
    by_event: dict[str, StrategySignalFixture] = {}
    signal_ids: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, StrategySignalFixture):
            raise ValueError("fixtures must be typed signal bindings")
        replace(fixture)
        if fixture.event_id not in event_ids:
            raise ValueError("fixture references an unknown event")
        if fixture.event_id in by_event or fixture.signal.signal_id in signal_ids:
            raise ValueError("duplicate event binding or signal identity")
        by_event[fixture.event_id] = fixture
        signal_ids.add(fixture.signal.signal_id)

    observations: list[StrategyReplayObservation] = []
    terminal_commands: list[ReplayCommand] = []
    for index, event in enumerate(events):
        step = replay.step(event)
        snapshot = replay.final_venue_snapshot
        fixture = by_event.get(event.event_id)
        decision = None
        command = None
        state = "missing_signal"
        if fixture is not None:
            decision = adapter.decide(fixture.signal, event, snapshot)
            state = "no_order"
            if decision.order is not None:
                command = ReplayCommand(decision.order.order_id, decision.order.submitted_at_ms, decision.order)
                if index == len(events) - 1:
                    state = "unexecuted_end_of_stream"
                    terminal_commands.append(command)
                else:
                    replay.submit_command(command)
                    state = "queued"
        observations.append(StrategyReplayObservation(event.event_id, step, snapshot, decision, command, state))
    replay.run()  # Also completes an empty stream deterministically.
    decision_counts: dict[str, int] = {}
    for observation in observations:
        action = observation.decision.action if observation.decision else "missing_signal"
        decision_counts[action] = decision_counts.get(action, 0) + 1
    payload = {
        "schema": SESSION_SCHEMA,
        "synthetic_only": True,
        "interpretation": INTERPRETATION,
        "strategy_config": strategy_config.to_dict(),
        "venue_config": venue_config.to_dict(),
        "fixtures": [by_event[event.event_id].to_dict() for event in events if event.event_id in by_event],
        "observations": [item.to_dict() for item in observations],
        "decision_counts": dict(sorted(decision_counts.items())),
        "replay": replay.to_dict(),
        "unexecuted_end_of_stream": [command.to_dict() for command in terminal_commands],
    }
    return StrategyReplayReport(_canonical(payload), _fingerprint(payload))


def verify_strategy_replay(first: StrategyReplayReport, second: StrategyReplayReport) -> bool:
    return first.verify_replay(second)


__all__ = [
    "SESSION_SCHEMA",
    "INTERPRETATION",
    "StrategySignalFixture",
    "StrategyReplayObservation",
    "StrategyReplayReport",
    "run_strategy_replay",
    "verify_strategy_replay",
]
