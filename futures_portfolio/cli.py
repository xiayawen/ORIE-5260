"""Entry points for the submitted baseline and selected 42-input strategy."""
from importlib import import_module
from pathlib import Path
import argparse

from futures_portfolio.paths import ROOT

COMMANDS = {
    "baseline": (
        "futures_portfolio.backtests.daily_baseline",
        "Course 11%-target daily TSMOM baseline",
    ),
    "selected42_target11": (
        "futures_portfolio.backtests.selected42_target11",
        "Final four-sleeve strategy: frozen 42 inputs, 11% target",
    ),
}
ALIASES = {"selected-42": "selected42_target11", "daily_baseline": "baseline"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the submitted futures backtests.")
    parser.add_argument("command", nargs="?", help="baseline or selected42_target11")
    parser.add_argument("--list", action="store_true", help="List available backtests")
    parser.add_argument("--dry-run", action="store_true", help="Show module without running it")
    args = parser.parse_args(argv)
    if args.list or not args.command:
        for name, (module, description) in COMMANDS.items():
            print(f"{name}: {description} [{module}]")
        return
    command = ALIASES.get(Path(args.command).stem, args.command)
    if command not in COMMANDS:
        parser.error(f"Unknown command {args.command!r}. Use --list.")
    module, description = COMMANDS[command]
    if args.dry_run:
        print(f"{command}: {module}\n{description}\nRepository: {ROOT}")
        return
    print(f"Running {command}: {module}", flush=True)
    import_module(module).main()
