"""Compatibility entrypoint for the original baseline/comparison.

Implementation: futures_portfolio.backtests.daily_baseline. See README.md for the selected42 workflow.
"""
from importlib import import_module
import sys

_implementation = import_module("futures_portfolio.backtests.daily_baseline")
if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
