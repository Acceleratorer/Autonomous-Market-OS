"""Compatibility alias for market_os.synthetic_evaluation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".synthetic_evaluation", __package__)
