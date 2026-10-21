"""How has the S&P 500's shareholder-payout mix changed over ten years?

Companies return cash to shareholders two main ways: dividends (steady,
sticky, cut only under duress) and buybacks (flexible, ramped up when
cash and confidence are high, slashed fast in a downturn). This script
compares the two using S&P Dow Jones Indices' own annual S&P 500
buyback-report data for 2015-2024: cash dividends, share repurchases,
and operating earnings, all in $ billions.

Coverage: calendar years 2015-2024 (calendar, not fiscal; matches the
S&P DJI report). All figures are final/vintage-published values, not
estimates. Nothing here is a forecast and nothing is presented as
financial advice.

Findings hinge on three derived measures:
- buyback share of total payout: buybacks / (buybacks + dividends)
- payout ratio: (buybacks + dividends) / operating earnings
- growth volatility: sample stdev of year-over-year growth, buybacks vs
  dividends -- a simple read on which channel managers flex first.
"""

import csv
import os
import statistics
import urllib.request

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# S&P Dow Jones Indices S&P 500 buyback reports ($ billions, calendar year).
# Sources and original press-release dates in SOURCES.md.
# ---------------------------------------------------------------------------
PAYOUT = [
    # year, dividends, buybacks, operating earnings
    (2015, 382.32, 572.16, 885.38),
    (2016, 397.21, 536.38, 919.85),
    (2017, 419.77, 519.40, 1066.00),
    (2018, 456.31, 806.41, 1281.66),
    (2019, 485.48, 728.74, 1304.76),
    (2020, 483.18, 519.76, 1019.04),
    (2021, 511.23, 881.72, 1762.75),
    (2022, 564.57, 922.68, 1656.66),
    (2023, 588.23, 795.16, 1787.36),
    (2024, 629.62, 942.55, 1966.53),
]


def fred_sp500_check():
    """Lightweight sanity check that FRED is reachable and returns S&P 500
    data (daily close, series SP500). This is context only -- the payout
    numbers above come from the S&P DJI reports, not FRED. Returns the
    latest observation string or None if unreachable."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500&cosd=2015-01-01&coed=2024-12-31"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            rows = resp.read().decode(errors="replace").strip().splitlines()
        dates = [r.split(",")[0] for r in rows[1:] if r]
        return rows[0], dates[0], dates[-1], len(dates)
    except Exception as exc:  # FRED unreachable -- analysis stands on its own
        print(f"  FRED check skipped (unreachable): {exc}")
        return None


def main():
    print("S&P DJI report values (calendar years, $B):")
    rows = []
    for year, div, buy, op in PAYOUT:
        total = div + buy
        rows.append({
            "year": year,
            "dividends_$B": round(div, 2),
            "buybacks_$B": round(buy, 2),
            "total_payout_$B": round(total, 2),
            "buyback_share_pct": round(buy / total * 100, 1),
            "dividend_share_pct": round(div / total * 100, 1),
            "payout_ratio_op_earnings_pct": round(total / op * 100, 1),
            "buybacks_vs_op_pct": round(buy / op * 100, 1),
            "dividends_vs_op_pct": round(div / op * 100, 1),
            "buyback_to_dividend_ratio": round(buy / div, 2),
        })

    # Year-over-year growth and volatility.
    div_g = [(rows[i]["dividends_$B"] / rows[i - 1]["dividends_$B"] - 1) * 100
             for i in range(1, len(rows))]
    buy_g = [(rows[i]["buybacks_$B"] / rows[i - 1]["buybacks_$B"] - 1) * 100
             for i in range(1, len(rows))]
    div_vol = statistics.stdev(div_g)
    buy_vol = statistics.stdev(buy_g)
    n = len(rows)
    div_cagr = (rows[-1]["dividends_$B"] / rows[0]["dividends_$B"]) ** (1 / (n - 1)) - 1
    buy_cagr = (rows[-1]["buybacks_$B"] / rows[0]["buybacks_$B"]) ** (1 / (n - 1)) - 1
    total_buy = sum(r["buybacks_$B"] for r in rows)
    total_div = sum(r["dividends_$B"] for r in rows)
    total_all = total_buy + total_div

    with open(os.path.join(HERE, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Chart: stacked payout mix over time.
    years = [r["year"] for r in rows]
    divs = [r["dividends_$B"] for r in rows]
    buys = [r["buybacks_$B"] for r in rows]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    ax1.bar(years, divs, label="Dividends", color="#1f77b4")
    ax1.bar(years, buys, bottom=divs, label="Buybacks", color="#ff7f0e")
    ax1.set_ylabel("$ billions")
    ax1.set_title("S&P 500 shareholder payouts, 2015-2024 (S&P DJI)")
    ax1.legend()
    for y, t in zip(years, [r["total_payout_$B"] for r in rows]):
        ax1.text(y, t + 18, f"${t:,.0f}B", ha="center", fontsize=7)

    buy_share = [r["buyback_share_pct"] for r in rows]
    ax2.plot(years, buy_share, marker="o", color="#ff7f0e")
    ax2.axhline(60, color="gray", linestyle="--", linewidth=0.8)
    ax2.set_ylabel("Buybacks as % of total payout")
    ax2.set_xlabel("Calendar year")
    ax2.set_xticks(years)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "results.png"), dpi=150)
    plt.close(fig)

    print("\nHeadline numbers:")
    print(f"  Total payout 2024: ${rows[-1]['total_payout_$B']:,.1f}B "
          f"(record; dividends ${rows[-1]['dividends_$B']:,.1f}B, "
          f"buybacks ${rows[-1]['buybacks_$B']:,.1f}B)")
    print(f"  Buyback share: {rows[0]['buyback_share_pct']}% in 2015 -> "
          f"{rows[-1]['buyback_share_pct']}% in 2024 "
          f"(10-yr total: ${total_buy:,.0f}B of ${total_all:,.0f}B = "
          f"{total_buy / total_all * 100:.1f}%)")
    print(f"  10-yr CAGR: dividends {div_cagr * 100:.1f}%, "
          f"buybacks {buy_cagr * 100:.1f}%")
    print(f"  Growth volatility (YoY stdev): buybacks {buy_vol:.1f} pts vs "
          f"dividends {div_vol:.1f} pts")
    # div_g / buy_g index i is growth in year PAYOUT[i+1].
    print(f"  2018 spike: buybacks {buy_g[2]:+.1f}% after the TCJA vs "
          f"dividends {div_g[2]:+.1f}%")
    print(f"  2020 cut: buybacks {buy_g[4]:+.1f}% vs dividends {div_g[4]:+.1f}%")
    peak = max(rows, key=lambda r: r["payout_ratio_op_earnings_pct"])
    print(f"  Payout ratio vs operating earnings: "
          f"{rows[0]['payout_ratio_op_earnings_pct']}% (2015) -> "
          f"{rows[-1]['payout_ratio_op_earnings_pct']}% (2024), "
          f"highest at {peak['payout_ratio_op_earnings_pct']:.1f}% "
          f"in {peak['year']}; 2020 stayed at 98.4% only because "
          f"earnings fell as fast as payouts")
    print("\n  FRED context check:")
    check = fred_sp500_check()
    if check:
        print(f"  {check[0]}: {check[3]} daily observations, "
              f"{check[1]} to {check[2]} (sanity context only)")
    print("\nWrote results.csv and results.png")


if __name__ == "__main__":
    main()
