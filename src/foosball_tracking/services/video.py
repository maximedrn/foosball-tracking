"""Read videos, detect the table and ball, and encode annotated frames."""

from math import isfinite
from typing import Self, cast

from cv2 import (
    CAP_PROP_FPS,
    CAP_PROP_FRAME_COUNT,
    CAP_PROP_FRAME_HEIGHT,
    CAP_PROP_FRAME_WIDTH,
    VideoCapture,
    VideoWriter,
)

from foosball_tracking.config import ApplicationConfig
from foosball_tracking.models import (
    BallDetection,
    BallTrack,
    Image,
    RunSummary,
    TableDetection,
    VideoMetadata,
)
from foosball_tracking.services.ball import BallDetector
from foosball_tracking.services.table import TableDetector
from foosball_tracking.services.tracking import BallTracker
from foosball_tracking.utils.messages import (
    EMPTY_VIDEO_ERROR,
    INPUT_NOT_FOUND_ERROR_TEMPLATE,
    INPUT_OUTPUT_PATH_ERROR,
    PROCESSING_PROGRESS_TEMPLATE,
    UNKNOWN_FRAME_COUNT,
    VIDEO_METADATA_ERROR,
    VIDEO_OPEN_ERROR_TEMPLATE,
    VIDEO_WRITER_ERROR_TEMPLATE,
)
from foosball_tracking.utils.preview import VideoPreview
from foosball_tracking.utils.rendering import FrameRenderer


class VideoProcessor:
    """Apply the detectors and renderer to each decoded video frame."""

    def __init__(self: Self, config: ApplicationConfig) -> None:
        """Create detectors and preview state for one processing run.

        :param config: Validated application configuration.
        :type config: ApplicationConfig
        :return: None.
        :rtype: None
        """
        self.config: ApplicationConfig = config
        self.table_detector: TableDetector = TableDetector(config.table)
        self.ball_detector: BallDetector = BallDetector(config.ball)
        self.renderer: FrameRenderer = FrameRenderer(config.drawing)
        self.preview: VideoPreview = VideoPreview(config.preview)

    def run(self: Self) -> RunSummary:
        """Process the source video and release resources even on failure.

        :return: Counts of written frames and frames with a detected ball.
        :rtype: RunSummary
        :raises ValueError: If input and output refer to the same file.
        :raises FileExistsError: If the output file already exists.
        :raises FileNotFoundError: If the input file does not exist.
        :raises RuntimeError: If the video cannot be decoded or encoded.
        """
        # Resolve paths before comparison so relative paths cannot hide the
        # input.
        if (
            self.config.video_path.resolve()
            == self.config.output_path.resolve()
        ):
            raise ValueError(INPUT_OUTPUT_PATH_ERROR)
        if self.config.output_path.exists():
            self.config.output_path.unlink()
        capture: VideoCapture = self._open_capture()
        writer: VideoWriter | None = None
        try:
            metadata: VideoMetadata = self._read_metadata(capture)
            # Decode once before creating an output for a possibly empty
            # source.
            success, frame = cast(tuple[bool, Image], capture.read())
            if not success:
                raise RuntimeError(EMPTY_VIDEO_ERROR)
            writer = self._create_writer(metadata)
            summary: RunSummary = self._process_frames(
                capture, writer, metadata, frame
            )
        finally:
            # Releasing the writer also finalizes the MP4 container on
            # interruption.
            capture.release()
            if writer is not None:
                writer.release()
            self.preview.close()
        return summary

    def _process_frames(
        self: Self,
        capture: VideoCapture,
        writer: VideoWriter,
        metadata: VideoMetadata,
        frame: Image,
    ) -> RunSummary:
        """Process the first decoded frame and all remaining requested frames.

        :param capture: Open source-video capture.
        :type capture: VideoCapture
        :param writer: Open annotated-video writer.
        :type writer: VideoWriter
        :param metadata: Validated source-video properties.
        :type metadata: VideoMetadata
        :param frame: First decoded BGR frame.
        :type frame: Image
        :return: Counts collected during the processing loop.
        :rtype: RunSummary
        """
        table: TableDetection | None = None
        frame_index: int = 0
        detected_frames: int = 0
        predicted_frames: int = 0
        # A fresh tracker prevents motion leaking between separate runs.
        tracker: BallTracker = BallTracker(self.config.tracking, metadata.fps)
        # The requested limit affects progress; decoding still stops at actual
        # EOF.
        total: int = metadata.frame_count
        if self.config.max_frames is not None:
            total = (
                min(total, self.config.max_frames)
                if total > 0
                else self.config.max_frames
            )
        while True:
            # Reuse the last valid field between scheduled table detections.
            if (
                table is None
                or frame_index % self.config.table.detection_every == 0
            ):
                new_table: TableDetection | None = self.table_detector.detect(
                    frame
                )
                if new_table is not None:
                    table = new_table
            # Ball detection runs on every frame with a known playing surface.
            ball_detection: BallDetection | None = None
            if table is not None:
                ball_detection = self.ball_detector.detect(
                    frame, table.playfield_box
                )
            # Predict only after a visual disappearance; real detections keep
            # priority and are counted separately from estimated positions.
            track: BallTrack = tracker.update(
                ball_detection.ball if ball_detection is not None else None,
                table.playfield_box if table is not None else None,
            )
            if track.ball is not None:
                detected_frames += 1
            elif track.prediction is not None:
                predicted_frames += 1
            summary: RunSummary = RunSummary(
                processed_frames=frame_index + 1,
                detected_frames=detected_frames,
                predicted_frames=predicted_frames,
            )
            # Draw on a copy, leaving the source pixels available to the
            # detectors.
            result: Image = self.renderer.render(
                frame, table, ball_detection, track, summary, total
            )
            writer.write(result)
            # Skipping preview refreshes never skips frames in the output
            # video.
            should_stop: bool = False
            if (
                self.config.preview.enabled
                and frame_index % self.config.preview.every_n_frames == 0
            ):
                should_stop = self.preview.update(result)
            frame_index += 1
            if frame_index % self.config.preview.progress_every == 0:
                print(
                    PROCESSING_PROGRESS_TEMPLATE.format(
                        current=frame_index,
                        total=total or UNKNOWN_FRAME_COUNT,
                        detected_frames=detected_frames,
                        detection_rate=summary.detection_rate,
                        predicted_frames=predicted_frames,
                        prediction_rate=summary.prediction_rate,
                        coverage_rate=summary.coverage_rate,
                    ),
                    flush=True,
                )
            if should_stop or (
                self.config.max_frames is not None
                and frame_index >= self.config.max_frames
            ):
                break
            # Read the next frame only after processing the current one.
            success, frame = cast(tuple[bool, Image], capture.read())
            if not success:
                break
        return summary

    def _open_capture(self: Self) -> VideoCapture:
        """Open the source video and check that it is readable.

        :return: An open source-video capture.
        :rtype: VideoCapture
        """
        if not self.config.video_path.is_file():
            raise FileNotFoundError(
                INPUT_NOT_FOUND_ERROR_TEMPLATE.format(
                    path=self.config.video_path
                )
            )
        capture: VideoCapture = VideoCapture(str(self.config.video_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                VIDEO_OPEN_ERROR_TEMPLATE.format(path=self.config.video_path)
            )
        return capture

    @staticmethod
    def _read_metadata(capture: VideoCapture) -> VideoMetadata:
        """Read source dimensions, frame count and frame rate.

        :param capture: Open source-video capture.
        :type capture: VideoCapture
        :return: Validated video metadata.
        :rtype: VideoMetadata
        """
        # Reject invalid metadata before configuring the encoder.
        fps: float = capture.get(CAP_PROP_FPS)
        width: int = int(capture.get(CAP_PROP_FRAME_WIDTH))
        height: int = int(capture.get(CAP_PROP_FRAME_HEIGHT))
        if not isfinite(fps) or fps <= 0 or width <= 0 or height <= 0:
            raise RuntimeError(VIDEO_METADATA_ERROR)
        return VideoMetadata(
            frame_count=max(0, int(capture.get(CAP_PROP_FRAME_COUNT))),
            fps=fps,
            width=width,
            height=height,
        )

    def _create_writer(self: Self, metadata: VideoMetadata) -> VideoWriter:
        """Create the MP4 writer without replacing an existing file.

        :param metadata: Validated source-video properties.
        :type metadata: VideoMetadata
        :return: An open annotated-video writer.
        :rtype: VideoWriter
        """
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        # Reserve a new file because OpenCV normally overwrites its
        # destination.
        self.config.output_path.touch(exist_ok=False)
        writer: VideoWriter = VideoWriter(
            str(self.config.output_path),
            VideoWriter.fourcc(*"mp4v"),
            metadata.fps,
            (metadata.width, metadata.height),
        )
        if not writer.isOpened():
            writer.release()
            self.config.output_path.unlink()
            raise RuntimeError(
                VIDEO_WRITER_ERROR_TEMPLATE.format(
                    path=self.config.output_path
                )
            )
        return writer
