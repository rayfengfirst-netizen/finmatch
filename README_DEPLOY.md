# FinMatch（财配台）部署说明

面向服务器 **`root@8.218.58.28`** 的首发与日常发布；敏感信息勿写入本文。

## 1）项目信息

| 项 | 值 |
|----|-----|
| GitHub | [https://github.com/rayfengfirst-netizen/finmatch.git](https://github.com/rayfengfirst-netizen/finmatch.git)（分支 `main`） |
| 服务器代码目录 | `/opt/finmatch` |
| systemd 服务名 | `finmatch` |
| 线上端口 | **8870**（`0.0.0.0`，与本地默认 8770 区分） |
| 访问示例 | `http://8.218.58.28:8870/` |

进程：`Gunicorn` + `uvicorn.workers.UvicornWorker`（见 `deploy/finmatch.service.example`）。

## 2）首次部署（服务器）

在**已能 SSH** 的机器上执行（按需调整分支名）。

```bash
ssh root@8.218.58.28

mkdir -p /opt/finmatch
cd /opt/finmatch
git clone https://github.com/rayfengfirst-netizen/finmatch.git .
# 若仓库为空，可先在本机 push 后再 clone；见 §5

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

cp .env.example .env
# 按需编辑 .env（如 DEBUG=false）

sudo cp /opt/finmatch/deploy/finmatch.service.example /etc/systemd/system/finmatch.service
sudo systemctl daemon-reload
sudo systemctl enable finmatch
sudo systemctl start finmatch
sudo systemctl status finmatch --no-pager
```

**云安全组 / 防火墙**：放行 **TCP 8870**（若仅内网使用则不必对公网开放）。

验收：

```bash
curl -sS http://127.0.0.1:8870/api/health
ss -tlnp | grep 8870
```

## 3）日常发布

服务器一键脚本。首次在服务器执行：

```bash
cp /opt/finmatch/deploy/deploy.sh.example /opt/finmatch/deploy.sh
chmod +x /opt/finmatch/deploy.sh
```

之后每次：

```bash
ssh root@8.218.58.28
bash /opt/finmatch/deploy.sh
```

脚本内容见仓库内 `deploy/deploy.sh.example`。

## 4）常用运维命令

```bash
systemctl status finmatch --no-pager
journalctl -u finmatch -n 100 --no-pager
systemctl restart finmatch
```

数据目录：`/opt/finmatch/data/`（任务与历史记录，勿误删；已在 `.gitignore`）。

## 5）本地推送到 GitHub（空仓库首发）

在本机项目根目录（`finmatch/` 上一级若需单独成库，则在 `finmatch` 内初始化）：

```bash
cd /path/to/finmatch
git init
git branch -M main
git remote add origin https://github.com/rayfengfirst-netizen/finmatch.git
git add .
git commit -m "chore: initial finmatch"
git push -u origin main
```

若 `git push` 需登录，请使用 GitHub 账号 **Personal Access Token** 或 SSH 远程 URL。

## 6）端口说明

| 环境 | 端口 | 说明 |
|------|------|------|
| 本地开发 | 8770（默认） | `./run_dev.sh` 或 `PORT=8770` |
| 生产 | **8870** | systemd / Gunicorn 绑定 |

## 7）修订记录

| 日期 | 说明 |
|------|------|
| 2026-03-24 | 首发：8870、GitHub、systemd、deploy 脚本 |
