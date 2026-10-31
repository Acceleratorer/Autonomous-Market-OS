from __future__ import annotations

import re
import threading
import urllib.parse
from collections import Counter
from collections.abc import Mapping


_ROUTE_PATTERNS = (
    (re.compile(r"^/(?:healthz|readyz)$"), "health"),
    (re.compile(r"^/metrics$"), "metrics"),
    (re.compile(r"^/operator(?:/.*)?$"), "operator"),
    (re.compile(r"^/v[123]/b4/portfolios(?:/.*)?$"), "portfolio"),
    (re.compile(r"^/v[123]/btc/.*$"), "btc"),
    (re.compile(r"^/v1/(?:tasks|benchmarks)$"), "workflow"),
)


def classify_route(path: str) -> str:
    """Map request paths to a small, non-sensitive metric label set."""
    path = urllib.parse.urlsplit(path).path
    for pattern, label in _ROUTE_PATTERNS:
        if pattern.match(path):
            return label
    return "other"


class MetricsRegistry:
    """Small dependency-free Prometheus exposition registry.

    Labels are deliberately bounded to method, route family, and status class;
    raw paths, IDs, subjects, and query strings never become metric labels.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Counter[tuple[str, str, str]] = Counter()
        self._events: Counter[str] = Counter()

    def record_request(self, method: str, path: str, status: int) -> None:
        method_value = method.upper() if method.upper() in {"GET", "HEAD", "POST"} else "OTHER"
        status_class = f"{max(0, int(status)) // 100}xx"
        with self._lock:
            self._requests[(method_value, classify_route(path), status_class)] += 1

    def record_event(self, event: str) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", event):
            return
        with self._lock:
            self._events[event] += 1

    def snapshot(self) -> Mapping[str, object]:
        with self._lock:
            return {"requests": dict(self._requests), "events": dict(self._events)}

    def render(self) -> bytes:
        snapshot = self.snapshot()
        lines = [
            "# HELP market_os_http_requests_total HTTP requests handled by route family.",
            "# TYPE market_os_http_requests_total counter",
        ]
        requests = snapshot["requests"]
        assert isinstance(requests, dict)
        for (method, route, status_class), value in sorted(requests.items()):
            lines.append(
                f'market_os_http_requests_total{{method="{method}",route="{route}",status_class="{status_class}"}} {value}',
            )
        lines.extend(
            [
                "# HELP market_os_audit_events_total Bounded audit events emitted by the gateway.",
                "# TYPE market_os_audit_events_total counter",
            ],
        )
        events = snapshot["events"]
        assert isinstance(events, dict)
        for event, value in sorted(events.items()):
            lines.append(f'market_os_audit_events_total{{event="{event}"}} {value}')
        return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = ["MetricsRegistry", "classify_route"]
