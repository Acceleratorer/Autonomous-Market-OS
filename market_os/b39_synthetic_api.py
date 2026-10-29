"""Compatibility alias for market_os.synthetic_session_api."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".synthetic_session_api", __package__)
