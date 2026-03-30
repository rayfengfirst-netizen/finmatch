# 财配台 FinMatch

面向财务的内部小工具：在网页端提交数据（表单或 JSON），由后端按任务类型调用对应脚本并返回匹配/处理结果。

- **GitHub**：[rayfengfirst-netizen/finmatch](https://github.com/rayfengfirst-netizen/finmatch.git)
- **线上部署**：见 [README_DEPLOY.md](./README_DEPLOY.md)（生产端口 **8870**）

## 目录结构

| 路径 | 说明 |
|------|------|
| `backend/` | FastAPI 服务：接收提交、路由到脚本、返回 JSON |
| `scripts/` | 财务脚本目录：每个脚本实现统一入口，便于注册与调用 |
| `static/` | 静态页面：`index.html` 为工具总面板；各功能有独立页面（如 `monthly_statement.html`） |

## 本地运行

默认使用 **8770** 端口（与 8765 等常见占用错开）。可用 `PORT` 覆盖。

```bash
cd finmatch/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
chmod +x run_dev.sh         # 仅首次
./run_dev.sh
```

或直接：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8770
```

浏览器打开：<http://127.0.0.1:8770/>（工具总面板），月度对账单：<http://127.0.0.1:8770/monthly-statement>

### 月度对账单（已落地）

1. 页面上传两份文件：出入库记录、供应商对账单（单文件上限 50MB）。
2. `POST /api/monthly-statement/run` 保存到 `data/jobs/<job_id>/`，调用 `scripts/monthly_statement.py`。
3. 出入库预处理：新增 `入库总价 = 变动 * 入库价`，并筛选出入库类型（采购入库/退货出库）。
4. 账单预处理：按 `供应商名称 + 采购单号 + SKU`（若无供应商则 `采购单号 + SKU`）先汇总数量与合计金额，再做对账。
5. 对账输出 `reconciliation_result.xlsx`（工作表：`账单核对`、`出入库明细_筛选后`），数值统一两位小数。
6. 历史记录：`GET /api/monthly-statement/runs` 查询，支持下载当次上传文件与结果文件。

完整规则见：`docs/REQUIREMENTS_MONTHLY_RECONCILIATION.md`。

## 扩展脚本

1. 在 `scripts/` 下新增 Python 文件，实现 `run(payload: dict) -> dict`。
2. 在 `backend/app/registry.py` 的 `SCRIPT_REGISTRY` 中注册 `脚本 ID → 模块路径`。
3. 前端「任务类型」下拉会随注册表更新（通过 `/api/scripts`）。

## 环境变量

复制 `backend/.env.example` 为 `backend/.env`，按需修改（如端口、调试开关）。
