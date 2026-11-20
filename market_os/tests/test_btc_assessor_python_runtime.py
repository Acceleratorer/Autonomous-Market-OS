from __future__ import annotations

import json
from pathlib import Path
import tempfile

from market_os.btc_assessor_python_runtime import (
    LOCK_PATH,
    AssessorPythonRuntimeError,
    _dependency_records,
    _safe_member,
    _tree_sha256,
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
    )

    assert evidence["schema"] == "market-os.btc-assessor-python-runtime-ci-evidence.v1"
    assert evidence["target"] == "windows-x64"
    assert evidence["runner"]["image_os"] == "windows-2025"
    assert evidence["runner"]["image_version"] == "20261103.298.1"
    assert evidence["runtime"]["version"] == "3.11.18"
    assert evidence["runtime"]["archive_sha256"] == "b" * 64
    assert evidence["runtime"]["manifest_sha256"] == "a" * 64
    assert evidence["runtime"]["tree_sha256"] == "c" * 64
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
