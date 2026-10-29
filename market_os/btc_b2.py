"""Compatibility alias for market_os.btc_features."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".btc_features", __package__)
