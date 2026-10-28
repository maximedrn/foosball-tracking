"""Validate annotation visibility and provenance independently of scoring."""

from typing import Literal

from pydantic import BaseModel


class FrameReview(BaseModel):
    """Describe whether a sampled reference can be scored.

    :param frame_index: Original source frame index.
    :type frame_index: int
    :param visibility: Visibility established by direct visual inspection.
    :type visibility: Literal["visible", "not_visible", "uncertain"]
    """

    frame_index: int
    visibility: Literal["visible", "not_visible", "uncertain"]


class ReferenceProvenance(BaseModel):
    """Read the provenance fields needed to validate an evaluation.

    :param source_sha256: Hash of the unmodified source video.
    :type source_sha256: str
    :param canonical_annotations_sha256: Hash of the reference export.
    :type canonical_annotations_sha256: str
    :param sample_stride: Distance between annotated source frame indices.
    :type sample_stride: int
    :param human_verified: Whether a person has independently checked labels.
    :type human_verified: bool
    :param review: Visibility decisions for every sampled frame.
    :type review: list[FrameReview]
    """

    source_sha256: str
    canonical_annotations_sha256: str
    sample_stride: int
    human_verified: bool
    review: list[FrameReview]
