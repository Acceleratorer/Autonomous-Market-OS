"""Compatibility alias for market_os.strategy_replay."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".strategy_replay", __package__)
