"""Compatibility alias for market_os.strategy."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".strategy", __package__)
