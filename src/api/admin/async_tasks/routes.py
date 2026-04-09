from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.models.admin_async_tasks import (
    AdminAsyncTaskDetail,
    AdminAsyncTaskItem,
    AdminAsyncTaskListResponse,
    AdminAsyncTaskStatsResponse,
)
from src.models.database import Provider, User, VideoTask
from src.models.provider_import import AllInHubImportJobStatusResponse
from src.services.provider_import.async_job import (
    get_all_in_hub_import_job,
    list_all_in_hub_import_jobs,
)
from src.services.provider_query.async_job import (
    get_provider_refresh_sync_job,
    list_provider_refresh_sync_jobs,
)
from src.services.provider_ops.async_job import (
    get_provider_proxy_probe_job,
    list_provider_proxy_probe_jobs,
)
from src.utils.auth_utils import get_current_user

router = APIRouter(prefix="/api/admin/async-tasks", tags=["Admin - Async Tasks"])

TASK_TYPE_VIDEO = "video"
TASK_TYPE_PROVIDER_IMPORT = "provider_import"
TASK_TYPE_PROVIDER_REFRESH_SYNC = "provider_refresh_sync"
TASK_TYPE_PROVIDER_PROXY_PROBE = "provider_proxy_probe"


def _safe_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _safe_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _build_provider_import_item(job: AllInHubImportJobStatusResponse) -> AdminAsyncTaskItem:
    summary_bits: list[str] = []
    if job.import_result is not None:
        summary_bits.append(f"新增 Provider {job.import_result.stats.providers_created}")
        summary_bits.append(f"新增 Endpoint {job.import_result.stats.endpoints_created}")
        if job.import_result.stats.keys_created > 0:
            summary_bits.append(f"新增 Key {job.import_result.stats.keys_created}")
    if not summary_bits and job.message:
        summary_bits.append(job.message)

    return AdminAsyncTaskItem(
        id=f"{TASK_TYPE_PROVIDER_IMPORT}:{job.task_id}",
        task_type=TASK_TYPE_PROVIDER_IMPORT,
        status=job.status,
        stage=job.stage,
        title="All-in-Hub 导入",
        summary="；".join(summary_bits),
        created_at=job.created_at,
        updated_at=job.updated_at,
        source_task_id=job.task_id,
    )


def _build_provider_refresh_item(job: Any) -> AdminAsyncTaskItem:
    summary = str(getattr(job, "message", "") or "")
    result = getattr(job, "result", None)
    if isinstance(result, dict):
        failed_count = int(result.get("providers_with_errors") or 0)
        if failed_count > 0 and f"失败 {failed_count}" not in summary:
            summary = f"{summary}；失败 {failed_count} 个渠道商".strip("；")
    title = "刷新并适配全部渠道商" if getattr(job, "scope", "") == "all" else (
        f"刷新并适配 {getattr(job, 'provider_name', None) or '指定渠道商'}"
    )


def _build_provider_proxy_probe_item(job: Any) -> AdminAsyncTaskItem:
    summary = str(getattr(job, "message", "") or "")
    result = getattr(job, "result", None)
    if isinstance(result, dict):
        failed_count = int(result.get("failed") or 0)
        if failed_count > 0 and f"失败 {failed_count}" not in summary:
            summary = f"{summary}；失败 {failed_count} 个渠道商".strip("；")
    title = "全局代理检测" if getattr(job, "scope", "") == "all" else (
        f"代理检测 {getattr(job, 'provider_name', None) or '指定渠道商'}"
    )
    return AdminAsyncTaskItem(
        id=f"{TASK_TYPE_PROVIDER_PROXY_PROBE}:{job.task_id}",
        task_type=TASK_TYPE_PROVIDER_PROXY_PROBE,
        status=job.status,
        stage=job.stage,
        title=title,
        summary=summary,
        provider_id=getattr(job, "provider_id", None),
        provider_name=getattr(job, "provider_name", None),
        created_at=job.created_at,
        updated_at=job.updated_at,
        source_task_id=job.task_id,
    )
    return AdminAsyncTaskItem(
        id=f"{TASK_TYPE_PROVIDER_REFRESH_SYNC}:{job.task_id}",
        task_type=TASK_TYPE_PROVIDER_REFRESH_SYNC,
        status=job.status,
        stage=job.stage,
        title=title,
        summary=summary,
        provider_id=getattr(job, "provider_id", None),
        provider_name=getattr(job, "provider_name", None),
        created_at=job.created_at,
        updated_at=job.updated_at,
        source_task_id=job.task_id,
    )


def _build_video_item(task: VideoTask, providers_map: dict[str, str], users_map: dict[str, str]) -> AdminAsyncTaskItem:
    summary = task.progress_message or task.prompt or ""
    if summary and len(summary) > 120:
        summary = f"{summary[:117]}..."
    return AdminAsyncTaskItem(
        id=f"{TASK_TYPE_VIDEO}:{task.id}",
        task_type=TASK_TYPE_VIDEO,
        status=task.status,
        stage=task.status,
        title=task.model or "视频任务",
        summary=summary,
        provider_id=task.provider_id,
        provider_name=providers_map.get(task.provider_id or "", "Unknown"),
        model=task.model,
        progress_percent=int(task.progress_percent or 0),
        created_at=_safe_iso(task.created_at),
        updated_at=_safe_iso(task.updated_at),
        completed_at=_safe_iso(task.completed_at),
        source_task_id=task.id,
    )


async def list_admin_async_tasks(
    db: Session,
    current_user: User,
    *,
    status: str | None = None,
    task_type: str | None = None,
    model: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AdminAsyncTaskListResponse:
    del current_user

    limit = max(page_size * 3, 60)
    providers_map = {provider.id: provider.name for provider in db.query(Provider).all()}
    users_map = {user.id: user.username for user in db.query(User).all()}

    items: list[AdminAsyncTaskItem] = []

    video_query = db.query(VideoTask).order_by(VideoTask.created_at.desc()).limit(limit)
    for task in video_query.all():
        items.append(_build_video_item(task, providers_map, users_map))

    import_jobs = await list_all_in_hub_import_jobs(limit=limit)
    items.extend(_build_provider_import_item(job) for job in import_jobs.items)

    refresh_jobs = await list_provider_refresh_sync_jobs(limit=limit)
    items.extend(_build_provider_refresh_item(job) for job in refresh_jobs.items)

    proxy_probe_jobs = await list_provider_proxy_probe_jobs(limit=limit)
    items.extend(_build_provider_proxy_probe_item(job) for job in proxy_probe_jobs.items)

    filtered = items
    if task_type:
        filtered = [item for item in filtered if item.task_type == task_type]
    if status:
        filtered = [item for item in filtered if item.status == status]
    if model:
        needle = model.lower()
        filtered = [
            item for item in filtered
            if needle in str(item.title or "").lower() or needle in str(item.summary or "").lower()
        ]

    filtered.sort(
        key=lambda item: (
            _safe_datetime(item.updated_at or item.created_at),
            _safe_datetime(item.created_at),
        ),
        reverse=True,
    )

    total = len(filtered)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    page_items = filtered[start:end]
    return AdminAsyncTaskListResponse(
        items=page_items,
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


async def get_admin_async_task_stats(
    db: Session,
    current_user: User,
) -> AdminAsyncTaskStatsResponse:
    listing = await list_admin_async_tasks(db, current_user, page=1, page_size=200)
    today_floor = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    by_status: dict[str, int] = {}
    by_task_type: dict[str, int] = {}
    today_count = 0
    processing_count = 0
    active_statuses = {"pending", "submitted", "queued", "processing", "running"}

    for item in listing.items:
        by_status[item.status] = by_status.get(item.status, 0) + 1
        by_task_type[item.task_type] = by_task_type.get(item.task_type, 0) + 1
        created_at = _safe_datetime(item.created_at)
        if created_at >= today_floor:
            today_count += 1
        if item.status in active_statuses:
            processing_count += 1

    return AdminAsyncTaskStatsResponse(
        total=listing.total,
        by_status=by_status,
        by_task_type=by_task_type,
        today_count=today_count,
        processing_count=processing_count,
    )


async def get_admin_async_task_detail(task_id: str, db: Session, current_user: User) -> AdminAsyncTaskDetail:
    del current_user
    if ":" not in task_id:
        raise HTTPException(status_code=404, detail="Task not found")

    task_type, raw_id = task_id.split(":", 1)
    if task_type == TASK_TYPE_PROVIDER_IMPORT:
        job = await get_all_in_hub_import_job(raw_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Task not found")
        item = _build_provider_import_item(job)
        return AdminAsyncTaskDetail(**item.model_dump(), detail=job.model_dump(mode="json"))

    if task_type == TASK_TYPE_PROVIDER_REFRESH_SYNC:
        job = await get_provider_refresh_sync_job(raw_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Task not found")
        item = _build_provider_refresh_item(job)
        return AdminAsyncTaskDetail(**item.model_dump(), detail=job.model_dump(mode="json"))

    if task_type == TASK_TYPE_PROVIDER_PROXY_PROBE:
        job = await get_provider_proxy_probe_job(raw_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Task not found")
        item = _build_provider_proxy_probe_item(job)
        return AdminAsyncTaskDetail(**item.model_dump(), detail=job.model_dump(mode="json"))

    if task_type == TASK_TYPE_VIDEO:
        task = db.query(VideoTask).filter(VideoTask.id == raw_id).first()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        providers_map = {provider.id: provider.name for provider in db.query(Provider).all()}
        users_map = {user.id: user.username for user in db.query(User).all()}
        item = _build_video_item(task, providers_map, users_map)
        detail = {
            "video_url": task.video_url,
            "progress_message": task.progress_message,
            "error_message": task.error_message,
            "provider_id": task.provider_id,
            "user_id": task.user_id,
            "username": users_map.get(task.user_id, "Unknown"),
        }
        return AdminAsyncTaskDetail(**item.model_dump(), detail=detail)

    raise HTTPException(status_code=404, detail="Task not found")


@router.get("")
async def list_async_tasks(
    status: str | None = Query(None),
    task_type: str | None = Query(None),
    model: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminAsyncTaskListResponse:
    return await list_admin_async_tasks(
        db,
        current_user,
        status=status,
        task_type=task_type,
        model=model,
        page=page,
        page_size=page_size,
    )


@router.get("/stats")
async def get_async_task_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminAsyncTaskStatsResponse:
    return await get_admin_async_task_stats(db, current_user)


@router.get("/{task_id}")
async def get_async_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminAsyncTaskDetail:
    return await get_admin_async_task_detail(task_id, db, current_user)
