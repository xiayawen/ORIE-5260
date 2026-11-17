"""Lecture 8 transaction cost model for monthly futures strategies.

Net return = gross return - explicit costs - implicit costs (taxes and fees
out of scope, as in the lecture).

Explicit costs (lecture slides 8, 24-26, 32)
- Commission / exchange / clearing fees: fixed bps per unit of notional traded.
- Futures roll: each roll trades the held notional out of the front contract and
  into the next one. Charged as roll_bps x |position| x rolls per month, so a
  buy-and-hold futures book still pays a cost. Rolls per year follow each
  contract's listed cycle where known (energy monthly, grains/livestock 5-8,
  financials quarterly) and fall back to the asset-class value otherwise.
- Margin / financing: futures embed notional leverage and need no portfolio
  financing, but initial margin must be posted from capital. Margin-to-equity is
  reported each month; any margin above the cash available (MAX_MARGIN_TO_EQUITY)
  would have to be financed at FINANCING_SPREAD_BPS a year. Futures carry no
  stock-borrow (shorting) fee, so no shorting cost is charged.

Implicit costs (slides 13-19, 27-28)
- Half-spread: paid on every unit of notional traded (asset-class level).
- Market impact: square-root model driven by the two features on slide 28,
  participation and volatility:
      MI_i = Y * sigma_daily_i * sqrt(trade_usd_i / (ADV_usd_i * execution_days))
  Cost in return units is MI_i x |trade weight_i|, so it grows with AUM^0.5 and
  is what makes capacity a real question. The trade is spread over
  ``execution_days`` (default 5): a monthly CTA does not trade its whole
  rebalance in one session, and with one day the $10bn case would need more
  than 100% of daily volume.

Turnover
- ``turnover="drift"`` (default when returns are passed): the trade needed is
  w_t - w_{t-1} (1 + r_{t-1}) / (1 + R_{t-1}), i.e. from last month's weights
  after they drifted with returns, not from last month's target.
- ``turnover="target"``: |w_t - w_{t-1}|, the definition used elsewhere in the repo.

All inputs used to price a trade executed in month t+1 are known at the
formation date t: volatility is the formation-date estimate, and liquidity uses
trailing daily volume through t. Parameter values are illustrative, fixed in
advance, and not fitted to strategy performance.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DAILY_DIR = ROOT / "FuturesUnderlyingData"
TRADING_DAYS = 252

# Approximate rolls per year when holding the liquid contract; instruments not
# listed use the asset-class value in CostParameters.rolls_per_year.
INSTRUMENT_ROLLS_PER_YEAR = {
    "BC": 12, "BG": 12, "ZU": 12, "ZB": 12, "ZH": 12, "ZN": 12,      # energy
    "ZC": 5, "ZS": 7, "ZM": 8, "ZL": 8, "ZO": 5, "MW": 5, "ZW": 5, "ZR": 6,  # grains
    "CC": 5, "CT": 5, "KC": 5, "SB": 4, "JO": 6, "LB": 6, "DA": 12,  # softs, other
    "ZG": 6, "ZI": 5, "ZK": 5, "ZA": 4, "ZP": 4,                     # metals
    "ZF": 8, "ZT": 6, "ZZ": 7,                                       # livestock
    "FF": 12,                                                        # monthly short rate
}


@dataclass(frozen=True)
class CostParameters:
    # explicit
    commission_bps: float = 1.0
    roll_bps: float = 1.0
    rolls_per_year: dict = field(default_factory=lambda: {"EQ": 4, "FI": 4, "FX": 4, "COMM": 6})
    instrument_rolls_per_year: dict = field(default_factory=lambda: dict(INSTRUMENT_ROLLS_PER_YEAR))
    margin_rate: dict = field(default_factory=lambda: {"EQ": 0.06, "FI": 0.03, "FX": 0.04, "COMM": 0.08})
    max_margin_to_equity: float = 1.0
    financing_spread_bps: float = 50.0
    # implicit
    half_spread_bps: dict = field(default_factory=lambda: {"EQ": 1.0, "FI": 0.5, "FX": 1.0, "COMM": 2.5})
    impact_coefficient: float = 0.5
    adv_usd: dict = field(default_factory=lambda: {"EQ": 5e9, "FI": 10e9, "FX": 5e9, "COMM": 1e9})
    illiquid_contract_volume: float = 2_000.0
    illiquid_adv_multiplier: float = 0.1
    execution_days: int = 5
    aum_usd: float = 1e9
    turnover: str = "drift"

    def with_aum(self, aum_usd: float) -> "CostParameters":
        return self.replace(aum_usd=aum_usd)

    def replace(self, **changes) -> "CostParameters":
        return CostParameters(**{**self.__dict__, **changes})


DEFAULT_PARAMETERS = CostParameters()


def trailing_contract_volume(index: pd.DatetimeIndex, instruments, window: int = TRADING_DAYS) -> pd.DataFrame:
    """Trailing median daily contract volume known at each month end (NaN if no daily file/history)."""
    out = {}
    for instrument in instruments:
        path = DAILY_DIR / f"{instrument}.csv"
        if not path.exists():
            continue
        daily = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
        volume = pd.to_numeric(daily["Volume"], errors="coerce").where(lambda v: v > 0)
        trailing = volume.rolling(window, min_periods=window // 2).median()
        # Use the offset object rather than the version-specific "M"/"ME"
        # string alias so this works across the project's supported pandas
        # environments without changing the month-end convention.
        out[instrument] = trailing.resample(pd.offsets.MonthEnd()).last().reindex(
            index, method="ffill", limit=1)
    return pd.DataFrame(out, index=index).reindex(columns=list(instruments))


def instrument_adv_usd(volume: pd.DataFrame, asset_class: pd.Series, params: CostParameters) -> pd.DataFrame:
    """Asset-class ADV assumption, cut for instruments whose trailing contract volume is thin.

    Contract volumes are not comparable across contracts without multipliers, so
    they are used only to flag clearly illiquid markets. Missing daily history
    falls back to the class assumption.
    """
    base = pd.Series({c: params.adv_usd[asset_class[c]] for c in volume.columns})
    illiquid = volume.lt(params.illiquid_contract_volume)
    multiplier = illiquid.astype(float).mul(params.illiquid_adv_multiplier - 1).add(1)
    return multiplier.mul(base, axis=1), illiquid


def trade_weights(executed: pd.DataFrame, returns: pd.DataFrame | None = None,
                  turnover: str = "drift") -> pd.DataFrame:
    """|trade| per instrument in month t as a fraction of NAV (initial entry included).

    Drift uses month t-1 returns only, which are known before the month-t trade.
    Without returns, falls back to the target-weight change.
    """
    executed = executed.fillna(0.0)
    if turnover not in ("drift", "target"):
        raise ValueError("turnover must be 'drift' or 'target'")
    if turnover == "target" or returns is None:
        return executed.diff().fillna(executed).abs()
    r = returns.reindex_like(executed).fillna(0.0)
    port = (executed * r).sum(axis=1)
    drifted = (executed * (1 + r)).div(1 + port, axis=0).shift(1).fillna(0.0)
    return (executed - drifted).abs()


def rolls_per_year(columns, classes: pd.Series, params: CostParameters) -> pd.Series:
    return pd.Series({c: params.instrument_rolls_per_year.get(c, params.rolls_per_year.get(classes[c], 4))
                      for c in columns}, dtype=float)


def cost_breakdown(executed: pd.DataFrame, formation_vol: pd.DataFrame, adv_usd: pd.DataFrame,
                   asset_class: pd.Series, params: CostParameters = DEFAULT_PARAMETERS,
                   returns: pd.DataFrame | None = None):
    """Monthly cost components in return units for execution-month weights.

    executed: weights earning month-t returns (formed at t-1).
    formation_vol, adv_usd: indexed by formation date; shifted here so month t
    trades use only t-1 information.
    returns: monthly instrument returns, needed for drift-adjusted turnover.
    Returns (monthly component DataFrame, per-instrument total cost DataFrame).
    """
    cols = executed.columns
    classes = asset_class.reindex(cols)
    by_class = lambda mapping: classes.map(mapping).astype(float)

    trade = trade_weights(executed, returns, params.turnover)
    held = executed.abs()
    vol = formation_vol.reindex(index=executed.index, columns=cols).ffill().shift(1)
    # Missing vol: same-date class median, then same-date cross-sectional median
    # (no full-sample statistic, so nothing from later dates leaks in).
    vol = vol.T.fillna(vol.T.groupby(classes).transform("median")).T
    vol = vol.apply(lambda col: col.fillna(vol.median(axis=1)))
    adv = adv_usd.reindex(index=executed.index, columns=cols).shift(1)
    adv = adv.apply(lambda col: col.fillna(params.adv_usd[classes[col.name]]))

    commission = trade * params.commission_bps / 1e4
    spread = trade.mul(by_class(params.half_spread_bps) / 1e4, axis=1)
    sigma_daily = vol / np.sqrt(TRADING_DAYS)
    participation = trade * params.aum_usd / (adv * params.execution_days)
    impact = params.impact_coefficient * sigma_daily * np.sqrt(participation) * trade
    roll = held.mul(rolls_per_year(cols, classes, params) / 12 * params.roll_bps / 1e4, axis=1)

    margin_to_equity = held.mul(by_class(params.margin_rate), axis=1).sum(axis=1)
    shortfall = (margin_to_equity - params.max_margin_to_equity).clip(lower=0)
    financing = shortfall * params.financing_spread_bps / 1e4 / 12

    per_instrument = commission + spread + impact + roll
    monthly = pd.DataFrame({
        "commission": commission.sum(axis=1),
        "roll": roll.sum(axis=1),
        "financing": financing,
        "half_spread": spread.sum(axis=1),
        "market_impact": impact.sum(axis=1),
    })
    monthly["explicit"] = monthly[["commission", "roll", "financing"]].sum(axis=1)
    monthly["implicit"] = monthly[["half_spread", "market_impact"]].sum(axis=1)
    monthly["total"] = monthly.explicit + monthly.implicit
    monthly["turnover"] = trade.sum(axis=1)
    monthly["gross_exposure"] = held.sum(axis=1)
    monthly["margin_to_equity"] = margin_to_equity
    monthly["max_participation"] = participation.max(axis=1)
    return monthly, per_instrument
