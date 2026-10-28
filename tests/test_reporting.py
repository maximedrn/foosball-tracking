"""Check compact coverage inputs and rendering without source videos."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self
from unittest import TestCase
from xml.etree import ElementTree

from pydantic import ValidationError

from reporting.cli.figures import main as figures_main
from reporting.models.coverage import (
    CoverageReport,
    VideoStatistics,
)
from reporting.models.inputs import ComparisonInputs
from reporting.models.plotting import ChartLayout
from reporting.models.positions import PositionComparison
from reporting.models.provenance import FrameReview, ReferenceProvenance
from reporting.paths import DATA_DIR
from reporting.plots.examples import EXAMPLE_FRAMES
from reporting.services.coverage import (
    aggregate_statistics,
    load_statistics,
)
from reporting.services.inputs import load_comparison_data
from reporting.services.positions import compare_frames
from reporting.utils.svg import THEME_STYLE_ID, apply_adaptive_theme
from tests.test_evaluation import make_report
from tracking.models.export import DetectionExport


class ReportingTests(TestCase):
    """Keep plotted counts faithful to exports and independent of videos."""

    def test_examples_cover_four_outcomes(self: Self) -> None:
        """Check saved positions support the gallery's four claimed cases.

        :return: None.
        :rtype: None
        """
        inputs: ComparisonInputs = load_comparison_data(DATA_DIR)
        frames: list[PositionComparison] = compare_frames(
            inputs.annotations, inputs.detections, inputs.provenance
        )
        statuses: dict[int, str] = {
            frame.frame_index: frame.status.value for frame in frames
        }
        self.assertEqual(len(EXAMPLE_FRAMES), 4)
        self.assertEqual(
            [statuses[index] for index in EXAMPLE_FRAMES],
            ["correct", "missed", "false_positive", "absent"],
        )

    def test_theme_normalization_and_replacement(self: Self) -> None:
        """Keep CSS selectors effective after repeated theme embedding.

        :return: None.
        :rtype: None
        """
        root: ElementTree.Element[str] = ElementTree.fromstring(
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path style="fill: #1F2328; stroke: #FFFFFF"/></svg>'
        )
        apply_adaptive_theme(root, "old stylesheet")
        apply_adaptive_theme(root, "new stylesheet")
        styles: list[ElementTree.Element[str]] = root.findall(
            "{http://www.w3.org/2000/svg}style"
        )
        self.assertEqual(len(styles), 1)
        self.assertEqual(styles[0].get("id"), THEME_STYLE_ID)
        self.assertEqual(styles[0].text, "new stylesheet")
        self.assertEqual(root[1].get("style"), "fill:#1f2328; stroke:#ffffff")

    def test_export_windows_and_weighted_coverage(self: Self) -> None:
        """Calculate exact windows and weight totals by frame counts.

        :return: None.
        :rtype: None
        """
        report: DetectionExport = make_report(
            [(1, 1), (2, 2), (3, 3), None], predicted={2}
        )
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / "export.json"
            path.write_text(report.model_dump_json())
            statistics: VideoStatistics = load_statistics(
                path, layout=ChartLayout(window_count=2)
            )
        self.assertEqual(statistics.observed_windows, (100.0, 0.0))
        self.assertEqual(statistics.coverage_rate, 75.0)
        total: VideoStatistics = aggregate_statistics(
            [
                statistics,
                VideoStatistics(
                    name="short",
                    frames=1,
                    detected=1,
                    estimated=0,
                    missing=0,
                    observed_windows=(100.0, 0.0),
                ),
            ]
        )
        self.assertEqual(total.frames, 5)
        self.assertEqual(total.coverage_rate, 80.0)

    def test_invalid_compact_counts_are_rejected(self: Self) -> None:
        """Reject cached statistics that cannot represent the stated total.

        :return: None.
        :rtype: None
        """
        with self.assertRaisesRegex(ValidationError, "sum to processed"):
            VideoStatistics(
                name="invalid",
                frames=10,
                detected=8,
                estimated=4,
                missing=0,
                observed_windows=(80.0,),
            )

    def test_compact_json_preserves_measured_windows(self: Self) -> None:
        """Preserve frame counts and timeline values through serialization.

        :return: None.
        :rtype: None
        """
        report: CoverageReport = CoverageReport(
            videos=[
                VideoStatistics(
                    name="sample",
                    frames=4,
                    detected=2,
                    estimated=1,
                    missing=1,
                    observed_windows=(100.0, 0.0),
                )
            ]
        )
        restored: CoverageReport = CoverageReport.model_validate_json(
            report.model_dump_json()
        )
        self.assertEqual(restored, report)

    def test_all_charts_render_from_json_without_videos(self: Self) -> None:
        """Generate both result charts with a nonexistent source video.

        :return: None.
        :rtype: None
        """
        with TemporaryDirectory() as directory:
            root: Path = Path(directory)
            report: DetectionExport = make_report([(1, 1), (2, 2)])
            report.source_video = root / "unavailable.mp4"
            self.assertFalse(report.source_video.exists())
            (root / "annotations.json").write_text(report.model_dump_json())
            (root / "detections.json").write_text(report.model_dump_json())
            provenance: ReferenceProvenance = ReferenceProvenance(
                source_sha256="0" * 64,
                canonical_annotations_sha256="0" * 64,
                sample_stride=3,
                human_verified=False,
                review=[
                    FrameReview(frame_index=0, visibility="visible"),
                    FrameReview(frame_index=3, visibility="visible"),
                ],
            )
            (root / "provenance.json").write_text(provenance.model_dump_json())
            coverage: CoverageReport = CoverageReport(
                videos=[
                    VideoStatistics(
                        name="sample",
                        frames=2,
                        detected=2,
                        estimated=0,
                        missing=0,
                        observed_windows=(100.0, 100.0),
                    )
                ]
            )
            (root / "generic-videos.json").write_text(
                coverage.model_dump_json()
            )
            output: Path = root / "figures"
            self.assertEqual(
                figures_main(
                    ["--data-dir", str(root), "--output-dir", str(output)]
                ),
                0,
            )
            filename: str
            for filename in ("trajectories.svg", "generic-videos.svg"):
                document: ElementTree.ElementTree[ElementTree.Element[str]] = (
                    ElementTree.parse(output / filename)
                )
                self.assertEqual(
                    document.getroot().tag,
                    "{http://www.w3.org/2000/svg}svg",
                )
                style: ElementTree.Element[str] | None = (
                    document.getroot().find(
                        '{http://www.w3.org/2000/svg}style[@id="github-adaptive-theme"]'
                    )
                )
                self.assertIsNotNone(style)
                if style is not None:
                    self.assertIn(
                        "prefers-color-scheme: dark", style.text or ""
                    )
