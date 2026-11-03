from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .descriptive import summarize_series


def histogram(values: pd.Series, bins: int = 10) -> tuple[list[dict[str, float | int]], dict[str, Any]]:
    observed = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    observed = observed[np.isfinite(observed)]
    summary = summarize_series(pd.Series(observed))
    if observed.size == 0:
        return [], summary
    counts, edges = np.histogram(observed, bins=bins)
    rows = [
        {"from": float(edges[index]), "to": float(edges[index + 1]), "count": int(counts[index])}
        for index in range(len(counts))
    ]
    return rows, summary

