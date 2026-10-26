"""Expose shared image types and video-processing results."""

from foosball_tracking.models.entities import (
    BallCandidate,
    BallDetection,
    BallPrediction,
    BallTrack,
    BGRColor,
    Box,
    Contour,
    Image,
    Point,
    RGBColor,
    RotatedRectangle,
    RunSummary,
    TableDetection,
    VideoMetadata,
)

__all__ = [
    "BGRColor",
    "BallCandidate",
    "BallDetection",
    "BallPrediction",
    "BallTrack",
    "Box",
    "Contour",
    "Image",
    "Point",
    "RGBColor",
    "RotatedRectangle",
    "RunSummary",
    "TableDetection",
    "VideoMetadata",
]
