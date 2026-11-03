from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd

Method = Literal["pearson", "spearman"]


def correlation_matrix(frame: pd.DataFrame, metrics: list[str], method: Method) -> dict[str, Any]:
    values = frame[metrics].apply(pd.to_numeric, errors="coerce")
    matrix = values.corr(method=method, min_periods=3)
    counts = values.notna().astype("int64").T.dot(values.notna().astype("int64"))
    serialized: list[list[float | None]] = []
    pairwise: list[list[int]] = []
    for left in metrics:
        row: list[float | None] = []
        count_row: list[int] = []
        for right in metrics:
            value = matrix.loc[left, right]
            n = int(counts.loc[left, right])
            number = float(value) if pd.notna(value) and np.isfinite(value) else None
            row.append(round(number, 4) if number is not None else None)
            count_row.append(n)
        serialized.append(row)
        pairwise.append(count_row)
    return {
        "labels": metrics,
        "matrix": serialized,
        "pairwise_n": pairwise,
        "method": "Pearson correlation" if method == "pearson" else "Spearman rank correlation",
        "note": "Descriptive association only; correlation does not imply causation. Pairs with fewer than three observed records or a constant series are unavailable. No statistical significance is calculated.",
    }


def interpret_correlation(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "Unavailable for this sample."
    magnitude = abs(value)
    strength = "negligible" if magnitude < 0.1 else "weak" if magnitude < 0.3 else "moderate" if magnitude < 0.7 else "strong"
    direction = "positive" if value > 0 else "negative" if value < 0 else "negligible"
    return f"{strength.capitalize()} {direction} association in this sample."

