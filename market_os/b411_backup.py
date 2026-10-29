"""Compatibility alias for market_os.portfolio_backup."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".portfolio_backup", __package__)
