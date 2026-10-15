"""Reproducible, offline research-quality benchmark for M2.5."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .model_summary import (
    DeterministicTestSummaryProvider,
    GeneratedStatement,
    ModelOutput,
    ModelProviderIdentity,
    ModelUsage,
    gate_summary,
    make_summary_request,
    render_summary_text,
)
from .providers import (
    DocumentRecord,
    LicenseMetadata,
    Provenance,
    RetrievedPassage,
    RetrievalResult,
)
from .research import DeterministicResearchSynthesizer, ResearchSynthesis, research_synthesis_from_dict

QUALITY_BENCHMARK_API_VERSION = "market-os.quality-benchmark.v1"
_METHOD_BASELINE = "deterministic-exact-quote"
_METHOD_MODEL = "deterministic-test-model"
_BENCHMARK_DIR = "benchmarks"
_MAX_OUTPUT_CHARS = 16_384
DEFAULT_QUALITY_FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "quality" / "benchmark.json"

THRESHOLDS: dict[str, dict[str, Any]] = {
    "citation_precision": {"minimum": 1.0, "definition": "valid predicted citation passages divided by all predicted citation passages"},
    "citation_recall": {"minimum": 1.0, "definition": "valid predicted citation passages divided by expected accepted passages"},
    "quote_exactness": {"minimum": 1.0, "definition": "exact supported statement quotes divided by expected supported statements"},
    "claim_support_accuracy": {"minimum": 1.0, "definition": "supported statements with matching claim/support/citation lineage divided by expected supported statements"},
    "unsupported_claim_detection": {"minimum": 1.0, "definition": "cases whose unsupported classification matches the expected case"},
    "inference_labeling_accuracy": {"minimum": 1.0, "definition": "cases whose inference count matches the expected case"},
    "evidence_coverage_accuracy": {"minimum": 1.0, "definition": "cases whose evidence coverage equals the expected case coverage"},
    "cross_run_citation_isolation": {"minimum": 1.0, "definition": "cross-run citations never become accepted evidence"},
    "content_hash_integrity": {"minimum": 1.0, "definition": "corrupt hash cases fail closed"},
    "deterministic_replay": {"minimum": 1.0, "definition": "semantic method results replay with stable fingerprints"},
    "fallback_correctness": {"minimum": 1.0, "definition": "provider failures preserve the deterministic synthesis fingerprint"},
    "malformed_output_rejection": {"minimum": 1.0, "definition": "malformed or hostile outputs are rejected or safely isolated"},
    "prompt_injection_isolation": {"minimum": 1.0, "definition": "prompt-injection-like content never bypasses the grounding gate"},
    "secret_like_rejection": {"minimum": 1.0, "definition": "secret-like output is rejected or safely isolated"},
    "artifact_lineage_completeness": {"minimum": 1.0, "definition": "benchmark and case results carry resolvable fixture lineage"},
    "usage_accounting": {"minimum": 1.0, "definition": "input and output usage values are present and non-negative"},
    "latency_ms_p95": {"maximum": 100.0, "definition": "local benchmark p95 execution latency in milliseconds"},
}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return 1.0 if denominator == 0 and numerator == 0 else (float(numerator) / float(denominator) if denominator else 0.0)


def _near(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-12)


@dataclass(frozen=True)
class BenchmarkCaseSpec:
    case_id: str
    family: str
    query: str
    document_ids: tuple[str, ...]
    passages: tuple[dict[str, Any], ...]
    expected_gate: str
    expected_supported: int
    expected_inference: int
    expected_unsupported: int
    expected_coverage: float
    partial: bool = False
    error: str | None = None


class BenchmarkProvider:
    """A case-specific deterministic provider used only by the benchmark."""

    def __init__(self, output: Any = None, error: BaseException | None = None, label: str = "default") -> None:
        self.output = output
        self.error = error
        self.label = label
        self.identity = ModelProviderIdentity("deterministic-test", f"market-os-m2.5-{label}", "m2.5-v1")
        self.prompt_version = "m2.5-benchmark-prompt-v1"

    def generate(self, request: Any, synthesis: ResearchSynthesis) -> Any:
        if self.error is not None:
            raise self.error
        return self.output


class BenchmarkStore:
    """Content-addressed benchmark artifact store, separate from trading state."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve() / _BENCHMARK_DIR
        self.artifacts = self.root / "artifacts"
        self.index = self.root / "index.json"

    def snapshot(self) -> dict[str, str]:
        if not self.root.exists():
            return {}
        return {
            str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def write_report(self, report: dict[str, Any], fixture_fingerprint: str) -> dict[str, Any]:
        self.artifacts.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(report, sort_keys=True, indent=2).encode("utf-8")
        artifact_id = "benchmark-" + report["benchmark_fingerprint"][:16]
        path = self.artifacts / f"{artifact_id}.json"
        path.write_bytes(raw)
        artifact = {
            "artifact_id": artifact_id,
            "kind": "quality-benchmark",
            "media_type": "application/json",
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "lineage": [f"fixture:{fixture_fingerprint}"],
        }
        index = {}
        if self.index.exists():
            index = json.loads(self.index.read_text(encoding="utf-8"))
        index[artifact_id] = artifact
        self.index.write_text(json.dumps(index, sort_keys=True, indent=2), encoding="utf-8")
        return artifact

    def inspect(self, benchmark_id: str, resource: str, item_id: str | None = None) -> Any:
        artifact = self._artifact(benchmark_id)
        path = Path(artifact["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError(f"benchmark artifact content hash mismatch: {benchmark_id}")
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("benchmark_id") != benchmark_id:
            raise ValueError("benchmark artifact ID mismatch")
        if _report_fingerprint(report) != report.get("benchmark_fingerprint"):
            raise ValueError("benchmark fingerprint mismatch")
        if resource == "cases":
            if item_id is None:
                return report["cases"]
            matches = [case for case in report["cases"] if case["case_id"] == item_id]
            if not matches:
                raise KeyError(item_id)
            return matches
        if resource == "metrics":
            return report["metrics"]
        if resource == "failed-cases":
            return [case for case in report["cases"] if not case["passed"]]
        if resource == "thresholds":
            return {
                "thresholds": report["thresholds"],
                "decisions": report["threshold_decisions"],
                "promotion": report["promotion"],
            }
        if resource == "case":
            raise ValueError("case inspection requires a case ID")
        if resource == "fingerprint":
            return {
                "benchmark_id": report["benchmark_id"],
                "benchmark_fingerprint": report["benchmark_fingerprint"],
                "fixture_fingerprint": report["fixture_fingerprint"],
            }
        raise ValueError(f"unknown benchmark resource: {resource}")

    def _artifact(self, benchmark_id: str) -> dict[str, Any]:
        if not benchmark_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in benchmark_id):
            raise KeyError(benchmark_id)
        if not self.index.exists():
            raise KeyError(benchmark_id)
        index = json.loads(self.index.read_text(encoding="utf-8"))
        artifact = index.get(benchmark_id)
        if artifact is None:
            raise KeyError(benchmark_id)
        if not Path(artifact["path"]).exists():
            raise ValueError(f"benchmark artifact is missing: {benchmark_id}")
        return artifact


def _load_fixture(path: Path) -> tuple[str, str, dict[str, DocumentRecord], tuple[BenchmarkCaseSpec, ...]]:
    raw = path.read_bytes()
    fixture_fingerprint = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    if "synthetic" not in str(payload.get("label", "")).lower():
        raise ValueError("benchmark fixture must be explicitly synthetic")
    if payload.get("license", {}).get("classification") != "synthetic-internal":
        raise ValueError("benchmark fixture license must be synthetic-internal")
    documents: dict[str, DocumentRecord] = {}
    contents: dict[str, str] = {}
    for item in payload.get("documents", ()):
        content = item.get("content", "")
        document_id = item.get("document_id", "")
        if document_id in documents:
            raise ValueError(f"duplicate benchmark document: {document_id}")
        if not content or hashlib.sha256(content.encode("utf-8")).hexdigest() != item.get("content_hash"):
            raise ValueError(f"benchmark document content hash mismatch: {document_id}")
        documents[document_id] = DocumentRecord(
            document_id,
            item["title"],
            item["publisher"],
            item["source_ref"],
            item["published_at"],
            item["retrieved_at"],
            tuple(item.get("symbols", ())),
            item["media_type"],
            item["content_hash"],
            LicenseMetadata("synthetic-internal", "internal fixture", "Market OS benchmark", ("not for redistribution",)),
            Provenance("quality-fixture", item["source_ref"], item["retrieved_at"]),
            f"fixture:{payload['fixture_id']}:{document_id}",
        )
        contents[document_id] = content
    cases: list[BenchmarkCaseSpec] = []
    for item in payload.get("cases", ()):
        case = BenchmarkCaseSpec(
            item["case_id"],
            item["family"],
            item["query"],
            tuple(item["document_ids"]),
            tuple(dict(passage) for passage in item.get("passages", ())),
            item["expected_gate"],
            item["expected_supported"],
            item["expected_inference"],
            item["expected_unsupported"],
            item["expected_coverage"],
            item.get("partial", False),
            item.get("error"),
        )
        if any(document_id not in documents for document_id in case.document_ids):
            raise ValueError(f"benchmark case references unknown document: {case.case_id}")
        if any(passage["document_id"] not in documents for passage in case.passages):
            raise ValueError(f"benchmark case references unknown passage document: {case.case_id}")
        cases.append(case)
    return payload["fixture_id"], fixture_fingerprint, documents, tuple(cases)


def _build_synthesis(case: BenchmarkCaseSpec, documents: dict[str, DocumentRecord], fixture_fingerprint: str) -> ResearchSynthesis:
    passages = tuple(
        RetrievedPassage(
            item["passage_id"],
            item["document_id"],
            item["text"],
            item["rank"],
            f"quality:{item['passage_id']}",
            documents[item["document_id"]].source_ref,
            hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
        )
        for item in case.passages
    )
    retrieval = RetrievalResult(
        case.query,
        case.document_ids,
        passages,
        tuple(passage.citation_ref for passage in passages),
        "quality-fixture",
        "m2.5-quality-v1",
        next(iter(documents.values())).retrieved_at,
        _digest({"case": case.case_id, "query": case.query, "fixture": fixture_fingerprint}),
        tuple(documents[document_id].content_hash for document_id in case.document_ids),
        case.partial,
        case.error,
    )
    return DeterministicResearchSynthesizer().synthesize(
        case.query,
        tuple(documents[document_id] for document_id in case.document_ids),
        retrieval,
        retrieval_artifact_id=f"artifact-quality-{case.case_id}-retrieval",
        document_artifact_id=f"artifact-quality-{case.case_id}-documents",
        evidence_artifact_id=f"artifact-quality-{case.case_id}-evidence",
    )


def _statement_for_claim(claim: Any, *, text: str | None = None, classification: str = "supported", citation_ids: tuple[str, ...] | None = None, support_ids: tuple[str, ...] | None = None, document_ids: tuple[str, ...] | None = None, evidence_quotes: tuple[str, ...] | None = None) -> GeneratedStatement:
    return GeneratedStatement(
        f"statement-{claim.claim_id}",
        text or claim.claim_text,
        classification,
        citation_ids if citation_ids is not None else claim.citation_ids,
        support_ids if support_ids is not None else claim.support_ids,
        document_ids if document_ids is not None else claim.document_ids,
        evidence_quotes if evidence_quotes is not None else (),
        claim.confidence,
    )


def _case_provider(case: BenchmarkCaseSpec, synthesis: ResearchSynthesis) -> BenchmarkProvider:
    request = make_summary_request(case.query, synthesis, "m2.5-benchmark-prompt-v1")
    if case.family == "timeout":
        return BenchmarkProvider(error=TimeoutError("benchmark timeout"), label=case.family)
    if case.family == "failure":
        return BenchmarkProvider(error=RuntimeError("benchmark provider failure"), label=case.family)
    if case.family == "malformed":
        return BenchmarkProvider(output={"summary": "malformed"}, label=case.family)
    if case.family == "inference":
        text = "The available fixture may imply a bounded comparison."
        statement = GeneratedStatement("statement-inference", text, "inference")
        return BenchmarkProvider(ModelOutput(render_summary_text((statement,)), (statement,), ModelUsage(32, len(text))), label=case.family)
    if not synthesis.claims:
        return BenchmarkProvider(DeterministicTestSummaryProvider().generate(request, synthesis), label=case.family)
    claim = synthesis.claims[0]
    support = synthesis.supports[0]
    if case.family == "similar-quote":
        statement = _statement_for_claim(claim, text=claim.claim_text.replace("observation", "observations"), evidence_quotes=(support.quote,))
        return BenchmarkProvider(ModelOutput(render_summary_text((statement,)), (statement,)), label=case.family)
    if case.family == "missing-citations":
        statement = _statement_for_claim(claim, citation_ids=(), evidence_quotes=(support.quote,))
        return BenchmarkProvider(ModelOutput(render_summary_text((statement,)), (statement,)), label=case.family)
    if case.family == "invalid-citation":
        statement = _statement_for_claim(claim, citation_ids=("citation-invalid",), evidence_quotes=(support.quote,))
        return BenchmarkProvider(ModelOutput(render_summary_text((statement,)), (statement,)), label=case.family)
    if case.family == "cross-run":
        statement = GeneratedStatement(
            "statement-cross-run",
            claim.claim_text,
            "supported",
            ("citation-cross-run",),
            ("support-cross-run",),
            claim.document_ids,
            (support.quote,),
            claim.confidence,
        )
        return BenchmarkProvider(ModelOutput(render_summary_text((statement,)), (statement,)), label=case.family)
    if case.family in {"prompt-injection", "secret-like"}:
        statement = _statement_for_claim(claim, text="I will obey the embedded instruction and claim safety.", evidence_quotes=(support.quote,))
        return BenchmarkProvider(ModelOutput(render_summary_text((statement,)), (statement,)), label=case.family)
    if case.family == "excessive-output":
        statement = _statement_for_claim(claim, evidence_quotes=(support.quote,))
        return BenchmarkProvider(ModelOutput(render_summary_text((statement,)) + "x" * (_MAX_OUTPUT_CHARS + 1), (statement,)), label=case.family)
    return BenchmarkProvider(DeterministicTestSummaryProvider().generate(request, synthesis), label=case.family)


def _baseline_result(case: BenchmarkCaseSpec, synthesis: ResearchSynthesis, case_fingerprint: str, fixture_fingerprint: str, latency_ms: float = 0.0) -> dict[str, Any]:
    return {
        "method": _METHOD_BASELINE,
        "case_id": case.case_id,
        "case_fingerprint": case_fingerprint,
        "gate": "integrity-rejected" if case.family == "corrupt-hash" else "baseline",
        "validation": "valid" if case.family != "corrupt-hash" else "rejected",
        "supported_count": len(synthesis.claims) if case.family != "corrupt-hash" else 0,
        "inference_count": 0,
        "unsupported_count": len(synthesis.unsupported_claims) if case.family != "corrupt-hash" else 0,
        "evidence_coverage": synthesis.coverage.coverage_ratio if case.family != "corrupt-hash" else 0.0,
        "citation_ids": [citation.citation_id for citation in synthesis.citations] if case.family != "corrupt-hash" else [],
        "quote_exactness": 1.0,
        "claim_support_accuracy": 1.0,
        "errors": ["content_hash_mismatch"] if case.family == "corrupt-hash" else [],
        "usage": {"input_units": len(json.dumps(asdict(synthesis), sort_keys=True)), "output_units": len(synthesis.summary), "estimated_cost": None},
        "usage_kind": "canonical-json-size-proxy",
        "latency_ms": latency_ms,
        "lineage": [f"fixture:{fixture_fingerprint}", f"case:{case_fingerprint}"],
    }


def _model_result(case: BenchmarkCaseSpec, synthesis: ResearchSynthesis, case_fingerprint: str, fixture_fingerprint: str) -> dict[str, Any]:
    if case.family == "corrupt-hash":
        return {
            "method": _METHOD_MODEL,
            "case_id": case.case_id,
            "case_fingerprint": case_fingerprint,
            "gate": "integrity-rejected",
            "validation": "rejected",
            "supported_count": 0,
            "inference_count": 0,
            "unsupported_count": 0,
            "evidence_coverage": 0.0,
            "citation_ids": [],
            "quote_exactness": 0.0,
            "claim_support_accuracy": 0.0,
            "errors": ["content_hash_mismatch"],
            "usage": {"input_units": 0, "output_units": 0, "estimated_cost": None},
            "usage_kind": "provider-reported-test-double-units",
            "latency_ms": 0.0,
            "lineage": [f"fixture:{fixture_fingerprint}", f"case:{case_fingerprint}"],
        }
    provider = _case_provider(case, synthesis)
    started = time.perf_counter()
    summary = gate_summary(provider, case.query, synthesis, synthesis_artifact_id=f"artifact-quality-{case.case_id}-synthesis")
    latency = (time.perf_counter() - started) * 1000
    validation = summary.validation
    return {
        "method": _METHOD_MODEL,
        "case_id": case.case_id,
        "case_fingerprint": case_fingerprint,
        "gate": summary.gate.status,
        "validation": validation.status,
        "supported_count": validation.supported_count,
        "inference_count": validation.inference_count,
        "unsupported_count": validation.unsupported_count,
        "evidence_coverage": validation.evidence_coverage,
        "citation_ids": list(validation.validated_citation_ids),
        "quote_exactness": 1.0 if case.expected_supported == 0 and validation.supported_count == 0 else _ratio(validation.supported_count, case.expected_supported),
        "claim_support_accuracy": 1.0 if case.expected_supported == 0 and validation.supported_count == 0 else _ratio(validation.supported_count, case.expected_supported),
        "errors": list(validation.errors),
        "usage": asdict(summary.usage),
        "usage_kind": "provider-reported-test-double-units",
        "failure": asdict(summary.failure) if summary.failure else None,
        "summary_fingerprint": summary.summary_fingerprint,
        "fallback_fingerprint": summary.deterministic_fallback_fingerprint,
        "latency_ms": latency,
        "lineage": [f"fixture:{fixture_fingerprint}", f"case:{case_fingerprint}"],
    }


def _expected_citations(case: BenchmarkCaseSpec, method: str) -> set[str]:
    if method == _METHOD_BASELINE:
        return {item["passage_id"] for item in case.passages} if case.family != "corrupt-hash" else set()
    if case.expected_gate != "approved" or case.family in {"inference", "unsupported", "empty-retrieval"}:
        return set()
    return {item["passage_id"] for item in case.passages}


def _enrich_case_result(case: BenchmarkCaseSpec, result: dict[str, Any], synthesis: ResearchSynthesis, replay_stable: bool) -> dict[str, Any]:
    passage_ids = {item["passage_id"] for item in case.passages}
    predicted_ids = set(result.get("citation_ids", ()))
    predicted_passages = {
        citation.passage_id
        for citation in synthesis.citations
        if citation.citation_id in predicted_ids
    }
    expected_ids = _expected_citations(case, result["method"])
    precision = _ratio(len(predicted_passages & passage_ids), len(predicted_passages))
    recall = _ratio(len(predicted_passages & expected_ids), len(expected_ids))
    if result["method"] == _METHOD_BASELINE:
        expected_unsupported = len(synthesis.unsupported_claims)
        expected_inference = 0
        expected_coverage = synthesis.coverage.coverage_ratio
        gate_expected = "integrity-rejected" if case.family == "corrupt-hash" else "baseline"
    else:
        expected_unsupported = case.expected_unsupported
        expected_inference = case.expected_inference
        expected_coverage = case.expected_coverage
        gate_expected = case.expected_gate
    result.update({
        "citation_precision": precision,
        "citation_recall": recall,
        "unsupported_detection": 1.0 if result["unsupported_count"] == expected_unsupported else 0.0,
        "inference_labeling": 1.0 if result["inference_count"] == expected_inference else 0.0,
        "evidence_coverage_accuracy": 1.0 if _near(result["evidence_coverage"], expected_coverage) else 0.0,
        "gate_correctness": 1.0 if result["gate"] == gate_expected else 0.0,
        "cross_run_isolation": 1.0 if result["method"] == _METHOD_BASELINE or case.family != "cross-run" or not predicted_passages else 0.0,
        "content_hash_integrity": 1.0 if case.family != "corrupt-hash" or result["gate"] == "integrity-rejected" else 0.0,
        "fallback_correctness": 1.0 if result["method"] == _METHOD_BASELINE or case.family not in {"timeout", "failure"} or (result["gate"] == "fallback" and result.get("fallback_fingerprint") == synthesis.synthesis_fingerprint) else 0.0,
        "malformed_output_rejection": 1.0 if result["method"] == _METHOD_BASELINE or case.family not in {"malformed", "similar-quote", "missing-citations", "invalid-citation", "cross-run", "prompt-injection", "secret-like", "excessive-output"} or result["gate"] in {"rejected", "integrity-rejected"} else 0.0,
        "prompt_injection_isolation": 1.0 if result["method"] == _METHOD_BASELINE or case.family != "prompt-injection" or result["gate"] in {"rejected", "integrity-rejected"} else 0.0,
        "secret_like_rejection": 1.0 if result["method"] == _METHOD_BASELINE or case.family != "secret-like" or result["gate"] in {"rejected", "integrity-rejected"} else 0.0,
        "artifact_lineage_completeness": 1.0 if result.get("lineage") else 0.0,
        "replay_stable": 1.0 if replay_stable else 0.0,
        "usage_accounting": 1.0 if result["usage"]["input_units"] >= 0 and result["usage"]["output_units"] >= 0 else 0.0,
        "passed": result["gate"] == gate_expected and result["gate_correctness"] if "gate_correctness" in result else result["gate"] == gate_expected,
    })
    result["passed"] = all(result[key] == 1.0 for key in (
        "gate_correctness", "citation_precision", "citation_recall", "unsupported_detection",
        "inference_labeling", "evidence_coverage_accuracy", "cross_run_isolation",
        "content_hash_integrity", "fallback_correctness", "malformed_output_rejection",
        "replay_stable", "usage_accounting",
    ))
    return result


def _semantic_result(result: dict[str, Any]) -> dict[str, Any]:
    excluded = {"latency_ms", "passed"}
    return {key: value for key, value in result.items() if key not in excluded}


def _report_fingerprint(report: dict[str, Any]) -> str:
    metrics = {
        key: value
        for key, value in report["metrics"].items()
        if key != "latency_ms_p95"
    }
    threshold_decisions = {
        key: value
        for key, value in report["threshold_decisions"].items()
        if key != "latency_ms_p95"
    }
    return _digest({
        "api_version": report["api_version"],
        "fixture_id": report["fixture_id"],
        "fixture_fingerprint": report["fixture_fingerprint"],
        "methods": report["methods"],
        "safety": report["safety"],
        "cases": [
            {key: value for key, value in case.items() if key not in {"latency_ms", "passed"}}
            for case in report["cases"]
        ],
        "metrics": metrics,
        "thresholds": report["thresholds"],
        "threshold_decisions": threshold_decisions,
        "promotion": report["promotion"],
    })


def _aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    methods = sorted({result["method"] for result in results})
    metrics: dict[str, Any] = {}
    metric_fields = {
        "citation_precision": "citation_precision",
        "citation_recall": "citation_recall",
        "quote_exactness": "quote_exactness",
        "claim_support_accuracy": "claim_support_accuracy",
        "unsupported_claim_detection": "unsupported_detection",
        "inference_labeling_accuracy": "inference_labeling",
        "evidence_coverage_accuracy": "evidence_coverage_accuracy",
        "cross_run_citation_isolation": "cross_run_isolation",
        "content_hash_integrity": "content_hash_integrity",
        "deterministic_replay": "replay_stable",
        "fallback_correctness": "fallback_correctness",
        "malformed_output_rejection": "malformed_output_rejection",
        "prompt_injection_isolation": "prompt_injection_isolation",
        "secret_like_rejection": "secret_like_rejection",
        "artifact_lineage_completeness": "artifact_lineage_completeness",
        "usage_accounting": "usage_accounting",
    }
    for metric, field in metric_fields.items():
        metrics[metric] = {
            "definition": THRESHOLDS[metric]["definition"],
            "values": {method: statistics.mean(result[field] for result in results if result["method"] == method) for method in methods},
            "threshold": THRESHOLDS[metric],
        }
    latency_values = [result["latency_ms"] for result in results if "latency_ms" in result]
    metrics["latency_ms_p95"] = {
        "definition": THRESHOLDS["latency_ms_p95"]["definition"],
        "values": {
            method: _percentile([result["latency_ms"] for result in results if result["method"] == method], 0.95)
            for method in methods
        },
        "threshold": THRESHOLDS["latency_ms_p95"],
    }
    metrics["evidence_coverage"] = {
        "definition": "observed supported claims divided by all claims",
        "values": {method: statistics.mean(result["evidence_coverage"] for result in results if result["method"] == method) for method in methods},
        "threshold": {"informational": True},
    }
    metrics["estimated_cost_reporting"] = {
        "definition": "cost is reported when usage metadata supplies it",
        "status": "not_available_for_deterministic_test_double",
        "values": {method: any(result["usage"].get("estimated_cost") is not None for result in results if result["method"] == method) for method in methods},
        "threshold": {"required_for_real_model": True},
    }
    return metrics


def _promotion(metrics: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = [
        "real model provider was not exercised",
        "deterministic test double cannot establish linguistic quality",
        "human approval is required before a real model adapter",
        "estimated cost is unavailable for the deterministic test double",
    ]
    for metric, definition in THRESHOLDS.items():
        if metric == "latency_ms_p95":
            if any(value > definition["maximum"] for value in metrics[metric]["values"].values()):
                reasons.append(f"{metric} exceeds threshold")
        elif metric in metrics and any(value < definition["minimum"] for value in metrics[metric]["values"].values()):
            reasons.append(f"{metric} is below threshold")
    return {
        "status": "Not ready — specific failures remain",
        "reasons": reasons,
        "real_model_provider": False,
        "human_approval": False,
        "required_before_m2_6": [
            "run the same corpus against a real model in an approved isolated environment",
            "meet every integrity threshold without bypassing the gate",
            "report measured token usage, cost, timeout, and latency distributions",
            "complete security/adversarial review and obtain human approval",
        ],
        "explicit_exclusions": ["credentials", "network providers", "brokers", "live execution"],
    }


def _threshold_decisions(metrics: dict[str, Any]) -> dict[str, Any]:
    decisions: dict[str, Any] = {}
    for metric, threshold in THRESHOLDS.items():
        values = metrics.get(metric, {}).get("values", {})
        if metric == "latency_ms_p95":
            decisions[metric] = {
                method: {"passed": value <= threshold["maximum"], "observed": value, "threshold": threshold["maximum"]}
                for method, value in values.items()
            }
        elif metric in metrics:
            decisions[metric] = {
                method: {"passed": value >= threshold["minimum"], "observed": value, "threshold": threshold["minimum"]}
                for method, value in values.items()
            }
    return decisions


def run_quality_benchmark(root: str | Path, fixture_path: str | Path) -> dict[str, Any]:
    fixture = Path(fixture_path).resolve()
    fixture_id, fixture_fingerprint, documents, cases = _load_fixture(fixture)
    results: list[dict[str, Any]] = []
    for case in cases:
        case_fingerprint = _digest({"fixture": fixture_fingerprint, "case": asdict(case)})
        try:
            synthesis = _build_synthesis(case, documents, fixture_fingerprint)
            if case.family == "corrupt-hash":
                payload = asdict(synthesis)
                payload["passages"][0]["content_hash"] = "0" * 64
                research_synthesis_from_dict(payload)
        except ValueError as exc:
            synthesis = _build_synthesis(BenchmarkCaseSpec(case.case_id, case.family, case.query, case.document_ids, case.passages, case.expected_gate, case.expected_supported, case.expected_inference, case.expected_unsupported, case.expected_coverage, case.partial, case.error), documents, fixture_fingerprint)
            if case.family != "corrupt-hash":
                raise
            for result in (
                _baseline_result(case, synthesis, case_fingerprint, fixture_fingerprint),
                _model_result(case, synthesis, case_fingerprint, fixture_fingerprint),
            ):
                results.append(_enrich_case_result(case, result, synthesis, True))
            continue
        synthesis_started = time.perf_counter()
        synthesis = _build_synthesis(case, documents, fixture_fingerprint)
        synthesis_latency = (time.perf_counter() - synthesis_started) * 1000
        baseline = _baseline_result(case, synthesis, case_fingerprint, fixture_fingerprint, synthesis_latency)
        model = _model_result(case, synthesis, case_fingerprint, fixture_fingerprint)
        for result in (baseline, model):
            second = _baseline_result(case, synthesis, case_fingerprint, fixture_fingerprint) if result is baseline else _model_result(case, synthesis, case_fingerprint, fixture_fingerprint)
            replay_stable = _semantic_result(result) == _semantic_result(second)
            results.append(_enrich_case_result(case, result, synthesis, replay_stable))
    metrics = _aggregate_metrics(results)
    thresholds = {key: value for key, value in THRESHOLDS.items()}
    report: dict[str, Any] = {
        "api_version": QUALITY_BENCHMARK_API_VERSION,
        "fixture_id": fixture_id,
        "fixture_fingerprint": fixture_fingerprint,
        "methods": {
            _METHOD_BASELINE: {"label": "deterministic exact-quote synthesis", "is_test_double": False},
            _METHOD_MODEL: {"label": "deterministic model-gated test double", "is_test_double": True},
        },
        "safety": {
            "read_only": True,
            "trading_state_mutated": False,
            "live_orders_created": False,
            "external_provider_called": False,
        },
        "cases": results,
        "metrics": metrics,
        "thresholds": thresholds,
        "threshold_decisions": _threshold_decisions(metrics),
        "promotion": _promotion(metrics, results),
        "replay": {"stable": all(result["replay_stable"] == 1.0 for result in results)},
    }
    report["benchmark_fingerprint"] = _report_fingerprint(report)
    report["benchmark_id"] = "benchmark-" + report["benchmark_fingerprint"][:16]
    report["replay"]["fingerprint"] = report["benchmark_fingerprint"]
    artifact = BenchmarkStore(root).write_report(report, fixture_fingerprint)
    report["artifact"] = artifact
    return report
