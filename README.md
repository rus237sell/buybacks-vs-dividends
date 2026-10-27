# Buybacks vs dividends

**Goal:** Compare how the S&P 500 split shareholder payouts between dividends and buybacks over ten years (2015-2024), and which channel actually moves when earnings or policy change.

**Macro steps:**
1. Transcribed annual dividends, buybacks, and operating earnings from S&P Dow Jones Indices buyback reports (calendar years 2015-2024, $B; see SOURCES.md).
2. Computed total payout, buyback share of payout, payout ratio vs operating earnings, and buyback-to-dividend ratio for each year (`results.csv`).
3. Compared growth behavior: 9-year CAGR and year-over-year growth volatility for each channel, plus the 2018 and 2020 episodes (`growth.csv`).
4. Built a dividend-smooth counterfactual (v2): buybacks re-grown each year at that year's dividend growth rate from the 2015 level, to separate timing from total (`counterfactual.csv`, `counterfactual.png`).
5. Charted the stacked payout mix and the buyback share over time (`results.png`). A live FRED pull (series SP500) is run only as a connectivity sanity check; payout figures come from the S&P DJI reports, not FRED.

**Versions:** v1, initial analysis. v2, dividend-smooth counterfactual + growth table (actual vs smooth buybacks, annual and cumulative excess) and the first test suite (12 tests); calculations refactored into build_rows / build_growth / build_counterfactual, with `results.csv` unchanged.

**Short results:** Buybacks were the majority channel in all 10 years, totaling $7,225B of $12,143B paid out (59.5%); the buyback share was 59.9% in 2015 and 60.0% in 2024, dipping to 51.8% in 2020 and peaking at 63.9% in 2018. Both channels grew at the same 5.7%/yr CAGR, but they behaved very differently year to year: buyback growth volatility was 32.8 points vs 3.1 for dividends. In 2018 buybacks jumped 55.3% after the TCJA while dividends rose 8.7%; in 2020 buybacks were cut 28.7% while dividends slipped only 0.5%. Total payout hit a record $1,572B in 2024, yet the payout ratio vs operating earnings fell from 107.8% in 2015 to 79.9% in 2024 because earnings grew faster than payouts. The v2 counterfactual shows that volatility was timing, not total: a dividend-smooth path lands at $942.3B in 2024 vs $942.6B actual and pays $7,360B over the decade vs $7,225B actual (just $135B more), even though actual buybacks ran as much as $244B behind the smooth path cumulatively by end-2020 (single-year gap -$203B in 2020, +$124B in 2018).

Run: `python3 buybacks_vs_dividends.py`
