# Futures Return EDA

## Scope
- Existing monthly return matrix: 58 assets, 552 month-end rows, 1969-01-31 to 2014-12-31.
- Non-missing monthly return observations: 20,987.
- Returns were also recomputed from each futures underlying daily close as month-end close-to-close percent changes.

## Outlier method
- Flagged a monthly return when it was outside 3x IQR bounds for that asset or had absolute robust z-score above 5.
- Total flagged asset-month outliers: 126.

## Data coverage
- Longest series: ZW with 551 returns.
- Shortest non-empty series: AP with 75 returns.

## Top assets by outlier count
- EC (EuroDollar): 21
- SS (UKSterlingShort): 7
- MW (Wheat): 7
- ZM (SoybeanMeal): 6
- ZP (Platinum): 6
- ZC (Corn): 5
- ZL (SoybeanOil): 5
- MP (MexicanPeso): 4
- KC (Coffee): 4
- ZI (Silver): 4

## Largest absolute flagged returns
- 1988-06-30 ZO: 93.91% (robust z 13.1)
- 1974-07-31 ZM: 75.20% (robust z 12.3)
- 1977-01-31 JO: 70.65% (robust z 10.3)
- 1973-05-31 ZM: 68.45% (robust z 11.2)
- 1983-05-31 SB: 67.41% (robust z 7.4)
- 1981-01-30 JO: 58.36% (robust z 8.5)
- 1974-07-31 ZS: 56.88% (robust z 10.5)
- 1973-05-31 ZS: 55.99% (robust z 10.3)
- 1979-09-28 ZI: 54.70% (robust z 8.1)
- 1974-07-31 ZL: 54.55% (robust z 7.8)
- 1994-06-30 KC: 53.17% (robust z 6.1)
- 1985-07-31 SB: 52.55% (robust z 5.8)
- 1975-07-31 KC: 52.13% (robust z 6.0)
- 1979-12-31 ZI: 50.75% (robust z 7.5)
- 1990-09-28 ZU: 48.47% (robust z 5.6)

## Return recomputation check
- Compared 14,974 overlapping asset-month points between supplied monthly returns and recomputed daily-close returns.
- Median max absolute difference by asset: 0.000000.
- Largest asset-level max absolute difference: RL at 0.046964.

## Files written
- computed_monthly_returns.csv
- summary_statistics.csv
- missingness.csv
- outliers.csv
- recomputation_check.csv
- observations_by_asset.svg
- top_outlier_counts.svg
- correlation_matrix.svg
