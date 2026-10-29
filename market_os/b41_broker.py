"""Compatibility alias for market_os.portfolio_broker."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".portfolio_broker", __package__)
