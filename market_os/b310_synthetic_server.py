"""Compatibility alias for market_os.synthetic_server."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".synthetic_server", __package__)
