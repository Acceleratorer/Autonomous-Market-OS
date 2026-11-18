"""Isolated, offline MiniRAG retrieval over caller-owned local documents.

The adapter injects deterministic local embedding and extraction functions. It
does not configure a hosted model or pass provider credentials to the isolated
runtime; document content remains local.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..providers import (
    CachePolicy,
    DocumentRecord,
    ProviderCapability,
    ProviderCancelled,
    ProviderDeadline,
    ProviderError,
    ProviderHealth,
    RetrievedPassage,
    RetrievalResult,
)


class MiniRAGUnavailable(RuntimeError):
    """The optional local MiniRAG runtime could not complete retrieval."""

    def __init__(self, message: str, *, code: str = "provider_unavailable", retryable: bool = False) -> None:
        self.provider_error = ProviderError(code, message, retryable, "minirag")
        super().__init__(f"{code}: {message}")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError(f"{field} must use UTC")
    return parsed


def _stop_child(process: subprocess.Popen[str]) -> None:
    """Stop the isolated runtime and close its pipes after cancellation."""
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
import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import re
import socket
import sys
import types
from pathlib import Path

import numpy as np

def _deny_network(*args, **kwargs):
    del args, kwargs
    raise RuntimeError("Network access is disabled in this Market OS MiniRAG process")


socket.create_connection = _deny_network
socket.getaddrinfo = _deny_network
socket.gethostbyname = _deny_network
socket.gethostbyname_ex = _deny_network

_Socket = socket.socket

class _OfflineSocket(_Socket):
    def connect(self, *args, **kwargs):
        return _deny_network(*args, **kwargs)

    def connect_ex(self, *args, **kwargs):
        return _deny_network(*args, **kwargs)

    def sendto(self, *args, **kwargs):
        return _deny_network(*args, **kwargs)


socket.socket = _OfflineSocket

if importlib.util.find_spec("sentence_transformers") is None:
    sentence_transformers = types.ModuleType("sentence_transformers")
    class _UnusedSentenceTransformer:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("MiniRAG model embeddings are disabled in this offline adapter")
    sentence_transformers.SentenceTransformer = _UnusedSentenceTransformer
    sys.modules["sentence_transformers"] = sentence_transformers

from minirag import MiniRAG, QueryParam
from minirag.utils import EmbeddingFunc


request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
symbols = request["symbols"]

try:
    runtime_version = importlib.metadata.version("minirag-hku")
except importlib.metadata.PackageNotFoundError:
    try:
        runtime_version = importlib.metadata.version("lightrag-hku")
    except importlib.metadata.PackageNotFoundError:
        runtime_version = "source-checkout"


def chunk_text(content, overlap, chunk_size, model_name):
    del model_name
    words = re.findall(r"\S+", content)
    size = max(1, int(chunk_size))
    step = max(1, size - max(0, int(overlap)))
    chunks = []
    for index, start in enumerate(range(0, len(words), step)):
        text = " ".join(words[start : start + size])
        if text.strip():
            chunks.append({"tokens": len(words[start : start + size]), "content": text, "chunk_order_index": index})
    return chunks


async def embed(texts):
    rows = np.zeros((len(texts), 64), dtype=np.float32)
    for row_index, text in enumerate(texts):
        for token in re.findall(r"[a-z0-9_]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for slot in range(4):
                position = int.from_bytes(digest[slot * 2 : slot * 2 + 2], "little") % 64
                sign = 1.0 if digest[8 + slot] & 1 else -1.0
                rows[row_index, position] += sign
        norm = np.linalg.norm(rows[row_index])
        if norm:
            rows[row_index] /= norm
    return rows


async def local_structure(prompt, **kwargs):
    del kwargs
    if "entities_from_query" in prompt:
        return json.dumps({"answer_type_keywords": ["ASSET"], "entities_from_query": symbols})
    match = re.search(r"Event start UTC milliseconds:\s*(\d+)", prompt)
    if match is None:
        raise ValueError("BTC candle document did not contain its event start timestamp")
    candle_id = f"CANDLE_{match.group(1)}"
    records = [
        f'("entity"<|>"{symbols[0]}"<|>"ASSET"<|>"BTCUSDT Spot instrument.")',
        f'("entity"<|>"{candle_id}"<|>"CANDLE"<|>"BTCUSDT Spot one-minute candle source record at UTC event start milliseconds {match.group(1)}.")',
        f'("relationship"<|>"{symbols[0]}"<|>"{candle_id}"<|>"BTCUSDT has a source record for the finalized one-minute candle at UTC event start milliseconds {match.group(1)}."<|>"BTCUSDT Spot 1m candle OHLCV source observation"<|>1.0)',
    ]
    return "##".join(records) + "<|COMPLETE|>"


def parse_sources(context):
    marker = re.search(r"-----Sources-----\s*```csv\s*(.*?)\s*```", context, flags=re.DOTALL)
    if marker is None:
        raise ValueError("MiniRAG context did not contain a Sources CSV section")
    rows = list(csv.reader(io.StringIO(marker.group(1))))
    if not rows or rows[0] != ["id", "content"]:
        raise ValueError("MiniRAG Sources CSV header is unsupported")
    return [row[1] for row in rows[1:] if len(row) == 2 and row[1].strip()]


async def main():
    Path(request["working_dir"]).mkdir(parents=True, exist_ok=True)
    rag = MiniRAG(
        working_dir=request["working_dir"],
        embedding_func=EmbeddingFunc(embedding_dim=64, max_token_size=2048, func=embed),
        llm_model_func=local_structure,
        llm_model_name="market-os-deterministic-structure-v1",
        llm_model_max_token_size=4096,
        chunk_token_size=192,
        chunk_overlap_token_size=24,
        entity_extract_max_gleaning=0,
        enable_llm_cache=False,
        max_parallel_insert=1,
        chunking_func=chunk_text,
    )
    await rag.ainsert(
        [item["content"] for item in request["documents"]],
        ids=[item["document_id"] for item in request["documents"]],
    )
    context = await rag.aquery(
        request["query"],
        QueryParam(mode="mini", only_need_context=True, top_k=request["top_k"]),
    )
    if not isinstance(context, str) or not context.strip():
        print(json.dumps({"status": "failure", "runtime_version": runtime_version, "source_commit": request["source_commit"], "message": "MiniRAG returned no source context"}, sort_keys=True))
        return

    chunks_by_content = {}
    for chunk_id in await rag.text_chunks.all_keys():
        chunk = await rag.text_chunks.get_by_id(chunk_id)
        if not isinstance(chunk, dict) or not isinstance(chunk.get("content"), str):
            continue
        document_id = chunk.get("full_doc_id")
        if isinstance(document_id, str) and document_id:
            chunks_by_content.setdefault(chunk["content"], []).append({"chunk_id": chunk_id, "document_id": document_id})

    passages = []
    for text in parse_sources(context):
        candidates = chunks_by_content.get(text, [])
        document_ids = {item["document_id"] for item in candidates}
        if len(document_ids) != 1 or not candidates:
            raise ValueError("MiniRAG source text could not be mapped to one input document")
        selected = min(candidates, key=lambda item: item["chunk_id"])
        passages.append({"document_id": selected["document_id"], "chunk_id": selected["chunk_id"], "text": text})

    print(json.dumps({"status": "success", "runtime_version": runtime_version, "source_commit": request["source_commit"], "passages": passages}, sort_keys=True))


asyncio.run(main())
'''


class MiniRAGAdapter:
    """Run MiniRAG's graph retrieval mode with deterministic local functions.

    Documents and their exact contents are supplied by Market OS. The adapter
    is intentionally BTCUSDT Spot-focused and fixture/offline-only; its local
    structure function is not a substitute for a semantic model assessment.
    """

    provider_name = "minirag"
    adapter_version = "market-os-minirag-mini-mode-v1"

    def __init__(
        self,
        contents_by_document_id: Mapping[str, str],
        *,
        reference_root: str | Path | None = None,
        python_executable: str | Path | None = None,
        workspace: str | Path | None = None,
        timeout_seconds: float = 120.0,
        top_k: int = 12,
    ) -> None:
        self.contents = dict(contents_by_document_id)
        if not self.contents or any(not key.strip() for key in self.contents):
            raise ValueError("MiniRAG requires a non-empty content map keyed by document ID")
        self.reference_root = Path(reference_root).resolve() if reference_root is not None else None
        requested_python = str(python_executable or sys.executable)
        self.python_executable = shutil.which(requested_python) or str(Path(requested_python).expanduser().resolve())
        self.workspace = Path(workspace or tempfile.gettempdir()).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "tiktoken-cache").mkdir(exist_ok=True)
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        self.timeout_seconds = timeout_seconds
        self.top_k = top_k
        self.last_retrieval_result: RetrievalResult | None = None

    def health(self) -> ProviderHealth:
        available = Path(self.python_executable).exists()
        if self.reference_root is not None:
            available = available and self.reference_root.is_dir()
        if not available:
            return ProviderHealth(
                self.provider_name,
                "unavailable",
                datetime.now(timezone.utc).isoformat(),
                "MiniRAG Python runtime path is unavailable",
            )
        try:
            probe = subprocess.run(
                [
                    self.python_executable,
                    "-c",
                    "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('minirag') and importlib.util.find_spec('numpy') else 1)",
                ],
                cwd=self.workspace,
                env=self._child_environment(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            probe = None
        status = "healthy" if probe is not None and probe.returncode == 0 else "degraded"
        message = "isolated local MiniRAG runtime is available" if status == "healthy" else "Python is available, but MiniRAG or NumPy is missing"
        return ProviderHealth(self.provider_name, status, datetime.now(timezone.utc).isoformat(), message)

    def capabilities(self) -> tuple[ProviderCapability, ...]:
        return (
            ProviderCapability("document-ingestion", "minirag-ainsert-v1", "local text ingestion with deterministic structure extraction"),
            ProviderCapability("retrieval", "minirag-aquery-mini-context-v1", "MiniRAG graph retrieval with cited source chunks"),
        )

    def retrieve(
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
            raise ProviderCancelled("MiniRAG retrieval cancelled before launch")
        if not query.strip() or not documents:
            raise ValueError("MiniRAG retrieval requires a query and at least one document")
        document_ids = [document.document_id for document in documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("MiniRAG retrieval document IDs must be unique")
        symbols = sorted({symbol for document in documents for symbol in document.symbols})
        if symbols != ["BTCUSDT"] or any("BTCUSDT" not in document.symbols for document in documents):
            raise ValueError("this MiniRAG adapter currently accepts BTCUSDT-tagged documents only")
        for document in documents:
            content = self.contents.get(document.document_id)
            if content is None or not content.strip() or _sha256(content) != document.content_hash:
                raise ValueError(f"MiniRAG document content hash mismatch: {document.document_id}")
            _utc(document.published_at, "published_at")
            _utc(document.retrieved_at, "retrieved_at")
        missing = set(document_ids) - set(self.contents)
        if missing:
            raise ValueError(f"MiniRAG content map is missing document IDs: {', '.join(sorted(missing))}")
        if not Path(self.python_executable).exists():
            raise MiniRAGUnavailable(f"MiniRAG Python executable is unavailable: {self.python_executable}", code="dependency_unavailable")
        if self.reference_root is not None and not self.reference_root.is_dir():
            raise MiniRAGUnavailable(f"MiniRAG source root is unavailable: {self.reference_root}", code="dependency_unavailable")

        run_dir = Path(tempfile.mkdtemp(prefix="market-os-minirag-", dir=self.workspace))
        try:
            request_path = run_dir / "request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "working_dir": str(run_dir / "rag"),
                        "query": query,
                        "symbols": symbols,
                        "top_k": self.top_k,
                        "source_commit": self._source_commit(),
                        "documents": [
                            {"document_id": document.document_id, "content": self.contents[document.document_id]}
                            for document in documents
                        ],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            runner_path = run_dir / "runner.py"
            runner_path.write_text(_RUNNER, encoding="utf-8")
            process = subprocess.Popen(
                [self.python_executable, str(runner_path), str(request_path)],
                cwd=run_dir,
                env=self._child_environment(run_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            timeout_seconds = deadline.timeout_seconds if deadline else self.timeout_seconds
            deadline_at = time.monotonic() + timeout_seconds
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    _stop_child(process)
                    raise ProviderCancelled("MiniRAG retrieval cancelled during execution")
                remaining = deadline_at - time.monotonic()
                if remaining <= 0:
                    _stop_child(process)
                    raise MiniRAGUnavailable("MiniRAG retrieval exceeded its execution deadline", code="deadline_exceeded", retryable=True)
                try:
                    stdout, stderr = process.communicate(timeout=min(remaining, 0.1))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode != 0:
                code = "dependency_unavailable" if "ModuleNotFoundError" in stderr else "provider_failed"
                raise MiniRAGUnavailable(f"MiniRAG process failed: {stderr[-1200:]}", code=code)
            try:
                envelope = json.loads(stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError) as exc:
                raise MiniRAGUnavailable("MiniRAG returned an invalid result envelope", code="provider_failed") from exc
            result = self._normalise_result(query, documents, envelope)
            self.last_retrieval_result = result
            return result
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def _normalise_result(
        self,
        query: str,
        documents: tuple[DocumentRecord, ...],
        raw: Any,
    ) -> RetrievalResult:
        if not isinstance(raw, dict) or raw.get("status") not in {"success", "failure"}:
            raise MiniRAGUnavailable("MiniRAG returned a malformed result envelope", code="provider_failed")
        runtime_version = str(raw.get("runtime_version", "")).strip()
        source_commit = str(raw.get("source_commit", "")).strip()
        if not runtime_version:
            raise MiniRAGUnavailable("MiniRAG did not report its runtime version", code="provider_failed")
        provider_version = f"{runtime_version}+{source_commit or 'no-commit'};{self.adapter_version}"
        query_fingerprint = _sha256(json.dumps({
            "query": query,
            "documents": [document.document_id for document in documents],
            "content": [document.content_hash for document in documents],
            "provider_version": provider_version,
        }, sort_keys=True, separators=(",", ":")))
        retrieved_at = datetime.now(timezone.utc).isoformat()
        document_ids = tuple(document.document_id for document in documents)
        fingerprints = tuple(document.content_hash for document in documents)
        if raw["status"] == "failure":
            return RetrievalResult(
                query, document_ids, (), (), self.provider_name, provider_version,
                retrieved_at, query_fingerprint, fingerprints,
                error=str(raw.get("message") or "no retrieval results"),
            )
        raw_passages = raw.get("passages")
        if not isinstance(raw_passages, list):
            raise MiniRAGUnavailable("MiniRAG result is missing source passages", code="provider_failed")
        by_id = {document.document_id: document for document in documents}
        passages: list[RetrievedPassage] = []
        for rank, item in enumerate(raw_passages, 1):
            if not isinstance(item, dict):
                raise MiniRAGUnavailable("MiniRAG returned a malformed source passage", code="provider_failed")
            document_id = str(item.get("document_id", ""))
            chunk_id = str(item.get("chunk_id", ""))
            text = item.get("text")
            document = by_id.get(document_id)
            if document is None or not chunk_id or not isinstance(text, str) or not text.strip():
                raise MiniRAGUnavailable("MiniRAG returned a source without valid input lineage", code="provider_failed")
            passage_hash = _sha256(text)
            passages.append(
                RetrievedPassage(
                    f"{document_id}:{chunk_id}",
                    document_id,
                    text,
                    rank,
                    f"minirag:{document_id}:{chunk_id}",
                    document.provenance.source_ref,
                    passage_hash,
                )
            )
        if not passages:
            return RetrievalResult(
                query, document_ids, (), (), self.provider_name, provider_version,
                retrieved_at, query_fingerprint, fingerprints, error="no_results",
            )
        return RetrievalResult(
            query,
            document_ids,
            tuple(passages),
            tuple(passage.citation_ref for passage in passages),
            self.provider_name,
            provider_version,
            retrieved_at,
            query_fingerprint,
            fingerprints,
        )

    def _source_commit(self) -> str:
        if self.reference_root is None:
            return ""
        try:
            result = subprocess.run(
                ["git", "-C", str(self.reference_root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    def _child_environment(self, temporary_dir: str | Path) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
            "TEMP": str(temporary_dir),
            "TMP": str(temporary_dir),
            "HOME": str(temporary_dir),
            "USERPROFILE": str(temporary_dir),
            "PYTHONNOUSERSITE": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": str(self.reference_root) if self.reference_root is not None else "",
            "TIKTOKEN_CACHE_DIR": str(self.workspace / "tiktoken-cache"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
