from __future__ import annotations

import io
import threading
from collections.abc import Sequence
from typing import Literal

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ChartKind = Literal["bar", "histogram", "scatter", "line", "boxplot", "correlation_heatmap"]
_RENDER_LOCK = threading.RLock()


def render_png(
    frame: pd.DataFrame,
    *,
    kind: ChartKind,
    metrics: Sequence[str],
    group_by: str | None = None,
    method: str = "pearson",
) -> bytes:
    """Render one controlled, bounded analytical figure without shared pyplot races."""
    if frame.empty:
        raise ValueError("No observed rows qualify for this visualization")
    with _RENDER_LOCK, plt.rc_context({
        "figure.facecolor": "#111511", "axes.facecolor": "#111511", "savefig.facecolor": "#111511",
        "axes.edgecolor": "#46513f", "axes.labelcolor": "#cdd4c5", "xtick.color": "#a2ac9a",
        "ytick.color": "#a2ac9a", "text.color": "#e6ecdf", "grid.color": "#293126",
        "font.size": 9,
    }):
        figure, axis = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
        try:
            if kind == "histogram":
                metric = metrics[0]
                data = pd.to_numeric(frame[metric], errors="coerce").dropna()
                if data.empty:
                    raise ValueError("No observed values qualify for this visualization")
                sns.histplot(data=data, bins="auto", color="#c7f36b", edgecolor="#111511", ax=axis)
                axis.axvline(data.mean(), color="#f0d56c", linestyle="--", linewidth=1.5, label="Mean")
                axis.axvline(data.median(), color="#79c8ff", linestyle=":", linewidth=1.7, label="Median")
                axis.set(xlabel=metric.replace("_", " ").title(), ylabel="Player records", title=f"Distribution of {metric.replace('_', ' ').title()}")
                axis.legend(frameon=False)
            elif kind == "boxplot":
                metric = metrics[0]
                clean = frame.loc[frame[metric].notna()].copy()
                if clean.empty:
                    raise ValueError("No observed values qualify for this visualization")
                order = None
                x_value = group_by if group_by and group_by in clean.columns else None
                if x_value:
                    order = clean.groupby(x_value)[metric].median().sort_values().index.tolist()[:20]
                    clean = clean[clean[x_value].isin(order)]
                sns.boxplot(data=clean, x=x_value, y=metric, order=order, color="#c7f36b", fliersize=3, ax=axis)
                axis.set(xlabel=(x_value or "All records").replace("_", " ").title(), ylabel=metric.replace("_", " ").title(), title=f"{metric.replace('_', ' ').title()} distribution")
                if x_value:
                    axis.tick_params(axis="x", rotation=25)
            elif kind == "scatter":
                left, right = metrics[:2]
                clean = frame[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
                if clean.empty:
                    raise ValueError("No paired observations qualify for this visualization")
                sns.scatterplot(data=clean, x=left, y=right, color="#c7f36b", edgecolor="#111511", alpha=.72, ax=axis)
                axis.set(title=f"{left.replace('_', ' ').title()} vs {right.replace('_', ' ').title()}")
            elif kind == "correlation_heatmap":
                values = frame[list(metrics)].apply(pd.to_numeric, errors="coerce")
                correlations = values.corr(method=method, min_periods=3)
                if correlations.isna().all().all():
                    raise ValueError("Correlation is unavailable for these metrics in this scope")
                sns.heatmap(correlations, annot=True, fmt=".2f", cmap=sns.diverging_palette(12, 140, as_cmap=True), center=0, vmin=-1, vmax=1, linewidths=.5, linecolor="#293126", mask=correlations.isna(), cbar_kws={"label": f"{method.title()} correlation"}, ax=axis)
                axis.set(title=f"{method.title()} correlation · descriptive association")
            else:
                metric = metrics[0]
                group = group_by if group_by and group_by in frame.columns else "competition"
                clean = frame.loc[frame[metric].notna()]
                if clean.empty:
                    raise ValueError("No observed values qualify for this visualization")
                grouped = clean.groupby(group, dropna=False)[metric].mean().sort_values(ascending=False).head(20)
                if kind == "bar":
                    grouped.sort_values().plot(kind="barh", color="#c7f36b", ax=axis)
                    axis.set(xlabel=f"Mean {metric.replace('_', ' ')}", ylabel=group.title(), title=f"Mean {metric.replace('_', ' ').title()} by {group}")
                else:
                    grouped = grouped.sort_index()
                    axis.plot(grouped.index.astype(str), grouped.values, color="#c7f36b", marker="o", linewidth=2)
                    axis.set(xlabel=group.title(), ylabel=f"Mean {metric.replace('_', ' ')}", title=f"Mean {metric.replace('_', ' ').title()} by {group}")
                    axis.tick_params(axis="x", rotation=25)
            axis.grid(True, axis="y", alpha=.3)
            axis.set_axisbelow(True)
            buffer = io.BytesIO()
            figure.savefig(buffer, format="png", dpi=140, bbox_inches="tight")
            return buffer.getvalue()
        finally:
            plt.close(figure)


def render_missingness_png(frame: pd.DataFrame) -> bytes:
    """Render per-column missingness for the currently loaded source release."""
    with _RENDER_LOCK, plt.rc_context({
        "figure.facecolor": "#111511", "axes.facecolor": "#111511", "savefig.facecolor": "#111511",
        "axes.edgecolor": "#46513f", "axes.labelcolor": "#cdd4c5", "xtick.color": "#a2ac9a",
        "ytick.color": "#a2ac9a", "text.color": "#e6ecdf", "grid.color": "#293126", "font.size": 9,
    }):
        missing = (frame.isna().mean() * 100).sort_values(ascending=True)
        missing = missing.loc[missing > 0].tail(20)
        figure, axis = plt.subplots(figsize=(9, max(3.5, min(8, .28 * max(1, len(missing))))), constrained_layout=True)
        try:
            if missing.empty:
                axis.text(.5, .5, "No missing observations in this scope", ha="center", va="center", color="#c7f36b", transform=axis.transAxes)
                axis.set_axis_off()
            else:
                sns.barplot(x=missing.to_numpy(), y=missing.index.to_list(), color="#c7f36b", ax=axis)
                axis.set(xlim=(0, 100), xlabel="Missing records (%)", ylabel="Column", title="Current release · column missingness (top 20)")
                axis.grid(True, axis="x", alpha=.3)
                axis.set_axisbelow(True)
            buffer = io.BytesIO()
            figure.savefig(buffer, format="png", dpi=140, bbox_inches="tight")
            return buffer.getvalue()
        finally:
            plt.close(figure)

