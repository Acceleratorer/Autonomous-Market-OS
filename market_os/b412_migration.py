"""Compatibility alias for market_os.portfolio_migration."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".portfolio_migration", __package__)
