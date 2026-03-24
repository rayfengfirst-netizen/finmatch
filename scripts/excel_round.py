"""Excel 导出用：数值列统一保留两位小数。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def round_numeric_columns(df: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    out = df.copy()
    num_cols = out.select_dtypes(include=[np.number]).columns
    for c in num_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce").round(decimals)
    return out
