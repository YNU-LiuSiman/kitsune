"""Synthetic regression tests for the pre-registered EWMA protocol."""
from __future__ import annotations

import importlib.util
import inspect
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "run_ewma_evaluation.py"
SPEC = importlib.util.spec_from_file_location("ewma_eval", MODULE_PATH)
ewma_eval = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(ewma_eval)


class EwmaEvaluationTests(unittest.TestCase):
    def test_ewma_hand_calculated_sequence(self) -> None:
        actual = ewma_eval.ewma(np.array([1.0, 2.0, 3.0]), 0.5, initial=1.0)
        np.testing.assert_allclose(actual, [1.0, 1.5, 2.25])

    def test_alpha_boundaries_and_invalid_values(self) -> None:
        scores = np.array([2.0, 4.0, 8.0])
        np.testing.assert_allclose(ewma_eval.ewma(scores, 0.0, initial=3.0), [3.0, 3.0, 3.0])
        np.testing.assert_allclose(ewma_eval.ewma(scores, 1.0), scores)
        with self.assertRaises(ValueError):
            ewma_eval.ewma(scores, -0.01)
        with self.assertRaises(ValueError):
            ewma_eval.ewma(scores, 1.01)

    def test_length_and_finiteness_preserved(self) -> None:
        scores = np.linspace(0.0, 10.0, 37)
        actual = ewma_eval.ewma(scores, 0.1)
        self.assertEqual(actual.size, scores.size)
        self.assertTrue(np.isfinite(actual).all())

    def test_threshold_isolation_and_extreme_values(self) -> None:
        calibration = np.r_[np.zeros(ewma_eval.CALIBRATION_ROWS - 1), 1e12]
        thresholds = ewma_eval.threshold_values(calibration)
        self.assertTrue(all(np.isfinite(value) for value in thresholds.values()))
        self.assertEqual(len(inspect.signature(ewma_eval.threshold_values).parameters), 1)
        # Labels cannot alter a score-only threshold function because they are
        # intentionally not accepted by its public interface.
        with self.assertRaises(TypeError):
            ewma_eval.threshold_values(calibration, np.ones(calibration.size))

    def test_alignment_mismatch_fails_before_metrics(self) -> None:
        with self.assertRaises(ValueError):
            ewma_eval.evaluate(np.array([1.0, 2.0]), np.array([0]), 1.0)

    def test_detection_delay_and_alert_segments(self) -> None:
        labels = np.array([0, 0, 1, 1, 1, 0, 1, 1], dtype=np.int8)
        predictions = np.array([0, 1, 0, 1, 1, 0, 1, 0], dtype=bool)
        metrics = ewma_eval.temporal_metrics(predictions, labels)
        self.assertEqual(metrics["detection_delay_rows"], 1)
        self.assertEqual(metrics["attack_interval_count"], 2)
        self.assertEqual(metrics["detected_attack_intervals"], 2)
        self.assertEqual(metrics["continuous_alert_segments"], 3)

    def test_no_attack_and_all_attack_are_supported(self) -> None:
        for labels in (np.zeros(4, dtype=np.int8), np.ones(4, dtype=np.int8)):
            metrics = ewma_eval.evaluate(np.arange(4, dtype=float), labels, 1.5)
            self.assertIsNone(metrics["roc_auc"])
            self.assertIsNone(metrics["pr_auc"])

    def test_interrupted_status_can_resume_completed_status_skips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            status = Path(temporary) / "status.json"
            status.write_text(json.dumps({"status": "interrupted"}), encoding="utf-8")
            self.assertFalse(ewma_eval.should_skip_completed(status, True))
            status.write_text(json.dumps({"status": "failed"}), encoding="utf-8")
            self.assertFalse(ewma_eval.should_skip_completed(status, True))
            status.write_text(json.dumps({"status": "completed"}), encoding="utf-8")
            self.assertTrue(ewma_eval.should_skip_completed(status, True))


if __name__ == "__main__":
    unittest.main()
