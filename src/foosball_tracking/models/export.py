"""Define the validated JSON format independently from runtime image data."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from foosball_tracking.config import ApplicationConfig
from foosball_tracking.models.entities import Point

type ExportBox = tuple[Point, Point, Point, Point]


class DetectionStatus(StrEnum):
    """Distinguish observed, extrapolated and absent ball positions."""

    DETECTED = "detected"
    ESTIMATED = "estimated"
    MISSING = "missing"


class StopReason(StrEnum):
    """Describe why the processing loop ended."""

    END_OF_VIDEO = "end_of_video"
    MAX_FRAMES = "max_frames"
    PREVIEW_CLOSED = "preview_closed"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class _ExportModel(BaseModel):
    """Read domain attributes and reject nonfinite numbers and extra keys."""

    model_config = ConfigDict(
        from_attributes=True, allow_inf_nan=False, extra="forbid"
    )


class BallExport(_ExportModel):
    """Store measured ball geometry without its raw contour or image mask."""

    center: Point
    radius: float
    area: float
    circularity: float
    aspect_ratio: float
    fill_ratio: float
    score: float


class TableExport(_ExportModel):
    """Store the four corners of the playing field and expanded table."""

    playfield_box: ExportBox
    table_box: ExportBox


class PredictionExport(_ExportModel):
    """Store a motion estimate separately from observed ball geometry."""

    center: Point
    radius: float
    origin: Point
    missing_seconds: float


class FrameExport(_ExportModel):
    """Describe one source frame using full-resolution image coordinates."""

    frame_index: int
    timestamp_seconds: float
    status: DetectionStatus
    table: TableExport | None
    ball: BallExport | None
    candidates: list[BallExport]
    prediction: PredictionExport | None


class MetadataExport(_ExportModel):
    """Describe the source video's frame count, timing and dimensions."""

    frame_count: int
    fps: float
    width: int
    height: int


class SummaryExport(_ExportModel):
    """Report counts and separate observation and prediction rates."""

    processed_frames: int
    detected_frames: int
    predicted_frames: int
    detection_rate: float
    prediction_rate: float
    coverage_rate: float


class ExportHeader(_ExportModel):
    """Define the file header shared by streaming and complete exports."""

    schema_version: Literal[1] = 1
    source_video: Path
    output_video: Path
    metadata: MetadataExport
    configuration: ApplicationConfig


class ExportFooter(_ExportModel):
    """Define the summary and termination fields written after the frames."""

    summary: SummaryExport
    completed: bool
    stop_reason: StopReason


class DetectionExport(ExportHeader, ExportFooter):
    """Define the complete JSON document for validation and schema generation.

    The writer serializes the header, each frame and the footer separately
    using the same models to keep its memory usage bounded.
    """

    frames: list[FrameExport]
