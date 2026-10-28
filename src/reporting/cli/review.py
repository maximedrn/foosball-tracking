"""Generate source-frame examples and review videos from saved positions."""

from reporting.cli.figures import parse_arguments
from reporting.models.arguments import FigureArguments
from reporting.models.inputs import ComparisonInputs
from reporting.models.provenance import (
    FrameReview,
)
from reporting.paths import REVIEW_DIR
from reporting.plots.examples import render_examples
from reporting.services.inputs import load_comparison_data
from reporting.services.review import (
    render_review,
)


def main(argv: list[str] | None = None) -> int:
    """Overlay annotation and observation JSON on the original video.

    :param argv: Explicit arguments or None for process arguments.
    :type argv: list[str] | None
    :return: Zero after examples, sheets and review videos are saved.
    :rtype: int
    """
    args: FigureArguments = parse_arguments(argv)
    inputs: ComparisonInputs = load_comparison_data(args.data_dir)
    not_visible: set[int] = set()
    review: FrameReview
    for review in inputs.provenance.review:
        if review.visibility == "not_visible":
            not_visible.add(review.frame_index)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (REVIEW_DIR / "review").mkdir(parents=True, exist_ok=True)
    render_examples(
        inputs.annotations,
        inputs.detections,
        not_visible,
        destination=args.output_dir / "examples.svg",
    )
    render_review(
        inputs.annotations,
        inputs.detections,
        not_visible,
        output_dir=REVIEW_DIR,
    )
    print(f"Saved example image and review videos to {REVIEW_DIR}")
    return 0
