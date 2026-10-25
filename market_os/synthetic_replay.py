"""Deterministic, local-only replay driver for the synthetic paper venue."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from .paper_venue import (
    InvalidMarketEvent,
    InvalidOrder,
    OrderRejected,
    SyntheticMarketEvent,
    VenueConfig,
    VenueError,
    VenueSnapshot,
    VirtualOrder,
    VirtualPaperVenue,
)


REPLAY_SCHEMA = "market-os.b3-3.synthetic-replay@v1"
REPLAY_VERSION = "v1"
REPLAY_FINGERPRINT_VERSION = "market-os.b3-3.synthetic-replay-fingerprint@v1"
REPLAY_INTERPRETATION = "synthetic replay only; contract and accounting replay, never predictive evidence or execution"
STATUS_READY = "ready"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
_FORBIDDEN = ("http://", "https://", "\\", "binance", "provider", "credential", "openai", "typesafe", "jev")


class ReplayError(ValueError):
    """Base error for fail-closed replay validation."""


class ReplayStateError(ReplayError):
    """Replay lifecycle violation."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _safe_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ReplayError(f"{field} must be a bounded non-empty string")
    lowered = value.lower()
    if any(token in lowered for token in _FORBIDDEN) or re.search(r"[\x00-\x1f]", value):
        raise ReplayError(f"{field} contains a non-synthetic identity")
    return value


def _timestamp(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReplayError(f"{field} must be a non-negative integer timestamp")
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ReplayError(f"{field} must be finite")
    return float(value)


def _digest(value: Any, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ReplayError(f"{field} must be a lowercase SHA-256 fingerprint")


def _validate_fingerprint(value: str, projection: Mapping[str, Any], field: str) -> None:
    _digest(value, field)
    if value != _fingerprint(projection):
        raise ReplayError(f"{field} mismatch")


@dataclass(frozen=True)
class ReplayClock:
    current_time_ms: int
    start_time_ms: int
    end_time_ms: int
    speed: float = 0.0
    step_mode: bool = True
    paused: bool = False
    synthetic_only: bool = True
    fingerprint: str = ""

    def __post_init__(self) -> None:
        for value, field in ((self.current_time_ms, "current_time_ms"), (self.start_time_ms, "start_time_ms"), (self.end_time_ms, "end_time_ms")):
            _timestamp(value, field)
        if self.end_time_ms < self.start_time_ms or not self.start_time_ms <= self.current_time_ms <= self.end_time_ms:
            raise ReplayError("clock times must be ordered and current time must be within the range")
        speed = _finite(self.speed, "speed")
        if speed < 0:
            raise ReplayError("speed must be non-negative")
        if self.synthetic_only is not True:
            raise ReplayError("clock must be synthetic-only")
        object.__setattr__(self, "speed", speed)
        projection = self.to_dict(include_fingerprint=False)
        if self.fingerprint:
            _validate_fingerprint(self.fingerprint, projection, "clock fingerprint")
        else:
            object.__setattr__(self, "fingerprint", _fingerprint(projection))

    @property
    def running(self) -> bool:
        return not self.paused

    @property
    def mode(self) -> str:
        return "step" if self.step_mode else "speed"

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": REPLAY_SCHEMA + ".clock",
            "current_time_ms": self.current_time_ms,
            "start_time_ms": self.start_time_ms,
            "end_time_ms": self.end_time_ms,
            "speed": self.speed,
            "step_mode": self.step_mode,
            "paused": self.paused,
            "running": self.running,
            "synthetic_only": self.synthetic_only,
        }
        if include_fingerprint:
            result["fingerprint"] = self.fingerprint
        return result


@dataclass(frozen=True)
class ReplayCommand:
    command_id: str
    submitted_at_ms: int
    order: VirtualOrder
    synthetic_only: bool = True
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _safe_text(self.command_id, "command_id")
        _timestamp(self.submitted_at_ms, "submitted_at_ms")
        if not isinstance(self.order, VirtualOrder):
            raise ReplayError("command order must be a VirtualOrder")
        if self.order.submitted_at_ms != self.submitted_at_ms:
            raise ReplayError("command and order timestamps must match")
        if self.synthetic_only is not True or self.order.synthetic_only is not True:
            raise ReplayError("command must be synthetic-only")
        projection = self.to_dict(include_fingerprint=False)
        if self.fingerprint:
            _validate_fingerprint(self.fingerprint, projection, "command fingerprint")
        else:
            object.__setattr__(self, "fingerprint", _fingerprint(projection))

    @property
    def virtual_order(self) -> VirtualOrder:
        return self.order

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": REPLAY_SCHEMA + ".command",
            "command_id": self.command_id,
            "submitted_at_ms": self.submitted_at_ms,
            "order": self.order.to_dict(),
            "synthetic_only": self.synthetic_only,
        }
        if include_fingerprint:
            result["fingerprint"] = self.fingerprint
        return result


@dataclass(frozen=True)
class RejectedReplayCommand:
    command: ReplayCommand
    reason: str
    event_id: str
    fingerprint: str = ""

    def __post_init__(self) -> None:
        _safe_text(self.reason, "reason")
        _safe_text(self.event_id, "event_id")
        projection = self.to_dict(include_fingerprint=False)
        if self.fingerprint:
            _validate_fingerprint(self.fingerprint, projection, "rejected command fingerprint")
        else:
            object.__setattr__(self, "fingerprint", _fingerprint(projection))

    @property
    def command_id(self) -> str:
        return self.command.command_id

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {"command": self.command.to_dict(), "reason": self.reason, "event_id": self.event_id}
        if include_fingerprint:
            result["fingerprint"] = self.fingerprint
        return result


@dataclass(frozen=True)
class ReplayStep:
    event_id: str
    event_time_ms: int
    accepted_commands: tuple[ReplayCommand, ...]
    rejected_commands: tuple[RejectedReplayCommand, ...]
    venue_snapshot_fingerprint: str
    clock_fingerprint: str
    step_fingerprint: str = ""

    def __post_init__(self) -> None:
        _safe_text(self.event_id, "event_id")
        _timestamp(self.event_time_ms, "event_time_ms")
        _digest(self.venue_snapshot_fingerprint, "venue snapshot fingerprint")
        _digest(self.clock_fingerprint, "clock fingerprint")
        object.__setattr__(self, "accepted_commands", tuple(self.accepted_commands))
        object.__setattr__(self, "rejected_commands", tuple(self.rejected_commands))
        projection = self.to_dict(include_fingerprint=False)
        if self.step_fingerprint:
            _validate_fingerprint(self.step_fingerprint, projection, "step fingerprint")
        else:
            object.__setattr__(self, "step_fingerprint", _fingerprint(projection))

    @property
    def accepted(self) -> tuple[ReplayCommand, ...]:
        return self.accepted_commands

    @property
    def rejected(self) -> tuple[RejectedReplayCommand, ...]:
        return self.rejected_commands

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": REPLAY_SCHEMA + ".step",
            "event_id": self.event_id,
            "event_time_ms": self.event_time_ms,
            "accepted_commands": [command.to_dict() for command in self.accepted_commands],
            "rejected_commands": [command.to_dict() for command in self.rejected_commands],
            "venue_snapshot_fingerprint": self.venue_snapshot_fingerprint,
            "clock_fingerprint": self.clock_fingerprint,
        }
        if include_fingerprint:
            result["step_fingerprint"] = self.step_fingerprint
        return result


class ReplaySession:
    """A deterministic step driver around :class:`VirtualPaperVenue`."""

    def __init__(
        self,
        events: Sequence[SyntheticMarketEvent],
        commands: Sequence[ReplayCommand | VirtualOrder],
        config: VenueConfig | None = None,
        session_id: str = "synthetic-replay-session-v1",
        *,
        venue_config: VenueConfig | None = None,
    ) -> None:
        if config is not None and venue_config is not None:
            raise ReplayError("provide config or venue_config, not both")
        self.config = venue_config or config or VenueConfig()
        self.session_id = _safe_text(session_id, "session_id")
        self.events = tuple(events)
        self._commands = [self._coerce_command(item) for item in commands]
        self._validate_events(self.events)
        self._validate_commands(self._commands)
        self._initial_commands = tuple(self._commands)
        if self.events:
            start, end = self.events[0].event_time_ms, self.events[-1].event_time_ms
        else:
            start = end = 0
        self._initial_clock = ReplayClock(start, start, end)
        self._reset_state()

    @staticmethod
    def _coerce_command(item: ReplayCommand | VirtualOrder) -> ReplayCommand:
        if isinstance(item, ReplayCommand):
            return item
        if isinstance(item, VirtualOrder):
            return ReplayCommand(item.order_id, item.submitted_at_ms, item)
        raise ReplayError("commands must be ReplayCommand or VirtualOrder")

    @staticmethod
    def _validate_events(events: Sequence[SyntheticMarketEvent]) -> None:
        previous_time: int | None = None
        seen: set[str] = set()
        for event in events:
            if not isinstance(event, SyntheticMarketEvent):
                raise InvalidMarketEvent("replay requires SyntheticMarketEvent values")
            _validate_fingerprint(event.event_fingerprint, event.to_dict(include_fingerprint=False), "event fingerprint")
            if event.event_id in seen:
                raise InvalidMarketEvent("duplicate event_id")
            if previous_time is not None and event.event_time_ms <= previous_time:
                raise InvalidMarketEvent("events must be strictly increasing in event_time_ms")
            seen.add(event.event_id)
            previous_time = event.event_time_ms

    @staticmethod
    def _validate_commands(commands: Sequence[ReplayCommand]) -> None:
        command_ids: set[str] = set()
        for command in commands:
            if not isinstance(command, ReplayCommand):
                raise ReplayError("commands must be ReplayCommand values")
            _validate_fingerprint(command.order.order_fingerprint, command.order.to_dict(include_fingerprint=False), "order fingerprint")
            _validate_fingerprint(command.fingerprint, command.to_dict(include_fingerprint=False), "command fingerprint")
            if command.command_id in command_ids:
                raise ReplayError("duplicate command_id")
            command_ids.add(command.command_id)

    def _reset_state(self) -> None:
        self._venue = VirtualPaperVenue(self.config)
        self._clock = self._initial_clock
        self._commands = list(self._initial_commands)
        self._cursor = 0
        self._steps: list[ReplayStep] = []
        self._handled_command_ids: set[str] = set()
        self._forced_rejections: dict[str, str] = {}
        self._accepted_commands: list[ReplayCommand] = []
        self._processed_events: list[SyntheticMarketEvent] = []
        self._status = STATUS_READY

    @property
    def commands(self) -> tuple[ReplayCommand, ...]:
        return tuple(self._commands)

    @property
    def _commands_by_time(self) -> tuple[ReplayCommand, ...]:
        return tuple(sorted(self._commands, key=lambda item: (item.submitted_at_ms, item.command_id, item.order.order_id)))

    @property
    def clock(self) -> ReplayClock:
        return self._clock

    @property
    def session_identity(self) -> str:
        return self.session_id

    @property
    def interpretation(self) -> str:
        return REPLAY_INTERPRETATION

    @property
    def status(self) -> str:
        return self._status

    @property
    def ordered_event_cursor(self) -> tuple[str, ...]:
        return tuple(event.event_id for event in self._processed_events)

    @property
    def event_cursor(self) -> tuple[str, ...]:
        return self.ordered_event_cursor

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def steps(self) -> tuple[ReplayStep, ...]:
        return tuple(self._steps)

    @property
    def final_venue_snapshot(self) -> VenueSnapshot:
        return self._venue.snapshot()

    @property
    def venue_snapshot(self) -> VenueSnapshot:
        return self.final_venue_snapshot

    @property
    def pending_commands(self) -> tuple[ReplayCommand, ...]:
        return tuple(command for command in self._commands_by_time if command.command_id not in self._handled_command_ids)

    def submit_command(self, command: ReplayCommand | VirtualOrder) -> ReplayCommand:
        """Queue a command; commands after the current event wait for a later step."""
        if self._status == STATUS_COMPLETED:
            raise ReplayStateError("completed replay session must be reset before submitting commands")
        normalized = self._coerce_command(command)
        self._validate_commands((normalized,))
        if any(existing.command_id == normalized.command_id for existing in self._commands):
            raise ReplayError("duplicate command_id")
        if self._processed_events and normalized.submitted_at_ms <= self._processed_events[-1].event_time_ms:
            self._forced_rejections[normalized.command_id] = "order timestamp would backdate into an already processed event"
        self._commands.append(normalized)
        return normalized

    @property
    def replay_fingerprint(self) -> str:
        return _fingerprint(self._session_projection())

    @property
    def fingerprint(self) -> str:
        return self.replay_fingerprint

    def pause(self) -> ReplayClock:
        if self._status == STATUS_COMPLETED:
            return self._clock
        self._clock = ReplayClock(self._clock.current_time_ms, self._clock.start_time_ms, self._clock.end_time_ms, self._clock.speed, self._clock.step_mode, True)
        self._status = STATUS_PAUSED
        return self._clock

    def resume(self) -> ReplayClock:
        if self._status == STATUS_COMPLETED:
            return self._clock
        self._clock = ReplayClock(self._clock.current_time_ms, self._clock.start_time_ms, self._clock.end_time_ms, self._clock.speed, self._clock.step_mode, False)
        self._status = STATUS_RUNNING
        return self._clock

    def reset(self) -> "ReplaySession":
        self._reset_state()
        return self

    def step(self, event: SyntheticMarketEvent | None = None) -> ReplayStep:
        if self._status == STATUS_COMPLETED:
            raise ReplayStateError("completed replay session must be reset before processing events")
        if self._status == STATUS_PAUSED:
            raise ReplayStateError("replay session is paused")
        if self._cursor >= len(self.events):
            self._status = STATUS_COMPLETED
            raise ReplayStateError("replay session has no remaining events")
        expected = self.events[self._cursor]
        if event is None:
            event = expected
        if not isinstance(event, SyntheticMarketEvent):
            raise InvalidMarketEvent("replay requires SyntheticMarketEvent values")
        if event.event_id != expected.event_id or event.event_time_ms != expected.event_time_ms or event.event_fingerprint != expected.event_fingerprint:
            if event.event_id in self.ordered_event_cursor:
                raise InvalidMarketEvent("duplicate event_id")
            raise InvalidMarketEvent("event is not the next ordered replay event")

        self._status = STATUS_RUNNING
        eligible = [command for command in self._commands_by_time if command.command_id not in self._handled_command_ids and command.submitted_at_ms <= event.event_time_ms]
        accepted: list[ReplayCommand] = []
        rejected: list[RejectedReplayCommand] = []
        for command in eligible:
            if command.command_id in self._handled_command_ids:
                rejected.append(RejectedReplayCommand(command, "duplicate command_id", event.event_id))
                continue
            error = self._forced_rejections.get(command.command_id)
            if error is None:
                candidate = [*self._accepted_commands, *accepted, command]
                error = self._simulation_error(candidate, event)
            if error is None:
                accepted.append(command)
            else:
                rejected.append(RejectedReplayCommand(command, error, event.event_id))
            self._handled_command_ids.add(command.command_id)

        for command in accepted:
            self._venue.submit_order(command.order)
        try:
            snapshot = self._venue.process_event(event)
        except (InvalidOrder, OrderRejected, VenueError) as exc:
            raise ReplayError(f"validated replay application failed: {exc}") from exc
        self._accepted_commands.extend(accepted)
        self._processed_events.append(event)
        self._cursor += 1
        self._clock = ReplayClock(event.event_time_ms, self._clock.start_time_ms, self._clock.end_time_ms, self._clock.speed, self._clock.step_mode, False)
        if self._cursor == len(self.events):
            self._status = STATUS_COMPLETED
        step = ReplayStep(event.event_id, event.event_time_ms, tuple(accepted), tuple(rejected), snapshot.fingerprint, self._clock.fingerprint)
        self._steps.append(step)
        return step

    def run(self) -> "ReplaySession":
        if self._status == STATUS_COMPLETED or self._status == STATUS_PAUSED:
            return self
        self._status = STATUS_RUNNING
        while self._cursor < len(self.events):
            self.step()
        self._status = STATUS_COMPLETED
        return self

    def _simulation_error(self, commands: Sequence[ReplayCommand], current_event: SyntheticMarketEvent) -> str | None:
        # ponytail: rebuild a tiny venue per candidate; optimize only if synthetic replay scales beyond fixtures.
        venue = VirtualPaperVenue(self.config)
        ordered_commands = tuple(sorted(commands, key=lambda item: (item.submitted_at_ms, item.command_id, item.order.order_id)))
        index = 0
        try:
            for prior_event in self._processed_events:
                while index < len(ordered_commands) and ordered_commands[index].submitted_at_ms <= prior_event.event_time_ms:
                    venue.submit_order(ordered_commands[index].order)
                    index += 1
                venue.process_event(prior_event)
            while index < len(ordered_commands) and ordered_commands[index].submitted_at_ms <= current_event.event_time_ms:
                venue.submit_order(ordered_commands[index].order)
                index += 1
            venue.process_event(current_event)
        except (InvalidOrder, OrderRejected, VenueError) as exc:
            return str(exc)
        return None

    def _session_projection(self) -> dict[str, Any]:
        return {
            "schema": REPLAY_SCHEMA,
            "version": REPLAY_VERSION,
            "session_id": self.session_id,
            "config": self.config.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "commands": [command.to_dict() for command in self._commands_by_time],
            "ordered_event_cursor": list(self.ordered_event_cursor),
            "steps": [step.to_dict() for step in self._steps],
            "final_venue_snapshot": self.final_venue_snapshot.to_dict(),
            "clock": self._clock.to_dict(),
            "status": self._status,
            "pending_commands": [command.to_dict() for command in self.pending_commands],
            "interpretation": REPLAY_INTERPRETATION,
        }

    def to_dict(self) -> dict[str, Any]:
        result = self._session_projection()
        result["replay_fingerprint"] = _fingerprint(result)
        return result

    def verify_replay(self, other: "ReplaySession") -> bool:
        return isinstance(other, ReplaySession) and self.to_dict() == other.to_dict()


def replay_synthetic(
    events: Sequence[SyntheticMarketEvent],
    commands: Sequence[ReplayCommand | VirtualOrder],
    config: VenueConfig | None = None,
) -> ReplaySession:
    return ReplaySession(events, commands, config).run()


def verify_deterministic_replay(first: ReplaySession, second: ReplaySession) -> bool:
    return first.verify_replay(second)


SyntheticReplaySession = ReplaySession


__all__ = [
    "REPLAY_SCHEMA", "REPLAY_VERSION", "REPLAY_INTERPRETATION", "STATUS_READY", "STATUS_RUNNING", "STATUS_PAUSED", "STATUS_COMPLETED",
    "ReplayError", "ReplayStateError", "ReplayClock", "ReplayCommand", "RejectedReplayCommand", "ReplayStep", "ReplaySession",
    "SyntheticReplaySession", "replay_synthetic", "verify_deterministic_replay",
]
