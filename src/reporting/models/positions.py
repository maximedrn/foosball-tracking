"""Describe aligned annotation and observation data used by figures."""

from enum import StrEnum

from pydantic import BaseModel

from tracking.models import Point


class ComparisonStatus(StrEnum):
    """Keep scoring outcomes separate from annotation availability."""

    CORRECT = "correct"
    WRONG = "wrong"
    MISSED = "missed"
    UNCERTAIN = "uncertain"
    FALSE_POSITIVE = "false_positive"
    ABSENT = "absent"


class PositionComparison(BaseModel):
    """Store one aligned frame without discarding unscored observations.

    :param frame_index: Original source frame index.
    :type frame_index: int
    :param timestamp_seconds: Original source timestamp.
    :type timestamp_seconds: float
    :param annotation: Readable annotation center, if available.
    :type annotation: Point | None
    :param observation: Code position, including outliers and false positives.
    :type observation: Point | None
    :param error_px: Distance on readable references with an observation.
    :type error_px: float | None
    :param status: Scoring outcome or reference availability.
    :type status: ComparisonStatus
    """

    frame_index: int
    timestamp_seconds: float
    annotation: Point | None
    observation: Point | None
    error_px: float | None
    status: ComparisonStatus
