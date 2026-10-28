"""Compare annotations and code exports with recorded visibility metadata."""

from argparse import ArgumentParser
from hashlib import sha256
from json import dumps
from pathlib import Path

from reporting.models.arguments import EvaluationArguments
from reporting.models.provenance import ReferenceProvenance
from reporting.paths import DATA_DIR
from reporting.services.evaluation import (
    Measurements,
    evaluate,
    validate_reference,
)
from tracking.models.export import DetectionExport


def parse_arguments(argv: list[str] | None = None) -> EvaluationArguments:
    """Parse paths for an evaluation at 10, 20 and 30 source pixels.

    :param argv: Arguments to parse, or None for process arguments.
    :type argv: list[str] | None
    :return: Typed reference, automatic export, provenance and output paths.
    :rtype: EvaluationArguments
    """
    parser: ArgumentParser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "reference",
        nargs="?",
        type=Path,
        default=DATA_DIR / "annotations.json",
    )
    parser.add_argument(
        "detections",
        nargs="?",
        type=Path,
        default=DATA_DIR / "detections.json",
    )
    parser.add_argument(
        "--provenance", type=Path, default=DATA_DIR / "provenance.json"
    )
    parser.add_argument(
        "--output", type=Path, default=DATA_DIR / "comparison.json"
    )
    return parser.parse_args(argv, namespace=EvaluationArguments())


def main(argv: list[str] | None = None) -> int:
    """Validate provenance and write reproducible threshold comparisons.

    :param argv: Arguments to parse, or None for process arguments.
    :type argv: list[str] | None
    :return: Zero after successful evaluation.
    :rtype: int
    :raises OSError: If an input or output cannot be accessed.
    :raises ValueError: If source hashes or reference data are inconsistent.
    """
    args: EvaluationArguments = parse_arguments(argv)
    reference_bytes: bytes = args.reference.read_bytes()
    reference: DetectionExport = DetectionExport.model_validate_json(
        reference_bytes
    )
    detected_bytes: bytes = args.detections.read_bytes()
    detected: DetectionExport = DetectionExport.model_validate_json(
        detected_bytes
    )
    provenance: ReferenceProvenance = ReferenceProvenance.model_validate_json(
        args.provenance.read_bytes()
    )
    if sha256(reference_bytes).hexdigest() != (
        provenance.canonical_annotations_sha256
    ):
        raise ValueError("Reference hash differs from the recorded provenance")
    if sha256(reference.source_video.read_bytes()).hexdigest() != (
        provenance.source_sha256
    ):
        raise ValueError("Source video hash differs from the reference")
    excluded: set[int] = validate_reference(reference, provenance)
    results: dict[str, Measurements] = {}
    threshold: int
    for threshold in (10, 20, 30):
        results[str(threshold)] = evaluate(
            reference,
            detected,
            excluded=excluded,
            threshold_px=threshold,
            sample_stride=provenance.sample_stride,
        )
    document: dict[str, object] = {
        "reference_sha256": sha256(reference_bytes).hexdigest(),
        "detections_sha256": sha256(detected_bytes).hexdigest(),
        "source_sha256": provenance.source_sha256,
        "sample_stride": provenance.sample_stride,
        "thresholds_px": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dumps(document, indent=2) + "\n")
    print(f"Saved {args.output}")
    return 0
