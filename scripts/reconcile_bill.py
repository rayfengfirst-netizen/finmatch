"""
账单与出入库明细核对：采购单号 + SKU 关联 来源单号 + sku，汇总变动与入库总价后与账单比对。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from excel_round import round_numeric_columns

BILL_REQUIRED = ("采购单号", "SKU", "数量", "合计金额")
INOUT_REQUIRED = ("来源单号", "sku", "变动", "入库总价")


def _clean_numeric_noise(s: pd.Series, *, decimals: int, zero_tol: float) -> pd.Series:
    """浮点减法会留下 ~1e-13 级残差，Excel 会显示成科学计数法；舍入并把接近 0 的当作 0。"""
    x = pd.to_numeric(s, errors="coerce").round(decimals)
    return x.where(x.abs() > zero_tol, 0.0)


def load_bill_excel(path: Path) -> dict:
    """读取账单 xlsx，首行为表头。"""
    try:
        df = pd.read_excel(path, sheet_name=0, header=0, engine="openpyxl")
    except Exception as e:
        return {"ok": False, "error": f"无法读取账单 Excel：{e}"}
    df.columns = df.columns.astype(str).str.strip()
    for c in BILL_REQUIRED:
        if c not in df.columns:
            return {
                "ok": False,
                "error": f"账单缺少列「{c}」。当前列：{list(df.columns)}",
            }
    return {"ok": True, "df": df}


def reconcile_bill_rows(inout_df: pd.DataFrame, bill_df: pd.DataFrame) -> pd.DataFrame:
    """
    按「采购单号」「SKU」与出入库「来源单号」「sku」对齐，汇总后追加列并计算差异。
    新增列：出入库变动合计、出入库入库总价合计、数量差异、金额差异。
    """
    inv = inout_df.copy()
    inv.columns = inv.columns.astype(str).str.strip()
    for c in INOUT_REQUIRED:
        if c not in inv.columns:
            raise ValueError(f"出入库表缺少列「{c}」")

    bill = bill_df.copy()
    bill.columns = bill.columns.astype(str).str.strip()
    for c in BILL_REQUIRED:
        if c not in bill.columns:
            raise ValueError(f"账单缺少列「{c}」")

    inv = inv.copy()
    inv["来源单号"] = inv["来源单号"].astype(str).str.strip()
    inv["sku"] = inv["sku"].astype(str).str.strip()
    inv["变动"] = pd.to_numeric(inv["变动"], errors="coerce").fillna(0)
    inv["入库总价"] = pd.to_numeric(inv["入库总价"], errors="coerce").fillna(0)

    agg = inv.groupby(["来源单号", "sku"], as_index=False).agg(
        出入库变动合计=("变动", "sum"),
        出入库入库总价合计=("入库总价", "sum"),
    )
    agg = agg.rename(columns={"来源单号": "采购单号", "sku": "SKU"})

    bill["采购单号"] = bill["采购单号"].astype(str).str.strip()
    bill["SKU"] = bill["SKU"].astype(str).str.strip()
    bill["数量"] = pd.to_numeric(bill["数量"], errors="coerce")
    bill["合计金额"] = pd.to_numeric(bill["合计金额"], errors="coerce")

    merged = bill.merge(agg, on=["采购单号", "SKU"], how="left")
    merged["出入库变动合计"] = merged["出入库变动合计"].fillna(0)
    merged["出入库入库总价合计"] = merged["出入库入库总价合计"].fillna(0)

    merged["数量差异"] = merged["出入库变动合计"] - merged["数量"]
    merged["金额差异"] = merged["出入库入库总价合计"] - merged["合计金额"]

    merged = round_numeric_columns(merged, 2)
    merged["数量差异"] = _clean_numeric_noise(merged["数量差异"], decimals=2, zero_tol=0.005)
    merged["金额差异"] = _clean_numeric_noise(merged["金额差异"], decimals=2, zero_tol=0.005)

    return merged


def write_reconciliation_excel(
    bill_with_diff: pd.DataFrame,
    inout_filtered: pd.DataFrame,
    dest: Path,
) -> None:
    """Sheet1 账单核对；Sheet2 出入库明细（筛选后）。"""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    bill_out = round_numeric_columns(bill_with_diff, 2)
    inout_out = round_numeric_columns(inout_filtered, 2)
    with pd.ExcelWriter(dest, engine="openpyxl") as writer:
        bill_out.to_excel(writer, sheet_name="账单核对", index=False)
        inout_out.to_excel(writer, sheet_name="出入库明细_筛选后", index=False)
