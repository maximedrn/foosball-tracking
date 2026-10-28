"""Compare source-image positions while keeping predictions separate."""

from __future__ import annotations

from collections import Counter
from math import hypot, sqrt
from statistics import fmean, median

from reporting.models.provenance import ReferenceProvenance
from reporting.services.inputs import align_frames
from tracking.models import Point
from tracking.models.export import DetectionExport, FrameExport

type Measurements = dict[str, int | float | None]


def error_statistics(errors: list[float], prefix: str) -> Measurements:
    """Summarize every available error, including incorrect localizations.

    :param errors: Euclidean distances in original image pixels.
    :type errors: list[float]
    :param prefix: Prefix distinguishing observations from combined outputs.
    :type prefix: str
    :return: Count, mean, median, RMSE and maximum, or null if unavailable.
    :rtype: Measurements
    """
    squared_sum: float = 0.0
    error: float
    for error in errors:
        squared_sum += error * error
    return {
        f"{prefix}_error_count": len(errors),
        f"{prefix}_error_mean_px": fmean(errors) if errors else None,
        f"{prefix}_error_median_px": median(errors) if errors else None,
        f"{prefix}_error_rmse_px": (
            sqrt(squared_sum / len(errors)) if errors else None
        ),
        f"{prefix}_error_max_px": max(errors) if errors else None,
    }


def frame_errors(
    reference: Point, detected: FrameExport
) -> tuple[float | None, float | None]:
    """Measure observation and combined position errors on one frame.

    :param reference: Independently annotated source-image center.
    :type reference: Point
    :param detected: Automatic detections and optional motion prediction.
    :type detected: FrameExport
    :return: Observation error and observation-or-prediction error.
    :rtype: tuple[float | None, float | None]
    """
    if detected.ball is not None:
        error: float = hypot(
            detected.ball.center[0] - reference[0],
            detected.ball.center[1] - reference[1],
        )
        return error, error
    if detected.prediction is not None:
        return None, hypot(
            detected.prediction.center[0] - reference[0],
            detected.prediction.center[1] - reference[1],
        )
    return None, None


def record_errors(
    counts: Counter[str],
    errors: tuple[float | None, float | None],
    *,
    threshold_px: float,
    prediction: bool,
) -> bool:
    """Classify one visible reference using the declared distance threshold.

    :param counts: Counts updated in place for this scored reference.
    :type counts: Counter[str]
    :param errors: Observation and combined localization errors.
    :type errors: tuple[float | None, float | None]
    :param threshold_px: Maximum accepted distance from the reference.
    :type threshold_px: float
    :param prediction: Whether the combined output is a motion prediction.
    :type prediction: bool
    :return: True when the combined position is within the threshold.
    :rtype: bool
    """
    observed_error: float | None
    combined_error: float | None
    observed_error, combined_error = errors
    if observed_error is not None and observed_error <= threshold_px:
        counts["true_positives"] += 1
    else:
        counts["false_negatives"] += 1
        if observed_error is not None:
            counts["false_positives"] += 1
    if combined_error is None or combined_error > threshold_px:
        return False
    counts["combined_correct"] += 1
    if prediction:
        counts["prediction_correct"] += 1
    return True


def evaluate(
    reference: DetectionExport,
    detected: DetectionExport,
    *,
    excluded: set[int],
    threshold_px: float = 20.0,
    sample_stride: int = 3,
) -> Measurements:
    """Score annotated frames without interpolating reference positions.

    A wrong observed location counts as both a false positive and a missed
    true position. Predictions are evaluated separately from observations.

    :param reference: Sparse reference export with original frame indices.
    :type reference: DetectionExport
    :param detected: Automatic export covering every reference frame.
    :type detected: DetectionExport
    :param excluded: Visually uncertain source frame indices to omit.
    :type excluded: set[int]
    :param threshold_px: Maximum Euclidean error counted as correct.
    :type threshold_px: float
    :param sample_stride: Expected interval between reference frame indices.
    :type sample_stride: int
    :return: Detection counts, rates, localization errors and sampled runs.
    :rtype: Measurements
    :raises ValueError: If metadata or frame coverage is inconsistent.
    """
    if threshold_px <= 0 or sample_stride < 1:
        raise ValueError("Threshold and sample stride must be positive")
    if (
        reference.metadata.width != detected.metadata.width
        or reference.metadata.height != detected.metadata.height
        or reference.metadata.fps != detected.metadata.fps
        or reference.source_video.name != detected.source_video.name
    ):
        raise ValueError("Source metadata differs between the exports")
    counts: Counter[str] = Counter(
        visible_samples=0,
        negative_samples=0,
        excluded_samples=0,
        true_positives=0,
        false_positives=0,
        false_negatives=0,
        true_negatives=0,
        combined_correct=0,
        prediction_correct=0,
        current_run=0,
        longest_run=0,
        previous_index=-sample_stride,
    )
    observed_errors: list[float] = []
    combined_errors: list[float] = []
    for sample, frame in align_frames(reference, detected):
        if sample.frame_index in excluded:
            counts["excluded_samples"] += 1
            counts["current_run"] = 0
            continue
        if sample.ball is None:
            counts["negative_samples"] += 1
            counts["false_positives" if frame.ball else "true_negatives"] += 1
            counts["current_run"] = 0
            continue
        counts["visible_samples"] += 1
        observed_error, combined_error = frame_errors(
            sample.ball.center, frame
        )
        if observed_error is not None:
            observed_errors.append(observed_error)
        if combined_error is not None:
            combined_errors.append(combined_error)
        if record_errors(
            counts,
            (observed_error, combined_error),
            threshold_px=threshold_px,
            prediction=frame.ball is None,
        ):
            counts["current_run"] = (
                counts["current_run"] + 1
                if sample.frame_index - counts["previous_index"]
                == sample_stride
                else 1
            )
            counts["longest_run"] = max(
                counts["longest_run"], counts["current_run"]
            )
        else:
            counts["current_run"] = 0
        counts["previous_index"] = sample.frame_index
    result: Measurements = summarize_counts(counts)
    result["threshold_px"] = threshold_px
    result["longest_correct_sampled_run_samples"] = counts["longest_run"]
    result["longest_correct_sampled_run_seconds"] = (
        max(counts["longest_run"] - 1, 0)
        * sample_stride
        / reference.metadata.fps
    )
    result.update(error_statistics(observed_errors, "observed"))
    result.update(error_statistics(combined_errors, "combined"))
    return result


def summarize_counts(counts: Counter[str]) -> Measurements:
    """Compute rates with explicit denominators and undefined-value handling.

    :param counts: Detection and visibility counts accumulated on the sample.
    :type counts: Counter[str]
    :return: Counts and precision, recall, F1 and combined localization rate.
    :rtype: Measurements
    """
    result: Measurements = dict(counts)
    result.pop("current_run")
    result.pop("previous_index")
    result.pop("longest_run")
    positive_outputs: int = (
        counts["true_positives"] + counts["false_positives"]
    )
    f1_denominator: int = (
        2 * counts["true_positives"]
        + counts["false_positives"]
        + counts["false_negatives"]
    )
    result["precision"] = (
        counts["true_positives"] / positive_outputs
        if positive_outputs
        else None
    )
    result["recall"] = (
        counts["true_positives"] / counts["visible_samples"]
        if counts["visible_samples"]
        else None
    )
    result["f1"] = (
        2 * counts["true_positives"] / f1_denominator
        if f1_denominator
        else None
    )
    result["combined_recall"] = (
        counts["combined_correct"] / counts["visible_samples"]
        if counts["visible_samples"]
        else None
    )
    return result


def validate_reference(
    reference: DetectionExport, provenance: ReferenceProvenance
) -> set[int]:
    """Validate source coordinates and exclude uncertain reference frames.

    :param reference: Reference export to check before evaluation.
    :type reference: DetectionExport
    :param provenance: Sampling and visibility sidecar.
    :type provenance: ReferenceProvenance
    :return: Uncertain source frame indices to omit from scoring.
    :rtype: set[int]
    :raises ValueError: If visibility, timestamps or coordinates disagree.
    """
    decisions: dict[int, str] = {}
    for review in provenance.review:
        if review.frame_index in decisions:
            raise ValueError("Duplicate reviewed frame index")
        decisions[review.frame_index] = review.visibility
    excluded: set[int] = set()
    previous_index: int = -1
    for sample in reference.frames:
        if sample.frame_index <= previous_index:
            raise ValueError("Reference indices must increase strictly")
        previous_index = sample.frame_index
        if (
            abs(
                sample.timestamp_seconds
                - sample.frame_index / reference.metadata.fps
            )
            > 1e-6
        ):
            raise ValueError("Reference timestamp does not match its index")
        if sample.frame_index not in decisions:
            raise ValueError("Missing visibility decision")
        if decisions[sample.frame_index] == "uncertain":
            excluded.add(sample.frame_index)
        elif (decisions[sample.frame_index] == "visible") != (
            sample.ball is not None
        ):
            raise ValueError("Reference position and visibility disagree")
        if sample.ball is not None and not (
            0 <= sample.ball.center[0] < reference.metadata.width
            and 0 <= sample.ball.center[1] < reference.metadata.height
        ):
            raise ValueError("Reference position is outside the source image")
    if len(decisions) != len(reference.frames):
        raise ValueError("Visibility and reference sample counts disagree")
    return excluded
