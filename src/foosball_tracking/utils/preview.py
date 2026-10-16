"""Display an optional OpenCV window independently from video encoding."""

from typing import Self, cast

from cv2 import INTER_AREA, destroyWindow, imshow, resize, waitKey

from foosball_tracking.config import PreviewConfig
from foosball_tracking.models import Image
from foosball_tracking.utils.messages import PREVIEW_WINDOW_TITLE


class VideoPreview:
    """Manage the preview window created by this application."""

    def __init__(self: Self, config: PreviewConfig) -> None:
        """Store preview settings without opening a window.

        :param config: Validated preview settings.
        :type config: PreviewConfig
        :return: None.
        :rtype: None
        """
        self.config: PreviewConfig = config
        self._window_open: bool = False
        self._window_name: str = PREVIEW_WINDOW_TITLE

    def update(self: Self, frame: Image) -> bool:
        """Display a scaled frame and check whether the user wants to stop.

        :param frame: Annotated BGR frame.
        :type frame: Image
        :return: True when Q or Escape was pressed.
        :rtype: bool
        """
        # Resize only the display image; encoding keeps the original
        # resolution.
        preview: Image = frame
        if frame.shape[1] > self.config.width:
            height: int = max(
                1, round(frame.shape[0] * self.config.width / frame.shape[1])
            )
            preview = cast(
                Image,
                resize(
                    frame,
                    (self.config.width, height),
                    interpolation=INTER_AREA,
                ),
            )
        imshow(self._window_name, preview)
        self._window_open = True
        # waitKey also processes the window events; Escape has key code 27.
        return waitKey(1) & 0xFF in (ord("q"), 27)

    def close(self: Self) -> None:
        """Close the application's preview window if one was opened.

        :return: None.
        :rtype: None
        """
        if self._window_open:
            destroyWindow(self._window_name)
            self._window_open = False
