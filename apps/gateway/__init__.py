"""Local Market OS HTTP application."""

from __future__ import annotations

import sys
from typing import Sequence

from market_os.cli import main as _market_os_main


def main(argv: Sequence[str] | None = None) -> int:
    """Delegate to the existing loopback-only service command."""
    return _market_os_main(["serve", *(list(sys.argv[1:]) if argv is None else list(argv))])


__all__ = ["main"]
