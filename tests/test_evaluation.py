"""Verify reference exports and scoring with independent expected results."""

from math import sqrt
from pathlib import Path
from typing import Self
from unittest import TestCase, main

from reporting.services.evaluation import evaluate
from tracking.config import ApplicationConfig
from tracking.models import Point
from tracking.models.export import (
    BallExport,
    DetectionExport,
    DetectionStatus,
    FrameExport,
    MetadataExport,
    PredictionExport,
    StopReason,
    SummaryExport,
)


def make_report(
    centers: list[Point | None],
    *,
    predicted: set[int] | None = None,
    stride: int = 3,
) -> DetectionExport:
    """Build a small export independently of the evaluation implementation.

    :param centers: Synthetic positions at regularly spaced source frames.
    :type centers: list[Point | None]
    :param predicted: Sample offsets containing predictions instead of balls.
    :type predicted: set[int] | None
    :param stride: Source-frame spacing between consecutive test positions.
    :type stride: int
    :return: Validated synthetic detection export.
    :rtype: DetectionExport
    """
    frames: list[FrameExport] = []
    detected_count: int = 0
    predicted_count: int = 0
    offset: int
    center: Point | None
    for offset, center in enumerate(centers):
        ball: BallExport | None = None
        prediction: PredictionExport | None = None
        status: DetectionStatus = DetectionStatus.MISSING
        if center is not None and predicted and offset in predicted:
            prediction = PredictionExport(
                center=center, radius=5, origin=center, missing_seconds=0.1
            )
            status = DetectionStatus.ESTIMATED
            predicted_count += 1
        elif center is not None:
            ball = BallExport(
                center=center,
                radius=None,
                area=None,
                circularity=None,
                aspect_ratio=None,
                fill_ratio=None,
                score=None,
            )
            status = DetectionStatus.DETECTED
            detected_count += 1
        frames.append(
            FrameExport(
                frame_index=offset * stride,
                timestamp_seconds=offset * stride / 30,
                status=status,
                table=None,
                ball=ball,
                candidates=[],
                prediction=prediction,
            )
        )
    return DetectionExport(
        source_video=Path("synthetic.mp4"),
        output_video=Path("synthetic-output.mp4"),
        metadata=MetadataExport(
            frame_count=100, fps=30, width=100, height=100
        ),
        configuration=ApplicationConfig(),
        frames=frames,
        summary=SummaryExport(
            processed_frames=len(frames),
            detected_frames=detected_count,
            predicted_frames=predicted_count,
            detection_rate=detected_count / len(frames) * 100,
            prediction_rate=predicted_count / len(frames) * 100,
            coverage_rate=(detected_count + predicted_count)
            / len(frames)
            * 100,
        ),
        completed=True,
        stop_reason=StopReason.MAX_FRAMES,
    )


class ReferenceExportTests(TestCase):
    """Keep unknown manual geometry distinct from measured zero values."""

    def test_dense_reference_run_uses_source_frame_rate(self: Self) -> None:
        """Score consecutive frames and interrupt a run on an unknown label.

        :return: None.
        :rtype: None
        """
        reference: DetectionExport = make_report(
            [(20, 20), (20, 20), None, (20, 20), (20, 20), (20, 20)],
            stride=1,
        )
        detected: DetectionExport = make_report([(20, 20)] * 6, stride=1)
        result: dict[str, int | float | None] = evaluate(
            reference, detected, excluded={2}, sample_stride=1
        )
        self.assertEqual(result["true_positives"], 5)
        self.assertEqual(result["excluded_samples"], 1)
        self.assertEqual(result["longest_correct_sampled_run_samples"], 3)
        self.assertAlmostEqual(
            float(result["longest_correct_sampled_run_seconds"] or 0),
            2 / 30,
        )

    def test_unmeasured_geometry_remains_null(self: Self) -> None:
        """Accept a reference center without inventing contour measurements.

        :return: None.
        :rtype: None
        """
        reference: BallExport = BallExport.model_validate(
            {
                "center": [10, 20],
                "radius": None,
                "area": None,
                "circularity": None,
                "aspect_ratio": None,
                "fill_ratio": None,
                "score": None,
            }
        )
        self.assertEqual(reference.center, (10, 20))
        self.assertIsNone(reference.radius)
        self.assertIsNone(reference.area)
        self.assertIsNone(reference.score)

    def test_numeric_detection_geometry_is_preserved(self: Self) -> None:
        """Keep complete automatic geometry unchanged through serialization.

        :return: None.
        :rtype: None
        """
        detection: BallExport = BallExport(
            center=(20, 30),
            radius=14,
            area=450,
            circularity=0.9,
            aspect_ratio=1.1,
            fill_ratio=0.7,
            score=6.8,
        )
        restored: BallExport = BallExport.model_validate_json(
            detection.model_dump_json()
        )
        self.assertEqual(restored, detection)
        self.assertEqual(restored.radius, 14)
        self.assertEqual(restored.score, 6.8)

    def test_wrong_positions_and_predictions_have_distinct_scores(
        self: Self,
    ) -> None:
        """Check localization, visibility and predictions with exact oracles.

        :return: None.
        :rtype: None
        """
        reference: DetectionExport = make_report(
            [(0, 0), (0, 0), (0, 0), None, None, (0, 0)]
        )
        detected: DetectionExport = make_report(
            [(3, 4), (30, 40), None, (10, 10), (1, 1), (6, 8)],
            predicted={5},
        )
        result: dict[str, int | float | None] = evaluate(
            reference, detected, excluded={9}, threshold_px=20
        )
        self.assertEqual(result["visible_samples"], 4)
        self.assertEqual(result["excluded_samples"], 1)
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 2)
        self.assertEqual(result["false_negatives"], 3)
        self.assertAlmostEqual(float(result["precision"] or 0), 1 / 3)
        self.assertAlmostEqual(float(result["recall"] or 0), 1 / 4)
        self.assertAlmostEqual(float(result["f1"] or 0), 2 / 7)
        self.assertEqual(result["observed_error_mean_px"], 27.5)
        self.assertAlmostEqual(
            float(result["observed_error_rmse_px"] or 0), sqrt(1262.5)
        )
        self.assertEqual(result["combined_correct"], 2)
        self.assertEqual(result["prediction_correct"], 1)
        self.assertEqual(result["combined_recall"], 0.5)
        self.assertEqual(result["longest_correct_sampled_run_samples"], 1)

    def test_no_positions_have_undefined_localization_error(
        self: Self,
    ) -> None:
        """Keep unavailable measurements null instead of reporting zero error.

        :return: None.
        :rtype: None
        """
        result: dict[str, int | float | None] = evaluate(
            make_report([(20, 20)]), make_report([None]), excluded=set()
        )
        self.assertIsNone(result["precision"])
        self.assertEqual(result["recall"], 0)
        self.assertIsNone(result["observed_error_mean_px"])
        self.assertIsNone(result["combined_error_rmse_px"])

    def test_missing_export_record_is_rejected(self: Self) -> None:
        """Reject an incomplete comparison instead of treating it as a miss.

        :return: None.
        :rtype: None
        """
        reference: DetectionExport = make_report([(20, 20), (30, 30)])
        detected: DetectionExport = make_report([(20, 20)])
        with self.assertRaisesRegex(ValueError, "Missing exported frame"):
            evaluate(reference, detected, excluded=set())

    def test_different_resolutions_are_rejected(self: Self) -> None:
        """Reject coordinates measured in different image dimensions.

        :return: None.
        :rtype: None
        """
        reference: DetectionExport = make_report([(20, 20)])
        detected: DetectionExport = make_report([(20, 20)])
        detected.metadata.width = 200
        with self.assertRaisesRegex(ValueError, "metadata"):
            evaluate(reference, detected, excluded=set())


if __name__ == "__main__":
    main()
