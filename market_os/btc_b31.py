"""Compatibility alias for market_os.btc_question_evaluation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".btc_question_evaluation", __package__)
