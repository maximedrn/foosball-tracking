"""Validate compact coverage data independently of chart rendering."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tracking.config import ApplicationConfig
from tracking.models.export import MetadataExport

type ObservationRate = Annotated[float, Field(ge=0, le=100)]


class VideoStatistics(BaseModel):
    """Store measured frame counts and equal-duration detection windows.

    :param name: Video label shown in the chart.
    :type name: str
    :param frames: Number of processed frames.
    :type frames: int
    :param detected: Frames containing a visual observation.
    :type detected: int
    :param estimated: Frames containing only a prediction.
    :type estimated: int
    :param missing: Frames without a position.
    :type missing: int
    :param observed_windows: Observed percentages in successive time windows.
    :type observed_windows: tuple[ObservationRate, ...]
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str
    frames: int = Field(gt=0)
    detected: int = Field(ge=0)
    estimated: int = Field(ge=0)
    missing: int = Field(ge=0)
    observed_windows: tuple[ObservationRate, ...]

    @model_validator(mode="after")
    def validate_counts(self: Self) -> Self:
        """Reject counts that disagree with the processed frame total.

        :return: Consistent statistics.
        :rtype: Self
        :raises ValueError: If status counts do not sum to the total.
        """
        if self.detected + self.estimated + self.missing != self.frames:
            raise ValueError("Status counts must sum to processed frames")
        return self

    @property
    def coverage_rate(self: Self) -> float:
        """Calculate availability with the processed-frame denominator.

        :return: Percentage with an observed or predicted position.
        :rtype: float
        """
        return (self.detected + self.estimated) / self.frames * 100.0


class CoverageSource(BaseModel):
    """Identify the original export behind a compact coverage record.

    :param path: Original detection JSON path.
    :type path: Path
    :param sha256: Hash of that original export.
    :type sha256: str
    :param configuration: Effective settings recorded in the export.
    :type configuration: ApplicationConfig
    :param metadata: Source video dimensions, frame count and frame rate.
    :type metadata: MetadataExport
    """

    path: Path
    sha256: str
    configuration: ApplicationConfig
    metadata: MetadataExport


class CoverageReport(BaseModel):
    """Persist the inputs needed to regenerate a multi-video chart.

    :param schema_version: Compact report format version.
    :type schema_version: Literal[1]
    :param videos: Measured coverage and timeline statistics.
    :type videos: list[VideoStatistics]
    :param sources: Original exports and their configuration snapshots.
    :type sources: list[CoverageSource]
    """

    schema_version: Literal[1] = 1
    videos: list[VideoStatistics] = Field(min_length=1)
    sources: list[CoverageSource] = Field(default_factory=list[CoverageSource])

    @model_validator(mode="after")
    def validate_windows(self: Self) -> Self:
        """Require comparable, nonempty timelines across videos.

        :return: Report with consistently sized time windows.
        :rtype: Self
        :raises ValueError: If timeline sizes differ or are empty.
        """
        window_count: int = len(self.videos[0].observed_windows)
        if not window_count:
            raise ValueError("Coverage timelines must not be empty")
        video: VideoStatistics
        for video in self.videos:
            if len(video.observed_windows) != window_count:
                raise ValueError("Coverage timeline sizes must agree")
        return self
