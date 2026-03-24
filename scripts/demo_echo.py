"""示例脚本：原样返回提交的数据，并附加匹配标记，便于联调。"""


def run(payload: dict) -> dict:
    rows = payload.get("rows") or []
    matched = sum(1 for r in rows if isinstance(r, dict) and r.get("amount") is not None)
    return {
        "ok": True,
        "message": "示例匹配完成（demo_echo）",
        "summary": {"row_count": len(rows), "matched_count": matched},
        "detail": payload,
    }
