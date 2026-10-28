"""Load shared annotation and detection inputs for reports."""

from collections.abc import Iterator
from pathlib import Path

from reporting.models.inputs import ComparisonInputs
from reporting.models.provenance import ReferenceProvenance
from tracking.models.export import DetectionExport, FrameExport


def load_comparison_inputs(
    data_dir: Path,
) -> tuple[DetectionExport, DetectionExport]:
    """Validate saved annotations and detections without opening a video.

    :param data_dir: Folder containing annotations.json and detections.json.
    :type data_dir: Path
    :return: Annotation and code output exports, in that order.
    :rtype: tuple[DetectionExport, DetectionExport]
    """
    annotations: DetectionExport = DetectionExport.model_validate_json(
        (data_dir / "annotations.json").read_bytes()
    )
    detections: DetectionExport = DetectionExport.model_validate_json(
        (data_dir / "detections.json").read_bytes()
    )
    return annotations, detections


def load_comparison_data(data_dir: Path) -> ComparisonInputs:
    """Load the shared exports and their reference visibility decisions.

    :param data_dir: Directory containing the three comparison JSON inputs.
    :type data_dir: Path
    :return: Validated inputs for examples and quantitative figures.
    :rtype: ComparisonInputs
    """
    annotations, detections = load_comparison_inputs(data_dir)
    provenance: ReferenceProvenance = ReferenceProvenance.model_validate_json(
        (data_dir / "provenance.json").read_bytes()
    )
    return ComparisonInputs(annotations, detections, provenance)


def index_frames(report: DetectionExport) -> dict[int, FrameExport]:
    """Index saved observations while rejecting ambiguous frame records.

    :param report: Export whose frames must have unique source indices.
    :type report: DetectionExport
    :return: Source indices mapped to their records.
    :rtype: dict[int, FrameExport]
    :raises ValueError: If any source index is repeated.
    """
    lookup: dict[int, FrameExport] = {}
    for frame in report.frames:
        if frame.frame_index in lookup:
            raise ValueError("Duplicate automatic frame index")
        lookup[frame.frame_index] = frame
    return lookup


def align_frames(
    reference: DetectionExport, detected: DetectionExport
) -> Iterator[tuple[FrameExport, FrameExport]]:
    """Pair records by source index, regardless of output list order.

    :param reference: Reference frames in source order.
    :type reference: DetectionExport
    :param detected: Automatic results covering each reference frame.
    :type detected: DetectionExport
    :return: Corresponding reference and output frames.
    :rtype: Iterator[tuple[FrameExport, FrameExport]]
    :raises ValueError: If an index is duplicated or a frame is missing.
    """
    lookup: dict[int, FrameExport] = index_frames(detected)
    for sample in reference.frames:
        if sample.frame_index not in lookup:
            raise ValueError(f"Missing exported frame {sample.frame_index}")
        yield sample, lookup[sample.frame_index]
