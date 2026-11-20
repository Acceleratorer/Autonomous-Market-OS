"""Prepare the pinned, target-native CPython runtime for the BTC assessor."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from typing import Any, BinaryIO
from urllib.request import Request, urlopen
import zipfile


LOCK_PATH = Path(__file__).parent / "models" / "btc_assessor_python_runtime.lock.json"
RUNTIME_RELATIVE_PATH = Path(".market_os") / "runtimes" / "btc-assessor-py311"
MAX_ARCHIVE_BYTES = 100_000_000
MAX_EXTRACTED_BYTES = 1_000_000_000
CHUNK_BYTES = 1024 * 1024


class AssessorPythonRuntimeError(RuntimeError):
    """Raised when the pinned assessor Python runtime cannot be verified."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK_BYTES):
            digest.update(block)
    return digest.hexdigest()


def _tree_sha256(root: Path) -> str:
    lines = []
    files = sorted(
        (path for path in root.rglob("*")
        if path.is_file()
        and path.name != "python-runtime-manifest.json"
        and path.suffix != ".pyc"
        and "__pycache__" not in path.parts),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )
    for path in files:
        relative = path.relative_to(root).as_posix()
        lines.append(f"{relative} {_sha256_file(path)}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _safe_member(root: Path, name: str) -> Path:
    member = PurePosixPath(name.replace("\\", "/"))
    if member.is_absolute() or any(":" in part for part in member.parts) or not member.parts or any(part in {"", ".", ".."} for part in member.parts):
        raise ValueError(f"unsafe Python archive member: {name!r}")
    target = (root / Path(*member.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Python archive member escapes its staging root: {name!r}")
    return target


def _copy_stream(source: BinaryIO, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        shutil.copyfileobj(source, output, CHUNK_BYTES)


def _extract_zip(archive: Path, destination: Path) -> None:
    total = 0
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = _safe_member(destination, member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            mode = member.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError(f"symlinks are not allowed in Python archives: {member.filename}")
            total += member.file_size
            if total > MAX_EXTRACTED_BYTES:
                raise ValueError("Python archive exceeds the extracted-size limit")
            with package.open(member, "r") as source:
                _copy_stream(source, target)


def _extract_tar(archive: Path, destination: Path) -> Path:
    total = 0
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as package:
        for member in package.getmembers():
            target = _safe_member(destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                total += member.size
                if total > MAX_EXTRACTED_BYTES:
                    raise ValueError("Python source archive exceeds the extracted-size limit")
                source = package.extractfile(member)
                if source is None:
                    raise ValueError(f"could not read Python source member: {member.name}")
                with source:
                    _copy_stream(source, target)
                target.chmod(member.mode & 0o755)
            else:
                raise ValueError(f"links and special files are not allowed in Python source archives: {member.name}")
    roots = tuple(path for path in destination.iterdir() if path.is_dir())
    if len(roots) != 1:
        raise ValueError("Python source archive must contain one top-level directory")
    return roots[0]


def _download(spec: dict[str, Any], destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"refusing to overwrite Python archive path: {destination}")
    partial = destination.with_name(destination.name + ".partial")
    request = Request(spec["url"], headers={"User-Agent": "Autonomous-Market-OS-BTC-Python-bootstrap/1"})
    digest = hashlib.sha256()
    received = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(request, timeout=30) as response, partial.open("wb") as output:
            while block := response.read(CHUNK_BYTES):
                received += len(block)
                if received > min(MAX_ARCHIVE_BYTES, int(spec["max_bytes"])):
                    raise ValueError(f"Python archive exceeded its download limit: {destination.name}")
                digest.update(block)
                output.write(block)
        actual = digest.hexdigest()
        if actual != spec["sha256"]:
            raise ValueError(f"Python archive SHA-256 mismatch: expected {spec['sha256']}, got {actual}")
        partial.replace(destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-800:]
        raise AssessorPythonRuntimeError(f"Python runtime preparation command failed ({Path(command[0]).name}): {detail or 'no command output'}")
    return result


def _pip_environment() -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith("PIP_") and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE"}
    }
    env["PIP_INDEX_URL"] = "https://pypi.org/simple"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _project_dependencies(project_root: Path) -> list[str]:
    project = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies = project.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies or any(not isinstance(item, str) for item in dependencies):
        raise ValueError("pyproject.toml must declare non-empty project dependencies")
    return dependencies


def _relative_import_entry(base: Path, target: Path) -> str:
    return os.path.relpath(target, base).replace("\\", "/")


def _windows_runtime_pth_path(runtime_root: Path) -> Path:
    dll_candidates = (
        runtime_root / "python311.dll",
        runtime_root / "DLLs" / "python311.dll",
        *runtime_root.rglob("python311.dll"),
    )
    dll = next((path for path in dll_candidates if path.is_file()), None)
    if dll is None:
        raise ValueError("Windows Python runtime is missing python311.dll")
    shared_library_pth = dll.with_name("python311._pth")
    executable_pth = runtime_root / "python._pth"
    pth_path = shared_library_pth if shared_library_pth.is_file() else executable_pth
    if not pth_path.is_file():
        raise ValueError("Windows Python runtime is missing its python311._pth path file")
    return pth_path


def _package_runtime(runtime_root: Path, target: str, output: Path) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    output = output.resolve()
    if target not in {"windows-x64", "linux-x64"}:
        raise ValueError(f"unsupported BTC assessor runtime target: {target}")
    if output.is_relative_to(runtime_root):
        raise ValueError("runtime bundle output must be outside the runtime tree")
    suffix = ".zip" if target == "windows-x64" else ".tar.gz"
    if not output.name.lower().endswith(suffix):
        raise ValueError(f"{target} runtime bundle must use the {suffix} format")
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = sorted(runtime_root.rglob("*"), key=lambda path: path.relative_to(runtime_root).as_posix())
    try:
        if target == "windows-x64":
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
                for path in paths:
                    if path.is_symlink():
                        raise ValueError(f"Windows runtime bundle cannot contain symlinks: {path}")
                    relative = path.relative_to(runtime_root).as_posix()
                    if path.is_dir():
                        package.writestr(relative + "/", "")
                    elif path.is_file():
                        package.write(path, relative)
                    else:
                        raise ValueError(f"runtime contains an unsupported file type: {path}")
        else:
            with tarfile.open(output, "w:gz") as package:
                for path in paths:
                    if path.is_symlink() and not path.resolve().is_relative_to(runtime_root):
                        raise ValueError(f"Linux runtime symlink escapes its tree: {path}")
                    if not (path.is_dir() or path.is_file() or path.is_symlink()):
                        raise ValueError(f"runtime contains an unsupported file type: {path}")
                    package.add(path, arcname=path.relative_to(runtime_root).as_posix(), recursive=False)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {
        "archive": output.name,
        "format": "zip" if target == "windows-x64" else "tar.gz",
        "bytes": output.stat().st_size,
        "sha256": _sha256_file(output),
    }


def _dependency_records(report_path: Path) -> list[dict[str, str]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    records = []
    for package in report.get("install", []):
        metadata = package.get("metadata", {})
        hashes = package.get("download_info", {}).get("archive_info", {}).get("hashes", {})
        name, version, sha256 = metadata.get("name"), metadata.get("version"), hashes.get("sha256")
        if not all(isinstance(value, str) and value for value in (name, version, sha256)):
            raise ValueError("pip install report is missing a package version or SHA-256")
        records.append({"name": name, "version": version, "wheel_sha256": sha256})
    if not records:
        raise ValueError("pip install report contains no installed dependencies")
    return sorted(records, key=lambda record: record["name"].casefold())


def _verify_runtime(runtime_root: Path, project_root: Path, spec: dict[str, Any], target: str) -> dict[str, Any]:
    manifest_path = runtime_root / "python-runtime-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "market-os.btc-assessor-python-runtime.v1"
        or manifest.get("target") != target
        or manifest.get("python_version") != spec["version"]
        or manifest.get("python_archive_sha256") != spec["sha256"]
    ):
        raise AssessorPythonRuntimeError("existing BTC assessor Python runtime does not match the approved target lock")
    if _tree_sha256(runtime_root) != manifest.get("runtime_tree_sha256_excluding_manifest_and_bytecode"):
        raise AssessorPythonRuntimeError("existing BTC assessor Python runtime failed its tree SHA-256 check")
    interpreter = (runtime_root / spec["interpreter"]).resolve()
    if not interpreter.is_relative_to(runtime_root.resolve()) or not interpreter.is_file():
        raise AssessorPythonRuntimeError("pinned BTC assessor Python interpreter is missing or escapes its runtime")
    try:
        result = _run(
            [str(interpreter), "-B", "-c", "import json,sys,duckdb,pyarrow; print(json.dumps({'sys_path':sys.path}), file=sys.stderr); import market_os.cli; print(json.dumps({'version': '.'.join(map(str,sys.version_info[:3]))}))"],
            cwd=project_root,
            env={**_pip_environment(), "PYTHONPATH": ""},
            timeout=30,
        )
    except AssessorPythonRuntimeError as exc:
        if target == "windows-x64":
            pth_path = _windows_runtime_pth_path(runtime_root)
            raise AssessorPythonRuntimeError(f"{exc}; active Windows path file {pth_path}: {pth_path.read_text(encoding='utf-8')!r}") from exc
        raise
    observed = json.loads(result.stdout.strip())
    if observed.get("version") != spec["version"]:
        raise AssessorPythonRuntimeError(f"pinned Python interpreter reported {observed.get('version')}, expected {spec['version']}")
    return {"runtime_root": runtime_root, "interpreter": interpreter, "manifest": manifest, "manifest_sha256": _sha256_file(manifest_path)}


def _install_windows(project_root: Path, work_root: Path, staging_root: Path, spec: dict[str, Any]) -> tuple[Path, Path]:
    archive = work_root / "downloads" / spec["archive"]
    _download(spec, archive)
    source_root = _extract_tar(archive, work_root / "source")
    build_script = source_root / "PCbuild" / "build.bat"
    if not build_script.is_file():
        raise ValueError("official CPython source archive is missing PCbuild/build.bat")
    _run([str(build_script), "-e", "-p", "x64"], cwd=source_root, timeout=1800)
    build_python = source_root / "PCbuild" / "amd64" / "python.exe"
    layout_package = source_root / "PC" / "layout"
    if not build_python.is_file() or not (layout_package / "__main__.py").is_file():
        raise ValueError("CPython Windows source build is missing its interpreter or layout tool")
    embedded_archive = work_root / "python-embed.zip"
    _run(
        [str(build_python), str(layout_package), "--zip", str(embedded_archive), "--preset-embed"],
        cwd=source_root,
        timeout=300,
    )
    _extract_zip(embedded_archive, staging_root)
    site_packages = staging_root / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    report_path = staging_root / "packages-install-report.json"
    dependencies = _project_dependencies(project_root)
    _run(
        [
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", "--no-input",
            "--only-binary=:all:", "--retries", "0", "--python-version", "3.11", "--implementation", "cp",
            "--abi", "cp311", "--platform", "win_amd64", "--target", str(site_packages),
            "--report", str(report_path), *dependencies,
        ],
        cwd=project_root,
        env=_pip_environment(),
    )
    pth_path = _windows_runtime_pth_path(staging_root)
    lines = pth_path.read_text(encoding="utf-8").splitlines()
    lines = ["import site" if line.strip() == "#import site" else line for line in lines]
    final_runtime_root = project_root / RUNTIME_RELATIVE_PATH
    final_pth_directory = final_runtime_root / pth_path.parent.relative_to(staging_root)
    project_entry = _relative_import_entry(final_pth_directory, project_root)
    site_packages_entry = _relative_import_entry(final_pth_directory, final_runtime_root / "Lib" / "site-packages")
    for entry in (site_packages_entry, project_entry):
        if entry not in lines:
            lines.append(entry)
    if "import site" not in lines:
        lines.append("import site")
    pth_path.write_text("\n".join(dict.fromkeys(lines)) + "\n", encoding="ascii")
    return staging_root / spec["interpreter"], report_path


def _install_linux(project_root: Path, work_root: Path, staging_root: Path, spec: dict[str, Any]) -> tuple[Path, Path]:
    archive = work_root / "downloads" / spec["archive"]
    _download(spec, archive)
    source_root = _extract_tar(archive, work_root / "source")
    configure = source_root / "configure"
    if not configure.is_file():
        raise ValueError("official CPython source archive is missing configure")
    _run([str(configure), f"--prefix={staging_root}", "--with-ensurepip=install"], cwd=source_root)
    jobs = max(1, min(4, os.cpu_count() or 1))
    _run(["make", f"-j{jobs}"], cwd=source_root, timeout=1800)
    _run(["make", "install"], cwd=source_root, timeout=900)
    interpreter = staging_root / spec["interpreter"]
    site_result = _run(
        [str(interpreter), "-B", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        cwd=project_root,
        env=_pip_environment(),
        timeout=30,
    )
    site_packages = Path(site_result.stdout.strip()).resolve()
    if not site_packages.is_relative_to(staging_root.resolve()):
        raise ValueError("CPython site-packages path escaped the staged runtime")
    site_packages.mkdir(parents=True, exist_ok=True)
    report_path = staging_root / "packages-install-report.json"
    _run(
        [
            str(interpreter), "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", "--no-input",
            "--only-binary=:all:", "--retries", "0", "--report", str(report_path),
            *_project_dependencies(project_root),
        ],
        cwd=project_root,
        env=_pip_environment(),
        timeout=600,
    )
    final_site_packages = project_root / RUNTIME_RELATIVE_PATH / site_packages.relative_to(staging_root)
    project_entry = _relative_import_entry(final_site_packages, project_root)
    (site_packages / "market-os-source.pth").write_text(project_entry + "\n", encoding="utf-8")
    return interpreter, report_path


def bootstrap_runtime(project_root: str | Path, target: str, *, verify_only: bool = False) -> dict[str, Any]:
    root = Path(project_root).resolve()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if lock.get("schema") != "market-os.btc-assessor-python-runtime-lock.v1":
        raise ValueError("unsupported BTC assessor Python runtime lock schema")
    spec = lock["targets"][target]
    if target == "windows-x64" and os.name != "nt" or target == "linux-x64" and not sys.platform.startswith("linux"):
        raise ValueError(f"Python runtime target {target} does not match this host")
    runtime_parent = root / RUNTIME_RELATIVE_PATH.parent
    runtime_root = root / RUNTIME_RELATIVE_PATH
    runtime_parent.mkdir(parents=True, exist_ok=True)
    if runtime_root.exists():
        return _verify_runtime(runtime_root, root, spec, target)
    if verify_only:
        raise AssessorPythonRuntimeError(f"pinned BTC assessor Python runtime is not installed: {runtime_root}")

    with tempfile.TemporaryDirectory(prefix=".btc-assessor-python-", dir=runtime_parent) as temporary:
        work_root = Path(temporary)
        staging_root = work_root / "runtime"
        staging_root.mkdir()
        interpreter, report_path = (
            _install_windows(root, work_root, staging_root, spec)
            if target == "windows-x64"
            else _install_linux(root, work_root, staging_root, spec)
        )
        smoke = _run(
            [str(interpreter), "-B", "-c", "import json,sys,duckdb,pyarrow; print(json.dumps({'version': '.'.join(map(str,sys.version_info[:3]))}))"],
            cwd=root,
            env=_pip_environment(),
            timeout=30,
        )
        if json.loads(smoke.stdout.strip()).get("version") != spec["version"]:
            raise AssessorPythonRuntimeError("prepared CPython version does not match its target lock")
        manifest = {
            "schema": "market-os.btc-assessor-python-runtime.v1",
            "target": target,
            "python_version": spec["version"],
            "python_distribution": spec["distribution"],
            "python_archive": spec["archive"],
            "python_archive_url": spec["url"],
            "python_archive_sha256": spec["sha256"],
            "python_executable": spec["interpreter"],
            "python_executable_sha256": _sha256_file(interpreter),
            "pyproject_sha256": _sha256_file(root / "pyproject.toml"),
            "dependencies": _dependency_records(report_path),
            "runtime_tree_sha256_excluding_manifest_and_bytecode": _tree_sha256(staging_root),
            "verification": {
                "result": "passed",
                "checks": ["target Python version", "duckdb import", "pyarrow import", "market_os.cli import"],
                "model_inference": "not run",
            },
        }
        (staging_root / "python-runtime-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging_root.replace(runtime_root)
    return _verify_runtime(runtime_root, root, spec, target)


def runtime_ci_evidence(
    target: str,
    verified: dict[str, Any],
    *,
    image_os: str,
    image_version: str,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not image_os or not image_version:
        raise AssessorPythonRuntimeError("CI runtime evidence requires the exact hosted runner image identity")
    manifest = verified["manifest"]
    runtime = {
        "version": manifest["python_version"],
        "distribution": manifest["python_distribution"],
        "archive": manifest["python_archive"],
        "archive_sha256": manifest["python_archive_sha256"],
        "manifest_sha256": verified["manifest_sha256"],
        "tree_sha256": manifest["runtime_tree_sha256_excluding_manifest_and_bytecode"],
        "dependencies": manifest["dependencies"],
        "verification": manifest["verification"],
    }
    if bundle is not None:
        runtime["bundle"] = bundle
    return {
        "schema": "market-os.btc-assessor-python-runtime-ci-evidence.v1",
        "target": target,
        "runner": {
            "image_os": image_os,
            "image_version": image_version,
            "platform": sys.platform,
            "architecture": platform.machine(),
        },
        "runtime": runtime,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=("windows-x64", "linux-x64"))
    parser.add_argument("--verify-only", action="store_true", help="verify an installed runtime without downloading or building")
    parser.add_argument("--evidence-output", type=Path, help="write CI evidence with the hosted runner image and runtime hashes")
    parser.add_argument("--bundle-output", type=Path, help="package the verified runtime as a target-native archive")
    args = parser.parse_args()
    result = bootstrap_runtime(Path(__file__).resolve().parents[1], args.target, verify_only=args.verify_only)
    bundle = _package_runtime(result["runtime_root"], args.target, args.bundle_output) if args.bundle_output else None
    if args.evidence_output:
        evidence = runtime_ci_evidence(
            args.target,
            result,
            image_os=os.environ.get("ImageOS", ""),
            image_version=os.environ.get("ImageVersion", ""),
            bundle=bundle,
        )
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"verified BTC assessor Python runtime: {result['interpreter']}")
    print(f"runtime manifest SHA-256: {result['manifest_sha256']}")
    if bundle:
        print(f"runtime bundle SHA-256: {bundle['sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, tarfile.TarError, zipfile.BadZipFile, subprocess.SubprocessError, AssessorPythonRuntimeError) as exc:
        print(f"BTC assessor Python runtime preparation failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
