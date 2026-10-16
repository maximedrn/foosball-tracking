"""Extrapolate recent ball motion through short visual occlusions."""

from typing import Self

from cv2 import pointPolygonTest

from foosball_tracking.config import BallTrackerConfig
from foosball_tracking.models import (
    BallCandidate,
    BallPrediction,
    BallTrack,
    Box,
    Point,
)


class BallTracker:
    """Track observed velocity without feeding predictions back as evidence."""

    def __init__(self: Self, config: BallTrackerConfig, fps: float) -> None:
        """Initialize motion state for one video.

        :param config: Prediction duration and velocity smoothing settings.
        :type config: BallTrackerConfig
        :param fps: Validated positive source frame rate.
        :type fps: float
        :return: None.
        :rtype: None
        """
        self.config: BallTrackerConfig = config
        self.fps: float = fps
        self._last_ball: BallCandidate | None = None
        self._velocity: tuple[float, float] | None = None
        self._missing_frames: int = 0

    def update(
        self: Self, ball: BallCandidate | None, playfield_box: Box | None
    ) -> BallTrack:
        """Prefer visual measurements and extrapolate only when they disappear.

        :param ball: Current visually detected ball, or None during occlusion.
        :type ball: BallCandidate | None
        :param playfield_box: Playing-surface polygon in frame coordinates.
        :type playfield_box: Box | None
        :return: A real ball, a bounded prediction, or an empty track.
        :rtype: BallTrack
        """
        if playfield_box is None:
            self._reset()
            return BallTrack()
        if ball is not None:
            # A new observation immediately replaces the estimated position.
            self._observe(ball)
            return BallTrack(ball=ball)
        if self._last_ball is None:
            return BallTrack()

        self._missing_frames += 1
        elapsed: float = self._missing_frames / self.fps
        if elapsed > self.config.maximum_prediction_seconds:
            # Forget stale motion before trying to acquire a new trajectory.
            self._reset()
            return BallTrack()
        if self._velocity is None:
            # One observation gives a position but no direction or speed.
            return BallTrack()

        # Constant-velocity model: p(t) = last_observed_position + v * t.
        # Always start from the last real center, never from a prediction.
        x: float = self._last_ball.center[0] + self._velocity[0] * elapsed
        y: float = self._last_ball.center[1] + self._velocity[1] * elapsed
        center: Point = (round(x), round(y))
        if pointPolygonTest(playfield_box, (x, y), False) < 0:
            # Test the polygon itself: a rotated field is not its bounding box.
            # Do not invent a bounce or clamp the ball against the boundary.
            self._reset()
            return BallTrack()
        return BallTrack(
            prediction=BallPrediction(
                center=center,
                radius=self._last_ball.radius,
                origin=self._last_ball.center,
                missing_seconds=elapsed,
            )
        )

    def _observe(self: Self, ball: BallCandidate) -> None:
        """Update velocity from two real observations and their elapsed time.

        :param ball: Newly measured ball candidate.
        :type ball: BallCandidate
        :return: None.
        :rtype: None
        """
        if self._last_ball is not None:
            # Include missing frames when a measurement follows an occlusion.
            elapsed: float = (self._missing_frames + 1) / self.fps
            measured_velocity: tuple[float, float] = (
                (ball.center[0] - self._last_ball.center[0]) / elapsed,
                (ball.center[1] - self._last_ball.center[1]) / elapsed,
            )
            if self._velocity is None:
                self._velocity = measured_velocity
            else:
                # Exponential smoothing: v = alpha * measured + (1-alpha) * v.
                weight: float = self.config.velocity_smoothing
                self._velocity = (
                    weight * measured_velocity[0]
                    + (1.0 - weight) * self._velocity[0],
                    weight * measured_velocity[1]
                    + (1.0 - weight) * self._velocity[1],
                )
        self._last_ball = ball
        self._missing_frames = 0

    def _reset(self: Self) -> None:
        """Discard motion after expiry or departure from the playing surface.

        :return: None.
        :rtype: None
        """
        self._last_ball = None
        self._velocity = None
        self._missing_frames = 0
