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
- earnings responsiveness (v3): correlation and regression beta of
  each channel's growth on operating-earnings growth, plus average
  growth in earnings-up years vs earnings-down years. Volatility (v1)
  says buybacks move more; responsiveness says what they move WITH --
  earnings -- and how much of the move dividends simply do not make.
  Only 9 growth years (7 up, 2 down), so this is a description of this
  decade, not a fitted forecasting model.
- cumulative / era lens (v4): yearly rows cumulated from 2015
  (cumulative payout vs cumulative earnings and the cumulative payout
  ratio) and grouped into eras (2015-2019 pre-pandemic, 2020-2022
  shock and rebound, 2023-2024 late, plus the full period). The annual
  cuts show a mix that swings year to year; cumulation and era
  aggregation test whether that swing survives averaging -- it mostly
  does not: the era buyback share stays within about a point of 59-60%
  even though the annual share ranges over 12 points.
- retention lens (v5): the complement of the payout ratio -- operating
  earnings minus total payout, per year and cumulated, plus the same
  pooling by era. A payout ratio above 100% means the index paid out
  more than it earned that year; retention makes that concrete in
  dollars and shows when the cumulative balance turned. Dividends
  alone never took more than 47.4% of earnings in any year, so every
  over-payout year is arithmetically a buyback story.
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


def _raw_growth(rows, key):
    """Unrounded year-over-year growth (%) for a row field, 2016 on."""
    return [(rows[i][key] / rows[i - 1][key] - 1) * 100
            for i in range(1, len(rows))]


def build_responsiveness(rows):
    """How strongly each payout channel's growth tracks earnings growth.

    Beta is the OLS slope of channel growth on operating-earnings
    growth (both unrounded): a beta near 1 means the channel moves
    roughly point-for-point with earnings, near 0 means it grows on
    its own schedule regardless. The up/down split is the same point
    without any regression: average channel growth in the years
    earnings rose vs the years they fell.
    """
    earn = _raw_growth(rows, "_op_earnings_$B")
    channels = [
        ("dividends", "dividends_$B"),
        ("buybacks", "buybacks_$B"),
        ("total_payout", "total_payout_$B"),
    ]
    out = []
    mean_e = statistics.mean(earn)
    var_e = sum((e - mean_e) ** 2 for e in earn)
    for name, key in channels:
        growth = _raw_growth(rows, key)
        mean_g = statistics.mean(growth)
        cov = sum((e - mean_e) * (g - mean_g) for e, g in zip(earn, growth))
        var_g = sum((g - mean_g) ** 2 for g in growth)
        if var_e == 0 or var_g == 0:
            corr, beta = None, None
        else:
            corr = round(cov / (var_e * var_g) ** 0.5, 2)
            beta = round(cov / var_e, 2)
        up = [g for e, g in zip(earn, growth) if e > 0]
        down = [g for e, g in zip(earn, growth) if e < 0]
        out.append({
            "channel": name,
            "correlation_with_earnings_growth": corr,
            "beta_to_earnings_growth": beta,
            "avg_growth_earnings_up_pct": (
                round(statistics.mean(up), 1) if up else None),
            "avg_growth_earnings_down_pct": (
                round(statistics.mean(down), 1) if down else None),
            "earnings_up_years": len(up),
            "earnings_down_years": len(down),
        })
    return out


def build_cumulative(rows):
    """Running totals from the first year: payout vs earnings.

    The cumulative payout ratio is the decade-to-date version of the
    annual payout ratio in results.csv: total payout cumulated from
    2015 divided by operating earnings cumulated over the same span.
    Cumulation smooths the annual bounce (77-108%) into the question
    of whether the decade as a whole paid out more than it earned.
    """
    out = []
    cum_div = cum_buy = cum_earn = 0.0
    for r in rows:
        cum_div += r["dividends_$B"]
        cum_buy += r["buybacks_$B"]
        cum_earn += r["_op_earnings_$B"]
        cum_total = cum_div + cum_buy
        out.append({
            "year": r["year"],
            "cumulative_dividends_$B": round(cum_div, 2),
            "cumulative_buybacks_$B": round(cum_buy, 2),
            "cumulative_total_payout_$B": round(cum_total, 2),
            "cumulative_operating_earnings_$B": round(cum_earn, 2),
            "cumulative_payout_ratio_pct": round(cum_total / cum_earn * 100, 1),
            "cumulative_buyback_share_pct": round(cum_buy / cum_total * 100, 1),
        })
    return out


# Era boundaries follow the shocks in the series, not round numbers:
# the pre-pandemic run, the 2020 earnings/payout shock plus the 2021-
# 2022 rebound, and the two late years after the rebound faded.
ERAS = [
    ("2015-2019_pre_pandemic", 2015, 2019),
    ("2020-2022_shock_and_rebound", 2020, 2022),
    ("2023-2024_late", 2023, 2024),
    ("2015-2024_full_period", 2015, 2024),
]


def build_eras(rows, eras=ERAS):
    """Era totals: payout mix and payout ratio with the years pooled.

    Pooling is the point: an era's buyback share is total era buybacks
    over total era payout (a dollar-weighted mix), not the average of
    the annual shares, so big-payout years count for more -- the same
    way the decade total in v1 is computed.
    """
    out = []
    for name, start, end in eras:
        sel = [r for r in rows if start <= r["year"] <= end]
        div = sum(r["dividends_$B"] for r in sel)
        buy = sum(r["buybacks_$B"] for r in sel)
        earn = sum(r["_op_earnings_$B"] for r in sel)
        total = div + buy
        out.append({
            "era": name,
            "years": len(sel),
            "dividends_$B": round(div, 2),
            "buybacks_$B": round(buy, 2),
            "total_payout_$B": round(total, 2),
            "operating_earnings_$B": round(earn, 2),
            "buyback_share_pct": round(buy / total * 100, 1),
            "payout_ratio_op_earnings_pct": round(total / earn * 100, 1),
            "avg_annual_payout_$B": round(total / len(sel), 2),
        })
    return out


def build_retention(rows):
    """Retained operating earnings: what was left after total payout.

    retained = operating earnings - total payout, so the retention
    ratio is exactly 100 minus the payout ratio in results.csv. A
    negative year is an over-payout year: the index returned more
    than it earned, funded from prior retention or the balance sheet.
    The cumulative column is the running retained balance from 2015.
    """
    out = []
    cum = 0.0
    for r in rows:
        earn = r["_op_earnings_$B"]
        retained = earn - r["total_payout_$B"]
        cum += retained
        out.append({
            "year": r["year"],
            "operating_earnings_$B": round(earn, 2),
            "total_payout_$B": r["total_payout_$B"],
            "retained_$B": round(retained, 2),
            "retention_ratio_pct": round(retained / earn * 100, 1),
            "cumulative_retained_$B": round(cum, 2),
            "over_payout": "yes" if retained < 0 else "no",
        })
    return out


def build_retention_eras(rows, eras=ERAS):
    """Era-pooled retention: era earnings minus era payout.

    Pooling is dollar-weighted, as in build_eras: an era's retention
    ratio is its pooled retained dollars over its pooled earnings,
    not the average of the annual ratios.
    """
    by_year = {r["year"]: r for r in build_retention(rows)}
    out = []
    for name, start, end in eras:
        sel = [by_year[y] for y in sorted(by_year) if start <= y <= end]
        earn = sum(s["operating_earnings_$B"] for s in sel)
        retained = sum(s["retained_$B"] for s in sel)
        out.append({
            "era": name,
            "years": len(sel),
            "operating_earnings_$B": round(earn, 2),
            "retained_$B": round(retained, 2),
            "retention_ratio_pct": round(retained / earn * 100, 1),
            "over_payout_years": sum(
                1 for s in sel if s["over_payout"] == "yes"),
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
    response = build_responsiveness(rows)
    cumulative = build_cumulative(rows)
    eras = build_eras(rows)
    retention = build_retention(rows)
    retention_eras = build_retention_eras(rows)

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
    _write_csv(os.path.join(HERE, "responsiveness.csv"), response)
    _write_csv(os.path.join(HERE, "cumulative.csv"), cumulative)
    _write_csv(os.path.join(HERE, "eras.csv"), eras)
    _write_csv(os.path.join(HERE, "retention.csv"), retention)
    _write_csv(os.path.join(HERE, "retention_eras.csv"), retention_eras)

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

    # Chart 3: each channel's growth against earnings growth (the v3
    # responsiveness cut). Buybacks scatter along the earnings axis;
    # dividends sit in a flat band whatever earnings do.
    fig, ax = plt.subplots(figsize=(10, 6))
    earn_g = [g["operating_earnings_growth_pct"] for g in growth]
    ax.scatter(earn_g, [g["buyback_growth_pct"] for g in growth],
               color="#ff7f0e", s=70, label="Buybacks")
    ax.scatter(earn_g, [g["dividend_growth_pct"] for g in growth],
               color="#1f77b4", s=70, label="Dividends")
    for g in growth:
        ax.annotate(str(g["year"]), (g["operating_earnings_growth_pct"],
                                     g["buyback_growth_pct"]),
                    textcoords="offset points", xytext=(4, 4), fontsize=7)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Operating earnings growth, %")
    ax.set_ylabel("Payout channel growth, %")
    ax.set_title("Payout growth vs earnings growth, 2016-2024")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "responsiveness.png"), dpi=150)
    plt.close(fig)

    # Chart 4: cumulative payout vs cumulative earnings, and the
    # cumulative payout ratio settling as the decade cumulates (v4).
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    ax1.plot(years, [c["cumulative_total_payout_$B"] for c in cumulative],
             marker="o", color="#333333", label="Cumulative total payout")
    ax1.plot(years,
             [c["cumulative_operating_earnings_$B"] for c in cumulative],
             marker="s", color="#2ca02c",
             label="Cumulative operating earnings")
    ax1.set_ylabel("$ billions")
    ax1.set_title("Cumulative payout vs cumulative earnings, 2015-2024")
    ax1.legend()
    ax2.plot(years, [c["cumulative_payout_ratio_pct"] for c in cumulative],
             marker="o", color="#333333")
    ax2.axhline(100, color="gray", linestyle="--", linewidth=0.8)
    ax2.set_ylabel("Cumulative payout ratio, %")
    ax2.set_xlabel("Calendar year")
    ax2.set_xticks(years)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "cumulative.png"), dpi=150)
    plt.close(fig)

    # Chart 5: annual retained earnings (red when the year paid out
    # more than it earned) and the cumulative retained balance (v5).
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    retained = [r["retained_$B"] for r in retention]
    ax1.bar(years, retained,
            color=["#d62728" if v < 0 else "#2ca02c" for v in retained])
    ax1.axhline(0, color="black", linewidth=0.8)
    ax1.set_ylabel("Retained, $ billions")
    ax1.set_title("Operating earnings retained after payout, 2015-2024")
    ax2.plot(years, [r["cumulative_retained_$B"] for r in retention],
             marker="o", color="#333333")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_ylabel("Cumulative retained, $B")
    ax2.set_xlabel("Calendar year")
    ax2.set_xticks(years)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "retention.png"), dpi=150)
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
    resp = {r["channel"]: r for r in response}
    print(f"  Earnings responsiveness: buyback growth beta "
          f"{resp['buybacks']['beta_to_earnings_growth']:.2f} / correlation "
          f"{resp['buybacks']['correlation_with_earnings_growth']:.2f} vs "
          f"dividends beta {resp['dividends']['beta_to_earnings_growth']:.2f} "
          f"/ correlation "
          f"{resp['dividends']['correlation_with_earnings_growth']:.2f}; "
          f"in the {resp['buybacks']['earnings_down_years']} earnings-down "
          f"years buybacks averaged "
          f"{resp['buybacks']['avg_growth_earnings_down_pct']:+.1f}% while "
          f"dividends averaged "
          f"{resp['dividends']['avg_growth_earnings_down_pct']:+.1f}%")
    era_by_name = {e["era"]: e for e in eras}
    era_shares = [era_by_name[n]["buyback_share_pct"] for n, _, _ in ERAS[:3]]
    print(f"  Cumulative / eras: decade payout "
          f"${cumulative[-1]['cumulative_total_payout_$B']:,.2f}B vs "
          f"cumulative earnings "
          f"${cumulative[-1]['cumulative_operating_earnings_$B']:,.2f}B "
          f"(cumulative payout ratio "
          f"{cumulative[-1]['cumulative_payout_ratio_pct']:.1f}%, down "
          f"from {cumulative[0]['cumulative_payout_ratio_pct']:.1f}% in "
          f"2015 alone); era buyback shares "
          f"{era_shares[0]:.1f}% / {era_shares[1]:.1f}% / "
          f"{era_shares[2]:.1f}% (pre-pandemic / shock+rebound / late) "
          f"vs an annual range of "
          f"{min(r['buyback_share_pct'] for r in rows):.1f}-"
          f"{max(r['buyback_share_pct'] for r in rows):.1f}%; era payout "
          f"ratios {era_by_name[ERAS[0][0]]['payout_ratio_op_earnings_pct']:.1f}% "
          f"-> {era_by_name[ERAS[1][0]]['payout_ratio_op_earnings_pct']:.1f}% "
          f"-> {era_by_name[ERAS[2][0]]['payout_ratio_op_earnings_pct']:.1f}%")
    over = [r for r in retention if r["over_payout"] == "yes"]
    trough = min(retention, key=lambda r: r["cumulative_retained_$B"])
    first_pos = next(r for r in retention
                     if r["cumulative_retained_$B"] > 0)
    ret_era = {e["era"]: e for e in retention_eras}
    print(f"  Retention: decade retained "
          f"${retention[-1]['cumulative_retained_$B']:,.2f}B "
          f"({ret_era[ERAS[-1][0]]['retention_ratio_pct']:.1f}% of "
          f"earnings); over-payout years "
          f"{[r['year'] for r in over]} totaling "
          f"${sum(r['retained_$B'] for r in over):,.2f}B, cumulative "
          f"retained trough ${trough['cumulative_retained_$B']:,.2f}B "
          f"at end-{trough['year']}, first positive at end-"
          f"{first_pos['year']} "
          f"(${first_pos['cumulative_retained_$B']:,.2f}B); era "
          f"retention ratios "
          f"{ret_era[ERAS[0][0]]['retention_ratio_pct']:.1f}% -> "
          f"{ret_era[ERAS[1][0]]['retention_ratio_pct']:.1f}% -> "
          f"{ret_era[ERAS[2][0]]['retention_ratio_pct']:.1f}%; dividends "
          f"alone never took more than "
          f"{max(r['dividends_vs_op_pct'] for r in rows):.1f}% of "
          f"earnings in any year")
    print("\n  FRED context check:")
    check = fred_sp500_check()
    if check:
        print(f"  {check[0]}: {check[3]} daily observations, "
              f"{check[1]} to {check[2]} (sanity context only)")
    print("\nWrote results.csv, growth.csv, counterfactual.csv, "
          "responsiveness.csv, cumulative.csv, eras.csv, retention.csv, "
          "retention_eras.csv, results.png, counterfactual.png, "
          "responsiveness.png, cumulative.png and retention.png")


if __name__ == "__main__":
    main()
