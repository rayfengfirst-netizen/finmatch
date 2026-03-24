"""月度对账单：双文件上传、调用脚本、提供结果下载与历史记录。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.registry import resolve_runner

_MAX_BYTES = 50 * 1024 * 1024


def build_router(*, root: Path) -> APIRouter:
    router = APIRouter(prefix="/api/monthly-statement", tags=["monthly-statement"])
    jobs_root = root / "data" / "jobs"

    async def _save_upload(dest: Path, upload: UploadFile) -> None:
        size = 0
        try:
            with dest.open("wb") as f:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > _MAX_BYTES:
                        raise HTTPException(status_code=413, detail="单个文件超过 50MB 上限")
                    f.write(chunk)
        except HTTPException:
            if dest.exists():
                dest.unlink(missing_ok=True)
            raise

    @router.post("/run")
    async def run_monthly(
        inout_file: UploadFile = File(..., description="出入库记录"),
        supplier_file: UploadFile = File(..., description="供应商对账单"),
    ):
        job_id = str(uuid.uuid4())
        job_dir = jobs_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        in_name = Path(inout_file.filename or "inout").name
        sup_name = Path(supplier_file.filename or "supplier").name
        inout_path = job_dir / f"upload_inout_{in_name}"
        supplier_path = job_dir / f"upload_supplier_{sup_name}"
        output_dir = job_dir / "output"

        try:
            await _save_upload(inout_path, inout_file)
            await _save_upload(supplier_path, supplier_file)
        except Exception:
            _rm_tree(job_dir)
            raise

        payload = {
            "job_id": job_id,
            "paths": {
                "inout": str(inout_path.resolve()),
                "supplier": str(supplier_path.resolve()),
            },
            "output_dir": str(output_dir.resolve()),
        }

        try:
            runner = resolve_runner("monthly_statement")
        except KeyError as e:
            _rm_tree(job_dir)
            raise HTTPException(status_code=500, detail=str(e)) from e

        try:
            result = runner(payload)
        except Exception as e:
            _rm_tree(job_dir)
            if settings.debug:
                raise HTTPException(status_code=500, detail=repr(e)) from e
            raise HTTPException(status_code=500, detail=f"脚本执行失败: {e}") from e

        if not isinstance(result, dict):
            _rm_tree(job_dir)
            raise HTTPException(status_code=500, detail="脚本必须返回 dict")

        if not result.get("ok"):
            _rm_tree(job_dir)
            raise HTTPException(
                status_code=400,
                detail=result.get("error") or "对账脚本返回失败",
            )

        result_file = result.get("result_filename")
        if not result_file:
            _rm_tree(job_dir)
            raise HTTPException(status_code=500, detail="脚本未返回 result_filename")

        out_file = output_dir / result_file
        if not out_file.is_file():
            _rm_tree(job_dir)
            raise HTTPException(status_code=500, detail="结果文件未生成")

        created_at = datetime.now(timezone.utc).isoformat()
        meta = {
            "job_id": job_id,
            "created_at": created_at,
            "inout_original_name": in_name,
            "supplier_original_name": sup_name,
            "inout_storage_name": inout_path.name,
            "supplier_storage_name": supplier_path.name,
            "result_filename": result_file,
            "summary": result.get("summary"),
            "messages": result.get("messages"),
        }
        (job_dir / "job_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "job_id": job_id,
            "created_at": created_at,
            "summary": result.get("summary"),
            "messages": result.get("messages"),
            "download_url": f"/api/monthly-statement/download/{job_id}",
            "inout_download_url": f"/api/monthly-statement/runs/{job_id}/download/inout",
            "supplier_download_url": f"/api/monthly-statement/runs/{job_id}/download/supplier",
        }

    def _load_job_meta(job_dir: Path) -> dict | None:
        p = job_dir / "job_meta.json"
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    @router.get("/runs")
    def list_runs():
        """列出历史对账记录（含上传与结果文件路径，供前台下载）。"""
        if not jobs_root.is_dir():
            return {"runs": []}

        items = []
        for child in jobs_root.iterdir():
            if not child.is_dir():
                continue
            try:
                uuid.UUID(child.name)
            except ValueError:
                continue
            meta = _load_job_meta(child)
            if not meta:
                continue
            created = meta.get("created_at")
            if not created:
                meta_path = child / "job_meta.json"
                try:
                    created = datetime.fromtimestamp(
                        meta_path.stat().st_mtime, tz=timezone.utc
                    ).isoformat()
                except OSError:
                    created = ""

            summary = meta.get("summary") or {}
            items.append(
                {
                    "job_id": child.name,
                    "created_at": created,
                    "inout_original_name": meta.get("inout_original_name"),
                    "supplier_original_name": meta.get("supplier_original_name"),
                    "summary": summary,
                    "result_download_url": f"/api/monthly-statement/download/{child.name}",
                    "inout_download_url": f"/api/monthly-statement/runs/{child.name}/download/inout",
                    "supplier_download_url": f"/api/monthly-statement/runs/{child.name}/download/supplier",
                }
            )

        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"runs": items[:200]}

    @router.get("/runs/{job_id}/download/inout")
    def download_inout_upload(job_id: str):
        try:
            uuid.UUID(job_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="无效的 job_id") from e

        job_dir = jobs_root / job_id
        meta = _load_job_meta(job_dir)
        if not meta:
            raise HTTPException(status_code=404, detail="任务不存在")

        name = meta.get("inout_storage_name") or f"upload_inout_{meta.get('inout_original_name', 'inout')}"
        path = job_dir / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="出入库上传文件不存在")

        dl = meta.get("inout_original_name") or name
        return FileResponse(str(path), filename=dl, media_type="application/octet-stream")

    @router.get("/runs/{job_id}/download/supplier")
    def download_supplier_upload(job_id: str):
        try:
            uuid.UUID(job_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="无效的 job_id") from e

        job_dir = jobs_root / job_id
        meta = _load_job_meta(job_dir)
        if not meta:
            raise HTTPException(status_code=404, detail="任务不存在")

        name = meta.get("supplier_storage_name") or f"upload_supplier_{meta.get('supplier_original_name', 'supplier')}"
        path = job_dir / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="账单上传文件不存在")

        dl = meta.get("supplier_original_name") or name
        return FileResponse(str(path), filename=dl, media_type="application/octet-stream")

    @router.get("/download/{job_id}")
    def download_result(job_id: str):
        try:
            uuid.UUID(job_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="无效的 job_id") from e

        job_dir = jobs_root / job_id
        meta_path = job_dir / "job_meta.json"
        if not meta_path.is_file():
            raise HTTPException(status_code=404, detail="任务不存在或已过期")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        name = meta.get("result_filename")
        if not name:
            raise HTTPException(status_code=500, detail="元数据损坏")

        path = job_dir / "output" / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="结果文件不存在")

        dl_name = f"月度对账结果_{job_id[:8]}_{name}"
        return FileResponse(
            str(path),
            filename=dl_name,
            media_type="application/octet-stream",
        )

    return router


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    import shutil

    shutil.rmtree(path, ignore_errors=True)
