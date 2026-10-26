"""Stream detection records to a complete JSON document with bounded memory."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Self, TextIO, cast

from foosball_tracking.config import ApplicationConfig
from foosball_tracking.models import (
    BallTrack,
    FrameDetection,
    RunSummary,
    VideoMetadata,
)
from foosball_tracking.models.export import (
    BallExport,
    DetectionStatus,
    ExportFooter,
    ExportHeader,
    FrameExport,
    MetadataExport,
    PredictionExport,
    StopReason,
    SummaryExport,
    TableExport,
)


class DetectionExporter:
    """Append frames without retaining their JSON representation in memory."""

    def __init__(
        self: Self,
        stream: TextIO,
        config: ApplicationConfig,
        metadata: VideoMetadata,
    ) -> None:
        """Start a JSON document with source metadata and the effective config.

        :param stream: Text stream owned by the export context.
        :param config: Effective settings after command-line overrides.
        :param metadata: Validated source dimensions and frame rate.
        """
        self._stream: TextIO = stream
        self._fps: float = metadata.fps
        self._summary: RunSummary = RunSummary(0, 0)
        self.stop_reason: StopReason = StopReason.ERROR
        header: ExportHeader = ExportHeader(
            source_video=config.video_path,
            output_video=config.output_path,
            metadata=MetadataExport.model_validate(metadata),
            configuration=config,
        )
        self._stream.write(header.model_dump_json()[:-1])
        self._stream.write(',"frames":[')  # Open the frame array.

    def write_frame(
        self: Self,
        frame: FrameDetection,
        track: BallTrack,
        summary: RunSummary,
    ) -> None:
        """Append a record with separate observations and estimates.

        :param frame: Source frame and visual detection results.
        :param track: Current observed or extrapolated ball.
        :param summary: Counts including this processed frame.
        :return: None.
        :rtype: None
        """
        candidates: list[BallExport] = [
            BallExport.model_validate(candidate)
            for candidate in (
                frame.ball_detection.candidates
                if frame.ball_detection is not None
                else []
            )
        ]
        status: DetectionStatus = (
            DetectionStatus.DETECTED
            if track.ball is not None
            else DetectionStatus.ESTIMATED
            if track.prediction is not None
            else DetectionStatus.MISSING
        )
        record: FrameExport = FrameExport(
            frame_index=frame.frame_index,
            timestamp_seconds=frame.frame_index / self._fps,
            status=status,
            table=(
                TableExport.model_validate(frame.table)
                if frame.table is not None
                else None
            ),
            ball=(
                BallExport.model_validate(track.ball)
                if track.ball is not None
                else None
            ),
            candidates=candidates,
            prediction=(
                PredictionExport.model_validate(track.prediction)
                if track.prediction is not None
                else None
            ),
        )
        # Serialize first so a conversion failure cannot leave half a record.
        encoded: str = record.model_dump_json()
        if self._summary.processed_frames:
            self._stream.write(",")  # Separate records with a comma.
        self._stream.write(encoded)
        self._summary = summary

    def finish(self: Self) -> None:
        """Close the frame array and append counts and the termination reason.

        :return: None.
        :rtype: None
        """
        footer: ExportFooter = ExportFooter(
            summary=SummaryExport.model_validate(self._summary),
            completed=self.stop_reason
            in (StopReason.END_OF_VIDEO, StopReason.MAX_FRAMES),
            stop_reason=self.stop_reason,
        )
        self._stream.write("],")  # Close the frame array.
        self._stream.write(footer.model_dump_json()[1:])


@contextmanager
def detection_export(
    config: ApplicationConfig, metadata: VideoMetadata
) -> Generator[DetectionExporter]:
    """Publish valid JSON after processing, including orderly partial runs.

    :param config: Effective output paths and processing settings.
    :param metadata: Validated source properties.
    :return: Streaming exporter whose document is finalized on context exit.
    :rtype: Generator[DetectionExporter]
    """
    destination: Path = config.detections_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    finalized: bool = False
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.stem}-",
            suffix=".json.tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            exporter: DetectionExporter = DetectionExporter(
                cast(TextIO, stream), config, metadata
            )
            try:
                yield exporter
            except BaseException as failure:
                exporter.stop_reason = (
                    StopReason.INTERRUPTED
                    if isinstance(failure, KeyboardInterrupt)
                    else StopReason.ERROR
                )
                raise
            finally:
                exporter.finish()
                # Close successfully before publishing, even on interruption.
                stream.close()
                finalized = True
    finally:
        if temporary_path is not None:
            if finalized:
                temporary_path.replace(destination)
            else:
                temporary_path.unlink(missing_ok=True)
