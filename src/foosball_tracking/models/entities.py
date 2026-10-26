"""Models for the foosball video detector."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from numpy import int32, uint8
from numpy.typing import NDArray

# Images are BGR/RGB frames (height, width, 3) or masks (height, width).
type Image = NDArray[uint8]
# OpenCV uses signed coordinates, including after a crop-origin translation.
type Contour = NDArray[int32]
type Box = NDArray[int32]
type Point = tuple[int, int]
type RGBColor = tuple[int, int, int]
type BGRColor = tuple[int, int, int]
type RotatedRectangle = tuple[Sequence[float], Sequence[float], float]


# Runtime results are small dataclasses; validation belongs to configuration.
@dataclass(slots=True)
class TableDetection:
    """Store the geometric result of baby-foot detection.

    :param playfield_box: Four corners of the detected green playfield.
    :type playfield_box: Box
    :param table_box: Expanded rectangle approximating the complete table.
    :type table_box: Box
    """

    playfield_box: Box
    table_box: Box


@dataclass(slots=True)
class BallCandidate:
    """Represent one valid yellow-ball candidate.

    :param center: Candidate center in full-frame coordinates.
    :type center: Point
    :param radius: Radius of the minimum enclosing circle.
    :type radius: float
    :param area: Contour area in pixels.
    :type area: float
    :param circularity: Circularity defined as 4πA/P².
    :type circularity: float
    :param aspect_ratio: Ratio between the largest and smallest dimensions.
    :type aspect_ratio: float
    :param fill_ratio: Fraction of the enclosing circle filled by the contour.
    :type fill_ratio: float
    :param score: Candidate likelihood score.
    :type score: float
    :param contour: Original OpenCV contour in ROI coordinates.
    :type contour: Contour
    """

    center: Point
    radius: float
    area: float
    circularity: float
    aspect_ratio: float
    fill_ratio: float
    score: float
    contour: Contour


@dataclass(slots=True)
class BallDetection:
    """Store the result of ball detection for one frame.

    :param ball: Highest-scoring candidate, or ``None``.
    :type ball: BallCandidate | None
    :param candidates: All candidates that passed the filters.
    :type candidates: list[BallCandidate]
    :param mask: Binary yellow-color segmentation mask.
    :type mask: Image
    """

    ball: BallCandidate | None
    candidates: list[BallCandidate]
    mask: Image


@dataclass(slots=True, frozen=True)
class BallPrediction:
    """Estimate the ball position during a short visual occlusion.

    :param center: Extrapolated center in full-frame coordinates.
    :type center: Point
    :param radius: Radius of the last observed ball.
    :type radius: float
    :param origin: Last observed center, used to draw the motion direction.
    :type origin: Point
    :param missing_seconds: Time elapsed since the last observation.
    :type missing_seconds: float
    """

    center: Point
    radius: float
    origin: Point
    missing_seconds: float


@dataclass(slots=True, frozen=True)
class BallTrack:
    """Keep a measured ball separate from a motion-only estimate.

    :param ball: Ball observed in the current frame, or None.
    :type ball: BallCandidate | None
    :param prediction: Estimated position when the ball is hidden, or None.
    :type prediction: BallPrediction | None
    """

    ball: BallCandidate | None = None
    prediction: BallPrediction | None = None


@dataclass(slots=True)
class VideoMetadata:
    """Describe basic source-video properties.

    :param frame_count: Number of frames reported by OpenCV.
    :type frame_count: int
    :param fps: Source frame rate.
    :type fps: float
    :param width: Frame width in pixels.
    :type width: int
    :param height: Frame height in pixels.
    :type height: int
    """

    frame_count: int
    fps: float
    width: int
    height: int


@dataclass(slots=True, frozen=True)
class RunSummary:
    """Report measured and estimated ball coverage across processed frames.

    :param processed_frames: Number of frames written to the output.
    :type processed_frames: int
    :param detected_frames: Number of frames with an accepted ball candidate.
    :type detected_frames: int
    :param predicted_frames: Number of frames with only an estimated position.
    :type predicted_frames: int
    """

    processed_frames: int
    detected_frames: int
    predicted_frames: int = 0

    @property
    def detection_rate(self: Self) -> float:
        """Compute the percentage of frames with a visual detection.

        :return: Detection percentage, or zero before processing starts.
        :rtype: float
        """
        # Predictions never increase the count of actual detections.
        return self.detected_frames / max(self.processed_frames, 1) * 100.0

    @property
    def prediction_rate(self: Self) -> float:
        """Compute the percentage of frames filled by motion prediction.

        :return: Prediction percentage, or zero before processing starts.
        :rtype: float
        """
        return self.predicted_frames / max(self.processed_frames, 1) * 100.0

    @property
    def coverage_rate(self: Self) -> float:
        """Compute the percentage with either a detection or a prediction.

        :return: Combined coverage percentage of the processed frames.
        :rtype: float
        """
        # Both counts refer to disjoint frame sets with the same denominator.
        return self.detection_rate + self.prediction_rate
