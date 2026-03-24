import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.monthly_routes import build_router as build_monthly_router
from app.registry import SCRIPT_REGISTRY, resolve_runner

# 项目根 finmatch/ 下的 scripts/ 可被 import
_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _ROOT / "scripts"
if _SCRIPTS_DIR.is_dir() and str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

app = FastAPI(title="财配台 FinMatch", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC = _ROOT / "static"
if _STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC)), name="assets")

app.include_router(build_monthly_router(root=_ROOT))


class SubmitBody(BaseModel):
    script_id: str = Field(..., description="任务类型，对应 registry 中的脚本 ID")
    payload: dict = Field(default_factory=dict, description="业务 JSON，由脚本解析")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "finmatch"}


@app.get("/api/scripts")
def list_scripts():
    return {"scripts": [{"id": k, "label": k} for k in SCRIPT_REGISTRY.keys()]}


@app.post("/api/match")
def match(body: SubmitBody):
    try:
        runner = resolve_runner(body.script_id)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (ImportError, AttributeError, TypeError) as e:
        if settings.debug:
            raise HTTPException(status_code=500, detail=repr(e)) from e
        raise HTTPException(status_code=500, detail="脚本加载失败") from e

    try:
        result = runner(body.payload)
    except Exception as e:
        if settings.debug:
            raise HTTPException(status_code=500, detail=repr(e)) from e
        raise HTTPException(status_code=500, detail=f"脚本执行失败: {e}") from e

    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="脚本必须返回 dict")
    return {"result": result}


def _static_file(name: str) -> FileResponse:
    path = _STATIC / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"未找到 static/{name}")
    return FileResponse(str(path))


@app.get("/")
def index():
    return _static_file("index.html")


@app.get("/monthly-statement")
def monthly_statement_page():
    return _static_file("monthly_statement.html")
