"""Compatibility alias for market_os.synthetic_session."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".synthetic_session", __package__)
