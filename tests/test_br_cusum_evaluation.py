"""Synthetic tests for the fixed BR-CUSUM protocol."""
from __future__ import annotations

import importlib.util
import inspect
import unittest
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "run_br_cusum_evaluation.py"
SPEC = importlib.util.spec_from_file_location("br_cusum_eval", MODULE_PATH)
br = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(br)


class BrCusumTests(unittest.TestCase):
    def calibration(self, values: list[float]) -> np.ndarray:
        return np.resize(np.asarray(values, dtype=float), br.CALIBRATION_ROWS)

    def test_median_mad_hand_calculation(self) -> None:
        p = br.robust_parameters(self.calibration([1, 2, 3, 4, 5]))
        self.assertEqual(p["calibration_median"], 3.0)
        self.assertEqual(p["calibration_mad"], 1.0)
        self.assertAlmostEqual(p["robust_scale"], 1.4826 + br.EPSILON)

    def test_zero_mad_uses_epsilon(self) -> None:
        p = br.robust_parameters(self.calibration([7.0]))
        self.assertEqual(p["calibration_mad"], 0.0)
        self.assertEqual(p["robust_scale"], br.EPSILON)

    def test_upper_and_lower_directions(self) -> None:
        upper, lower = br.robust_channels(np.array([8.0, 10.0, 12.0]), 10.0, 2.0)
        np.testing.assert_allclose(upper, [0, 0, 1]); np.testing.assert_allclose(lower, [1, 0, 0])

    def test_cusum_hand_recurrence_and_k_boundaries(self) -> None:
        plus, minus = br.cusum(np.array([1.0, 0.0, 2.0]), np.array([0.0, 1.0, 0.0]), 0.5)
        np.testing.assert_allclose(plus, [0.5, 0.0, 1.5]); np.testing.assert_allclose(minus, [0.0, 0.5, 0.0])
        with self.assertRaises(ValueError): br.cusum(np.array([1.0]), np.array([1.0]), -0.1)

    def test_length_finiteness_and_extreme_values(self) -> None:
        values = np.array([0.0, 1e100, 1.0])
        upper, lower = br.robust_channels(values, 0.0, 1.0)
        plus, minus = br.cusum(upper, lower, 0.5)
        self.assertEqual(plus.size, values.size); self.assertTrue(np.isfinite(plus).all()); self.assertTrue(np.isfinite(minus).all())

    def test_constant_single_spike_and_sustained_offsets(self) -> None:
        upper, lower = br.robust_channels(np.array([0., 0., 10., 0.]), 0., 1.)
        plus, _ = br.cusum(upper, lower, .5); self.assertGreater(plus[2], 0)
        upper, lower = br.robust_channels(np.array([2., 2., 2.]), 0., 1.)
        plus, _ = br.cusum(upper, lower, .5); self.assertGreater(plus[-1], plus[0])
        upper, lower = br.robust_channels(np.array([-2., -2., -2.]), 0., 1.)
        _, minus = br.cusum(upper, lower, .5); self.assertGreater(minus[-1], minus[0])

    def test_state_continues_across_calibration_boundary(self) -> None:
        upper = np.array([1., 0., 2., 1.]); lower = np.zeros(4)
        all_plus, _ = br.cusum(upper, lower, .5)
        first_plus, first_minus = br.cusum(upper[:2], lower[:2], .5)
        resumed_plus, _ = br.cusum(upper[2:], lower[2:], .5, first_plus[-1], first_minus[-1])
        np.testing.assert_allclose(all_plus[2:], resumed_plus)

    def test_score_only_parameter_interface_and_resume_status(self) -> None:
        self.assertEqual(len(inspect.signature(br.robust_parameters).parameters), 1)
        self.assertTrue(br.can_resume("interrupted")); self.assertTrue(br.can_resume("failed")); self.assertFalse(br.can_resume("completed"))


if __name__ == "__main__": unittest.main()
