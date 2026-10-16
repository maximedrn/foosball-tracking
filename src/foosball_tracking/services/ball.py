"""Ball for the foosball video detector."""

from __future__ import annotations

from math import pi
from typing import Self, cast

from cv2 import (
    CHAIN_APPROX_SIMPLE,
    COLOR_BGR2HSV,
    MORPH_CLOSE,
    MORPH_ELLIPSE,
    RETR_EXTERNAL,
    GaussianBlur,
    arcLength,
    bitwise_and,
    boundingRect,
    contourArea,
    cvtColor,
    fillConvexPoly,
    findContours,
    getStructuringElement,
    inRange,
    minEnclosingCircle,
    morphologyEx,
)
from numpy import array, int32, uint8, zeros

from foosball_tracking.config import BallDetectorConfig
from foosball_tracking.models import (
    BallCandidate,
    BallDetection,
    Box,
    Contour,
    Image,
    Point,
)


class BallDetector:
    """Detect a yellow ball from color and geometric properties."""

    def __init__(self: Self, config: BallDetectorConfig) -> None:
        """Initialize the detector.

        :param config: Validated ball detector configuration.
        :type config: BallDetectorConfig
        :return: None.
        :rtype: None
        """
        self.config: BallDetectorConfig = config

    def detect(self: Self, frame: Image, playfield_box: Box) -> BallDetection:
        """Detect the ball inside the baby-foot playfield.

        :param frame: Full BGR video frame.
        :type frame: Image
        :param playfield_box: Four corners of the detected playing area.
        :type playfield_box: Box
        :return: Ball detection result containing the best candidate, every
            accepted
            candidate and the binary segmentation mask.
        :rtype: BallDetection
        """
        # Process the field's bounding region instead of the whole image.
        x, y, width, height = self._bounding_roi(frame, playfield_box)
        roi: Image = frame[y : y + height, x : x + width]
        if roi.size == 0:
            return BallDetection(
                ball=None, candidates=[], mask=zeros((1, 1), dtype=uint8)
            )
        # The polygon excludes corners outside the rotated playing surface.
        table_mask: Image = self._create_playfield_mask(
            roi, playfield_box, x, y
        )
        color_mask: Image = self._create_color_mask(roi, table_mask)
        candidates: list[BallCandidate] = self._extract_candidates(
            color_mask, x, y
        )
        # Keep every valid candidate, then select the best geometric match.
        candidates.sort(key=BallDetector._candidate_priority, reverse=True)
        ball: BallCandidate | None = candidates[0] if candidates else None
        return BallDetection(ball=ball, candidates=candidates, mask=color_mask)

    @staticmethod
    def _bounding_roi(
        frame: Image, playfield_box: Box
    ) -> tuple[int, int, int, int]:
        """Compute a clipped ROI enclosing the playfield.

        :param frame: Full input frame.
        :type frame: Image
        :param playfield_box: Four playfield corners.
        :type playfield_box: Box
        :return: Tuple ``(x, y, width, height)`` describing the clipped ROI.
        :rtype: tuple[int, int, int, int]
        """
        # Clip the crop to avoid indexing beyond the decoded frame.
        x, y, width, height = boundingRect(playfield_box)
        x = max(x, 0)
        y = max(y, 0)
        right: int = min(x + width, frame.shape[1])
        bottom: int = min(y + height, frame.shape[0])
        return (x, y, max(right - x, 0), max(bottom - y, 0))

    @staticmethod
    def _create_playfield_mask(
        roi: Image, playfield_box: Box, roi_x: int, roi_y: int
    ) -> Image:
        """Create a binary mask restricting detection to the playfield.

        :param roi: Cropped BGR region containing the playfield.
        :type roi: Image
        :param playfield_box: Global playfield coordinates.
        :type playfield_box: Box
        :param roi_x: Horizontal origin of the ROI.
        :type roi_x: int
        :param roi_y: Vertical origin of the ROI.
        :type roi_y: int
        :return: Binary mask containing the playfield polygon.
        :rtype: Image
        """
        mask: Image = zeros(roi.shape[:2], dtype=uint8)
        # Translate full-frame corners into the cropped image's coordinates.
        local_box: Box = playfield_box - array([roi_x, roi_y], dtype=int32)
        fillConvexPoly(mask, local_box, 255)
        return mask

    def _create_color_mask(
        self: Self, roi: Image, playfield_mask: Image
    ) -> Image:
        """Segment yellow pixels inside the playfield.

        :param roi: BGR region containing the playing field.
        :type roi: Image
        :param playfield_mask: Binary mask restricting valid pixels.
        :type playfield_mask: Image
        :return: Morphologically cleaned yellow segmentation mask.
        :rtype: Image
        """
        # Smooth compression noise before applying the configured HSV range.
        kernel_size: int = self.config.blur_kernel_size
        blurred: Image = cast(
            Image, GaussianBlur(roi, (kernel_size, kernel_size), 0)
        )
        hsv: Image = cast(Image, cvtColor(blurred, COLOR_BGR2HSV))
        mask: Image = cast(
            Image,
            inRange(
                hsv,
                self.config.hsv.lower_array(),
                self.config.hsv.upper_array(),
            ),
        )
        # A pixel must match the ball color and belong to the playing field.
        mask = cast(Image, bitwise_and(mask, playfield_mask))
        close_kernel: Image = cast(
            Image,
            getStructuringElement(
                MORPH_ELLIPSE,
                (self.config.close_kernel_size, self.config.close_kernel_size),
            ),
        )
        # Closing reconnects small gaps without changing the color thresholds.
        return cast(
            Image, morphologyEx(mask, MORPH_CLOSE, close_kernel, iterations=1)
        )

    def _extract_candidates(
        self: Self, mask: Image, roi_x: int, roi_y: int
    ) -> list[BallCandidate]:
        """Extract geometrically valid ball candidates.

        :param mask: Yellow binary segmentation mask.
        :type mask: Image
        :param roi_x: Global x-coordinate of the ROI origin.
        :type roi_x: int
        :param roi_y: Global y-coordinate of the ROI origin.
        :type roi_y: int
        :return: List of candidates satisfying all geometric constraints.
        :rtype: list[BallCandidate]
        """
        # External contours describe the visible colored blobs, ignoring holes.
        contours, _ = cast(
            tuple[tuple[Contour, ...], Image | None],
            findContours(mask, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE),
        )
        candidates: list[BallCandidate] = []
        for contour in contours:
            candidate: BallCandidate | None = self._contour_to_candidate(
                contour, roi_x, roi_y
            )
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    def _contour_to_candidate(
        self: Self, contour: Contour, roi_x: int, roi_y: int
    ) -> BallCandidate | None:
        """Validate a contour and convert it into a ball candidate.

        :param contour: Yellow contour detected in ROI coordinates.
        :type contour: Contour
        :param roi_x: Horizontal ROI offset in the original image.
        :type roi_x: int
        :param roi_y: Vertical ROI offset in the original image.
        :type roi_y: int
        :return: A valid ball candidate or ``None`` if the contour fails any
            geometric
            constraint.
        :rtype: BallCandidate | None
        """
        # Reject blobs that are too small or too large to represent the ball.
        area: float = contourArea(contour)
        if not self.config.minimum_area <= area <= self.config.maximum_area:
            return None
        perimeter: float = arcLength(contour, True)
        if perimeter <= 0.0:
            return None
        # Circularity = 4*pi*A/P²; an ideal circle has a value of one.
        circularity: float = 4.0 * pi * area / (perimeter * perimeter)
        if circularity < self.config.minimum_circularity:
            return None
        _, _, width, height = boundingRect(contour)
        if width <= 0 or height <= 0:
            return None
        # Elongated blobs usually come from reflections or field markings.
        aspect_ratio: float = max(width, height) / min(width, height)
        if aspect_ratio > self.config.maximum_aspect_ratio:
            return None
        local_center, radius = minEnclosingCircle(contour)
        if (
            not self.config.minimum_radius
            <= radius
            <= self.config.maximum_radius
        ):
            return None
        # A real ball should fill much of its enclosing circle, not just an
        # arc.
        enclosing_area: float = pi * radius * radius
        fill_ratio: float = (
            area / enclosing_area if enclosing_area > 0.0 else 0.0
        )
        if fill_ratio < self.config.minimum_fill_ratio:
            return None
        # Restore full-frame coordinates so the renderer can draw the marker.
        center: Point = (
            round(local_center[0]) + roi_x,
            round(local_center[1]) + roi_y,
        )
        score: float = self._candidate_score(circularity, fill_ratio, radius)
        return BallCandidate(
            center=center,
            radius=float(radius),
            area=area,
            circularity=circularity,
            aspect_ratio=aspect_ratio,
            fill_ratio=fill_ratio,
            score=score,
            contour=contour,
        )

    def _candidate_score(
        self: Self, circularity: float, fill_ratio: float, radius: float
    ) -> float:
        """Compute a likelihood score for a valid ball candidate.

        :param circularity: Candidate circularity.
        :type circularity: float
        :param fill_ratio: Fraction of its enclosing circle that is filled.
        :type fill_ratio: float
        :param radius: Candidate radius in pixels.
        :type radius: float
        :return: Larger score for candidates resembling the expected ball.
        :rtype: float
        """
        # Reward round, filled blobs whose radius matches the expected size.
        radius_error: float = abs(radius - self.config.expected_radius)
        radius_score: float = max(
            0.0, 1.0 - radius_error / self.config.expected_radius
        )
        return 4.0 * circularity + 3.0 * fill_ratio + 2.0 * radius_score

    @staticmethod
    def _candidate_priority(candidate: BallCandidate) -> float:
        """Expose the candidate score for descending sorting.

        :param candidate: Candidate to rank.
        :type candidate: BallCandidate
        :return: The geometric candidate score.
        :rtype: float
        """
        return candidate.score
