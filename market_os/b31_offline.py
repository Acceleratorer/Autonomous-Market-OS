"""Compatibility alias for market_os.evaluation_protocol."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".evaluation_protocol", __package__)
