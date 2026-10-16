"""Expose foosball video processing as a typed command-line application."""

from argparse import ArgumentParser, Namespace
from os import EX_OK
from pathlib import Path
from signal import SIGINT
from sys import stderr
from typing import Final

from jsonc import loads

from foosball_tracking.config import ApplicationConfig
from foosball_tracking.models import RunSummary
from foosball_tracking.services.video import VideoProcessor
from foosball_tracking.utils.messages import (
    CLI_CONFIG_HELP,
    CLI_DESCRIPTION,
    CLI_MAX_FRAMES_HELP,
    CLI_OUTPUT_HELP,
    CLI_PREVIEW_HELP,
    CLI_VIDEO_HELP,
    COVERAGE_SUMMARY_TEMPLATE,
    DETECTION_SUMMARY_TEMPLATE,
    ERROR_MESSAGE_TEMPLATE,
    OUTPUT_VIDEO_TEMPLATE,
    PREDICTION_SUMMARY_TEMPLATE,
    PROCESSED_FRAMES_TEMPLATE,
    PROCESSING_INTERRUPTED_MESSAGE,
)

# Python exposes no standard constant for a generic failure status.
EXIT_FAILURE: Final[int] = 1
# Shells report signal interruptions as 128 plus the signal number.
EXIT_INTERRUPTED: Final[int] = 128 + SIGINT


class CliArguments(Namespace):
    """Describe the named values produced by the command-line parser.

    :param video: Optional source path overriding the configuration.
    :type video: Path | None
    :param output: Optional destination path overriding the configuration.
    :type output: Path | None
    :param preview: Whether to enable the OpenCV preview window.
    :type preview: bool
    :param max_frames: Optional positive frame limit.
    :type max_frames: int | None
    :param config: Optional JSON or JSONC configuration path.
    :type config: Path | None
    """

    video: Path | None
    output: Path | None
    preview: bool
    max_frames: int | None
    config: Path | None


def create_parser() -> ArgumentParser:
    """Create the command-line parser.

    :return: Parser for source, output, preview and frame-limit options.
    :rtype: ArgumentParser
    """
    parser: ArgumentParser = ArgumentParser(description=CLI_DESCRIPTION)
    parser.add_argument(
        "video",
        nargs="?",
        type=Path,
        help=CLI_VIDEO_HELP,
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=CLI_OUTPUT_HELP,
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help=CLI_PREVIEW_HELP,
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        help=CLI_MAX_FRAMES_HELP,
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=CLI_CONFIG_HELP,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and process the requested video.

    :param argv: Arguments to parse, or None to use the process arguments.
    :type argv: list[str] | None
    :return: Zero on success, one on processing failure, or 130 on
        interruption.
    :rtype: int
    """
    parser: ArgumentParser = create_parser()
    arguments: CliArguments = parser.parse_args(argv, namespace=CliArguments())
    try:
        # Validate the JSON or JSONC configuration before applying command-line
        # overrides.
        config: ApplicationConfig = (
            ApplicationConfig.model_validate(
                loads(arguments.config.read_text(encoding="utf-8"))
            )
            if arguments.config is not None
            else ApplicationConfig()
        )
        # Unspecified options keep their file value or the application default.
        if arguments.video is not None:
            config.video_path = arguments.video
        if arguments.output is not None:
            config.output_path = arguments.output
        if arguments.max_frames is not None:
            config.max_frames = arguments.max_frames
        if arguments.preview:
            config.preview.enabled = True
        summary: RunSummary = VideoProcessor(config).run()
    except (OSError, ValueError, RuntimeError) as failure:
        print(ERROR_MESSAGE_TEMPLATE.format(error=failure), file=stderr)
        return EXIT_FAILURE
    except KeyboardInterrupt:
        print(PROCESSING_INTERRUPTED_MESSAGE, file=stderr)
        return EXIT_INTERRUPTED
    # Keep actual observations separate from the extra coverage of predictions.
    print(
        PROCESSED_FRAMES_TEMPLATE.format(
            processed_frames=summary.processed_frames
        )
    )
    print(
        DETECTION_SUMMARY_TEMPLATE.format(
            detected_frames=summary.detected_frames,
            detection_rate=summary.detection_rate,
        )
    )
    print(
        PREDICTION_SUMMARY_TEMPLATE.format(
            predicted_frames=summary.predicted_frames,
            prediction_rate=summary.prediction_rate,
        )
    )
    print(
        COVERAGE_SUMMARY_TEMPLATE.format(coverage_rate=summary.coverage_rate)
    )
    print(OUTPUT_VIDEO_TEMPLATE.format(path=config.output_path))
    return EX_OK
