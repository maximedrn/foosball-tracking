"""Centralize figure labels, captions and review overlay text."""

from typing import Final

# Coverage charts use named placeholders for values read from JSON exports.
COVERAGE_TITLE: Final[str] = "Ball tracking coverage"
COVERAGE_SUMMARY_TEMPLATE: Final[str] = (
    "{videos} videos  ·  {frames:,} processed frames"
    "  ·  Results from exported detections"
)
COVERAGE_DESCRIPTION: Final[str] = (
    "of frames have a detected or predicted position"
)
COVERAGE_COLUMN: Final[str] = "COVERAGE"
ALL_VIDEOS: Final[str] = "All videos"
VIDEO_ROW_TEMPLATE: Final[str] = "{name}\n{frames:,} frames"
PERCENT_TEMPLATE: Final[str] = "{value:.1f}%"
PERCENT_TICK_TEMPLATE: Final[str] = "{value:g}%"
DETECTED_LABEL: Final[str] = "Visual detection"
ESTIMATED_LABEL: Final[str] = "Motion estimate"
MISSING_LABEL: Final[str] = "No position"
TIMELINE_TITLE: Final[str] = "Detection consistency over time"
TIMELINE_DESCRIPTION: Final[str] = (
    "Visual detections within equal-duration video segments"
)
TIMELINE_AXIS: Final[str] = "Progress within each video (normalized to 100%)"
COVERAGE_FOOTNOTE: Final[str] = (
    "Coverage is not accuracy: ground-truth ball positions are required "
    "to evaluate correctness."
)

# Localization plots distinguish scored, incorrect and unscored observations.
ANNOTATIONS_LABEL: Final[str] = "Annotations"
CORRECT_OBSERVATIONS_LABEL: Final[str] = "Correct observations"
WRONG_OBSERVATIONS_LABEL: Final[str] = "Wrong detections"
UNSCORED_OBSERVATIONS_LABEL: Final[str] = "Unscored observations"
OBSERVATION_COUNT_TEMPLATE: Final[str] = "{label} ({count})"
POSITIONS_TITLE: Final[str] = "All observations in source coordinates"
POSITION_X_LABEL: Final[str] = "x (pixels)"
POSITION_Y_LABEL: Final[str] = "y (pixels)"
ERROR_TITLE: Final[str] = "Observed localization error"
ERROR_TIME_LABEL: Final[str] = "Time (seconds)"
ERROR_DISTANCE_LABEL: Final[str] = "Distance to annotation (pixels)"
ERROR_CRITERION_TEMPLATE: Final[str] = "{threshold:g} px criterion"
COMPARISON_TITLE: Final[str] = "Annotations and code observations"
READABLE_SUMMARY_TEMPLATE: Final[str] = (
    "{correct}/{visible} readable frames within {threshold:g} px"
)
NO_READABLE_CENTERS: Final[str] = "No readable reference centers"
NEGATIVE_SUMMARY_TEMPLATE: Final[str] = (
    "{false_positive}/{negative} false detections when no ball is visible"
)
NO_NEGATIVE_FRAMES: Final[str] = "No reference frames without a visible ball"
COMPARISON_SUMMARY_TEMPLATE: Final[str] = "{readable} · {negative}"
OBSERVATIONS_FOOTNOTE_TEMPLATE: Final[str] = (
    "All {count} code observations are shown as markers; "
    "red crosses identify errors."
)
ERROR_FOOTNOTE_TEMPLATE: Final[str] = (
    "Error is measurable on {count} observations. "
    "Gray time bands have no readable reference center."
)

# Example panels show observations only; motion predictions are not markers.
EXAMPLE_FRAME_TEMPLATE: Final[str] = (
    "Frame {index} · {seconds:.2f} s\n{caption}"
)
EXAMPLE_CORRECT: Final[str] = "Both correct"
EXAMPLE_WRONG: Final[str] = "Orange incorrect"
EXAMPLE_MISSED: Final[str] = "Green only · no observation"
EXAMPLE_UNCERTAIN: Final[str] = "Uncertain annotation · not scored"
EXAMPLE_FALSE_POSITIVE: Final[str] = "Orange incorrect · no ball"
EXAMPLE_ABSENT: Final[str] = "No ball · no observation"
EXAMPLE_ERROR_TEMPLATE: Final[str] = "{caption} · {error:.1f} px"
EXAMPLES_LEGEND: Final[str] = "Green: annotations · Orange: code observations"
EXAMPLES_FOOTNOTE: Final[str] = (
    "Source crops · Motion predictions are not drawn"
)

# OpenCV overlays use ASCII so its built-in font can render every character.
REFERENCE_NOT_SAMPLED: Final[str] = "Reference: not sampled; no interpolation"
REFERENCE_NOT_VISIBLE: Final[str] = "Reference: target ball not visible"
REFERENCE_UNCERTAIN: Final[str] = "Reference: uncertain, excluded from scoring"
REFERENCE_CENTER_TEMPLATE: Final[str] = (
    "Visual reference center: {center} source pixels"
)
REVIEW_FRAME_TEMPLATE: Final[str] = "Frame {index:03d}"
REVIEW_LEGEND: Final[str] = "Green: annotations / Orange: code observations"
REVIEW_DETAIL_TEMPLATE: Final[str] = "Frame {index:03d} | {caption}"
