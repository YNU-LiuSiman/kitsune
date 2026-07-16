"""Synthetic tests for the final fixed Leaky BR-CUSUM protocol."""
from __future__ import annotations

import importlib.util
import inspect
import unittest
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "run_leaky_br_cusum_evaluation.py"
SPEC = importlib.util.spec_from_file_location("leaky_eval", MODULE_PATH)
leaky = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(leaky)


class LeakyBrCusumTests(unittest.TestCase):
    def test_rho_zero_has_no_history(self) -> None:
        plus, minus = leaky.leaky_cusum(np.array([1., 2., 3.]), np.zeros(3), 0.0, .5)
        np.testing.assert_allclose(plus, [.5, 1.5, 2.5]); np.testing.assert_allclose(minus, [0, 0, 0])

    def test_hand_recurrence_and_rho_near_one(self) -> None:
        plus, _ = leaky.leaky_cusum(np.array([1., 1., 1.]), np.zeros(3), .5, .5)
        np.testing.assert_allclose(plus, [.5, .75, .875])
        near, _ = leaky.leaky_cusum(np.array([1., 1.]), np.zeros(2), .99, .5)
        self.assertGreater(near[-1], .9)

    def test_length_continuity_and_finite_extreme(self) -> None:
        upper = np.array([1., 0., 1e100, 1.]); lower = np.zeros(4)
        full, _ = leaky.leaky_cusum(upper, lower, .95, .5)
        first, first_minus = leaky.leaky_cusum(upper[:2], lower[:2], .95, .5)
        resumed, _ = leaky.leaky_cusum(upper[2:], lower[2:], .95, .5, first[-1], first_minus[-1])
        self.assertEqual(full.size, upper.size); self.assertTrue(np.isfinite(full).all()); np.testing.assert_allclose(full[2:], resumed)

    def test_spike_and_sustained_high_low_offsets(self) -> None:
        spike, _ = leaky.leaky_cusum(np.array([0., 10., 0., 0.]), np.zeros(4), .5, .5)
        self.assertGreater(spike[1], spike[-1])
        high, _ = leaky.leaky_cusum(np.full(4, 2.), np.zeros(4), .95, .5)
        _, low = leaky.leaky_cusum(np.zeros(4), np.full(4, 2.), .95, .5)
        self.assertGreater(high[-1], high[0]); self.assertGreater(low[-1], low[0])

    def test_invalid_parameters_and_score_only_interfaces(self) -> None:
        with self.assertRaises(ValueError): leaky.leaky_cusum(np.ones(1), np.ones(1), 1.01, .5)
        self.assertEqual(len(inspect.signature(leaky.robust_parameters).parameters), 1)
        self.assertEqual(len(inspect.signature(leaky.quantile_thresholds).parameters), 1)


if __name__ == "__main__": unittest.main()
