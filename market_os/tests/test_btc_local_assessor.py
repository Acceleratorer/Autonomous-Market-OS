from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any
from unittest import skipUnless
from unittest.mock import Mock, patch

import pytest

from market_os import btc_local_assessor as local_assessor
from market_os import btc_local_assessor_store as assessor_store
from market_os.btc_evidence_packet import EvidencePacketError, SourceTimeBounds, build_b31_evidence_packet
from market_os.btc_features import B2_FEATURE_VERSION
from market_os.btc_local_assessor import (
    LocalAssessorError,
    LocalB31Assessor,
    LocalLlamaRuntime,
    _WindowsResourceJob,
    _verify_windows_egress_rules,
    local_runtime_health,
)
from market_os.btc_local_assessor_store import LocalAssessmentStore, LocalAssessmentStoreError
from market_os.btc_question_evaluation import B31Status
from market_os.providers import DocumentRecord, LicenseMetadata, Provenance, RetrievedPassage, RetrievalResult


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _packet(
    *,
    publication_time_status: str = "recorded",
    receipt_offset_ms: int = -25,
    clock_error_bound_ms: int | None = 0,
) -> dict[str, Any]:
    now = time.time_ns() // 1_000_000
    close_ms = now - 120_000
    decision_ms = close_ms + 50
    dataset_revision = "btc-local-assessor-synthetic-v1"
    input_refs = []
    for index, open_ms in enumerate([close_ms - 60_000, *range(close_ms - 360_000, close_ms - 60_000, 60_000)]):
        candle_close_ms = open_ms + 60_000
        source_ms = candle_close_ms
        received_ms = candle_close_ms + 50
        input_refs.append({
            "role": "current" if index == 0 else "lookback",
            "open_time_ms": open_ms,
            "close_time_ms": candle_close_ms,
            "source_timestamp": _iso_ms(source_ms),
            "received_at": _iso_ms(received_ms),
            "availability_timestamp": _iso_ms(received_ms),
            "canonical_fingerprint": hashlib.sha256(f"candle-{open_ms}".encode()).hexdigest(),
        })
    feature: dict[str, Any] = {
        "feature_version": B2_FEATURE_VERSION,
        "dataset_revision": dataset_revision,
        "close_time_ms": close_ms,
        "close_time": _iso_ms(close_ms),
        "source_timestamp": _iso_ms(close_ms),
        "received_at": _iso_ms(decision_ms),
        "availability_timestamp": _iso_ms(decision_ms),
        "decision_eligible_at": _iso_ms(decision_ms),
        "decision_eligible": True,
        "status": "eligible",
        "reason": None,
        "values": {"close": 100_000.0, "log_return_1m": 0.001, "log_return_5m": 0.002, "range_pct": 0.001, "log_volume": 1.0},
        "input_refs": input_refs,
    }
    feature["input_fingerprint"] = hashlib.sha256(_canonical({"dataset_revision": dataset_revision, "feature": feature})).hexdigest()

    receipt_ms = decision_ms + receipt_offset_ms
    retrieval_ms = decision_ms + 10
    ready_ms = decision_ms + 20
    source_texts = (
        ("doc-a", "fixture:source-a", "fixture:citation-a", "group-a", "Synthetic fixture source A describes a positive directional indicator. It is not a real observation."),
        ("doc-b", "fixture:source-b", "fixture:citation-b", "group-b", "Synthetic fixture source B describes a conflicting directional indicator. It is not a real observation."),
    )
    documents = []
    passages = []
    source_times = {}
    for document_id, source_ref, citation_ref, group, text in source_texts:
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        documents.append(DocumentRecord(
            document_id=document_id,
            title=f"Synthetic BTC evidence {document_id}",
            publisher="Market OS test fixture",
            source_ref=source_ref,
            published_at=_iso_ms(close_ms - 300_000 if publication_time_status == "recorded" else receipt_ms),
            retrieved_at=_iso_ms(receipt_ms),
            symbols=("BTCUSDT",),
            media_type="text/plain",
            content_hash=content_hash,
            license=LicenseMetadata("synthetic_fixture"),
            provenance=Provenance("fixture", source_ref, _iso_ms(receipt_ms)),
        ))
        passages.append(RetrievedPassage(
            passage_id=f"passage-{document_id}",
            document_id=document_id,
            text=text,
            rank=len(passages) + 1,
            citation_ref=citation_ref,
            source_ref=source_ref,
            content_hash=content_hash,
        ))
        source_times[document_id] = SourceTimeBounds(
            event_start_ms=close_ms - 120_000,
            event_end_ms=close_ms,
            dependency_group_id=group,
            available_at_ms=receipt_ms,
            publication_time_status=publication_time_status,
            clock_error_bound_ms=clock_error_bound_ms,
        )
    retrieval = RetrievalResult(
        query="synthetic BTC evidence fixture",
        document_ids=tuple(document.document_id for document in documents),
        passages=tuple(passages),
        citations=tuple(passage.citation_ref for passage in passages),
        provider="minirag",
        provider_version="synthetic-fixture-v1",
        retrieved_at=_iso_ms(retrieval_ms),
        query_fingerprint=hashlib.sha256(b"synthetic-query").hexdigest(),
        content_fingerprints=tuple(document.content_hash for document in documents),
    )
    packet = build_b31_evidence_packet(
        feature,
        retrieval,
        documents,
        source_times,
        hypothesis_claim="Synthetic fixture hypothesis: supplied evidence is compatible with a positive five-minute BTC return claim.",
        packet_ready_at_ms=ready_ms,
        independent_evidence_group_ids=("group-a", "group-b"),
    )
    first = {**packet["hypotheses"][0], "hypothesis_id": "h-up"}
    second = {
        **first,
        "hypothesis_id": "h-nonpositive",
        "claim": "Synthetic fixture hypothesis: supplied evidence is compatible with a non-positive five-minute BTC return claim.",
    }
    packet["stable_hypothesis_ids"] = ["h-up", "h-nonpositive"]
    packet["hypotheses"] = [first, second]
    packet["hypothesis_evidence_groups"] = {"h-up": ["group-a"], "h-nonpositive": ["group-b"]}
    packet.pop("packet_fingerprint")
    packet["packet_fingerprint"] = hashlib.sha256(_canonical(packet)).hexdigest()
    return packet


def test_b31_packet_accepts_bounded_local_receipt_with_unknown_publication() -> None:
    packet = _packet(
        publication_time_status="unknown-not-captured",
        clock_error_bound_ms=20,
    )

    evidence = packet["evidence"][0]
    assert evidence["published_at"] is None
    assert evidence["publication_time_status"] == "unknown-not-captured"
    assert evidence["available_at_ms"] == evidence["received_at_ms"] + 20
    assert evidence["available_at_ms"] == packet["timestamps"]["decision_eligible_at_ms"] - 5


def test_b31_packet_rejects_receipt_bound_after_decision_eligibility() -> None:
    with pytest.raises(EvidencePacketError, match="unavailable at B2 decision eligibility"):
        _packet(
            publication_time_status="unknown-not-captured",
            receipt_offset_ms=-5,
            clock_error_bound_ms=10,
        )


def test_b31_packet_rejects_unknown_publication_without_utc_error_bound() -> None:
    with pytest.raises(EvidencePacketError, match="requires a recorded local receipt and UTC clock error bound"):
        _packet(
            publication_time_status="unknown-not-captured",
            clock_error_bound_ms=None,
        )


def _usable_response(*, bad_citation: bool = False, self_comparison: bool = False) -> dict[str, Any]:
    agreement_up = {
        "hypothesis_id": "h-up",
        "label": "contradiction",
        "evidence_refs": ["fixture:citation-a", "fixture:citation-b"],
    }
    if self_comparison:
        agreement_up["comparison_hypothesis_ids"] = ["h-up"]
    return {
        "support": [
            {"hypothesis_id": "h-up", "label": "supported", "evidence_refs": ["fixture:outside"] if bad_citation else ["fixture:citation-a"]},
            {"hypothesis_id": "h-nonpositive", "label": "unsupported", "evidence_refs": ["fixture:citation-b"]},
        ],
        "agreement": [
            agreement_up,
            {
                "hypothesis_id": "h-nonpositive",
                "label": "contradiction",
                "evidence_refs": ["fixture:citation-a", "fixture:citation-b"],
            },
        ],
        "abstention": {
            "label": "answerable",
            "basis_hypothesis_ids": ["h-up", "h-nonpositive"],
            "evidence_refs": ["fixture:citation-a", "fixture:citation-b"],
        },
    }


@dataclass
class FakeRuntime:
    response: dict[str, Any]
    provider: str = "local_qwen_evidence_assessor"
    model: str = "Qwen/Qwen3-4B-GGUF"
    model_version: str = "synthetic-runtime-model-v1"
    runtime_version: str = "fake-local-runtime"
    manifest_fingerprint: str = "a" * 64
    last_messages: list[dict[str, str]] | None = None

    def complete(self, messages: list[dict[str, str]], schema: dict[str, Any], *, timeout_seconds: float) -> tuple[dict[str, Any], int]:
        assert messages[0]["role"] == "system"
        assert schema["type"] == "object"
        assert 1 <= timeout_seconds <= 300
        self.last_messages = messages
        return {"choices": [{"message": {"content": json.dumps(self.response)}}]}, 5


def test_local_assessor_normalizes_typed_results_without_claiming_jev() -> None:
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(_packet())

    assert record.outcome == "usable"
    assert record.provider == "local_qwen_evidence_assessor"
    assert record.model != "Jev"
    assert record.calibration_status == "uncalibrated_hard_labels_one_hot_serialization"
    assert record.assessment is not None
    assert record.assessment["status"] == B31Status.USABLE.value
    assert record.assessment["agreement_results"][0]["selected_label"] == "contradiction"
    assert record.assessment["agreement_results"][0]["comparison_hypothesis_ids"] == ("h-nonpositive",)
    assert record.assessment["agreement_results"][0]["comparison_evidence_group_ids"] == ("group-b",)
    assert record.assessment["support_results"][0]["probabilities"] == {"supported": 1.0, "mixed": 0.0, "unknown": 0.0, "unsupported": 0.0}
    assert "market_probability_up" not in record.assessment


def test_local_prompt_defines_contradiction_and_does_not_abstain_on_classifiable_disagreement() -> None:
    runtime = FakeRuntime(_usable_response())
    LocalB31Assessor(runtime).assess(_packet())

    assert runtime.last_messages is not None
    system_prompt = runtime.last_messages[0]["content"]
    assert "contradiction means incompatible claims about the same event and horizon" in system_prompt
    assert "answerable when these semantic labels can be selected from the supplied evidence" in system_prompt
    assert "abstain only when the assessment is insufficient or unsafe" in system_prompt


def test_local_assessor_rejects_model_citations_outside_the_packet() -> None:
    record = LocalB31Assessor(FakeRuntime(_usable_response(bad_citation=True))).assess(_packet())

    assert record.outcome == "rejected"
    assert record.failure is not None
    assert record.failure["code"] == "invalid_response"
    assert record.assessment is None


def test_self_comparison_is_rejected_before_normalization() -> None:
    record = LocalB31Assessor(FakeRuntime(_usable_response(self_comparison=True))).assess(_packet())

    assert record.outcome == "rejected"
    assert record.failure is not None
    assert record.failure["code"] == "invalid_response"


def test_model_abstention_remains_a_terminal_advisory_result() -> None:
    response = _usable_response()
    response["abstention"]["label"] = "abstain"
    record = LocalB31Assessor(FakeRuntime(response)).assess(_packet())

    assert record.outcome == "abstained"
    assert record.assessment is not None
    assert record.assessment["abstention_result"]["status"] == B31Status.ABSTAINED.value
    assert record.assessment["abstention_result"]["reason"] == "model_recommended_abstention"


def _windows_powershell_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "Windows" / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    path.parent.mkdir(parents=True)
    path.touch()
    return path


def test_windows_egress_health_requires_exact_active_store_executable_paths(tmp_path: Path) -> None:
    server = Path(sys.executable).parent / "llama-server.exe"
    payload = {
        "schema": "market-os.btc-assessor-firewall.v1",
        "status": "enforced",
        "checked_executables": {"python": sys.executable, "llama_server": str(server)},
        "checked_rule_names": {
            "python": "MarketOS-BTC-LocalAssessor-Python-OutboundBlock-SecondaryCheckout",
            "llama_server": "MarketOS-BTC-LocalAssessor-LlamaServer-OutboundBlock-SecondaryCheckout",
        },
    }
    powershell = _windows_powershell_fixture(tmp_path)
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    with patch("market_os.btc_local_assessor._windows_powershell_path", return_value=powershell), patch(
        "market_os.btc_local_assessor.Path.is_file", return_value=True
    ), patch("market_os.btc_local_assessor.subprocess.run", side_effect=run):
        health = _verify_windows_egress_rules(server)

    assert health["status"] == "enforced"
    assert health["checked_executables"] == ["python", "llama-server"]
    assert health["checked_rule_names"] == payload["checked_rule_names"]
    command, kwargs = calls[0]
    assert command[command.index("-File") + 1] == str(Path(__file__).parents[1] / "btc_assessor_firewall.ps1")
    assert command[command.index("-ExecutionPolicy") + 1] == "Bypass"
    assert "-PythonExecutable" not in command and "-ServerExecutable" not in command
    assert kwargs["shell"] is False
    assert kwargs["env"]["MARKET_OS_PYTHON_EXECUTABLE"] == sys.executable
    assert kwargs["env"]["MARKET_OS_SERVER_EXECUTABLE"] == str(server)


def test_windows_egress_health_fails_closed_on_mismatched_or_unreadable_policy(tmp_path: Path) -> None:
    server = Path(sys.executable).parent / "llama-server.exe"
    powershell = _windows_powershell_fixture(tmp_path)
    payload = {
        "schema": "market-os.btc-assessor-firewall.v1",
        "status": "enforced",
        "checked_executables": {"python": sys.executable, "llama_server": str(server.with_name("other.exe"))},
    }
    with patch("market_os.btc_local_assessor._windows_powershell_path", return_value=powershell), patch(
        "market_os.btc_local_assessor.Path.is_file", return_value=True
    ), patch(
        "market_os.btc_local_assessor.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, json.dumps(payload), ""),
    ):
        assert _verify_windows_egress_rules(server)["status"] == "unverified"

    with patch("market_os.btc_local_assessor._windows_powershell_path", return_value=powershell), patch(
        "market_os.btc_local_assessor.Path.is_file", return_value=True
    ), patch(
        "market_os.btc_local_assessor.subprocess.run",
        return_value=subprocess.CompletedProcess([], 1, "not-json", "firewall unavailable"),
    ):
        assert _verify_windows_egress_rules(server)["status"] == "unverified"

    with patch("market_os.btc_local_assessor._windows_powershell_path", return_value=powershell), patch(
        "market_os.btc_local_assessor.Path.is_file", return_value=True
    ), patch(
        "market_os.btc_local_assessor.subprocess.run",
        return_value=subprocess.CompletedProcess([], 2, "\udcff", "\udcff"),
    ):
        assert _verify_windows_egress_rules(server)["status"] == "unverified"


def test_local_runtime_start_fails_closed_when_egress_isolation_is_unverified() -> None:
    runtime = object.__new__(LocalLlamaRuntime)
    runtime._lock = threading.RLock()
    runtime.server_path = Path(sys.executable)

    with patch("market_os.btc_local_assessor.os.name", "nt"), patch(
        "market_os.btc_local_assessor._verify_windows_egress_rules",
        return_value={"status": "unverified", "reason": "synthetic missing policy"},
    ):
        try:
            runtime.start()
        except LocalAssessorError as exc:
            assert exc.code == "network_isolation_unverified"
        else:
            raise AssertionError("local runtime started without verified network isolation")


def test_local_runtime_health_uses_the_fail_closed_startup_preflight() -> None:
    runtime = Mock()
    health = {"status": "healthy", "network_isolation": {"status": "enforced"}}
    startup_failure = LocalAssessorError("network_isolation_unverified", "synthetic missing policy")
    runtime.start.side_effect = startup_failure
    runtime.health.return_value = health

    with patch("market_os.btc_local_assessor.LocalLlamaRuntime", return_value=runtime):
        result = local_runtime_health("unused-install-root")

    runtime.start.assert_called_once_with()
    runtime.health.assert_called_once_with()
    runtime.stop.assert_called_once_with()
    assert result["status"] == "unavailable"
    assert result["startup_failure"] == {
        "code": "network_isolation_unverified",
        "message": "synthetic missing policy",
    }


def test_linux_runtime_cannot_bypass_unverified_isolation_for_health() -> None:
    runtime = object.__new__(LocalLlamaRuntime)
    runtime._lock = threading.RLock()
    runtime.server_path = Path("llama-server")
    with patch("market_os.btc_local_assessor.os.name", "posix"), patch(
        "market_os.btc_assessor_linux_isolation.verify_linux_isolation",
        return_value={"status": "unverified", "network_isolation": {"status": "unverified", "reason": "missing scope"}},
    ):
        try:
            runtime.start(require_network_isolation=False)
        except LocalAssessorError as exc:
            assert exc.code == "network_isolation_unverified"
        else:
            raise AssertionError("Linux runtime bypassed network isolation during health startup")


def test_local_runtime_rejects_a_different_python_executable_before_loading_model(tmp_path: Path) -> None:
    lock_path = Path(__file__).resolve().parents[1] / "models" / "btc_local_assessor_runtime.lock.json"
    lock_bytes = lock_path.read_bytes()
    target = "windows-x64-cuda-13.5" if os.name == "nt" else "linux-x64-cpu"
    python_target = "windows-x64" if os.name == "nt" else "linux-x64"
    python_lock = json.loads((lock_path.parent / "btc_assessor_python_runtime.lock.json").read_text(encoding="utf-8"))
    python_manifest = {
        "python_version": python_lock["targets"][python_target]["version"],
        "runtime_tree_sha256_excluding_manifest_and_bytecode": "b" * 64,
    }
    (tmp_path / "install-manifest.json").write_text(
        json.dumps({
            "schema": "market-os.btc-local-assessor-install.v1",
            "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
            "target": target,
            "python_runtime": {
                "target": python_target,
                "version": python_manifest["python_version"],
                "runtime_root_relative_path": ".market_os/runtimes/btc-assessor-py311",
                "manifest_sha256": "a" * 64,
                "runtime_tree_sha256": python_manifest["runtime_tree_sha256_excluding_manifest_and_bytecode"],
            },
        }),
        encoding="utf-8",
    )
    verified = {
        "manifest": python_manifest,
        "manifest_sha256": "a" * 64,
        "interpreter": tmp_path / "different-python.exe",
    }

    with patch("market_os.btc_local_assessor.bootstrap_runtime", return_value=verified) as verify_runtime:
        try:
            LocalLlamaRuntime(tmp_path)
        except LocalAssessorError as exc:
            assert exc.code == "runtime_integrity_failed"
            assert "exact pinned target CPython runtime" in str(exc)
        else:
            raise AssertionError("local assessor accepted an installation launched by a different Python executable")
    verify_runtime.assert_called_once_with(Path(__file__).resolve().parents[2], python_target, verify_only=True)


def test_local_assessment_store_replays_without_calling_an_inference_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(local_assessor, "LOCAL_ADAPTER_VERSION", "market-os-btc-local-assessor-v1")
    packet = _packet()
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(packet)
    store = LocalAssessmentStore(tmp_path)

    path = store.persist(packet, record)
    monkeypatch.setattr(local_assessor, "_messages", lambda _payload: [{"role": "system", "content": "revised prompt"}])
    monkeypatch.setattr(local_assessor, "LOCAL_ADAPTER_VERSION", "market-os-btc-local-assessor-v2")
    replay = store.replay(record.run_id)

    assert path.is_file()
    assert replay["status"] == "verified"
    assert replay["verification"] == "offline-packet-gates-and-response-normalization"
    assert replay["inference_calls"] == 0
    assert replay["network_requests"] == 0
    assert replay["packet_fingerprint"] == record.packet_fingerprint
    assert store.persist(packet, record) == path


def test_local_assessment_store_rejects_new_run_when_total_store_limit_is_full(tmp_path, monkeypatch) -> None:
    packet = _packet()
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(packet)
    store = LocalAssessmentStore(tmp_path)
    first_path = store.persist(packet, record)
    monkeypatch.setattr(assessor_store, "MAX_STORE_BYTES", first_path.stat().st_size)

    assert store.persist(packet, record) == first_path

    second_response = _usable_response()
    second_response["support"][0]["label"] = "mixed"
    second_record = LocalB31Assessor(FakeRuntime(second_response)).assess(packet)
    assert second_record.run_id != record.run_id

    with pytest.raises(assessor_store.LocalAssessmentStoreCapacityError, match="store byte limit") as exc:
        store.persist(packet, second_record)

    assert exc.value.code == "store_capacity_exceeded"
    assert first_path.is_file()
    assert not (store.runs / f"{second_record.run_id}.json").exists()
    assert store.replay(record.run_id)["status"] == "verified"


def test_local_assessment_store_serializes_concurrent_writes_at_total_limit(tmp_path, monkeypatch) -> None:
    packet = _packet()
    first_record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(packet)
    second_response = _usable_response()
    second_response["support"][0]["label"] = "mixed"
    second_record = LocalB31Assessor(FakeRuntime(second_response)).assess(packet)

    first_candidate = LocalAssessmentStore(tmp_path / "candidate-first").persist(packet, first_record)
    second_candidate = LocalAssessmentStore(tmp_path / "candidate-second").persist(packet, second_record)
    quota = max(first_candidate.stat().st_size, second_candidate.stat().st_size)
    monkeypatch.setattr(assessor_store, "MAX_STORE_BYTES", quota)
    store = LocalAssessmentStore(tmp_path / "shared")
    barrier = threading.Barrier(3)

    def persist(record):
        barrier.wait(timeout=10)
        try:
            store.persist(packet, record)
            return "stored"
        except assessor_store.LocalAssessmentStoreCapacityError:
            return "full"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(persist, record) for record in (first_record, second_record)]
        barrier.wait(timeout=10)
        outcomes = [future.result(timeout=20) for future in futures]

    committed = list(store.runs.glob("*.json"))
    assert sorted(outcomes) == ["full", "stored"]
    assert len(committed) == 1
    assert sum(path.stat().st_size for path in committed) <= quota


def test_local_assessment_store_does_not_accept_a_jev_identity(tmp_path) -> None:
    packet = _packet()
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(packet)

    try:
        LocalAssessmentStore(tmp_path).persist(packet, replace(record, provider="typesafe", model="jev-1.14.0"))
    except LocalAssessmentStoreError as exc:
        assert "pinned local Qwen" in str(exc)
    else:
        raise AssertionError("local assessment store accepted a hosted Jev identity")


def test_local_assessment_store_replays_typed_runtime_start_failure(tmp_path) -> None:
    class StartFailureRuntime(FakeRuntime):
        def start(self) -> None:
            raise LocalAssessorError("startup_timeout", "synthetic startup failure", retryable=True)

    packet = _packet()
    with LocalB31Assessor(StartFailureRuntime(_usable_response())) as assessor:
        record = assessor.assess(packet)
    store = LocalAssessmentStore(tmp_path)
    store.persist(packet, record)

    replay = store.replay(record.run_id)

    assert record.outcome == "unavailable"
    assert record.failure is not None
    assert record.failure["code"] == "startup_timeout"
    assert replay["status"] == "verified"


def test_local_assessment_store_rejects_modified_run_bundles(tmp_path) -> None:
    packet = _packet()
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(packet)
    store = LocalAssessmentStore(tmp_path)
    path = store.persist(packet, record)
    bundle = json.loads(path.read_text(encoding="utf-8"))
    bundle["record"]["provider"] = "tampered-provider"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    try:
        store.replay(record.run_id)
    except LocalAssessmentStoreError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("modified local assessment run was accepted")


@skipUnless(os.name == "nt" and sys.maxsize > 2**32, "Windows Job Objects require 64-bit Windows")
def test_windows_resource_job_limits_memory_and_resumes_suspended_process() -> None:
    script = "bytearray(512 * 1024 * 1024)"
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_SUSPENDED", 0x00000004),
    )
    job = None
    try:
        job = _WindowsResourceJob(process, memory_limit_bytes=128 * 1024**2)
        _, stderr = process.communicate(timeout=10)
        assert process.returncode != 0
        assert b"MemoryError" in stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if job is not None:
            job.close()
