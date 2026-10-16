"""Rendering for the foosball video detector."""

from __future__ import annotations

from typing import Self

from cv2 import (
    FONT_HERSHEY_SIMPLEX,
    LINE_AA,
    arrowedLine,
    circle,
    polylines,
    putText,
    rectangle,
)
from numpy import amin

from foosball_tracking.config import DrawingConfig
from foosball_tracking.models import (
    BallCandidate,
    BallDetection,
    BallPrediction,
    BallTrack,
    BGRColor,
    Image,
    RunSummary,
    TableDetection,
)
from foosball_tracking.utils.messages import (
    BALL_DETAILS_TEMPLATE,
    BALL_DETECTED_LABEL,
    BALL_ESTIMATE_TEMPLATE,
    BALL_ESTIMATED_LABEL,
    BALL_NOT_DETECTED_LABEL,
    DETECTION_RATE_TEMPLATE,
    FRAME_COUNTER_TEMPLATE,
    TABLE_LABEL,
    TRACKING_RATE_TEMPLATE,
)


class FrameRenderer:
    """Draw ball observations, predictions and cumulative frame percentages."""

    def __init__(self: Self, config: DrawingConfig) -> None:
        """Initialize the renderer.

        :param config: Visualization configuration.
        :type config: DrawingConfig
        :return: None.
        :rtype: None
        """
        self.config: DrawingConfig = config

    def render(
        self: Self,
        frame: Image,
        table: TableDetection | None,
        ball_detection: BallDetection | None,
        track: BallTrack,
        summary: RunSummary,
        frame_count: int,
    ) -> Image:
        """Render all detections on one frame.

        :param frame: Original BGR frame.
        :type frame: Image
        :param table: Current table detection.
        :type table: TableDetection | None
        :param ball_detection: Current ball detection result.
        :type ball_detection: BallDetection | None
        :param track: Current observed ball or estimated position.
        :type track: BallTrack
        :param summary: Counts including the frame currently being rendered.
        :type summary: RunSummary
        :param frame_count: Expected number of frames to process.
        :type frame_count: int
        :return: Annotated BGR frame.
        :rtype: Image
        """
        # Keep drawing separate from detection: overlays must not enter HSV
        # masks.
        result: Image = frame.copy()
        if table is not None:
            self._draw_table(result, table)
        if ball_detection is not None:
            self._draw_candidates(result, ball_detection.candidates)
        if track.ball is not None:
            self._draw_ball(result, track.ball)
        elif track.prediction is not None:
            self._draw_prediction(result, track.prediction)
        self._draw_status(result, track, summary, frame_count)
        self._draw_progress(result, summary.processed_frames - 1, frame_count)
        return result

    def _draw_table(
        self: Self, frame: Image, detection: TableDetection
    ) -> None:
        """Draw the detected baby-foot boundary.

        :param frame: Frame modified in place.
        :type frame: Image
        :param detection: Current table detection.
        :type detection: TableDetection
        :return: None.
        :rtype: None
        """
        polylines(
            frame,
            [detection.table_box],
            True,
            self.config.table_color,
            3,
            LINE_AA,
        )
        # Anchor the label above the table and keep it inside the visible
        # image.
        x: int = int(amin(detection.table_box[:, 0]))
        y: int = int(amin(detection.table_box[:, 1]))
        putText(
            frame,
            TABLE_LABEL,
            (x, max(y - 10, 30)),
            FONT_HERSHEY_SIMPLEX,
            0.8,
            self.config.table_color,
            2,
            LINE_AA,
        )

    def _draw_candidates(
        self: Self, frame: Image, candidates: list[BallCandidate]
    ) -> None:
        """Draw secondary valid ball candidates.

        :param frame: Frame modified in place.
        :type frame: Image
        :param candidates: Candidates ordered from best to worst.
        :type candidates: list[BallCandidate]
        :return: None.
        :rtype: None
        """
        # The first candidate is highlighted separately as the selected ball.
        for candidate in candidates[1:]:
            circle(
                frame,
                candidate.center,
                round(candidate.radius),
                self.config.candidate_color,
                1,
                LINE_AA,
            )

    def _draw_ball(self: Self, frame: Image, ball: BallCandidate) -> None:
        """Highlight the best ball candidate in yellow.

        :param frame: Frame modified in place.
        :type frame: Image
        :param ball: Selected ball candidate.
        :type ball: BallCandidate
        :return: None.
        :rtype: None
        """
        # Add an outer ring and center dot without covering the whole ball.
        radius: int = round(ball.radius)
        circle(
            frame, ball.center, radius + 4, self.config.ball_color, 3, LINE_AA
        )
        circle(frame, ball.center, 3, self.config.center_color, -1, LINE_AA)
        putText(
            frame,
            BALL_DETAILS_TEMPLATE.format(
                circularity=ball.circularity, radius=ball.radius
            ),
            (ball.center[0] + 15, max(ball.center[1] - 15, 30)),
            FONT_HERSHEY_SIMPLEX,
            0.55,
            self.config.ball_color,
            2,
            LINE_AA,
        )

    def _draw_prediction(
        self: Self, frame: Image, prediction: BallPrediction
    ) -> None:
        """Draw an estimated position with a distinct ring and motion arrow.

        :param frame: Frame modified in place.
        :type frame: Image
        :param prediction: Bounded estimate since the last visual observation.
        :type prediction: BallPrediction
        :return: None.
        :rtype: None
        """
        # The arrow links the last measured center to the current estimate.
        # A stationary ball needs only a ring; a zero-length arrow adds noise.
        if prediction.origin != prediction.center:
            arrowedLine(
                frame,
                prediction.origin,
                prediction.center,
                self.config.prediction_color,
                2,
                LINE_AA,
                tipLength=0.2,
            )
        circle(
            frame,
            prediction.center,
            round(prediction.radius) + 4,
            self.config.prediction_color,
            2,
            LINE_AA,
        )
        putText(
            frame,
            BALL_ESTIMATE_TEMPLATE.format(
                missing_seconds=prediction.missing_seconds
            ),
            (prediction.center[0] + 15, max(prediction.center[1] - 15, 30)),
            FONT_HERSHEY_SIMPLEX,
            0.55,
            self.config.prediction_color,
            2,
            LINE_AA,
        )

    def _draw_status(
        self: Self,
        frame: Image,
        track: BallTrack,
        summary: RunSummary,
        frame_count: int,
    ) -> None:
        """Draw status, frame counter and rates over all processed frames.

        :param frame: Frame modified in place.
        :type frame: Image
        :param track: Observed ball or predicted position in this frame.
        :type track: BallTrack
        :param summary: Cumulative counts including the current frame.
        :type summary: RunSummary
        :param frame_count: Expected number of frames to process.
        :type frame_count: int
        :return: None.
        :rtype: None
        """
        status: str = BALL_NOT_DETECTED_LABEL
        status_color: BGRColor = (0, 0, 255)
        if track.ball is not None:
            status = BALL_DETECTED_LABEL
            status_color = (0, 255, 0)
        elif track.prediction is not None:
            status = BALL_ESTIMATED_LABEL
            status_color = self.config.prediction_color
        putText(
            frame,
            status,
            (20, 40),
            FONT_HERSHEY_SIMPLEX,
            1.0,
            status_color,
            2,
            LINE_AA,
        )
        putText(
            frame,
            FRAME_COUNTER_TEMPLATE.format(
                frame_number=summary.processed_frames, frame_count=frame_count
            ),
            (20, 70),
            FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            LINE_AA,
        )
        # These are cumulative frame percentages, not prediction confidence.
        putText(
            frame,
            DETECTION_RATE_TEMPLATE.format(
                detected_frames=summary.detected_frames,
                processed_frames=summary.processed_frames,
                detection_rate=summary.detection_rate,
            ),
            (20, 100),
            FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            LINE_AA,
        )
        putText(
            frame,
            TRACKING_RATE_TEMPLATE.format(
                prediction_rate=summary.prediction_rate,
                coverage_rate=summary.coverage_rate,
            ),
            (20, 130),
            FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            LINE_AA,
        )

    @staticmethod
    def _draw_progress(
        frame: Image, frame_index: int, frame_count: int
    ) -> None:
        """Draw a processing-progress bar directly on the video.

        :param frame: Frame modified in place.
        :type frame: Image
        :param frame_index: Current zero-based frame index.
        :type frame_index: int
        :param frame_count: Total number of frames.
        :type frame_count: int
        :return: None.
        :rtype: None
        """
        # Convert the zero-based index into the fraction of completed frames.
        # A denominator of one also handles videos with an unknown frame count.
        progress: float = (frame_index + 1) / max(frame_count, 1)
        x: int = 20
        y: int = frame.shape[0] - 25
        width: int = frame.shape[1] - 40
        height: int = 8
        rectangle(frame, (x, y), (x + width, y + height), (80, 80, 80), 1)
        rectangle(
            frame,
            (x, y),
            (x + int(width * progress), y + height),
            (255, 255, 255),
            -1,
        )
