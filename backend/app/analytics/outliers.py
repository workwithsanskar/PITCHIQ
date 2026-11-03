from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def iqr_outliers(frame: pd.DataFrame, metric: str, *, multiplier: float = 1.5, limit: int = 100) -> dict[str, Any]:
    values = pd.to_numeric(frame[metric], errors="coerce")
    observed = values.dropna().to_numpy(dtype=float)
    observed = observed[np.isfinite(observed)]
    if observed.size == 0:
        return {"metric": metric, "n": 0, "q1": None, "q3": None, "iqr": None, "lower_bound": None, "upper_bound": None, "outlier_count": 0, "items": []}
    q1, q3 = (float(value) for value in np.percentile(observed, [25, 75]))
    spread = q3 - q1
    lower = q1 - multiplier * spread
    upper = q3 + multiplier * spread
    mask = values.notna() & ((values < lower) | (values > upper))
    candidates = frame.loc[mask, ["record_id", "player_id", "player", "position_raw", "club", "competition", "season", metric]].copy()
    candidates["distance_from_fence"] = np.where(candidates[metric] < lower, lower - candidates[metric], candidates[metric] - upper)
    candidates = candidates.sort_values(["distance_from_fence", metric], ascending=[False, False]).head(limit)
    items = []
    for row in candidates.to_dict(orient="records"):
        items.append({key: (None if pd.isna(value) else value.item() if isinstance(value, np.generic) else value) for key, value in row.items()})
    return {
        "metric": metric, "n": int(observed.size), "q1": q1, "q3": q3,
        "iqr": spread, "multiplier": multiplier, "lower_bound": lower, "upper_bound": upper,
        "outlier_count": int(mask.sum()), "items": items,
        "methodology": "Potential outliers are observed records below Q1 − multiplier×IQR or above Q3 + multiplier×IQR. They remain in the dataset and are not presumed erroneous.",
    }

