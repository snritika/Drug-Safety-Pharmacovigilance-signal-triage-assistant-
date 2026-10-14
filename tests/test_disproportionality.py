import unittest

from pharmsignal.disproportionality import compute


class ComputeTests(unittest.TestCase):
    def test_no_association_gives_ratios_of_one(self):
        result = compute(10, 90, 100, 900)
        self.assertAlmostEqual(result.prr, 1.0)
        self.assertAlmostEqual(result.ror, 1.0)
        self.assertAlmostEqual(result.chi2, 0.0)
        self.assertFalse(result.meets_evans)
        self.assertFalse(result.ror_lower_above_one)

    def test_known_signal_values(self):
        result = compute(20, 80, 50, 950)
        self.assertAlmostEqual(result.prr, 4.0)
        self.assertAlmostEqual(result.ror, 4.75)
        self.assertAlmostEqual(result.chi2, 34.33, places=1)
        self.assertTrue(result.meets_evans)
        self.assertTrue(result.ror_lower_above_one)
        self.assertFalse(result.haldane_applied)

    def test_interval_brackets_point_estimate(self):
        result = compute(20, 80, 50, 950)
        self.assertLess(result.prr_lower, result.prr)
        self.assertLess(result.prr, result.prr_upper)
        self.assertLess(result.ror_lower, result.ror)
        self.assertLess(result.ror, result.ror_upper)

    def test_zero_cell_applies_haldane_and_stays_finite(self):
        result = compute(0, 100, 50, 950)
        self.assertTrue(result.haldane_applied)
        self.assertGreater(result.prr, 0)
        self.assertLess(result.prr, float("inf"))
        self.assertFalse(result.meets_evans)

    def test_evans_requires_three_cases(self):
        # Ratios are huge, but only two reports have the drug and the reaction.
        result = compute(2, 0, 1, 997)
        self.assertGreaterEqual(result.prr, 2.0)
        self.assertFalse(result.meets_evans)

    def test_negative_count_raises(self):
        with self.assertRaises(ValueError):
            compute(-1, 5, 5, 5)

    def test_empty_table_raises(self):
        with self.assertRaises(ValueError):
            compute(0, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()