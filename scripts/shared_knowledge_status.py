"""Show the shared knowledge checkpoint and the next maintenance action."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UA = ROOT / ".ua"


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc


def project_changes(checkpoint: str) -> list[str]:
    if not checkpoint:
        return []
    changed = git("diff", "--name-only", checkpoint, "HEAD", "--", ".").splitlines()
    return [path for path in changed if path != ".ua" and not path.startswith(".ua/")]


def main() -> int:
    graph = read_json(UA / "knowledge-graph.json")
    meta = read_json(UA / "meta.json")
    fingerprints = read_json(UA / "fingerprints.json")
    scan = read_json(UA / "intermediate" / "scan-result.json")

    checkpoint = graph.get("project", {}).get("gitCommitHash", "")
    metadata_match = len({checkpoint, meta.get("gitCommitHash", ""), fingerprints.get("gitCommitHash", "")}) == 1
    head = git("rev-parse", "HEAD")
    drift = project_changes(checkpoint) if metadata_match else ["<graph metadata mismatch>"]
    worktree = git("status", "--short").splitlines()
    worktree_source = [
        line[3:]
        for line in worktree
        if len(line) >= 4 and line[3:] != ".ua" and not line[3:].startswith(".ua/")
    ]
    files = {item.get("path") for item in scan.get("files", []) if isinstance(item, dict)}

    print("Shared knowledge status")
    print(f"  HEAD:       {head}")
    print(f"  checkpoint: {checkpoint or '<missing>'}")
    print(f"  files:      {len(files)}")
    print(f"  nodes:      {len(graph.get('nodes', []))}")
    print(f"  edges:      {len(graph.get('edges', []))}")
    print(f"  metadata:   {'ok' if metadata_match else 'MISMATCH'}")
    source_stale = bool(drift or worktree_source)
    print(f"  source:     {'current' if not source_stale else 'STALE'}")
    if drift:
        print("  source changes after checkpoint:")
        for path in drift[:20]:
            print(f"    - {path}")
    if worktree_source:
        print("  uncommitted source changes:")
        for path in worktree_source[:20]:
            print(f"    - {path}")
    if worktree:
        print(f"  worktree:   {len(worktree)} changed path(s)")
    else:
        print("  worktree:   clean")

    if not metadata_match or source_stale:
        print("Next: commit source/canonical knowledge, then run /understand --language en.")
        return 1
    print("Next: use /understand-dashboard for the shared local graph; refresh after meaningful source/docs changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
