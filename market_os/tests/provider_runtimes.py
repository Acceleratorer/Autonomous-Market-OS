"""Discover and validate isolated optional-provider Python runtimes."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def find_optional_python(
    env_name: str,
    runtime_prefix: str,
    import_probe: str,
    *,
    pythonpath: Path,
    include_system_python: bool = False,
) -> str | None:
    """Return the first configured or matching runtime that passes its import probe."""
    pythonpath = Path(pythonpath)
    if not pythonpath.is_dir():
        return None

    candidates = [os.environ.get(env_name)]
    runtime_dirs = sorted(
        Path(tempfile.gettempdir()).glob(f"{runtime_prefix}-*"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    for runtime_dir in runtime_dirs:
        for relative in (Path("Scripts") / "python.exe", Path("bin") / "python"):
            executable = runtime_dir / relative
            if executable.is_file():
                candidates.append(str(executable))
                break
    if include_system_python:
        candidates.append(shutil.which("python"))

    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(pythonpath), environment.get("PYTHONPATH", "")) if value
    )
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        identity = os.path.normcase(os.path.abspath(candidate))
        if identity in seen:
            continue
        seen.add(identity)
        try:
            result = subprocess.run(
                [candidate, "-c", import_probe],
                check=False,
                capture_output=True,
                cwd=pythonpath,
                env=environment,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return str(Path(candidate).resolve())
    return None
