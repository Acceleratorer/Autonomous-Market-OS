"""Compatibility alias for market_os.synthetic_catalog."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".synthetic_catalog", __package__)
