"""Compatibility entrypoint for the original baseline/comparison.

Implementation: orie5260.backtests.compare_baseline. See README.md for the selected42 workflow.
"""
from importlib import import_module
import sys

_implementation = import_module("orie5260.backtests.compare_baseline")
if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
