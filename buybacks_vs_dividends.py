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

Findings hinge on four derived measures:
- buyback share of total payout: buybacks / (buybacks + dividends)
- payout ratio: (buybacks + dividends) / operating earnings
- growth volatility: sample stdev of year-over-year growth, buybacks vs
  dividends -- a simple read on which channel managers flex first.
- dividend-smooth counterfactual (v2): buybacks re-grown each year at
  that year's dividend growth rate, anchored to actual 2015 buybacks.
  Because both channels share the same 9-year CAGR, the counterfactual
  isolates timing: how far actual buybacks ran ahead of or behind a
  smooth path, and whether the decade total actually changed.
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


def build_rows(payout=PAYOUT):
    """One derived row per year (the original results.csv schema)."""
    rows = []
    for year, div, buy, op in payout:
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
            "_op_earnings_$B": round(op, 2),
        })
    return rows


def public_rows(rows):
    """Rows without the private earnings helper column (results.csv)."""
    return [{k: v for k, v in r.items() if not k.startswith("_")}
            for r in rows]


def build_growth(rows):
    """Year-over-year growth per channel plus operating earnings.

    The first year has no predecessor, so growth starts in 2016.
    ``buyback_minus_dividend_gap_pts`` is the flex gap in a year:
    positive when buybacks outgrew dividends, negative when they were
    cut (or grew less) -- the signature of the flexible channel.
    """
    out = []
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        div_g = (cur["dividends_$B"] / prev["dividends_$B"] - 1) * 100
        buy_g = (cur["buybacks_$B"] / prev["buybacks_$B"] - 1) * 100
        earn_g = (cur["_op_earnings_$B"] / prev["_op_earnings_$B"] - 1) * 100
        out.append({
            "year": cur["year"],
            "dividend_growth_pct": round(div_g, 1),
            "buyback_growth_pct": round(buy_g, 1),
            "buyback_minus_dividend_gap_pts": round(buy_g - div_g, 1),
            "operating_earnings_growth_pct": round(earn_g, 1),
            "total_payout_growth_pct": round(
                (cur["total_payout_$B"] / prev["total_payout_$B"] - 1) * 100, 1),
        })
    return out


def build_counterfactual(rows):
    """Dividend-smooth counterfactual buybacks.

    Anchor: 2015 counterfactual = actual 2015 buybacks. Each later year
    the counterfactual grows at that year's dividend growth rate, so it
    is exactly the path buybacks would have taken with dividend-like
    smoothness and (by construction, up to rounding) the same endpoint
    growth. Annual and cumulative excess measure timing only.
    """
    out = []
    cf = rows[0]["buybacks_$B"]
    cum = 0.0
    for i, r in enumerate(rows):
        if i > 0:
            div_g = r["dividends_$B"] / rows[i - 1]["dividends_$B"]
            cf = cf * div_g
        excess = r["buybacks_$B"] - cf
        cum += excess
        out.append({
            "year": r["year"],
            "actual_buybacks_$B": r["buybacks_$B"],
            "counterfactual_buybacks_$B": round(cf, 2),
            "annual_excess_$B": round(excess, 2),
            "cumulative_excess_$B": round(cum, 2),
        })
    return out


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


def _write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    print("S&P DJI report values (calendar years, $B):")
    rows = build_rows()
    growth = build_growth(rows)
    counter = build_counterfactual(rows)

    div_g = [g["dividend_growth_pct"] for g in growth]
    buy_g = [g["buyback_growth_pct"] for g in growth]
    # Volatility/CAGR on unrounded growth, as in v1.
    div_g_raw = [(rows[i]["dividends_$B"] / rows[i - 1]["dividends_$B"] - 1) * 100
                 for i in range(1, len(rows))]
    buy_g_raw = [(rows[i]["buybacks_$B"] / rows[i - 1]["buybacks_$B"] - 1) * 100
                 for i in range(1, len(rows))]
    div_vol = statistics.stdev(div_g_raw)
    buy_vol = statistics.stdev(buy_g_raw)
    n = len(rows)
    div_cagr = (rows[-1]["dividends_$B"] / rows[0]["dividends_$B"]) ** (1 / (n - 1)) - 1
    buy_cagr = (rows[-1]["buybacks_$B"] / rows[0]["buybacks_$B"]) ** (1 / (n - 1)) - 1
    total_buy = sum(r["buybacks_$B"] for r in rows)
    total_div = sum(r["dividends_$B"] for r in rows)
    total_all = total_buy + total_div
    total_cf = sum(c["counterfactual_buybacks_$B"] for c in counter)

    _write_csv(os.path.join(HERE, "results.csv"), public_rows(rows))
    _write_csv(os.path.join(HERE, "growth.csv"), growth)
    _write_csv(os.path.join(HERE, "counterfactual.csv"), counter)

    # Chart 1: stacked payout mix over time (unchanged from v1).
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

    # Chart 2: actual vs dividend-smooth counterfactual buybacks, and
    # the cumulative timing gap underneath.
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    ax1.plot(years, buys, marker="o", color="#ff7f0e", label="Actual buybacks")
    ax1.plot(years, [c["counterfactual_buybacks_$B"] for c in counter],
             marker="s", color="#1f77b4", label="Dividend-smooth counterfactual")
    ax1.set_ylabel("$ billions")
    ax1.set_title("Buybacks vs a dividend-smooth path, 2015-2024")
    ax1.legend()
    cum = [c["cumulative_excess_$B"] for c in counter]
    ax2.bar(years, cum, color="#7f7f7f")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_ylabel("Cumulative excess, $B")
    ax2.set_xlabel("Calendar year")
    ax2.set_xticks(years)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "counterfactual.png"), dpi=150)
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
    print(f"  2018 spike: buybacks {buy_g_raw[2]:+.1f}% after the TCJA vs "
          f"dividends {div_g_raw[2]:+.1f}%")
    print(f"  2020 cut: buybacks {buy_g_raw[4]:+.1f}% vs dividends {div_g_raw[4]:+.1f}%")
    peak = max(rows, key=lambda r: r["payout_ratio_op_earnings_pct"])
    print(f"  Payout ratio vs operating earnings: "
          f"{rows[0]['payout_ratio_op_earnings_pct']}% (2015) -> "
          f"{rows[-1]['payout_ratio_op_earnings_pct']}% (2024), "
          f"highest at {peak['payout_ratio_op_earnings_pct']:.1f}% "
          f"in {peak['year']}; 2020 stayed at 98.4% only because "
          f"earnings fell as fast as payouts")
    worst = min(counter, key=lambda c: c["cumulative_excess_$B"])
    print(f"  Counterfactual: 2024 smooth-path buybacks "
          f"${counter[-1]['counterfactual_buybacks_$B']:,.2f}B vs actual "
          f"${counter[-1]['actual_buybacks_$B']:,.2f}B; decade total "
          f"${total_cf:,.0f}B smooth vs ${total_buy:,.0f}B actual "
          f"({total_buy - total_cf:+,.0f}B); deepest cumulative timing "
          f"gap ${worst['cumulative_excess_$B']:,.2f}B at end-{worst['year']}")
    print("\n  FRED context check:")
    check = fred_sp500_check()
    if check:
        print(f"  {check[0]}: {check[3]} daily observations, "
              f"{check[1]} to {check[2]} (sanity context only)")
    print("\nWrote results.csv, growth.csv, counterfactual.csv, "
          "results.png and counterfactual.png")


if __name__ == "__main__":
    main()
