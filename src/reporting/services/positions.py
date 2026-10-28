"""Align plotted positions with the same visibility rules as evaluation."""

from math import hypot

from reporting.models.positions import ComparisonStatus, PositionComparison
from reporting.models.provenance import ReferenceProvenance
from reporting.services.evaluation import validate_reference
from reporting.services.inputs import align_frames
from tracking.models import Point
from tracking.models.export import DetectionExport, FrameExport


def classify_position(
    annotation: Point | None,
    observation: Point | None,
    *,
    uncertain: bool,
    threshold_px: float,
) -> tuple[ComparisonStatus, float | None]:
    """Distinguish real errors from frames without a readable reference.

    :param annotation: Readable annotation center, if present.
    :type annotation: Point | None
    :param observation: Code observation, if present.
    :type observation: Point | None
    :param uncertain: Whether the reference is excluded from scoring.
    :type uncertain: bool
    :param threshold_px: Maximum error counted as correct.
    :type threshold_px: float
    :return: Classification and distance only when both centers are readable.
    :rtype: tuple[ComparisonStatus, float | None]
    """
    if uncertain:
        return ComparisonStatus.UNCERTAIN, None
    if annotation is None:
        return (
            ComparisonStatus.FALSE_POSITIVE
            if observation is not None
            else ComparisonStatus.ABSENT,
            None,
        )
    if observation is None:
        return ComparisonStatus.MISSED, None
    error: float = hypot(
        observation[0] - annotation[0], observation[1] - annotation[1]
    )
    return (
        ComparisonStatus.CORRECT
        if error <= threshold_px
        else ComparisonStatus.WRONG,
        error,
    )


def compare_frames(
    reference: DetectionExport,
    detected: DetectionExport,
    provenance: ReferenceProvenance,
    *,
    threshold_px: float = 20.0,
) -> list[PositionComparison]:
    """Match source indices and retain every available code observation.

    :param reference: Annotation export in source-image coordinates.
    :type reference: DetectionExport
    :param detected: Code export in the same coordinate system.
    :type detected: DetectionExport
    :param provenance: Visibility decisions for the reference frames.
    :type provenance: ReferenceProvenance
    :param threshold_px: Maximum localization error counted as correct.
    :type threshold_px: float
    :return: Aligned positions and explicit scoring status for each reference.
    :rtype: list[PositionComparison]
    :raises ValueError: If source data, indices or timestamps are inconsistent.
    """
    if threshold_px <= 0:
        raise ValueError("Threshold must be positive")
    if (
        reference.metadata != detected.metadata
        or reference.source_video.name != detected.source_video.name
    ):
        raise ValueError("Source metadata differs between the exports")
    excluded: set[int] = validate_reference(reference, provenance)
    frame: FrameExport
    comparisons: list[PositionComparison] = []
    sample: FrameExport
    for sample, frame in align_frames(reference, detected):
        if abs(frame.timestamp_seconds - sample.timestamp_seconds) > 1e-6:
            raise ValueError("Code timestamp differs from the reference")
        annotation: Point | None = (
            sample.ball.center if sample.ball is not None else None
        )
        observation: Point | None = (
            frame.ball.center if frame.ball is not None else None
        )
        status: ComparisonStatus
        error: float | None
        status, error = classify_position(
            annotation,
            observation,
            uncertain=sample.frame_index in excluded,
            threshold_px=threshold_px,
        )
        comparisons.append(
            PositionComparison(
                frame_index=sample.frame_index,
                timestamp_seconds=sample.timestamp_seconds,
                annotation=annotation,
                observation=observation,
                error_px=error,
                status=status,
            )
        )
    return comparisons
