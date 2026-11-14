import itertools

import numpy as np
import pandas as pd

import economic_trend as et

TRAIN = ("1980-01-01", "1997-12-31")
VALID = ("1998-01-01", "2014-12-31")


def sharpe(x: pd.Series) -> float:
    return x.mean() / x.std() * np.sqrt(12)


def main() -> None:
    returns = et.read_returns()
    rows = []
    for smooth, balance in itertools.product([1, 3], [False, True]):
        et.SMOOTH_MONTHS, et.CLASS_BALANCE = smooth, balance
        strategies, _ = et.build(returns, et.ROOT / "macro_data")
        for name in ["price_trend", "economic_trend"] + [f"blend_{int(round(w*100))}" for w in et.BLEND_WEIGHTS]:
            bt = et.backtest(strategies[name], returns)
            econ_w = strategies["economic_trend"].shift(1)
            row = {"smooth": smooth, "class_balance": balance, "strategy": name}
            for label, (a, b) in {"train": TRAIN, "valid": VALID}.items():
                seg = bt.loc[a:b]
                row[f"{label}_sharpe"] = sharpe(seg.net)
                row[f"{label}_turnover"] = seg.turnover.mean() * 12
            fi = et.read_asset_map().set_index("ID")["AssetClass"].reindex(returns.columns)
            fi_cols = [c for c in returns.columns if fi.get(c) == "FI" or c in et.RATE_FUTURES_IN_FX]
            row["econ_net_bond_pos"] = econ_w[fi_cols].sum(axis=1).loc[TRAIN[0]:VALID[1]].mean()
            rows.append(row)
    table = pd.DataFrame(rows)
    et.OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(et.OUT / "validation_grid.csv", index=False)

    econ = table[table.strategy == "economic_trend"]
    best = econ.loc[econ.train_sharpe.idxmax()]
    blends = table[(table.smooth == best.smooth) & (table.class_balance == best.class_balance)
                   & table.strategy.str.startswith("blend")]
    best_blend = blends.loc[blends.train_sharpe.idxmax()]
    print(econ.round(2).to_string(index=False))
    print(f"\nchosen on TRAIN: smooth={best.smooth}, class_balance={best.class_balance}, {best_blend.strategy}")
    print(blends.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
