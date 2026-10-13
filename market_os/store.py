"""Restart-safe JSONL events and immutable JSON artifacts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import Artifact, RunEvent

class RunStore:
    def __init__(self, root: str | Path = ".market_os") -> None:
        self.root = Path(root)
        self.events = self.root / "events.jsonl"
        self.runs = self.root / "runs.jsonl"
        self.artifact_index = self.root / "artifacts.jsonl"
        self.recovery = self.root / "recovery.jsonl"
        self.idempotency = self.root / "idempotency.json"
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.events.touch(exist_ok=True)
        self.runs.touch(exist_ok=True)
        self.artifact_index.touch(exist_ok=True)
        self.recovery.touch(exist_ok=True)
        self.last_artifact_attempt: Artifact | None = None

    def append_event(self, event: RunEvent) -> None:
        with self.events.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.__dict__, sort_keys=True) + "\n")

    def save_run(self, run: Any) -> None:
        with self.runs.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(run.__dict__, sort_keys=True) + "\n")

    def latest_run(self, run_id: str) -> dict[str, Any] | None:
        latest = None
        for line in self.runs.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line)["run_id"] == run_id:
                latest = json.loads(line)
        return latest

    def events_for(self, run_id: str) -> list[RunEvent]:
        result: list[RunEvent] = []
        for line in self.events.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item["run_id"] == run_id:
                    result.append(RunEvent(**item))
        return result

    def write_artifact(self, run_id: str, kind: str, payload: Any, lineage: tuple[str, ...] = ()) -> Artifact:
        raw = json.dumps(payload, sort_keys=True, indent=2).encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = self.artifacts / f"{run_id}-{kind}-{digest[:12]}.json"
        artifact = Artifact(f"artifact-{digest[:16]}", run_id, kind, "application/json", str(path), datetime.now(timezone.utc).isoformat(), digest, lineage)
        self.last_artifact_attempt = artifact
        if not path.exists():
            path.write_bytes(raw)
        if not any(item.artifact_id == artifact.artifact_id for item in self.artifacts_for(run_id)):
            self._append_artifact_index(artifact)
        return artifact

    def _append_artifact_index(self, artifact: Artifact) -> None:
        with self.artifact_index.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(artifact.__dict__, sort_keys=True) + "\n")

    def append_recovery(self, record: dict[str, Any]) -> None:
        with self.recovery.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def recovery_for(self, run_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for line in self.recovery.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("run_id") == run_id:
                    result.append(item)
        return result

    def artifacts_for(self, run_id: str) -> list[Artifact]:
        result = []
        for line in self.artifact_index.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item["run_id"] == run_id:
                    result.append(Artifact(**item))
        return result

    def idempotent_result(self, key: str) -> dict[str, Any] | None:
        if not self.idempotency.exists():
            return None
        return json.loads(self.idempotency.read_text(encoding="utf-8")).get(key)

    def save_idempotent_result(self, key: str, result: dict[str, Any]) -> None:
        values = {}
        if self.idempotency.exists() and self.idempotency.read_text(encoding="utf-8").strip():
            values = json.loads(self.idempotency.read_text(encoding="utf-8"))
        values[key] = result
        self.idempotency.write_text(json.dumps(values, sort_keys=True), encoding="utf-8")
