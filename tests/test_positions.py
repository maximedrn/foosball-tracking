"""Verify plot classifications against independent geometric examples."""

from typing import Self
from unittest import TestCase

from reporting.models.positions import PositionComparison
from reporting.models.provenance import FrameReview, ReferenceProvenance
from reporting.services.positions import compare_frames
from tests.test_evaluation import make_report
from tracking.models.export import DetectionExport


class PositionComparisonTests(TestCase):
    """Preserve outliers and distinguish unscored or nonvisible targets."""

    def test_align_frames_and_keep_every_observation(self: Self) -> None:
        """Classify a 3-4-5 match, a 30-40-50 error and unknown frames.

        :return: None.
        :rtype: None
        """
        annotations: DetectionExport = make_report(
            [(0, 0), (0, 0), None, None, None, (0, 0)]
        )
        detections: DetectionExport = make_report(
            [(3, 4), (30, 40), (99, 99), (10, 10), None, None]
        )
        detections.frames.reverse()
        provenance: ReferenceProvenance = ReferenceProvenance(
            source_sha256="0" * 64,
            canonical_annotations_sha256="0" * 64,
            sample_stride=3,
            human_verified=False,
            review=[
                FrameReview(frame_index=0, visibility="visible"),
                FrameReview(frame_index=3, visibility="visible"),
                FrameReview(frame_index=6, visibility="uncertain"),
                FrameReview(frame_index=9, visibility="not_visible"),
                FrameReview(frame_index=12, visibility="not_visible"),
                FrameReview(frame_index=15, visibility="visible"),
            ],
        )
        frames: list[PositionComparison] = compare_frames(
            annotations, detections, provenance
        )
        self.assertEqual(
            [frame.frame_index for frame in frames], [0, 3, 6, 9, 12, 15]
        )
        self.assertEqual(
            [frame.status.value for frame in frames],
            [
                "correct",
                "wrong",
                "uncertain",
                "false_positive",
                "absent",
                "missed",
            ],
        )
        self.assertEqual(
            [frame.error_px for frame in frames],
            [5.0, 50.0, None, None, None, None],
        )
        self.assertEqual(frames[1].observation, (30, 40))
        self.assertEqual(frames[2].observation, (99, 99))
        self.assertEqual(frames[3].observation, (10, 10))
        self.assertEqual(sum(f.observation is not None for f in frames), 4)

    def test_duplicate_output_indices_are_rejected(self: Self) -> None:
        """Reject an ambiguous output before drawing apparently valid lines.

        :return: None.
        :rtype: None
        """
        reference: DetectionExport = make_report([(10, 10)])
        detected: DetectionExport = make_report([(10, 10)])
        detected.frames.append(detected.frames[0])
        provenance: ReferenceProvenance = ReferenceProvenance(
            source_sha256="0" * 64,
            canonical_annotations_sha256="0" * 64,
            sample_stride=3,
            human_verified=False,
            review=[FrameReview(frame_index=0, visibility="visible")],
        )
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            compare_frames(reference, detected, provenance)

    def test_mismatched_timestamps_are_rejected(self: Self) -> None:
        """Reject temporal misalignment rather than labeling it an outlier.

        :return: None.
        :rtype: None
        """
        reference: DetectionExport = make_report([(10, 10)])
        detected: DetectionExport = make_report([(10, 10)])
        detected.frames[0].timestamp_seconds = 1.0
        provenance: ReferenceProvenance = ReferenceProvenance(
            source_sha256="0" * 64,
            canonical_annotations_sha256="0" * 64,
            sample_stride=3,
            human_verified=False,
            review=[FrameReview(frame_index=0, visibility="visible")],
        )
        with self.assertRaisesRegex(ValueError, "timestamp"):
            compare_frames(reference, detected, provenance)
