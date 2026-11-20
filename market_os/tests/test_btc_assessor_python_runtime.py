from __future__ import annotations

import json
from pathlib import Path
import tarfile
import tempfile
import zipfile

from market_os.btc_assessor_python_runtime import (
    LOCK_PATH,
    AssessorPythonRuntimeError,
    _dependency_records,
    _package_runtime,
    _relative_import_entry,
    _safe_member,
    _tree_sha256,
    _write_project_import_pth,
    _windows_runtime_pth_path,
    runtime_ci_evidence,
)


def test_runtime_lock_matches_the_latest_approved_python_org_source_archive() -> None:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))

    assert lock["schema"] == "market-os.btc-assessor-python-runtime-lock.v1"
    for target in ("windows-x64", "linux-x64"):
        assert lock["targets"][target]["version"] == "3.11.18"
        assert lock["targets"][target]["distribution"] == "python.org source build"
        assert lock["targets"][target]["archive"] == "Python-3.11.18.tgz"
        assert lock["targets"][target]["sha256"] == (
            "5f62711b12470fd435f83f1451c1b1ef4a179aebc715c716874b0967567d814e"
        )
        assert lock["targets"][target]["url"] == "https://www.python.org/ftp/python/3.11.18/Python-3.11.18.tgz"


def test_ci_runtime_evidence_binds_runner_image_and_runtime_hashes() -> None:
    verified = {
        "manifest_sha256": "a" * 64,
        "manifest": {
            "python_version": "3.11.18",
            "python_distribution": "python.org source build",
            "python_archive": "Python-3.11.18.tgz",
            "python_archive_sha256": "b" * 64,
            "runtime_tree_sha256_excluding_manifest_and_bytecode": "c" * 64,
            "dependencies": [{"name": "duckdb", "version": "2.0.0", "wheel_sha256": "d" * 64}],
            "verification": {"result": "passed"},
        },
    }

    evidence = runtime_ci_evidence(
        "windows-x64",
        verified,
        image_os="windows-2025",
        image_version="20261103.298.1",
        bundle={"archive": "runtime.zip", "format": "zip", "bytes": 10, "sha256": "e" * 64},
    )

    assert evidence["schema"] == "market-os.btc-assessor-python-runtime-ci-evidence.v1"
    assert evidence["target"] == "windows-x64"
    assert evidence["runner"]["image_os"] == "windows-2025"
    assert evidence["runner"]["image_version"] == "20261103.298.1"
    assert evidence["runtime"]["version"] == "3.11.18"
    assert evidence["runtime"]["archive_sha256"] == "b" * 64
    assert evidence["runtime"]["manifest_sha256"] == "a" * 64
    assert evidence["runtime"]["tree_sha256"] == "c" * 64
    assert evidence["runtime"]["bundle"]["sha256"] == "e" * 64
    try:
        runtime_ci_evidence("windows-x64", verified, image_os="windows-2025", image_version="")
    except AssessorPythonRuntimeError:
        pass
    else:
        raise AssertionError("CI runtime evidence without an exact runner image version was accepted")


def test_safe_python_archive_member_rejects_path_escape_and_drive_paths(tmp_path: Path) -> None:
    for member in ("../outside", "C:/outside", "/outside"):
        try:
            _safe_member(tmp_path, member)
        except ValueError:
            continue
        raise AssertionError(f"unsafe member was accepted: {member}")


def test_runtime_tree_digest_ignores_bytecode_and_its_manifest(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    (runtime / "Lib" / "__pycache__").mkdir(parents=True)
    (runtime / "python.exe").write_bytes(b"pinned interpreter")
    (runtime / "Lib" / "__pycache__" / "module.cpython-311.pyc").write_bytes(b"first cache")
    before = _tree_sha256(runtime)

    (runtime / "python-runtime-manifest.json").write_text("{}", encoding="utf-8")
    (runtime / "Lib" / "__pycache__" / "module.cpython-311.pyc").write_bytes(b"next cache")

    assert _tree_sha256(runtime) == before


def test_runtime_import_entries_resolve_from_the_final_bundle_location(tmp_path: Path) -> None:
    project = tmp_path / "project"
    runtime = project / ".market_os" / "runtimes" / "btc-assessor-py311"
    windows_site_packages = runtime / "Lib" / "site-packages"
    windows_entry = _relative_import_entry(windows_site_packages, project)
    linux_site_packages = runtime / "lib" / "python3.11" / "site-packages"
    linux_entry = _relative_import_entry(linux_site_packages, project)

    assert not Path(windows_entry).is_absolute()
    assert not Path(linux_entry).is_absolute()
    assert (windows_site_packages / windows_entry).resolve() == project.resolve()
    assert (linux_site_packages / linux_entry).resolve() == project.resolve()


def test_project_import_path_is_written_relative_to_final_site_packages(tmp_path: Path) -> None:
    project = tmp_path / "project"
    site_packages = tmp_path / "staging" / "Lib" / "site-packages"
    final_site_packages = project / ".market_os" / "runtimes" / "btc-assessor-py311" / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)

    _write_project_import_pth(site_packages, final_site_packages, project)

    entry = (site_packages / "market-os-source.pth").read_text(encoding="utf-8").strip()
    assert not Path(entry).is_absolute()
    assert (final_site_packages / entry).resolve() == project.resolve()


def test_windows_runtime_uses_the_shared_library_path_file_when_dll_is_nested(tmp_path: Path) -> None:
    project = tmp_path / "project"
    staging = tmp_path / "staging"
    dll_directory = staging / "DLLs"
    dll_directory.mkdir(parents=True)
    (dll_directory / "python311.dll").write_bytes(b"runtime dll")
    shared_library_pth = dll_directory / "python311._pth"
    shared_library_pth.write_text("relative path file", encoding="ascii")
    (staging / "python311._pth").write_text("executable path file", encoding="ascii")

    pth_path = _windows_runtime_pth_path(staging)
    final_runtime = project / ".market_os" / "runtimes" / "btc-assessor-py311"
    final_pth_directory = final_runtime / "DLLs"
    project_entry = _relative_import_entry(final_pth_directory, project)
    site_packages = final_runtime / "Lib" / "site-packages"
    site_packages_entry = _relative_import_entry(final_pth_directory, site_packages)

    assert pth_path == shared_library_pth
    assert not Path(project_entry).is_absolute()
    assert (final_pth_directory / project_entry).resolve() == project.resolve()
    assert (final_pth_directory / site_packages_entry).resolve() == site_packages.resolve()


def test_target_runtime_bundles_preserve_tree_paths_and_linux_modes(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    interpreter = runtime / "bin" / "python3.11"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"pinned interpreter")
    interpreter.chmod(0o755)
    (runtime / "python-runtime-manifest.json").write_text("{}", encoding="utf-8")

    windows_bundle = tmp_path / "windows.zip"
    windows_record = _package_runtime(runtime, "windows-x64", windows_bundle)
    with zipfile.ZipFile(windows_bundle) as package:
        assert "bin/python3.11" in package.namelist()
    assert windows_record["sha256"]
    assert windows_record["format"] == "zip"

    linux_bundle = tmp_path / "linux.tar.gz"
    linux_record = _package_runtime(runtime, "linux-x64", linux_bundle)
    with tarfile.open(linux_bundle, "r:gz") as package:
        member = package.getmember("bin/python3.11")
        assert member.isfile()
        source_mode = interpreter.stat().st_mode & 0o777
        assert member.mode == source_mode
        if source_mode & 0o111:
            assert member.mode & 0o111
    assert linux_record["sha256"]
    assert linux_record["format"] == "tar.gz"


def test_pip_report_requires_wheel_sha256() -> None:
    with tempfile.TemporaryDirectory() as directory:
        report_path = Path(directory) / "report.json"
        report_path.write_text(json.dumps({"install": [{"metadata": {"name": "duckdb", "version": "2.0.0"}, "download_info": {"archive_info": {"hashes": {"sha256": "a" * 64}}}}]}), encoding="utf-8")

        assert _dependency_records(report_path) == [{"name": "duckdb", "version": "2.0.0", "wheel_sha256": "a" * 64}]

        report_path.write_text(json.dumps({"install": [{"metadata": {"name": "duckdb", "version": "2.0.0"}, "download_info": {"archive_info": {}}}]}), encoding="utf-8")
        try:
            _dependency_records(report_path)
        except ValueError:
            pass
        else:
            raise AssertionError("pip report without a wheel hash was accepted")
