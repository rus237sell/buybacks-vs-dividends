"""Tests for buybacks_vs_dividends: sourced totals, growth, counterfactual."""
import statistics
import unittest

from buybacks_vs_dividends import (
    ERAS, PAYOUT, build_counterfactual, build_cumulative, build_eras,
    build_growth, build_responsiveness, build_rows, public_rows,
)


class TestRows(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()

    def test_ten_years(self):
        self.assertEqual([r["year"] for r in self.rows],
                         list(range(2015, 2025)))

    def test_shares_sum_to_100(self):
        for r in self.rows:
            self.assertAlmostEqual(
                r["buyback_share_pct"] + r["dividend_share_pct"], 100.0,
                places=0)

    def test_decade_totals_match_readme(self):
        total_buy = sum(r["buybacks_$B"] for r in self.rows)
        total_div = sum(r["dividends_$B"] for r in self.rows)
        self.assertAlmostEqual(total_buy, 7224.96, places=1)
        self.assertAlmostEqual(total_buy / (total_buy + total_div) * 100,
                               59.5, places=1)

    def test_public_rows_hide_helper(self):
        for r in public_rows(self.rows):
            self.assertNotIn("_op_earnings_$B", r)


class TestGrowth(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.growth = build_growth(self.rows)
        self.by_year = {g["year"]: g for g in self.growth}

    def test_nine_growth_years(self):
        self.assertEqual(len(self.growth), 9)
        self.assertEqual(self.growth[0]["year"], 2016)

    def test_2018_and_2020_episodes(self):
        self.assertAlmostEqual(self.by_year[2018]["buyback_growth_pct"],
                               55.3, places=0)
        self.assertAlmostEqual(self.by_year[2020]["buyback_growth_pct"],
                               -28.7, places=0)
        self.assertAlmostEqual(self.by_year[2020]["dividend_growth_pct"],
                               -0.5, places=0)

    def test_volatility_gap(self):
        div = [(self.rows[i]["dividends_$B"] / self.rows[i - 1]["dividends_$B"] - 1) * 100
               for i in range(1, len(self.rows))]
        buy = [(self.rows[i]["buybacks_$B"] / self.rows[i - 1]["buybacks_$B"] - 1) * 100
               for i in range(1, len(self.rows))]
        self.assertAlmostEqual(statistics.stdev(buy), 32.8, places=0)
        self.assertAlmostEqual(statistics.stdev(div), 3.1, places=0)


class TestCounterfactual(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.cf = build_counterfactual(self.rows)
        self.by_year = {c["year"]: c for c in self.cf}

    def test_anchor_year_has_zero_excess(self):
        self.assertEqual(self.cf[0]["annual_excess_$B"], 0.0)
        self.assertEqual(self.cf[0]["counterfactual_buybacks_$B"], 572.16)

    def test_2016_hand_math(self):
        # 572.16 grown at 2016 dividend growth (397.21 / 382.32).
        expected = 572.16 * 397.21 / 382.32
        self.assertAlmostEqual(
            self.by_year[2016]["counterfactual_buybacks_$B"], expected,
            places=1)

    def test_endpoint_converges(self):
        # Same CAGR for both channels, so the smooth path lands on the
        # actual 2024 level within a dollar.
        self.assertAlmostEqual(
            self.by_year[2024]["counterfactual_buybacks_$B"], 942.26,
            places=1)
        self.assertLess(abs(self.by_year[2024]["annual_excess_$B"]), 1.0)

    def test_cumulative_is_running_sum(self):
        run = 0.0
        for c in self.cf:
            run += c["annual_excess_$B"]
            self.assertAlmostEqual(c["cumulative_excess_$B"], run, places=1)

    def test_decade_timing_not_total(self):
        total_cf = sum(c["counterfactual_buybacks_$B"] for c in self.cf)
        total_actual = sum(r["buybacks_$B"] for r in self.rows)
        # Smooth path pays slightly MORE over the decade, not less.
        self.assertAlmostEqual(total_actual - total_cf, -134.9, places=0)
        worst = min(self.cf, key=lambda c: c["cumulative_excess_$B"])
        self.assertEqual(worst["year"], 2020)
        self.assertAlmostEqual(worst["cumulative_excess_$B"], -244.5,
                               places=0)


class TestResponsiveness(unittest.TestCase):
    def setUp(self):
        self.resp = build_responsiveness(build_rows())
        self.by_channel = {r["channel"]: r for r in self.resp}

    def test_three_channels_in_order(self):
        self.assertEqual([r["channel"] for r in self.resp],
                         ["dividends", "buybacks", "total_payout"])

    def test_up_down_year_counts(self):
        # Earnings rose in 7 growth years and fell in 2 (2020, 2022).
        for r in self.resp:
            self.assertEqual(r["earnings_up_years"], 7)
            self.assertEqual(r["earnings_down_years"], 2)

    def test_buybacks_track_earnings_dividends_do_not(self):
        buy = self.by_channel["buybacks"]
        div = self.by_channel["dividends"]
        self.assertAlmostEqual(
            buy["correlation_with_earnings_growth"], 0.84, places=1)
        self.assertAlmostEqual(buy["beta_to_earnings_growth"], 1.06,
                               places=1)
        self.assertAlmostEqual(
            div["correlation_with_earnings_growth"], 0.26, places=1)
        self.assertAlmostEqual(div["beta_to_earnings_growth"], 0.03,
                               places=1)
        self.assertGreater(buy["beta_to_earnings_growth"],
                           10 * div["beta_to_earnings_growth"])

    def test_total_payout_sits_between_channels(self):
        total = self.by_channel["total_payout"]
        self.assertAlmostEqual(total["beta_to_earnings_growth"], 0.59,
                               places=1)
        self.assertGreater(total["beta_to_earnings_growth"],
                           self.by_channel["dividends"]
                           ["beta_to_earnings_growth"])
        self.assertLess(total["beta_to_earnings_growth"],
                        self.by_channel["buybacks"]
                        ["beta_to_earnings_growth"])

    def test_up_down_split(self):
        buy = self.by_channel["buybacks"]
        div = self.by_channel["dividends"]
        # Buybacks were cut on average when earnings fell; dividends
        # still grew (2020 -0.5% and 2022 +10.4% average to +5.0%).
        self.assertAlmostEqual(buy["avg_growth_earnings_up_pct"], 15.8,
                               places=0)
        self.assertAlmostEqual(buy["avg_growth_earnings_down_pct"], -12.0,
                               places=0)
        self.assertAlmostEqual(div["avg_growth_earnings_down_pct"], 5.0,
                               places=0)

    def test_synthetic_proportional_channel(self):
        # Buyback growth is exactly 2x earnings growth each year
        # (+20/-20/+20 vs +10/-10/+10), dividends exactly 1x: beta and
        # correlation must come back 2.0/1.0 and 1.0/1.0.
        rows = build_rows([
            (2000, 100.0, 100.0, 100.0),
            (2001, 110.0, 120.0, 110.0),
            (2002, 99.0, 96.0, 99.0),
            (2003, 108.9, 115.2, 108.9),
        ])
        by_channel = {r["channel"]: r for r in build_responsiveness(rows)}
        self.assertAlmostEqual(
            by_channel["buybacks"]["beta_to_earnings_growth"], 2.0,
            places=2)
        self.assertAlmostEqual(
            by_channel["buybacks"]["correlation_with_earnings_growth"],
            1.0, places=2)
        self.assertAlmostEqual(
            by_channel["dividends"]["beta_to_earnings_growth"], 1.0,
            places=2)

    def test_constant_channel_has_no_beta(self):
        # A channel that never grows has zero variance: beta/corr are
        # None, never a crash or a fake 0.
        rows = build_rows([
            (2000, 100.0, 100.0, 100.0),
            (2001, 100.0, 120.0, 110.0),
            (2002, 100.0, 96.0, 99.0),
        ])
        by_channel = {r["channel"]: r for r in build_responsiveness(rows)}
        self.assertIsNone(
            by_channel["dividends"]["beta_to_earnings_growth"])
        self.assertIsNone(
            by_channel["dividends"]["correlation_with_earnings_growth"])


class TestCumulativeEras(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.cum = build_cumulative(self.rows)
        self.eras = build_eras(self.rows)
        self.by_era = {e["era"]: e for e in self.eras}

    def test_cumulative_first_year_equals_annual(self):
        # Cumulation starts at the 2015 annual row itself, so the first
        # cumulative payout ratio is the 2015 annual ratio (107.8%).
        first = self.cum[0]
        self.assertEqual(first["cumulative_total_payout_$B"], 954.48)
        self.assertAlmostEqual(first["cumulative_payout_ratio_pct"],
                               107.8, places=0)

    def test_cumulative_is_running_sum(self):
        run_payout = run_earn = 0.0
        for c, r in zip(self.cum, self.rows):
            run_payout += r["total_payout_$B"]
            run_earn += r["_op_earnings_$B"]
            self.assertAlmostEqual(c["cumulative_total_payout_$B"],
                                   run_payout, places=1)
            self.assertAlmostEqual(
                c["cumulative_operating_earnings_$B"], run_earn, places=1)

    def test_cumulative_endpoint_matches_decade_totals(self):
        last = self.cum[-1]
        self.assertAlmostEqual(last["cumulative_total_payout_$B"],
                               12142.88, places=1)
        self.assertAlmostEqual(
            last["cumulative_operating_earnings_$B"], 13649.99, places=1)
        # The decade paid out 89.0% of what it earned, even though the
        # first year alone paid out 107.8%.
        self.assertAlmostEqual(last["cumulative_payout_ratio_pct"],
                               89.0, places=0)
        self.assertAlmostEqual(last["cumulative_buyback_share_pct"],
                               59.5, places=0)

    def test_era_rows_cover_decade_exactly_once(self):
        parts = [e for e in self.eras if e["era"] != ERAS[-1][0]]
        self.assertEqual(sum(e["years"] for e in parts), 10)
        full = self.by_era[ERAS[-1][0]]
        self.assertAlmostEqual(
            sum(e["total_payout_$B"] for e in parts),
            full["total_payout_$B"], places=1)
        self.assertAlmostEqual(
            sum(e["buybacks_$B"] for e in parts),
            full["buybacks_$B"], places=1)

    def test_era_buyback_share_is_stable(self):
        # The v4 headline: pooled by era the mix barely moves, even
        # though the annual share ranges 51.8% to 63.9%.
        shares = [self.by_era[name]["buyback_share_pct"]
                  for name, _, _ in ERAS[:3]]
        self.assertAlmostEqual(shares[0], 59.6, places=0)
        self.assertAlmostEqual(shares[1], 59.9, places=0)
        self.assertAlmostEqual(shares[2], 58.8, places=0)
        self.assertLess(max(shares) - min(shares), 2.0)
        annual = [r["buyback_share_pct"] for r in self.rows]
        self.assertGreater(max(annual) - min(annual), 10.0)

    def test_era_payout_ratio_falls(self):
        ratios = [self.by_era[name]["payout_ratio_op_earnings_pct"]
                  for name, _, _ in ERAS[:3]]
        self.assertAlmostEqual(ratios[0], 97.2, places=0)
        self.assertAlmostEqual(ratios[1], 87.5, places=0)
        self.assertAlmostEqual(ratios[2], 78.7, places=0)
        self.assertEqual(ratios, sorted(ratios, reverse=True))

    def test_era_hand_math_pre_pandemic(self):
        # 2015-2019 pooled by hand from PAYOUT.
        sel = [p for p in PAYOUT if 2015 <= p[0] <= 2019]
        div = sum(p[1] for p in sel)
        buy = sum(p[2] for p in sel)
        earn = sum(p[3] for p in sel)
        era = self.by_era[ERAS[0][0]]
        self.assertAlmostEqual(era["dividends_$B"], div, places=1)
        self.assertAlmostEqual(era["buybacks_$B"], buy, places=1)
        self.assertAlmostEqual(era["payout_ratio_op_earnings_pct"],
                               (div + buy) / earn * 100, places=0)
        self.assertAlmostEqual(era["avg_annual_payout_$B"],
                               (div + buy) / 5, places=1)


if __name__ == "__main__":
    unittest.main()
