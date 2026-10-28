"""Overlap bounded video reading, ball detection and ordered encoding."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Generator, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from queue import Full, Queue
from threading import Event, get_native_id
from typing import Self, cast

from cv2 import VideoCapture, VideoWriter

from tracking.config import ApplicationConfig
from tracking.models import (
    BallDetection,
    FrameDetection,
    Image,
    TableDetection,
)
from tracking.services.ball import BallDetector
from tracking.services.table import TableDetector


@dataclass(slots=True)
class _WorkerResult:
    """Identify the worker that produced one frame's ball detection."""

    ball_detection: BallDetection | None
    thread_id: int


@dataclass(slots=True)
class _PreparedFrame:
    """Retain a decoded frame and its sequentially resolved table."""

    frame_index: int
    frame: Image
    table: TableDetection | None


@dataclass(slots=True)
class _PendingFrame(_PreparedFrame):
    """Associate a detection future with its immutable source-order context."""

    future: Future[_WorkerResult]


class DetectionPipeline:
    """Keep table fallback sequential while detecting balls concurrently."""

    def __init__(
        self: Self,
        capture: VideoCapture,
        first_frame: Image,
        config: ApplicationConfig,
        table_detector: TableDetector,
        ball_detector: BallDetector,
    ) -> None:
        """Store the capture and components owned by the video processor.

        :param capture: Source capture, read only by the producer thread.
        :param first_frame: Already decoded first source frame.
        :param config: Processing limits and detection frequency.
        :param table_detector: Sequential table detector.
        :param ball_detector: Stateless ball detector shared by workers.
        """
        self.capture: VideoCapture = capture
        self.first_frame: Image = first_frame
        self.config: ApplicationConfig = config
        self.table_detector: TableDetector = table_detector
        self.ball_detector: BallDetector = ball_detector
        self._queue: Queue[_PendingFrame | None] = Queue(
            maxsize=config.processing.buffer_size
        )
        self._stop: Event = Event()
        # Dedicated queues distribute even very short tasks to every worker.
        self._executors: tuple[ThreadPoolExecutor, ...] = tuple(
            ThreadPoolExecutor(max_workers=1)
            for _ in range(config.processing.workers)
        )

    @contextmanager
    def frames(self: Self) -> Generator[Iterator[FrameDetection]]:
        """Yield ordered results and join every thread on exit.

        :return: Context managing the ordered frame iterator.
        :rtype: Generator[Iterator[FrameDetection]]
        """
        reader: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)
        producer: Future[None] = reader.submit(self._produce)
        try:
            yield self._ordered_results(producer)
        finally:
            # Unblock the producer even if it is waiting on a full queue.
            self._stop.set()
            try:
                reader.shutdown(wait=True)
            finally:
                # Cancel every worker's backlog before waiting for active work.
                for executor in self._executors:
                    executor.shutdown(wait=False, cancel_futures=True)
                for executor in self._executors:
                    executor.shutdown(wait=True)

    def _put(self: Self, item: _PendingFrame | None) -> bool:
        """Wait for queue capacity until the consumer stops.

        :param item: Pending frame or end marker.
        :return: Whether the item reached the queue.
        :rtype: bool
        """
        while not self._stop.is_set():
            try:
                self._queue.put(item, timeout=0.05)
                return True
            except Full:
                continue
        return False

    def _produce(self: Self) -> None:
        """Prepare bounded batches and retain the last valid playing field.

        :return: None.
        :rtype: None
        """
        frame_index: int = 0
        frame: Image = self.first_frame
        table: TableDetection | None = None
        prepared: deque[_PreparedFrame] = deque()
        # Start work after one frame per worker, even with a large queue.
        batch_size: int = min(
            self.config.processing.buffer_size, self.config.processing.workers
        )
        try:
            while not self._stop.is_set():
                if (
                    table is None
                    or frame_index % self.config.table.detection_every == 0
                ):
                    detected: TableDetection | None = (
                        self.table_detector.detect(frame)
                    )
                    if detected is not None:
                        table = detected
                prepared.append(_PreparedFrame(frame_index, frame, table))
                if len(prepared) >= batch_size:
                    # Do not retry a failed dispatch from the tail flush.
                    ready: deque[_PreparedFrame] = prepared
                    prepared = deque()
                    self._dispatch(ready)
                if self._stop.is_set():
                    break
                frame_index += 1
                if (
                    self.config.max_frames is not None
                    and frame_index >= self.config.max_frames
                ):
                    break
                success, decoded_frame = self.capture.read()
                if not success:
                    break
                frame = cast(Image, decoded_frame)
        finally:
            try:
                # Flush the tail and any valid prefix before a reader failure.
                self._dispatch(prepared)
            finally:
                self._put(None)

    def _dispatch(self: Self, prepared: deque[_PreparedFrame]) -> None:
        """Distribute a ready batch round-robin across dedicated workers.

        :param prepared: Source-ordered frames, consumed as they are submitted.
        :return: None.
        :rtype: None
        """
        while prepared and not self._stop.is_set():
            item: _PreparedFrame = prepared.popleft()
            executor: ThreadPoolExecutor = self._executors[
                item.frame_index % len(self._executors)
            ]
            future: Future[_WorkerResult] = executor.submit(
                self._detect_ball, item.frame, item.table
            )
            if not self._put(
                _PendingFrame(item.frame_index, item.frame, item.table, future)
            ):
                future.cancel()
                break

    def _detect_ball(
        self: Self, frame: Image, table: TableDetection | None
    ) -> _WorkerResult:
        """Detect independently using the table valid for this frame.

        :param frame: Unannotated source frame.
        :param table: Sequentially resolved table snapshot, if available.
        :return: Ball detection and the native worker identifier.
        :rtype: _WorkerResult
        """
        return _WorkerResult(
            ball_detection=(
                self.ball_detector.detect(frame, table.playfield_box)
                if table is not None
                else None
            ),
            thread_id=get_native_id(),
        )

    def _ordered_results(
        self: Self, producer: Future[None]
    ) -> Iterator[FrameDetection]:
        """Wait for futures in submission order, propagating their failures.

        :param producer: Reader task retaining any producer failure.
        :return: Chronological frames, including frames without a table.
        :rtype: Iterator[FrameDetection]
        """
        while True:
            item: _PendingFrame | None = self._queue.get()
            if item is None:
                # A producer failure must not be reported as a normal EOF.
                producer.result()
                return
            result: _WorkerResult = item.future.result()
            yield FrameDetection(
                frame_index=item.frame_index,
                frame=item.frame,
                table=item.table,
                ball_detection=result.ball_detection,
                worker_thread_id=result.thread_id,
            )


@contextmanager
def buffered_video_writer(
    writer: VideoWriter, buffer_size: int
) -> Generator[Callable[[Image], None]]:
    """Encode in one dedicated thread with bounded pending writes.

    :param writer: Open writer, released by its owner after this context.
    :param buffer_size: Maximum frames awaiting encoding.
    :return: Function submitting one frame for ordered encoding.
    :rtype: Generator[Callable[[Image], None]]
    """
    pending: deque[Future[None]] = deque()
    executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)

    def enqueue(frame: Image) -> None:
        """Apply backpressure before retaining another annotated frame."""
        if len(pending) >= buffer_size:
            pending.popleft().result()
        pending.append(executor.submit(writer.write, frame))

    try:
        yield enqueue
    finally:
        try:
            # Drain accepted writes even after preview closes or Ctrl+C.
            while pending:
                pending.popleft().result()
        finally:
            executor.shutdown(wait=True)
