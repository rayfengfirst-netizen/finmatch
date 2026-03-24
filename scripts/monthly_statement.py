"""
月度对账单：出入库记录 + 账单 → 按采购单号/SKU 汇总并与账单数量、金额比对，输出 Excel。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from inout_excel import process_inout_dataframe
from reconcile_bill import load_bill_excel, reconcile_bill_rows, write_reconciliation_excel


def _diff_stats(merged: pd.DataFrame) -> dict:
    """统计数量/金额存在差异的行数（与两位小数舍入一致，忽略浮点噪声）。"""
    qd = pd.to_numeric(merged["数量差异"], errors="coerce").fillna(0)
    ad = pd.to_numeric(merged["金额差异"], errors="coerce").fillna(0)
    tol = 0.005
    n_qty = int((qd.abs() > tol).sum())
    n_amt = int((ad.abs() > tol).sum())
    n_any = int(((qd.abs() > tol) | (ad.abs() > tol)).sum())
    return {
        "rows_with_qty_diff": n_qty,
        "rows_with_amount_diff": n_amt,
        "rows_with_any_diff": n_any,
        "bill_rows": int(len(merged)),
    }


def run(payload: dict) -> dict:
    paths = payload.get("paths") or {}
    inout_s = paths.get("inout")
    supplier_s = paths.get("supplier")
    output_dir_s = payload.get("output_dir")

    if not inout_s or not supplier_s:
        return {"ok": False, "error": "缺少 paths.inout 或 paths.supplier"}
    if not output_dir_s:
        return {"ok": False, "error": "缺少 output_dir"}

    inout_path = Path(inout_s)
    supplier_path = Path(supplier_s)
    out_dir = Path(output_dir_s)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not inout_path.is_file() or not supplier_path.is_file():
        return {"ok": False, "error": "源文件不存在或不可读"}

    if inout_path.suffix.lower() != ".xlsx":
        return {
            "ok": False,
            "error": "出入库记录请上传 .xlsx 格式（当前扩展名：%s）" % inout_path.suffix,
        }
    if supplier_path.suffix.lower() != ".xlsx":
        return {
            "ok": False,
            "error": "账单请上传 .xlsx 格式（当前扩展名：%s）" % supplier_path.suffix,
        }

    proc = process_inout_dataframe(inout_path)
    if not proc.get("ok"):
        return {"ok": False, "error": proc.get("error") or "出入库表格处理失败"}

    inout_df = proc["df"]

    bill_load = load_bill_excel(supplier_path)
    if not bill_load.get("ok"):
        return {"ok": False, "error": bill_load.get("error") or "账单读取失败"}

    bill_df = bill_load["df"]

    try:
        merged = reconcile_bill_rows(inout_df, bill_df)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    result_filename = "reconciliation_result.xlsx"
    result_path = out_dir / result_filename

    try:
        write_reconciliation_excel(merged, inout_df, result_path)
    except Exception as e:
        return {"ok": False, "error": f"写入结果 Excel 失败：{e}"}

    stats = _diff_stats(merged)

    return {
        "ok": True,
        "result_filename": result_filename,
        "summary": {
            "inout_rows_before": proc.get("rows_before"),
            "inout_rows_after_filter": proc.get("rows_after"),
            "bill_rows": stats["bill_rows"],
            "rows_with_any_diff": stats["rows_with_any_diff"],
            "rows_with_qty_diff": stats["rows_with_qty_diff"],
            "rows_with_amount_diff": stats["rows_with_amount_diff"],
            "result_path": str(result_path.resolve()),
        },
        "messages": [
            "已按「采购单号+SKU」与出入库「来源单号+sku」汇总变动与入库总价，"
            "并与账单「数量」「合计金额」比对；差异见列「数量差异」「金额差异」。"
            "结果含工作表「账单核对」「出入库明细_筛选后」。",
        ],
    }
