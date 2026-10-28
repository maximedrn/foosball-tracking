"""Apply the shared GitHub palette before creating Matplotlib artists."""

from matplotlib import rcParams

from reporting.models.plotting import GitHubColor


def configure_plot_theme() -> None:
    """Use adaptive palette colors for text, axes, backgrounds and legends.

    :return: None.
    :rtype: None
    """
    rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "svg.fonttype": "path",
            "axes.unicode_minus": False,
            "text.color": GitHubColor.TEXT,
            "axes.labelcolor": GitHubColor.TEXT,
            "axes.edgecolor": GitHubColor.BORDER,
            "axes.facecolor": GitHubColor.CANVAS,
            "figure.facecolor": GitHubColor.CANVAS,
            "xtick.color": GitHubColor.MUTED,
            "ytick.color": GitHubColor.MUTED,
            "grid.color": GitHubColor.BORDER,
            "legend.facecolor": GitHubColor.SURFACE,
            "legend.edgecolor": GitHubColor.BORDER,
        }
    )
