"""
出入库记录 Excel：新增「入库总价」= 变动 × 入库价，仅保留出入库类型为「采购入库」「退货出库」的行。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from excel_round import round_numeric_columns

KEEP_TYPES = frozenset({"采购入库", "退货出库"})


def process_inout_dataframe(src: Path) -> dict:
    """
    读取出入库 xlsx，插入「入库总价」，筛选类型，返回 DataFrame。
    成功：{"ok": True, "df": df, "rows_before", "rows_after"}；失败：{"ok": False, "error": "..."}。
    """
    try:
        df = pd.read_excel(src, sheet_name=0, header=0, engine="openpyxl")
    except Exception as e:
        return {"ok": False, "error": f"无法读取 Excel：{e}"}

    df.columns = df.columns.astype(str).str.strip()

    for c in ("变动", "入库价", "出入库类型"):
        if c not in df.columns:
            return {
                "ok": False,
                "error": f"缺少列「{c}」。当前表头前 15 列：{list(df.columns)[:15]}",
            }

    bd = pd.to_numeric(df["变动"], errors="coerce")
    inj = pd.to_numeric(df["入库价"], errors="coerce")
    total = bd * inj

    cols = list(df.columns)
    insert_at = cols.index("入库价") + 1
    df.insert(insert_at, "入库总价", total)

    rows_before = len(df)
    typ = df["出入库类型"].astype(str).str.strip()
    mask = typ.isin(KEEP_TYPES)
    df = df.loc[mask].copy()
    rows_after = len(df)

    df = round_numeric_columns(df, 2)

    return {
        "ok": True,
        "df": df,
        "rows_before": int(rows_before),
        "rows_after": int(rows_after),
    }


def process_inout_excel(src: Path, dest: Path) -> dict:
    """
    读取 xlsx，插入「入库总价」列（在「入库价」右侧），筛选类型后写入 dest。
    成功返回 {"ok": True, "rows_before", "rows_after", ...}；失败返回 {"ok": False, "error": "..."}。
    """
    built = process_inout_dataframe(src)
    if not built.get("ok"):
        return built
    df = built["df"]

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(dest, index=False, engine="openpyxl")
    except Exception as e:
        return {"ok": False, "error": f"写入 Excel 失败：{e}"}

    return {
        "ok": True,
        "rows_before": built["rows_before"],
        "rows_after": built["rows_after"],
        "dest": str(dest.resolve()),
    }
