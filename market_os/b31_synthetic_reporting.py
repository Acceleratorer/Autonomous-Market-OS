"""Compatibility alias for market_os.synthetic_reporting."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".synthetic_reporting", __package__)
