"""Compatibility alias for market_os.accounting."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".accounting", __package__)
