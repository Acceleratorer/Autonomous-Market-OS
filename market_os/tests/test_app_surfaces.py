from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_cli_surface_delegates_to_canonical_parser() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "apps.cli", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "market-os" in completed.stdout


def test_gateway_surface_delegates_without_renaming_canonical_module() -> None:
    from apps.gateway import main
    from market_os.cli import build_parser

    assert callable(main)
    assert build_parser().prog == "market-os"


def test_web_artifact_source_matches_legacy_preview() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/build_web_artifact.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_web_artifact_packaging_is_exact_and_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    manifests = []
    for output in (first, second):
        manifest = tmp_path / f"{output.name}.manifest.json"
        completed = subprocess.run(
            [sys.executable, "scripts/build_web_artifact.py", "--output", str(output), "--manifest", str(manifest)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert sorted(path.name for path in output.iterdir()) == [".htaccess", "DEPLOYMENT.txt", "index.html"]
        manifests.append(manifest.read_bytes())
    assert {
        path.name: path.read_bytes()
        for path in first.iterdir()
    } == {
        path.name: path.read_bytes()
        for path in second.iterdir()
    }
    assert manifests[0] == manifests[1]
    payload = __import__("json").loads(manifests[0])
    assert payload["schema"] == "market-os.web-static-artifact@v1"
    assert [item["path"] for item in payload["files"]] == ["index.html", ".htaccess", "DEPLOYMENT.txt"]
