"""Compatibility alias for market_os.btc_jev_evaluation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".btc_jev_evaluation", __package__)
