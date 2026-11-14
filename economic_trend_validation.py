import itertools

import numpy as np
import pandas as pd

import economic_trend as et

TRAIN = ("1980-01-01", "1997-12-31")
VALID = ("1998-01-01", "2014-12-31")


def sharpe(x: pd.Series) -> float:
    return x.mean() / x.std() * np.sqrt(12)


def evaluate(returns: pd.DataFrame, **config) -> list[dict]:
    comm_sign = config.pop("TRADE_COMM", None)
    defaults = {k: getattr(et, k) for k in config}
    for k, v in config.items():
        setattr(et, k, v)
    if comm_sign is not None:
        et.SIGNS.loc["trade", "COMM"] = comm_sign
    strategies, _ = et.build(returns)
    names = ["price_trend", "economic_trend"] + [et.blend_name(w) for w in et.BLEND_WEIGHTS]
    rows = []
    for name in names:
        bt = et.backtest(strategies[name], returns)
        row = {**config, "trade_comm_sign": et.SIGNS.loc["trade", "COMM"], "strategy": name}
        for label, (a, b) in {"train": TRAIN, "valid": VALID}.items():
            row[f"{label}_sharpe"] = sharpe(bt.net.loc[a:b])
            row[f"{label}_turnover"] = bt.turnover.loc[a:b].mean() * 12
        rows.append(row)
    for k, v in defaults.items():           # restore module state
        setattr(et, k, v)
    et.SIGNS.loc["trade", "COMM"] = 1
    return rows


def main() -> None:
    returns = et.load_returns().loc[:et.IS_END]
    rows = []
    # 1) variants reported for transparency (full grid, main design otherwise)
    for signal, comm in itertools.product(["sign", "zscore"], [-1, 1]):
        rows += evaluate(returns, SIGNAL_MODE=signal, TRADE_COMM=comm, SMOOTH_MONTHS=1, CLASS_BALANCE=False)
    # 2) construction choices made on TRAIN
    for smooth, balance in itertools.product([1, 3], [False, True]):
        rows += evaluate(returns, SIGNAL_MODE="sign", TRADE_COMM=1, SMOOTH_MONTHS=smooth, CLASS_BALANCE=balance)
    table = pd.DataFrame(rows).drop_duplicates(subset=["SIGNAL_MODE", "trade_comm_sign", "SMOOTH_MONTHS", "CLASS_BALANCE", "strategy"])
    et.OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(et.OUT / "validation_grid.csv", index=False)

    econ = table[(table.strategy == "economic_trend") & (table.SIGNAL_MODE == "sign") & (table.trade_comm_sign == 1)]
    best = econ.loc[econ.train_sharpe.idxmax()]
    blends = table[(table.SIGNAL_MODE == "sign") & (table.trade_comm_sign == 1)
                   & (table.SMOOTH_MONTHS == best.SMOOTH_MONTHS) & (table.CLASS_BALANCE == best.CLASS_BALANCE)
                   & table.strategy.str.startswith(("blend", "price"))]
    best_blend = blends[blends.strategy != "price_trend"].train_sharpe.idxmax()
    pd.set_option("display.width", 200)
    print(table[table.strategy == "economic_trend"].round(2).to_string(index=False))
    print(f"\nchosen on TRAIN: smooth={best.SMOOTH_MONTHS}, class_balance={best.CLASS_BALANCE}, "
          f"{blends.loc[best_blend, 'strategy']}")
    print(blends.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
