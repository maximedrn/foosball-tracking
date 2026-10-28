"""Group the validated JSON inputs shared by report views."""

from typing import NamedTuple

from reporting.models.provenance import ReferenceProvenance
from tracking.models.export import DetectionExport


class ComparisonInputs(NamedTuple):
    """Keep annotation, detection and visibility data together.

    :param annotations: Validated annotation export.
    :type annotations: DetectionExport
    :param detections: Validated code output.
    :type detections: DetectionExport
    :param provenance: Annotation visibility decisions and hashes.
    :type provenance: ReferenceProvenance
    """

    annotations: DetectionExport
    detections: DetectionExport
    provenance: ReferenceProvenance
