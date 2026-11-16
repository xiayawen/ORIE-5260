"""Command-line entry point for the final turning-point model."""

from __future__ import annotations

import argparse

from turning_point_model.final_model import run_final_model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--returns",
        default=None,
        help="Optional path to MonthlyReturns_FullSample.xlsx or a compatible CSV.",
    )
    parser.add_argument(
        "--macro-dir",
        default=None,
        help="Directory containing INDPRO.csv, CPIAUCSL.csv, GS2.csv, and optional BAA10Y.csv.",
    )
    args = parser.parse_args()
    run_final_model(args.returns, args.macro_dir or "macro_data")


if __name__ == "__main__":
    main()
