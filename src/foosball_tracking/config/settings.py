"""Config for the foosball video detector."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from numpy import asarray, uint8
from pydantic import BaseModel, Field, model_validator

from foosball_tracking.models import BGRColor, Image, RGBColor
from foosball_tracking.utils.messages import (
    AREA_BOUNDS_ERROR,
    KERNEL_SIZE_ERROR,
    RADIUS_BOUNDS_ERROR,
    RGB_BOUNDS_ERROR,
)


class RGBRange(BaseModel):
    """Bound a color interval in 8-bit RGB space.

    :param lower: Inclusive lower red, green and blue values.
    :type lower: RGBColor
    :param upper: Inclusive upper red, green and blue values.
    :type upper: RGBColor
    """

    lower: RGBColor
    upper: RGBColor

    @model_validator(mode="after")
    def validate_bounds(self: Self) -> Self:
        """Reject invalid or inverted RGB bounds before array conversion.

        :return: The validated RGB interval.
        :rtype: Self
        """
        for channel in range(3):
            if not 0 <= self.lower[channel] <= self.upper[channel] <= 255:
                raise ValueError(RGB_BOUNDS_ERROR)
        return self

    def lower_array(self: Self) -> Image:
        """Return the RGB bound as an unsigned 8-bit array.

        :return: Lower RGB bound as an unsigned 8-bit array.
        :rtype: Image
        """
        return asarray(self.lower, dtype=uint8)

    def upper_array(self: Self) -> Image:
        """Return the RGB bound as an unsigned 8-bit array.

        :return: Upper RGB bound as an unsigned 8-bit array.
        :rtype: Image
        """
        return asarray(self.upper, dtype=uint8)


class TableDetectorConfig(BaseModel):
    """Configure baby-foot detection.

    The detector localizes the baby-foot from its large green
    playing surface, then expands the detected rectangle to
    approximate the complete table.

    :param rgb: RGB interval used to segment the green playfield.
    :type rgb: RGBRange
    :param detection_every: Number of frames between two table detections.
    :type detection_every: int
    :param scale: Scale factor used during table detection.
    :type scale: float
    :param minimum_area_ratio: Minimum image fraction occupied by the field.
    :type minimum_area_ratio: float
    :param close_kernel_size: Morphological closing kernel size.
    :type close_kernel_size: int
    :param close_iterations: Number of morphological closing iterations.
    :type close_iterations: int
    :param box_expansion: Expansion applied around the detected playfield to
        approximate the complete baby-foot.
    :type box_expansion: float
    """

    # Segment the green surface; detect it periodically because the table moves
    # much less than the ball.
    rgb: RGBRange = RGBRange(lower=(0, 140, 0), upper=(160, 230, 160))
    detection_every: int = Field(default=15, ge=1)
    scale: float = Field(default=0.5, gt=0.0, le=1.0)
    minimum_area_ratio: float = Field(default=0.05, gt=0.0, lt=1.0)
    close_kernel_size: int = Field(default=11, ge=1)
    close_iterations: int = Field(default=2, ge=0)
    box_expansion: float = Field(default=1.18, ge=1.0)


class BallDetectorConfig(BaseModel):
    """Configure yellow ball detection.

    :param rgb: RGB interval corresponding to the yellow ball.
    :type rgb: RGBRange
    :param minimum_area: Minimum accepted contour area in pixels.
    :type minimum_area: float
    :param maximum_area: Maximum accepted contour area in pixels.
    :type maximum_area: float
    :param minimum_radius: Minimum enclosing-circle radius.
    :type minimum_radius: float
    :param maximum_radius: Maximum enclosing-circle radius.
    :type maximum_radius: float
    :param minimum_circularity: Minimum contour circularity.
    :type minimum_circularity: float
    :param maximum_aspect_ratio: Maximum accepted bounding-box ratio.
    :type maximum_aspect_ratio: float
    :param minimum_fill_ratio: Minimum contour-to-circle fill ratio.
    :type minimum_fill_ratio: float
    :param expected_radius: Expected radius used for candidate scoring.
    :type expected_radius: float
    :param blur_kernel_size: Gaussian blur kernel size.
    :type blur_kernel_size: int
    :param close_kernel_size: Morphological closing kernel size.
    :type close_kernel_size: int
    """

    # Initial yellow thresholds; adjust them for the video's lighting.
    rgb: RGBRange = RGBRange(lower=(100, 100, 0), upper=(255, 255, 120))
    minimum_area: float = Field(default=30.0, ge=0.0)
    maximum_area: float = Field(default=400.0, gt=0.0)
    minimum_radius: float = Field(default=4.0, ge=0.0)
    maximum_radius: float = Field(default=18.0, gt=0.0)
    minimum_circularity: float = Field(default=0.4, ge=0.0, le=1.0)
    maximum_aspect_ratio: float = Field(default=2.3, ge=1.0)
    minimum_fill_ratio: float = Field(default=0.3, ge=0.0, le=1.0)
    expected_radius: float = Field(default=10.0, gt=0.0)
    blur_kernel_size: int = Field(default=3, ge=1)
    close_kernel_size: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def validate_geometry(self: Self) -> BallDetectorConfig:
        """Validate ball geometry parameters.

        :return: The validated ball detector configuration.
        :rtype: BallDetectorConfig
        """
        # Validate relationships that cannot be checked on one field alone.
        if self.maximum_area <= self.minimum_area:
            raise ValueError(AREA_BOUNDS_ERROR)
        if self.maximum_radius <= self.minimum_radius:
            raise ValueError(RADIUS_BOUNDS_ERROR)
        # Odd kernel sizes place the central pixel at an exact array position.
        for kernel_size in (self.blur_kernel_size, self.close_kernel_size):
            if kernel_size % 2 == 0:
                raise ValueError(KERNEL_SIZE_ERROR)
        return self


class BallTrackerConfig(BaseModel):
    """Bound motion extrapolation when the ball is temporarily hidden.

    :param maximum_prediction_seconds: Maximum time without a real detection.
    :type maximum_prediction_seconds: float
    :param velocity_smoothing: Weight given to the latest measured velocity.
    :type velocity_smoothing: float
    """

    # Use seconds so the same limit works with different video frame rates.
    # Zero disables prediction while retaining the visual detector.
    maximum_prediction_seconds: float = Field(default=0.4, ge=0.0)
    # Favor recent motion while reducing small contour-center fluctuations.
    velocity_smoothing: float = Field(default=0.7, gt=0.0, le=1.0)


class PreviewConfig(BaseModel):
    """Configure the optional OpenCV preview and terminal progress.

    :param enabled: Enable or disable live preview.
    :type enabled: bool
    :param every_n_frames: Refresh preview every N processed frames.
    :type every_n_frames: int
    :param width: Maximum preview width in pixels.
    :type width: int
    :param progress_every: Update textual progress every N frames.
    :type progress_every: int
    """

    # The preview refresh rate is independent of the encoded frame rate.
    enabled: bool = False
    every_n_frames: int = Field(default=3, ge=1)
    width: int = Field(default=1000, ge=100)
    progress_every: int = Field(default=20, ge=1)


class DrawingConfig(BaseModel):
    """Configure colors used for visualization.

    OpenCV uses BGR rather than RGB.

    :param table_color: Color of the detected baby-foot outline.
    :type table_color: BGRColor
    :param ball_color: Yellow color used for the detected ball.
    :type ball_color: BGRColor
    :param candidate_color: Color used for secondary ball candidates.
    :type candidate_color: BGRColor
    :param center_color: Color of the detected ball center.
    :type center_color: BGRColor
    :param prediction_color: Color of the estimated ball and direction arrow.
    :type prediction_color: BGRColor
    """

    # Drawing colors use BGR order; detector thresholds use RGB order.
    table_color: BGRColor = (255, 255, 0)
    ball_color: BGRColor = (0, 255, 255)
    draw_candidates: bool = True
    candidate_color: BGRColor = (0, 165, 255)
    center_color: BGRColor = (0, 0, 255)
    prediction_color: BGRColor = (255, 0, 255)


class ApplicationConfig(BaseModel):
    """Global application configuration.

    :param video_path: Source video path.
    :type video_path: Path
    :param output_path: Destination video path.
    :type output_path: Path
    :param max_frames: Optional maximum number of frames to process.
    :type max_frames: int | None
    :param table: Baby-foot detector configuration.
    :type table: TableDetectorConfig
    :param ball: Ball detector configuration.
    :type ball: BallDetectorConfig
    :param tracking: Motion prediction configuration.
    :type tracking: BallTrackerConfig
    :param preview: Window preview configuration.
    :type preview: PreviewConfig
    :param drawing: Rendering configuration.
    :type drawing: DrawingConfig
    """

    video_path: Path = Path("video.mp4")
    # Use a separate directory to preserve the notebook's historical output.
    output_path: Path = Path("output/tracking.mp4")
    max_frames: int | None = Field(default=None, ge=1)
    table: TableDetectorConfig = TableDetectorConfig()
    ball: BallDetectorConfig = BallDetectorConfig()
    tracking: BallTrackerConfig = BallTrackerConfig()
    preview: PreviewConfig = PreviewConfig()
    drawing: DrawingConfig = DrawingConfig()
