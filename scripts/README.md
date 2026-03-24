在此目录放置财务脚本。每个脚本文件需导出函数：

```python
def run(payload: dict) -> dict:
    """payload 来自网页提交的 JSON；返回值会原样展示给前端。"""
    ...
```

在 `backend/app/registry.py` 的 `SCRIPT_REGISTRY` 中登记 `脚本ID` → `模块名:run`（模块名即文件名去掉 `.py`）。
