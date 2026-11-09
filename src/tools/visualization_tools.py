import re
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "visualizations"


def _save_figure(title: str, draw: Callable[[plt.Axes], None]) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", title).strip("_").lower()
    filename = f"{slug or 'chart'}_{uuid4().hex[:8]}.png"
    output_path = OUTPUT_DIR / filename

    figure, axes = plt.subplots(figsize=(10, 6), constrained_layout=True)
    try:
        draw(axes)
        if title:
            axes.set_title(title)
        figure.savefig(output_path, dpi=150, bbox_inches="tight")
    finally:
        plt.close(figure)

    return str(output_path.relative_to(OUTPUT_DIR.parents[1])).replace("\\", "/")


def plot(
    x_values: list[str],
    y_values: list[float],
    title: str,
    x_label: str = "",
    y_label: str = "",
) -> str:
    """Create and save a line chart for trends or sequential data.

    Use this to show change over time or another ordered x-axis. Provide one
    numeric y-value for each x-value. Returns the saved image path.
    """
    if not x_values or len(x_values) != len(y_values):
        raise ValueError("x_values and y_values must have the same non-zero length.")

    def draw(axes: plt.Axes) -> None:
        axes.plot(x_values, y_values, marker="o")
        axes.set_xlabel(x_label)
        axes.set_ylabel(y_label)
        axes.tick_params(axis="x", labelrotation=30)

    return _save_figure(title, draw)


def pie(labels: list[str], values: list[float], title: str) -> str:
    """Create and save a pie chart showing each category's share of a whole.

    Use only when values represent parts of a meaningful total. Values must be
    non-negative with a positive sum. Returns the saved image path.
    """
    if not labels or len(labels) != len(values):
        raise ValueError("labels and values must have the same non-zero length.")
    if any(value < 0 for value in values) or sum(values) <= 0:
        raise ValueError("Pie chart values must be non-negative with a positive sum.")

    def draw(axes: plt.Axes) -> None:
        axes.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        axes.axis("equal")

    return _save_figure(title, draw)


def bar(
    labels: list[str],
    values: list[float],
    title: str,
    x_label: str = "",
    y_label: str = "",
) -> str:
    """Create and save a vertical bar chart comparing a few named categories.

    Provide one numeric value for each category. For many or long category
    names, use barh instead. Returns the saved image path.
    """
    if not labels or len(labels) != len(values):
        raise ValueError("labels and values must have the same non-zero length.")

    def draw(axes: plt.Axes) -> None:
        axes.bar(labels, values)
        axes.set_xlabel(x_label)
        axes.set_ylabel(y_label)
        axes.tick_params(axis="x", labelrotation=30)

    return _save_figure(title, draw)


def barh(
    labels: list[str],
    values: list[float],
    title: str,
    x_label: str = "",
    y_label: str = "",
) -> str:
    """Create and save a horizontal bar chart for rankings or long category names.

    Provide one numeric value for each category. Returns the saved image path.
    """
    if not labels or len(labels) != len(values):
        raise ValueError("labels and values must have the same non-zero length.")

    def draw(axes: plt.Axes) -> None:
        axes.barh(labels, values)
        axes.set_xlabel(x_label)
        axes.set_ylabel(y_label)

    return _save_figure(title, draw)


def stackplot(
    x_values: list[str],
    series: dict[str, list[float]],
    title: str,
    x_label: str = "",
    y_label: str = "",
) -> str:
    """Create and save a stacked area chart showing how totals are composed over x.

    Use for multiple non-negative series measured at the same ordered x-values,
    such as category contributions over time. Returns the saved image path.
    """
    if not x_values or not series:
        raise ValueError("x_values and series must not be empty.")
    if any(len(values) != len(x_values) for values in series.values()):
        raise ValueError("Each series must have one value for every x_value.")
    if any(value < 0 for values in series.values() for value in values):
        raise ValueError("Stacked area chart values must be non-negative.")

    def draw(axes: plt.Axes) -> None:
        axes.stackplot(x_values, *series.values(), labels=list(series))
        axes.set_xlabel(x_label)
        axes.set_ylabel(y_label)
        axes.tick_params(axis="x", labelrotation=30)
        axes.legend(loc="upper left")

    return _save_figure(title, draw)


def imshow(
    data: list[list[float]],
    title: str,
    x_labels: list[str] | None = None,
    y_labels: list[str] | None = None,
) -> str:
    """Create and save a heatmap from a rectangular numeric matrix.

    Use to visualize a two-dimensional grid or intensity matrix, not ordinary
    category comparisons. Optional x_labels and y_labels label the matrix
    columns and rows. Returns the saved image path.
    """
    matrix = np.asarray(data, dtype=float)
    if matrix.ndim != 2 or not matrix.size:
        raise ValueError("data must be a non-empty rectangular numeric matrix.")
    if x_labels is not None and len(x_labels) != matrix.shape[1]:
        raise ValueError("x_labels must match the number of matrix columns.")
    if y_labels is not None and len(y_labels) != matrix.shape[0]:
        raise ValueError("y_labels must match the number of matrix rows.")

    def draw(axes: plt.Axes) -> None:
        image = axes.imshow(matrix, aspect="auto", interpolation="nearest")
        axes.figure.colorbar(image, ax=axes)
        if x_labels is not None:
            axes.set_xticks(range(len(x_labels)), labels=x_labels, rotation=30)
        if y_labels is not None:
            axes.set_yticks(range(len(y_labels)), labels=y_labels)

    return _save_figure(title, draw)
