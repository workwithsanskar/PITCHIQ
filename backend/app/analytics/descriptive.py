from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def summarize_series(values: pd.Series) -> dict[str, int | float | None]:
    observed = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    observed = observed[np.isfinite(observed)]
    count = int(observed.size)
    if count == 0:
        return {key: (0 if key == "count" else None) for key in (
            "count", "mean", "median", "standard_deviation", "variance", "minimum",
            "q1", "q2", "q3", "interquartile_range", "maximum",
        )}
    q1, q2, q3 = (float(item) for item in np.percentile(observed, [25, 50, 75]))
    return {
        "count": count,
        "mean": _number(np.mean(observed)),
        "median": _number(np.median(observed)),
        "standard_deviation": _number(np.std(observed, ddof=1)) if count > 1 else None,
        "variance": _number(np.var(observed, ddof=1)) if count > 1 else None,
        "minimum": _number(np.min(observed)),
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "interquartile_range": q3 - q1,
        "maximum": _number(np.max(observed)),
    }


def summarize_frame(frame: pd.DataFrame, metrics: list[str]) -> list[dict[str, Any]]:
    return [{"metric": metric, **summarize_series(frame[metric])} for metric in metrics]


def grouped_summaries(frame: pd.DataFrame, metrics: list[str], group_by: str) -> list[dict[str, Any]]:
    if group_by not in {"position", "competition", "club", "season"}:
        raise ValueError("Unsupported grouping field")
    if frame.empty:
        return []
    result: list[dict[str, Any]] = []
    for label, group in frame.groupby(group_by, dropna=False, sort=True):
        result.append({
            "group": str(label) if pd.notna(label) else "Unknown",
            "record_count": int(len(group)),
            "player_count": int(group["player_id"].nunique(dropna=True)),
            "metrics": summarize_frame(group, metrics),
        })
    return result

