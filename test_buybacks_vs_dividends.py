"""Tests for buybacks_vs_dividends: sourced totals, growth, counterfactual."""
import statistics
import unittest

from buybacks_vs_dividends import (
    PAYOUT, build_counterfactual, build_growth, build_rows, public_rows,
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


if __name__ == "__main__":
    unittest.main()
