"""Offline LightRAG document fixture and retrieval adapter."""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import Evidence
from ..providers import (
    CachePolicy,
    DocumentRecord,
    LicenseMetadata,
    ProviderCapability,
    ProviderCancelled,
    ProviderDeadline,
    ProviderError,
    ProviderHealth,
    Provenance,
    RetrievedPassage,
    RetrievalResult,
)


class LightRAGUnavailable(RuntimeError):
    """The optional LightRAG runtime cannot execute this request."""

    def __init__(self, message: str, *, code: str = "provider_unavailable", retryable: bool = False) -> None:
        self.provider_error = ProviderError(code, message, retryable, "lightrag")
        super().__init__(f"{code}: {message}")


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("document timestamps must use UTC")
    return parsed


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stop_child(process: subprocess.Popen[str]) -> None:
    """Stop the isolated provider process without waiting on inherited pipes."""
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        else:
            process.kill()
    for stream in (process.stdout, process.stderr):
        if stream is not None and not stream.closed:
            stream.close()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


_RUNNER = r'''
import asyncio
import json
import sys
from pathlib import Path

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc, Tokenizer, TokenizerInterface


class ProbeTokenizer(TokenizerInterface):
    def encode(self, content):
        return [ord(character) for character in content]

    def decode(self, tokens):
        return "".join(chr(token) for token in tokens)


async def embed(texts):
    rows = []
    for text in texts:
        values = np.zeros(8, dtype=np.float32)
        for index, value in enumerate(text.encode("utf-8")):
            values[index % 8] += value
        norm = np.linalg.norm(values)
        rows.append(values / norm if norm else values)
    return np.asarray(rows)


async def llm(prompt, **kwargs):
    return "{}"


async def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rag = LightRAG(
        working_dir=request["working_dir"],
        workspace=request["workspace"],
        llm_model_func=llm,
        embedding_func=EmbeddingFunc(embedding_dim=8, max_token_size=4096, func=embed),
        tokenizer=Tokenizer("market-os-m2.2-char", ProbeTokenizer()),
        entity_extraction_use_json=True,
        entity_extract_max_gleaning=0,
        max_parallel_insert=1,
    )
    await rag.initialize_storages()
    try:
        await rag.ainsert(
            [item["content"] for item in request["documents"]],
            ids=[item["document_id"] for item in request["documents"]],
            file_paths=[item["file_path"] for item in request["documents"]],
        )
        result = await rag.aquery_data(
            request["query"],
            QueryParam(mode="naive", enable_rerank=False, chunk_top_k=20),
        )
        print(json.dumps({"status": "ok", "result": result}, sort_keys=True))
    finally:
        await rag.finalize_storages()


asyncio.run(main())
'''


class LightRAGFixtureAdapter:
    """Validate local documents and retrieve cited passages through LightRAG."""

    provider_name = "lightrag"
    provider_version = "m2.2-lightrag-naive-v1"

    def __init__(
        self,
        corpus_path: str | Path,
        reference_root: str | Path,
        python_executable: str | Path | None = None,
        workspace: str | Path | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.corpus_path = Path(corpus_path).resolve()
        self.reference_root = Path(reference_root).resolve()
        self.python_executable = str(python_executable or sys.executable)
        self.workspace = Path(workspace or tempfile.gettempdir()).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        self.timeout_seconds = timeout_seconds
        self.fixture_id = ""
        self.fixture_checksum = ""
        self.records: tuple[DocumentRecord, ...] = ()
        self._contents: dict[str, str] = {}
        self._load_corpus()
        self.last_documents: tuple[DocumentRecord, ...] = ()
        self.last_retrieval_result: RetrievalResult | None = None
        self.last_document_payload: list[dict[str, Any]] = []

    def health(self) -> ProviderHealth:
        return ProviderHealth(self.provider_name, "healthy", self._retrieved_at(), "local synthetic corpus")

    def capabilities(self) -> tuple[ProviderCapability, ...]:
        return (
            ProviderCapability("document-ingestion", "lightrag-ainsert-v1", "offline text fixture ingestion"),
            ProviderCapability("retrieval", "lightrag-aquery-data-naive-v1", "structured cited chunk retrieval"),
        )

    def documents_for(self, symbols: tuple[str, ...] = ()) -> tuple[DocumentRecord, ...]:
        if not symbols:
            return self.records
        requested = set(symbols)
        selected = tuple(
            document
            for document in self.records
            if not document.symbols or requested.intersection(document.symbols)
        )
        if not selected:
            raise ValueError(f"no fixture documents match symbols: {', '.join(symbols)}")
        return selected

    def documents(
        self,
        query: str,
        symbols: tuple[str, ...],
        *,
        deadline: ProviderDeadline | None = None,
        cache: CachePolicy | None = None,
    ) -> tuple[DocumentRecord, ...]:
        del query, deadline, cache
        return self.documents_for(symbols)

    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str) -> list[Evidence]:
        del start, end
        selected = self.documents_for(symbols)
        result = self.retrieve_documents(objective, selected)
        self.last_documents = selected
        self.last_document_payload = [
            {"document": asdict(document), "content": self._contents[document.document_id]}
            for document in selected
        ]
        evidence: list[Evidence] = []
        by_id = {document.document_id: document for document in selected}
        for passage in result.passages:
            document = by_id[passage.document_id]
            evidence.append(
                Evidence(
                    passage.citation_ref,
                    "document",
                    f"{document.title} — cited passage {passage.rank}",
                    document.provenance.source_ref,
                    document.retrieved_at,
                    passage.text,
                    document.symbols,
                )
            )
        return evidence

    def retrieve_documents(
        self,
        query: str,
        documents: tuple[DocumentRecord, ...],
        *,
        deadline: ProviderDeadline | None = None,
        cache: CachePolicy | None = None,
        cancel_event: threading.Event | None = None,
    ) -> RetrievalResult:
        del cache
        if cancel_event is not None and cancel_event.is_set():
            raise ProviderCancelled("LightRAG retrieval cancelled before launch")
        if not documents:
            raise ValueError("LightRAG retrieval requires at least one document")
        if not self.reference_root.is_dir():
            raise LightRAGUnavailable(
                f"LightRAG reference repository is unavailable: {self.reference_root}",
                code="provider_unavailable",
            )
        if not Path(self.python_executable).exists():
            raise LightRAGUnavailable(
                f"LightRAG Python executable is unavailable: {self.python_executable}",
                code="dependency_unavailable",
            )
        run_dir = Path(tempfile.mkdtemp(prefix="m2-2-lightrag-", dir=self.workspace))
        try:
            request_path = run_dir / "request.json"
            working_dir = run_dir / "rag"
            working_dir.mkdir()
            request_path.write_text(
                json.dumps(
                    {
                        "working_dir": str(working_dir),
                        "workspace": "market-os-m2.2",
                        "query": query,
                        "documents": [
                            {
                                "document_id": document.document_id,
                                "file_path": f"{document.document_id}.md",
                                "content": self._contents[document.document_id],
                            }
                            for document in documents
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            runner_path = run_dir / "runner.py"
            runner_path.write_text(_RUNNER, encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(self.reference_root),
                    "NO_PROXY": "*",
                    "no_proxy": "*",
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                    "TOKENIZERS_PARALLELISM": "false",
                }
            )
            process = subprocess.Popen(
                [self.python_executable, str(runner_path), str(request_path)],
                cwd=self.reference_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            timeout_seconds = deadline.timeout_seconds if deadline else self.timeout_seconds
            deadline_at = time.monotonic() + timeout_seconds
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    _stop_child(process)
                    raise ProviderCancelled("LightRAG retrieval cancelled during execution")
                remaining = deadline_at - time.monotonic()
                if remaining <= 0:
                    _stop_child(process)
                    raise LightRAGUnavailable(
                        "LightRAG retrieval exceeded its execution deadline",
                        code="deadline_exceeded",
                        retryable=True,
                    )
                try:
                    stdout, stderr = process.communicate(timeout=min(remaining, 0.1))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode != 0:
                code = "dependency_unavailable" if "ModuleNotFoundError" in stderr else "provider_failed"
                raise LightRAGUnavailable(f"LightRAG process failed: {stderr[-1200:]}", code=code)
            try:
                envelope = json.loads(stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError) as exc:
                raise LightRAGUnavailable("LightRAG returned an invalid result envelope", code="provider_failed") from exc
            if envelope.get("status") != "ok":
                raise LightRAGUnavailable(f"LightRAG retrieval failed: {envelope}", code="provider_failed")
            result = self._normalise_result(query, documents, envelope.get("result"))
            self.last_retrieval_result = result
            return result
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_version": self.provider_version,
            "fixture_id": self.fixture_id,
            "fixture_sha256": self.fixture_checksum,
            "source_ref": f"repository:{self.reference_root}",
            "source_commit": _git_head(self.reference_root),
            "license": {"classification": "synthetic-internal", "license_name": "internal fixture"},
        }

    def _load_corpus(self) -> None:
        self.fixture_checksum = hashlib.sha256(self.corpus_path.read_bytes()).hexdigest()
        payload = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        self.fixture_id = payload.get("fixture_id", "")
        if not self.fixture_id or payload.get("label", "").lower().find("synthetic") < 0:
            raise ValueError("document fixture must have a stable synthetic label")
        if payload.get("license", {}).get("classification") != "synthetic-internal":
            raise ValueError("document fixture has an unknown license classification")
        records: list[DocumentRecord] = []
        seen: set[str] = set()
        for item in payload.get("documents", ()):
            document_id = item.get("document_id", "")
            content = item.get("content", "")
            if document_id in seen:
                raise ValueError(f"duplicate document ID: {document_id}")
            if not content.strip():
                raise ValueError(f"document content is empty: {document_id}")
            if item.get("media_type") not in {"text/plain", "text/markdown"}:
                raise ValueError(f"unsupported document media type: {item.get('media_type')}")
            if item.get("content_hash") != _sha256(content):
                raise ValueError(f"document content hash mismatch: {document_id}")
            _utc(item["published_at"])
            _utc(item["retrieved_at"])
            provenance = Provenance(self.provider_name, f"fixture:{self.fixture_id}:{document_id}", item["retrieved_at"])
            records.append(
                DocumentRecord(
                    document_id,
                    item["title"],
                    item["publisher"],
                    item["source_ref"],
                    item["published_at"],
                    item["retrieved_at"],
                    tuple(item.get("symbols", ())),
                    item["media_type"],
                    item["content_hash"],
                    LicenseMetadata("synthetic-internal", "internal fixture", "Market OS generated synthetic data", ("not for redistribution",)),
                    provenance,
                    f"fixture:{self.fixture_id}:{document_id}",
                )
            )
            seen.add(document_id)
            self._contents[document_id] = content
        if len(records) < 4:
            raise ValueError("document fixture must contain at least four documents")
        self.records = tuple(records)

    def _retrieved_at(self) -> str:
        return self.records[0].retrieved_at

    def _normalise_result(self, query: str, documents: tuple[DocumentRecord, ...], raw: Any) -> RetrievalResult:
        if not isinstance(raw, dict):
            raise LightRAGUnavailable("LightRAG returned a malformed retrieval result", code="provider_failed")
        query_fingerprint = _sha256(json.dumps({
            "query": query,
            "documents": [document.document_id for document in documents],
            "content": [document.content_hash for document in documents],
            "provider_version": self.provider_version,
        }, sort_keys=True))
        if raw.get("status") == "failure":
            message = str(raw.get("message") or "no retrieval results")
            return RetrievalResult(
                query,
                tuple(document.document_id for document in documents),
                (),
                (),
                self.provider_name,
                self.provider_version,
                self._retrieved_at(),
                query_fingerprint,
                tuple(document.content_hash for document in documents),
                error=message,
            )
        if raw.get("status") != "success":
            raise LightRAGUnavailable("LightRAG returned a malformed retrieval result", code="provider_failed")
        data = raw.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("chunks"), list):
            raise LightRAGUnavailable("LightRAG result is missing cited chunks", code="provider_failed")
        by_path = {f"{document.document_id}.md": document for document in documents}
        passages: list[RetrievedPassage] = []
        for rank, chunk in enumerate(data["chunks"], 1):
            if not isinstance(chunk, dict) or not isinstance(chunk.get("content"), str) or not chunk["content"].strip():
                raise LightRAGUnavailable("LightRAG returned a malformed passage", code="provider_failed")
            document = by_path.get(Path(str(chunk.get("file_path", ""))).name)
            if document is None:
                raise LightRAGUnavailable("LightRAG returned a passage with unknown provenance", code="provider_failed")
            chunk_id = str(chunk.get("chunk_id", ""))
            if not chunk_id:
                raise LightRAGUnavailable("LightRAG returned a passage without a chunk ID", code="provider_failed")
            score = chunk.get("score")
            passages.append(
                RetrievedPassage(
                    f"{document.document_id}:{chunk_id}",
                    document.document_id,
                    chunk["content"],
                    rank,
                    f"lightrag:{document.document_id}:{chunk_id}",
                    document.provenance.source_ref,
                    _sha256(chunk["content"]),
                    float(score) if isinstance(score, (int, float)) else None,
                )
            )
        if not passages:
            return RetrievalResult(
                query,
                tuple(document.document_id for document in documents),
                (),
                (),
                self.provider_name,
                self.provider_version,
                self._retrieved_at(),
                query_fingerprint,
                tuple(document.content_hash for document in documents),
                error="no_results",
            )
        return RetrievalResult(
            query,
            tuple(document.document_id for document in documents),
            tuple(passages),
            tuple(passage.citation_ref for passage in passages),
            self.provider_name,
            self.provider_version,
            self._retrieved_at(),
            query_fingerprint,
            tuple(document.content_hash for document in documents),
        )


def _git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"
    return result.stdout.strip()
