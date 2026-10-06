from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "FuturesUnderlyingData"
OUT_DIR = ROOT / "outputs" / "eda"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_asset_map() -> pd.DataFrame:
    asset_map = pd.read_csv(ROOT / "AssetMapCsv.csv")
    asset_map["ID"] = asset_map["ID"].astype(str).str.strip()
    return asset_map


def read_existing_monthly_returns() -> pd.DataFrame:
    returns = pd.read_csv(ROOT / "MonthlyReturns.csv")
    date_col = returns.columns[0]
    returns = returns.rename(columns={date_col: "Date"})
    returns["Date"] = pd.to_datetime(returns["Date"], errors="coerce")
    returns = returns.dropna(subset=["Date"]).set_index("Date").sort_index()
    return returns.apply(pd.to_numeric, errors="coerce")


def compute_monthly_returns_from_daily() -> pd.DataFrame:
    series = {}
    for path in sorted(DATA_DIR.glob("*.csv")):
        symbol = path.stem
        daily = pd.read_csv(path)
        date_col = daily.columns[0]
        daily[date_col] = pd.to_datetime(daily[date_col], errors="coerce")
        daily["Close"] = pd.to_numeric(daily["Close"], errors="coerce")
        daily = daily.dropna(subset=[date_col, "Close"]).sort_values(date_col)
        monthly_close = daily.set_index(date_col)["Close"].resample("ME").last().dropna()
        series[symbol] = monthly_close.pct_change()
    monthly = pd.DataFrame(series).sort_index()
    monthly.index.name = "Date"
    return monthly


def robust_outliers(returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for symbol in returns.columns:
        s = returns[symbol].dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        low = q1 - 3.0 * iqr
        high = q3 + 3.0 * iqr
        median = s.median()
        mad = np.median(np.abs(s - median))
        if mad == 0 or np.isnan(mad):
            robust_z = pd.Series(np.nan, index=s.index)
        else:
            robust_z = 0.6745 * (s - median) / mad
        mask = (s < low) | (s > high) | (robust_z.abs() > 5)
        for date, value in s[mask].items():
            rows.append(
                {
                    "Date": date,
                    "ID": symbol,
                    "Return": value,
                    "IQR_Lower": low,
                    "IQR_Upper": high,
                    "RobustZ": robust_z.loc[date],
                    "Rule": "IQR_3x_or_abs_robust_z_gt_5",
                }
            )
    outliers = pd.DataFrame(rows)
    if outliers.empty:
        return outliers
    return outliers.sort_values(["Date", "ID"]).reset_index(drop=True)


def summarize_returns(returns: pd.DataFrame, asset_map: pd.DataFrame) -> pd.DataFrame:
    summary = returns.agg(["count", "mean", "std", "min", "median", "max", "skew", "kurt"]).T
    summary["annualized_mean"] = (1 + summary["mean"]) ** 12 - 1
    summary["annualized_vol"] = summary["std"] * np.sqrt(12)
    summary["sharpe_0rf"] = summary["annualized_mean"] / summary["annualized_vol"]
    summary = summary.reset_index(names="ID")
    summary = summary.merge(asset_map, on="ID", how="left")
    cols = ["ID", "Name", "AssetClass", "Ccy", "count", "mean", "std", "annualized_mean",
            "annualized_vol", "sharpe_0rf", "min", "median", "max", "skew", "kurt"]
    return summary[cols].sort_values(["AssetClass", "ID"], na_position="last")


def missingness(returns: pd.DataFrame, asset_map: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for symbol in returns.columns:
        first = returns[symbol].first_valid_index()
        last = returns[symbol].last_valid_index()
        rows.append(
            {
                "ID": symbol,
                "first_return": first,
                "last_return": last,
                "observations": returns[symbol].count(),
                "missing": returns[symbol].isna().sum(),
                "missing_pct": returns[symbol].isna().mean(),
            }
        )
    return pd.DataFrame(rows).merge(asset_map, on="ID", how="left")


def compare_existing_to_recomputed(existing: pd.DataFrame, recomputed: pd.DataFrame) -> pd.DataFrame:
    common_idx = existing.index.intersection(recomputed.index)
    common_cols = existing.columns.intersection(recomputed.columns)
    diff = existing.loc[common_idx, common_cols] - recomputed.loc[common_idx, common_cols]
    rows = []
    for symbol in common_cols:
        d = diff[symbol].dropna()
        rows.append(
            {
                "ID": symbol,
                "matched_points": d.size,
                "max_abs_diff": d.abs().max() if d.size else np.nan,
                "mean_abs_diff": d.abs().mean() if d.size else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("max_abs_diff", ascending=False)


def _svg_bar(path: Path, labels: list[str], values: list[float], title: str, y_label: str, color: str) -> None:
    width, height = 1100, 520
    left, right, top, bottom = 70, 25, 55, 115
    chart_w = width - left - right
    chart_h = height - top - bottom
    max_val = max(values) if values else 1
    bar_gap = 2
    bar_w = max(2, (chart_w - bar_gap * (len(values) - 1)) / max(1, len(values)))
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">{title}</text>',
        f'<text x="18" y="{top + chart_h/2}" transform="rotate(-90 18 {top + chart_h/2})" text-anchor="middle" font-family="Arial" font-size="13">{y_label}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+chart_h}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top+chart_h}" x2="{left+chart_w}" y2="{top+chart_h}" stroke="#333"/>',
    ]
    for i in range(6):
        val = max_val * i / 5
        y = top + chart_h - chart_h * i / 5
        lines.append(f'<line x1="{left-4}" y1="{y:.1f}" x2="{left+chart_w}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        lines.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{val:.0f}</text>')
    for idx, (label, value) in enumerate(zip(labels, values)):
        x = left + idx * (bar_w + bar_gap)
        h = 0 if max_val == 0 else chart_h * value / max_val
        y = top + chart_h - h
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}"/>')
        if len(labels) <= 30 or idx % 2 == 0:
            tx = x + bar_w / 2
            lines.append(f'<text x="{tx:.1f}" y="{top+chart_h+16}" text-anchor="end" transform="rotate(-90 {tx:.1f} {top+chart_h+16})" font-family="Arial" font-size="10">{label}</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _svg_heatmap(path: Path, matrix: pd.DataFrame, title: str) -> None:
    labels = list(matrix.columns)
    n = len(labels)
    cell = max(8, min(16, 760 // max(1, n)))
    left, top = 110, 70
    width = left + n * cell + 160
    height = top + n * cell + 130

    def color(v):
        if pd.isna(v):
            return "#f3f4f6"
        v = max(-1, min(1, float(v)))
        if v >= 0:
            intensity = int(255 - 140 * v)
            return f"rgb({intensity},{intensity + 20 if intensity < 235 else 255},255)"
        intensity = int(255 + 120 * v)
        return f"rgb(255,{intensity},{intensity})"

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">{title}</text>',
    ]
    for i, label in enumerate(labels):
        x = left + i * cell + cell / 2
        y = top - 8
        lines.append(f'<text x="{x:.1f}" y="{y}" text-anchor="start" transform="rotate(-90 {x:.1f} {y})" font-family="Arial" font-size="8">{label}</text>')
        lines.append(f'<text x="{left-8}" y="{top+i*cell+cell*0.75:.1f}" text-anchor="end" font-family="Arial" font-size="8">{label}</text>')
    for r, row in enumerate(labels):
        for c, col in enumerate(labels):
            x = left + c * cell
            y = top + r * cell
            lines.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{color(matrix.loc[row, col])}"/>')
    legend_x = left + n * cell + 35
    legend_y = top
    for i, val in enumerate(np.linspace(1, -1, 80)):
        lines.append(f'<rect x="{legend_x}" y="{legend_y+i*3}" width="18" height="3" fill="{color(val)}"/>')
    lines.append(f'<text x="{legend_x+25}" y="{legend_y+5}" font-family="Arial" font-size="11">1.0</text>')
    lines.append(f'<text x="{legend_x+25}" y="{legend_y+122}" font-family="Arial" font-size="11">0.0</text>')
    lines.append(f'<text x="{legend_x+25}" y="{legend_y+240}" font-family="Arial" font-size="11">-1.0</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def plot_missingness(miss: pd.DataFrame) -> None:
    top = miss.sort_values("observations", ascending=False)
    _svg_bar(
        OUT_DIR / "observations_by_asset.svg",
        top["ID"].tolist(),
        top["observations"].astype(float).tolist(),
        "Monthly return observations by asset",
        "Non-missing monthly returns",
        "#4C78A8",
    )


def plot_outliers(outliers: pd.DataFrame, asset_map: pd.DataFrame) -> None:
    if outliers.empty:
        return
    counts = outliers.groupby("ID").size().reset_index(name="outlier_count")
    counts = counts.merge(asset_map, on="ID", how="left").sort_values("outlier_count", ascending=False).head(25)
    _svg_bar(
        OUT_DIR / "top_outlier_counts.svg",
        counts["ID"].tolist(),
        counts["outlier_count"].astype(float).tolist(),
        "Top assets by outlier count",
        "Outlier months",
        "#F58518",
    )


def plot_corr(returns: pd.DataFrame) -> None:
    corr = returns.corr(min_periods=60)
    _svg_heatmap(OUT_DIR / "correlation_matrix.svg", corr, "Return correlation matrix")


def write_report(existing, recomputed, summary, miss, outliers, compare):
    asset_count = len(existing.columns)
    start = existing.index.min().date()
    end = existing.index.max().date()
    total_obs = int(existing.count().sum())
    outlier_count = len(outliers)
    top_outliers = (
        outliers.groupby("ID").size().sort_values(ascending=False).head(10)
        if not outliers.empty
        else pd.Series(dtype=int)
    )
    top_abs = (
        outliers.assign(abs_return=outliers["Return"].abs())
        .sort_values("abs_return", ascending=False)
        .head(15)
        if not outliers.empty
        else pd.DataFrame()
    )

    lines = [
        "# Futures Return EDA",
        "",
        "## Scope",
        f"- Existing monthly return matrix: {asset_count} assets, {len(existing)} month-end rows, {start} to {end}.",
        f"- Non-missing monthly return observations: {total_obs:,}.",
        "- Returns were also recomputed from each futures underlying daily close as month-end close-to-close percent changes.",
        "",
        "## Outlier method",
        "- Flagged a monthly return when it was outside 3x IQR bounds for that asset or had absolute robust z-score above 5.",
        f"- Total flagged asset-month outliers: {outlier_count:,}.",
        "",
        "## Data coverage",
        f"- Longest series: {miss.sort_values('observations', ascending=False).iloc[0]['ID']} with {int(miss['observations'].max())} returns.",
        f"- Shortest non-empty series: {miss.loc[miss['observations'] > 0].sort_values('observations').iloc[0]['ID']} with {int(miss.loc[miss['observations'] > 0, 'observations'].min())} returns.",
        "",
        "## Top assets by outlier count",
    ]
    if top_outliers.empty:
        lines.append("- No outliers flagged.")
    else:
        for symbol, count in top_outliers.items():
            name = summary.loc[summary["ID"] == symbol, "Name"].dropna()
            label = f"{symbol} ({name.iloc[0]})" if len(name) else symbol
            lines.append(f"- {label}: {int(count)}")

    lines += ["", "## Largest absolute flagged returns"]
    if top_abs.empty:
        lines.append("- No outliers flagged.")
    else:
        for _, row in top_abs.iterrows():
            lines.append(f"- {row['Date'].date()} {row['ID']}: {row['Return']:.2%} (robust z {row['RobustZ']:.1f})")

    lines += [
        "",
        "## Return recomputation check",
        f"- Compared {int(compare['matched_points'].sum()):,} overlapping asset-month points between supplied monthly returns and recomputed daily-close returns.",
        f"- Median max absolute difference by asset: {compare['max_abs_diff'].median():.6f}.",
        f"- Largest asset-level max absolute difference: {compare.iloc[0]['ID']} at {compare.iloc[0]['max_abs_diff']:.6f}.",
        "",
        "## Files written",
        "- computed_monthly_returns.csv",
        "- summary_statistics.csv",
        "- missingness.csv",
        "- outliers.csv",
        "- recomputation_check.csv",
        "- observations_by_asset.svg",
        "- top_outlier_counts.svg",
        "- correlation_matrix.svg",
    ]
    (OUT_DIR / "eda_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    asset_map = read_asset_map()
    existing = read_existing_monthly_returns()
    recomputed = compute_monthly_returns_from_daily()

    summary = summarize_returns(existing, asset_map)
    miss = missingness(existing, asset_map)
    outliers = robust_outliers(existing)
    compare = compare_existing_to_recomputed(existing, recomputed)

    existing.to_csv(OUT_DIR / "monthly_returns_clean.csv", float_format="%.10g")
    recomputed.to_csv(OUT_DIR / "computed_monthly_returns.csv", float_format="%.10g")
    summary.to_csv(OUT_DIR / "summary_statistics.csv", index=False, float_format="%.10g")
    miss.to_csv(OUT_DIR / "missingness.csv", index=False)
    outliers.to_csv(OUT_DIR / "outliers.csv", index=False, float_format="%.10g")
    compare.to_csv(OUT_DIR / "recomputation_check.csv", index=False, float_format="%.10g")

    plot_missingness(miss)
    plot_outliers(outliers, asset_map)
    plot_corr(existing)
    write_report(existing, recomputed, summary, miss, outliers, compare)

    print(f"Wrote EDA outputs to {OUT_DIR}")
    print(f"Monthly returns shape: {existing.shape}")
    print(f"Outliers flagged: {len(outliers)}")
    print("Top outlier counts:")
    if outliers.empty:
        print("none")
    else:
        print(outliers.groupby("ID").size().sort_values(ascending=False).head(10).to_string())


if __name__ == "__main__":
    main()
