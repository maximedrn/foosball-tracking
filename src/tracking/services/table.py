"""Table for the foosball video detector."""

from __future__ import annotations

from typing import Self, cast

from cv2 import (
    CHAIN_APPROX_SIMPLE,
    COLOR_BGR2RGB,
    INTER_AREA,
    MORPH_CLOSE,
    MORPH_ELLIPSE,
    RETR_EXTERNAL,
    boxPoints,
    contourArea,
    cvtColor,
    findContours,
    getStructuringElement,
    inRange,
    minAreaRect,
    morphologyEx,
    resize,
)
from numpy import clip, float32, int32, mean
from numpy.typing import NDArray

from tracking.config import TableDetectorConfig
from tracking.models import (
    Box,
    Contour,
    Image,
    RotatedRectangle,
    TableDetection,
)


class TableDetector:
    """Detect the baby-foot from its green playing surface."""

    def __init__(self: Self, config: TableDetectorConfig) -> None:
        """Initialize the detector.

        :param config: Validated table detector configuration.
        :type config: TableDetectorConfig
        :return: None.
        :rtype: None
        """
        self.config: TableDetectorConfig = config

    def detect(self: Self, frame: Image) -> TableDetection | None:
        """Detect the baby-foot in one video frame.

        The frame is first downscaled for performance. The green playing
        surface is segmented in RGB space, the largest green contour is
        retained, and ``cv2.minAreaRect`` estimates its orientation.

        :param frame: BGR input image.
        :type frame: Image
        :return: A ``TableDetection`` containing the playfield and expanded
            table
            rectangles, or ``None`` if no plausible table exists.
        :rtype: TableDetection | None
        """
        # Detect the large field at lower resolution to reduce processing cost.
        small_frame: Image = self._resize_for_detection(frame)
        rgb: Image = cast(Image, cvtColor(small_frame, COLOR_BGR2RGB))
        mask: Image = cast(
            Image,
            inRange(
                rgb,
                self.config.rgb.lower_array(),
                self.config.rgb.upper_array(),
            ),
        )
        # Join green regions separated by thin lines, then keep the largest
        # one.
        mask = self._close_mask(mask)
        contour: Contour | None = self._largest_contour(mask)
        if contour is None:
            return None
        if not self._is_large_enough(contour, small_frame):
            return None
        # Return both the playing surface and an estimate of the entire table.
        playfield_box: Box = self._contour_to_box(contour)
        table_box: Box = self._expand_box(
            playfield_box, frame.shape[1], frame.shape[0]
        )
        return TableDetection(playfield_box=playfield_box, table_box=table_box)

    def _resize_for_detection(self: Self, frame: Image) -> Image:
        """Downscale a frame before table detection.

        :param frame: Full-resolution BGR frame.
        :type frame: Image
        :return: Resized BGR frame.
        :rtype: Image
        """
        return cast(
            Image,
            resize(
                frame,
                None,
                fx=self.config.scale,
                fy=self.config.scale,
                interpolation=INTER_AREA,
            ),
        )

    def _close_mask(self: Self, mask: Image) -> Image:
        """Reconnect green regions split by field markings.

        :param mask: Binary playfield mask.
        :type mask: Image
        :return: Morphologically closed mask.
        :rtype: Image
        """
        kernel: Image = cast(
            Image,
            getStructuringElement(
                MORPH_ELLIPSE,
                (self.config.close_kernel_size, self.config.close_kernel_size),
            ),
        )
        # Closing fills small breaks in the segmented green surface.
        return cast(
            Image,
            morphologyEx(
                mask,
                MORPH_CLOSE,
                kernel,
                iterations=self.config.close_iterations,
            ),
        )

    @staticmethod
    def _largest_contour(mask: Image) -> Contour | None:
        """Find the largest connected contour.

        :param mask: Binary segmentation mask.
        :type mask: Image
        :return: Largest contour, or ``None`` if the mask is empty.
        :rtype: Contour | None
        """
        contours, _ = cast(
            tuple[tuple[Contour, ...], Image | None],
            findContours(mask, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE),
        )
        if not contours:
            return None
        return max(contours, key=contourArea)

    def _is_large_enough(self: Self, contour: Contour, image: Image) -> bool:
        """Check whether a contour can plausibly be the playfield.

        :param contour: Candidate green contour.
        :type contour: Contour
        :param image: Image on which the contour was detected.
        :type image: Image
        :return: ``True`` when the contour occupies a sufficiently large
            fraction of the
            image.
        :rtype: bool
        """
        # A relative area threshold works across different video resolutions.
        contour_area: float = contourArea(contour)
        image_area: float = float(image.shape[0] * image.shape[1])
        return contour_area / image_area >= self.config.minimum_area_ratio

    def _contour_to_box(self: Self, contour: Contour) -> Box:
        """Convert a contour to a full-resolution oriented rectangle.

        :param contour: Contour detected on the downscaled frame.
        :type contour: Contour
        :return: Four rectangle corners in full-resolution coordinates.
        :rtype: Box
        """
        # Follow the field's orientation instead of an axis-aligned rectangle.
        rectangle: RotatedRectangle = minAreaRect(contour)
        box: NDArray[float32] = cast(NDArray[float32], boxPoints(rectangle))
        # Undo the detection scale to recover full-resolution coordinates.
        box /= self.config.scale
        return box.astype(int32)

    def _expand_box(
        self: Self, box: Box, frame_width: int, frame_height: int
    ) -> Box:
        """Expand the playfield rectangle to approximate the whole table.

        :param box: Four playfield corners.
        :type box: Box
        :param frame_width: Full image width.
        :type frame_width: int
        :param frame_height: Full image height.
        :type frame_height: int
        :return: Expanded and clipped four-corner rectangle.
        :rtype: Box
        """
        box_float: NDArray[float32] = box.astype(float32)
        center: NDArray[float32] = mean(box_float, axis=0)
        # Move each corner away from the center using the same expansion
        # factor.
        expanded: NDArray[float32] = cast(
            NDArray[float32],
            center + (box_float - center) * self.config.box_expansion,
        )
        # Keep the expanded outline within the image before integer conversion.
        expanded[:, 0] = clip(expanded[:, 0], 0, frame_width - 1)
        expanded[:, 1] = clip(expanded[:, 1], 0, frame_height - 1)
        return expanded.astype(int32)
