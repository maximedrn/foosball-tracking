"""Centralize display labels, console messages and application errors."""

from typing import Final

# Video overlays keep their formatting here; renderers supply measured values.
TABLE_LABEL: Final[str] = "BABY-FOOT"
BALL_DETECTED_LABEL: Final[str] = "BALL DETECTED"
BALL_NOT_DETECTED_LABEL: Final[str] = "BALL NOT DETECTED"
BALL_ESTIMATED_LABEL: Final[str] = "BALL ESTIMATED"
BALL_DETAILS_TEMPLATE: Final[str] = "BALL C={circularity:.2f} r={radius:.1f}"
BALL_ESTIMATE_TEMPLATE: Final[str] = "ESTIMATED (+{missing_seconds:.2f}s)"
FRAME_COUNTER_TEMPLATE: Final[str] = "Frame {frame_number}/{frame_count}"
DETECTION_RATE_TEMPLATE: Final[str] = (
    "Detected: {detected_frames}/{processed_frames} ({detection_rate:.1f}%)"
)
TRACKING_RATE_TEMPLATE: Final[str] = (
    "Estimated: {prediction_rate:.1f}% | Tracked: {coverage_rate:.1f}%"
)
PREVIEW_WINDOW_TITLE: Final[str] = "Foosball tracking - Q or Escape to stop"

# Command-line help describes the defaults and optional processing controls.
CLI_DESCRIPTION: Final[str] = (
    "Detect the foosball table and its yellow ball in a video."
)
CLI_VIDEO_HELP: Final[str] = "source video (video.mp4 by default)"
CLI_OUTPUT_HELP: Final[str] = "output MP4 (output/tracking.mp4 by default)"
CLI_PREVIEW_HELP: Final[str] = (
    "open a preview window; Q or Escape stops processing"
)
CLI_MAX_FRAMES_HELP: Final[str] = "process at most this many frames"
CLI_CONFIG_HELP: Final[str] = (
    "read detector and display settings from a JSON or JSONC file"
)

# Named placeholders keep callers independent of the displayed word order.
ERROR_MESSAGE_TEMPLATE: Final[str] = "Error: {error}"
PROCESSING_INTERRUPTED_MESSAGE: Final[str] = (
    "Processing interrupted; video resources released."
)
PROCESSED_FRAMES_TEMPLATE: Final[str] = "Frames processed: {processed_frames}"
DETECTION_SUMMARY_TEMPLATE: Final[str] = (
    "Ball detected: {detected_frames} ({detection_rate:.1f}%)"
)
PREDICTION_SUMMARY_TEMPLATE: Final[str] = (
    "Ball estimated: {predicted_frames} ({prediction_rate:.1f}%)"
)
COVERAGE_SUMMARY_TEMPLATE: Final[str] = (
    "Ball detected or estimated: {coverage_rate:.1f}%"
)
OUTPUT_VIDEO_TEMPLATE: Final[str] = "Output video: {path}"
PROCESSING_PROGRESS_TEMPLATE: Final[str] = (
    "Frames: {current}/{total} | ball: {detected_frames} "
    "({detection_rate:.1f}%) | estimated: {predicted_frames} "
    "({prediction_rate:.1f}%) | tracked: {coverage_rate:.1f}%"
)
UNKNOWN_FRAME_COUNT: Final[str] = "?"

# Video errors are shared by processing exceptions and their CLI presentation.
INPUT_OUTPUT_PATH_ERROR: Final[str] = (
    "Input and output video paths must be different"
)
OUTPUT_EXISTS_ERROR_TEMPLATE: Final[str] = "Output already exists: {path}"
EMPTY_VIDEO_ERROR: Final[str] = "The source video contains no decodable frames"
INPUT_NOT_FOUND_ERROR_TEMPLATE: Final[str] = "Input video not found: {path}"
VIDEO_OPEN_ERROR_TEMPLATE: Final[str] = "Cannot open video: {path}"
VIDEO_METADATA_ERROR: Final[str] = (
    "Source video has invalid dimensions or frame rate"
)
VIDEO_WRITER_ERROR_TEMPLATE: Final[str] = "Cannot create output video: {path}"

# Configuration validation reports invalid bounds before OpenCV is called.
HSV_BOUNDS_ERROR: Final[str] = (
    "HSV bounds must be ordered and within (179, 255, 255)"
)
AREA_BOUNDS_ERROR: Final[str] = (
    "maximum_area must be greater than minimum_area"
)
RADIUS_BOUNDS_ERROR: Final[str] = (
    "maximum_radius must be greater than minimum_radius"
)
KERNEL_SIZE_ERROR: Final[str] = "OpenCV kernel sizes must be odd"
