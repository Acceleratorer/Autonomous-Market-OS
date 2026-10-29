"""Compatibility alias for market_os.synthetic_audit."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".synthetic_audit", __package__)
