"""Install pinned BTC local-assessor model and llama.cpp artifacts.

This is an explicit setup-time downloader. The Market OS runtime never invokes
it and does not download or update model/runtime artifacts implicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile
from typing import Any, BinaryIO
from urllib.request import Request, urlopen
import zipfile


MAX_MODEL_BYTES = 3_000_000_000
MAX_RUNTIME_ARCHIVE_BYTES = 1_000_000_000
CHUNK_BYTES = 1024 * 1024


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_member(root: Path, name: str) -> Path:
    member = PurePosixPath(name.replace("\\", "/"))
    if member.is_absolute() or not member.parts or any(part in {"", ".", ".."} for part in member.parts):
        raise ValueError(f"unsafe archive member path: {name!r}")
    destination = (root / Path(*member.parts)).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise ValueError(f"archive member escapes install root: {name!r}")
    return destination


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK_BYTES):
            digest.update(block)
    return digest.hexdigest()


def _download(spec: dict[str, Any], destination: Path, *, byte_limit: int) -> None:
    expected_size = spec["size_bytes"]
    if not isinstance(expected_size, int) or not 0 < expected_size <= byte_limit:
        raise ValueError(f"artifact exceeds configured download bound: {spec['archive'] if 'archive' in spec else spec['file']}")
    if destination.is_file():
        if destination.stat().st_size == expected_size and _sha256_file(destination) == spec["sha256"]:
            print(f"verified existing: {destination.name}")
            return
        raise ValueError(f"existing artifact does not match the pinned lock: {destination}")

    partial = destination.with_name(destination.name + ".partial")
    request = Request(spec["url"], headers={"User-Agent": "Autonomous-Market-OS-local-assessor-bootstrap/1"})
    digest = hashlib.sha256()
    received = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(request, timeout=30) as response, partial.open("wb") as output:
            while block := response.read(CHUNK_BYTES):
                received += len(block)
                if received > expected_size or received > byte_limit:
                    raise ValueError(f"download exceeded pinned size bound: {destination.name}")
                digest.update(block)
                output.write(block)
        if received != expected_size:
            raise ValueError(f"download size mismatch for {destination.name}: expected {expected_size}, got {received}")
        actual = digest.hexdigest()
        if actual != spec["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {destination.name}: expected {spec['sha256']}, got {actual}")
        partial.replace(destination)
        print(f"verified download: {destination.name} ({received} bytes, sha256={actual})")
    except BaseException:
        if partial.exists():
            partial.unlink()
        raise


def _copy_stream(source: BinaryIO, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        shutil.copyfileobj(source, output, CHUNK_BYTES)


def _extract_zip(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = _safe_member(destination, member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            mode = member.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError(f"symlinks are not allowed in runtime archives: {member.filename}")
            with package.open(member, "r") as source:
                _copy_stream(source, target)


def _extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as package:
        for member in package.getmembers():
            target = _safe_member(destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                source = package.extractfile(member)
                if source is None:
                    raise ValueError(f"could not read runtime archive member: {member.name}")
                with source:
                    _copy_stream(source, target)
                target.chmod(member.mode & 0o755)
            else:
                raise ValueError(f"links and special files are not allowed in runtime archives: {member.name}")


def _extract(archive: Path, destination: Path, format_name: str) -> None:
    if format_name == "zip":
        _extract_zip(archive, destination)
    elif format_name == "tar.gz":
        _extract_tar(archive, destination)
    else:
        raise ValueError(f"unsupported pinned archive format: {format_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        choices=("windows-x64-cuda-13.5", "windows-x64-cpu", "linux-x64-cuda-13.5", "linux-x64-cpu"),
        help="Select one pinned llama.cpp build; CUDA targets also install its matching CUDA runtime package.",
    )
    args = parser.parse_args()

    root = _repo_root()
    lock_path = root / "market_os" / "models" / "btc_local_assessor_runtime.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema") != "market-os.btc-local-assessor-runtime-lock.v1":
        raise ValueError("unsupported local-assessor runtime lock schema")
    target_spec = lock["runtime"]["targets"][args.target]
    install_root = root / ".market_os" / "local-evidence-runtime" / args.target
    download_root = install_root / "downloads"
    engine_root = install_root / "engine"
    model_root = install_root / "models"
    install_root.mkdir(parents=True, exist_ok=True)

    model = lock["model"]
    model_path = model_root / model["file"]
    _download(model, model_path, byte_limit=MAX_MODEL_BYTES)

    runtime_archive = download_root / target_spec["archive"]
    _download(target_spec, runtime_archive, byte_limit=MAX_RUNTIME_ARCHIVE_BYTES)
    _extract(runtime_archive, engine_root, target_spec["format"])

    cuda_spec = target_spec.get("cuda_runtime")
    if cuda_spec:
        cuda_archive = download_root / cuda_spec["archive"]
        _download(cuda_spec, cuda_archive, byte_limit=MAX_RUNTIME_ARCHIVE_BYTES)
        _extract(cuda_archive, engine_root, cuda_spec["format"])

    server_name = "llama-server.exe" if os.name == "nt" else "llama-server"
    matches = tuple(engine_root.rglob(server_name))
    if len(matches) != 1 or not matches[0].is_file():
        raise ValueError(f"expected exactly one {server_name} in the verified runtime archive, found {len(matches)}")

    manifest = {
        "schema": "market-os.btc-local-assessor-install.v1",
        "target": args.target,
        "lock_sha256": _sha256_file(lock_path),
        "model": {key: model[key] for key in ("provider_identity", "repository", "revision", "file", "size_bytes", "sha256", "license")},
        "runtime": {
            "repository": lock["runtime"]["repository"],
            "release": lock["runtime"]["release"],
            "source_revision": lock["runtime"]["source_revision"],
            "server_relative_path": str(matches[0].relative_to(install_root)).replace("\\", "/"),
            "server_sha256": _sha256_file(matches[0]),
            "archive_sha256": target_spec["sha256"],
            "cuda_runtime_sha256": cuda_spec["sha256"] if cuda_spec else None,
        },
    }
    manifest_path = install_root / "install-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"installed local runtime and model: {install_root}")
    print(f"install manifest: {manifest_path}")
    print("runtime setup used the network; model inference uses only these local files")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
