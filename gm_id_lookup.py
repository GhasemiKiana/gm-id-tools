# gm_id_lookup.py
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, Optional
CSV_PATH_DEFAULT = "nmos_22nm_results.csv"

# Default CSV path (change if you put the CSV elsewhere)


def _find_column_by_candidates(cols, candidates):
    cols_lower = [c.lower() for c in cols]
    for cand in candidates:
        for i, cl in enumerate(cols_lower):
            if cand.lower() == cl:
                return cols[i]
    return None


def load_and_prepare(csv_path: str = CSV_PATH_DEFAULT) -> Tuple[pd.DataFrame, str]:
    """
    Load CSV and detect gm/Id column automatically.
    If gm_id column does not exist, compute gm/Id from gm and Id.

    Returns:
        df (pandas.DataFrame), gm_id_col (str)
    """
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    columns = df.columns.tolist()

    # Possible candidate names
    gm_id_candidates = ["gm_id", "gm/id", "gm/id", "gm/id", "gm id", "gm/id_v"]
    gm_candidates = ["gm", "g_m", "g_m"]
    id_candidates = ["id", "i_d", "current"]

    # Try find existing gm/Id col
    gm_id_col = None
    for c in columns:
        low = c.lower()
        if "gm" in low and "id" in low:
            gm_id_col = c
            break

    # Detect gm and Id columns if needed
    gm_col = _find_column_by_candidates(columns, gm_candidates)
    id_col = _find_column_by_candidates(columns, id_candidates)

    # If gm_id not found, attempt compute using detected gm and id
    if gm_id_col is None:
        if gm_col and id_col:
            # try numeric conversion
            df[gm_col] = pd.to_numeric(df[gm_col], errors="coerce")
            df[id_col] = pd.to_numeric(df[id_col], errors="coerce")
            df["gm_id_computed"] = df[gm_col] / df[id_col]
            gm_id_col = "gm_id_computed"
        else:
            raise ValueError("No gm/Id column found and cannot compute from gm and Id. "
                             "Make sure your CSV has gm and id or a gm_id column.")

    # ensure gm_id column numeric
    df[gm_id_col] = pd.to_numeric(df[gm_id_col], errors="coerce")

    return df, gm_id_col


def lookup_gm_id(target_gm_id: float,
                 csv_path: str = CSV_PATH_DEFAULT,
                 return_interpolated: bool = True,
                 required_columns: Optional[list] = None) -> Dict[str, Any]:
    """
    Lookup function for gm/Id.
    Returns a dict with:
      - type: "exact" or "interp"
      - rows: exact rows (if exact)
      - nearest_row: measured nearest row (pandas Series)
      - interpolated: dict of interpolated numeric values (if interp)
      - warning: text if extrapolating
    """
    df, gm_id_col = load_and_prepare(csv_path)
    df = df.dropna(subset=[gm_id_col]).reset_index(drop=True)
    if df.empty:
        raise RuntimeError("No numeric gm/Id data found in CSV.")

    # Exact match?
    exact_mask = np.isclose(df[gm_id_col].values, float(target_gm_id), atol=1e-12, rtol=0)
    exact_rows = df[exact_mask]
    if len(exact_rows) > 0:
        return {"type": "exact", "rows": exact_rows, "gm_id_col": gm_id_col}

    # Sort and create unique x for interpolation
    df_sorted = df.sort_values(by=gm_id_col).reset_index(drop=True)
    x = df_sorted[gm_id_col].values
    # Unique gm/Id values (keep first occurrence)
    unique_mask = np.concatenate(([True], x[1:] != x[:-1]))
    x_unique = x[unique_mask]
    df_unique = df_sorted.iloc[np.where(unique_mask)[0]]

    # Extrapolation check
    warning = None
    if target_gm_id < x_unique.min() or target_gm_id > x_unique.max():
        warning = f"Requested gm/Id={target_gm_id} is outside measured range [{x_unique.min()}, {x_unique.max()}]. Results will be extrapolated."

    interp_vals = None
    if return_interpolated:
        numeric_cols = df_unique.select_dtypes(include=[np.number]).columns.tolist()
        if required_columns:
            numeric_cols = [c for c in numeric_cols if c in required_columns]
        interp_vals = {}
        for c in numeric_cols:
            y = df_unique[c].values
            interp_vals[c] = float(np.interp(float(target_gm_id), x_unique, y))

    # Nearest measured row (from original sorted data)
    diffs = np.abs(x - float(target_gm_id))
    nearest_idx = int(np.argmin(diffs))
    nearest_row = df_sorted.iloc[nearest_idx]

    return {
        "type": "interp",
        "interpolated": interp_vals,
        "nearest_row": nearest_row,
        "warning": warning,
        "gm_id_col": gm_id_col
    }


# Expose API
__all__ = ["load_and_prepare", "lookup_gm_id", "CSV_PATH_DEFAULT"]