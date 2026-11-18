"""Compatibility entrypoint for the original 66-input submission.

Implementation: orie5260.backtests.final_strategy. See README.md for the selected42 workflow.
"""
from importlib import import_module
import sys

_implementation = import_module("orie5260.backtests.final_strategy")
if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
