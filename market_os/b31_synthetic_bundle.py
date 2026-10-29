"""Compatibility alias for market_os.synthetic_artifacts."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".synthetic_artifacts", __package__)
