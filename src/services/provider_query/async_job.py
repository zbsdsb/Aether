from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.orm import joinedload, selectinload

from src.clients.redis_client import get_redis_client
from src.core.logger import logger
from src.database import create_session
from src.models.admin_async_tasks import (
    ProviderRefreshSyncJobListResponse,
    ProviderRefreshSyncJobStartResponse,
    ProviderRefreshSyncJobStatusResponse,
)
from src.models.database import Provider

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

STAGE_QUEUED = "queued"
STAGE_REFRESHING = "refreshing"
STAGE_COMPLETED = "completed"
STAGE_FAILED = "failed"

SCOPE_SINGLE = "single"
SCOPE_ALL = "all"

_TASK_RETAIN_SECONDS = 1800
_REDIS_KEY_PREFIX = "provider_refresh_sync_job"
_REDIS_LIST_KEY = "provider_refresh_sync_jobs:recent"
_RECENT_TASK_LIMIT = 100
_running_tasks: set[asyncio.Task[None]] = set()


def _task_key(task_id: str) -> str:
    return f"{_REDIS_KEY_PREFIX}:{task_id}"


@dataclass
class ProviderRefreshSyncJobInfo:
    task_id: str
    scope: str
    provider_id: str | None = None
    provider_name: str | None = None
    api_key_id: str | None = None
    only_active: bool = True
    status: str = STATUS_PENDING
    stage: str = STAGE_QUEUED
    message: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "scope": self.scope,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "api_key_id": self.api_key_id,
            "only_active": self.only_active,
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderRefreshSyncJobInfo":
        return cls(
            task_id=str(data["task_id"]),
            scope=str(data.get("scope") or SCOPE_SINGLE),
            provider_id=data.get("provider_id"),
            provider_name=data.get("provider_name"),
            api_key_id=data.get("api_key_id"),
            only_active=bool(data.get("only_active", True)),
            status=str(data.get("status") or STATUS_PENDING),
            stage=str(data.get("stage") or STAGE_QUEUED),
            message=str(data.get("message") or ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            result=data.get("result"),
        )


async def _save_job(
    job: ProviderRefreshSyncJobInfo,
    ttl: int = _TASK_RETAIN_SECONDS,
    r: aioredis.Redis | None = None,
) -> None:
    if r is None:
        r = await get_redis_client(require_redis=False)
    if not r:
        return

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        if not job.created_at:
            job.created_at = now_iso
        job.updated_at = now_iso
        await r.setex(_task_key(job.task_id), ttl, json.dumps(job.to_dict()))
    except Exception as exc:
        logger.warning("Failed to save provider refresh/sync job: {}", exc)


async def _load_job(
    task_id: str,
    r: aioredis.Redis | None = None,
) -> ProviderRefreshSyncJobInfo | None:
    if r is None:
        r = await get_redis_client(require_redis=False)
    if not r:
        return None

    try:
        data = await r.get(_task_key(task_id))
        if data is None:
            return None
        return ProviderRefreshSyncJobInfo.from_dict(json.loads(data))
    except Exception as exc:
        logger.warning("Failed to load provider refresh/sync job: {}", exc)
        return None


async def _update_job(
    task_id: str,
    *,
    r: aioredis.Redis | None = None,
    **fields: Any,
) -> None:
    job = await _load_job(task_id, r=r)
    if job is None:
        return
    for key, value in fields.items():
        setattr(job, key, value)
    ttl = _TASK_RETAIN_SECONDS if job.status in {STATUS_COMPLETED, STATUS_FAILED} else _TASK_RETAIN_SECONDS * 2
    await _save_job(job, ttl=ttl, r=r)


async def _push_recent_job_id(task_id: str, *, r: aioredis.Redis | None = None) -> None:
    if r is None:
        r = await get_redis_client(require_redis=False)
    if not r:
        return

    try:
        await r.lrem(_REDIS_LIST_KEY, 0, task_id)
        await r.lpush(_REDIS_LIST_KEY, task_id)
        await r.ltrim(_REDIS_LIST_KEY, 0, _RECENT_TASK_LIMIT - 1)
        await r.expire(_REDIS_LIST_KEY, _TASK_RETAIN_SECONDS * 2)
    except Exception as exc:
        logger.warning("Failed to update provider refresh/sync recent jobs list: {}", exc)


def _to_response(job: ProviderRefreshSyncJobInfo) -> ProviderRefreshSyncJobStatusResponse:
    return ProviderRefreshSyncJobStatusResponse(
        task_id=job.task_id,
        status=job.status,
        stage=job.stage,
        message=job.message,
        scope=job.scope,
        provider_id=job.provider_id,
        provider_name=job.provider_name,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=job.result,
    )


async def submit_provider_refresh_sync_job(provider_id: str, api_key_id: str | None = None) -> str:
    r = await get_redis_client(require_redis=False)
    if not r:
        raise RuntimeError("Redis is required for provider refresh/sync jobs but is not available")

    provider_name: str | None = None
    with create_session() as db:
        provider = db.query(Provider).filter(Provider.id == provider_id).first()
        if provider is not None:
            provider_name = str(provider.name)

    task_id = uuid.uuid4().hex[:16]
    job = ProviderRefreshSyncJobInfo(
        task_id=task_id,
        scope=SCOPE_SINGLE,
        provider_id=provider_id,
        provider_name=provider_name,
        api_key_id=api_key_id,
        status=STATUS_PENDING,
        stage=STAGE_QUEUED,
        message="refresh/sync job queued",
    )
    await _save_job(job, ttl=_TASK_RETAIN_SECONDS * 2, r=r)
    await _push_recent_job_id(task_id, r=r)

    async def _runner() -> None:
        try:
            await _run_provider_refresh_sync_job(task_id=task_id, redis_client=r)
        finally:
            current = asyncio.current_task()
            if current is not None:
                _running_tasks.discard(current)

    bg = asyncio.create_task(_runner(), name=f"provider-refresh-sync-{task_id}")
    _running_tasks.add(bg)
    return task_id


async def submit_provider_refresh_sync_all_job(only_active: bool = True) -> str:
    r = await get_redis_client(require_redis=False)
    if not r:
        raise RuntimeError("Redis is required for provider refresh/sync jobs but is not available")

    task_id = uuid.uuid4().hex[:16]
    job = ProviderRefreshSyncJobInfo(
        task_id=task_id,
        scope=SCOPE_ALL,
        only_active=only_active,
        status=STATUS_PENDING,
        stage=STAGE_QUEUED,
        message="refresh/sync-all job queued",
    )
    await _save_job(job, ttl=_TASK_RETAIN_SECONDS * 2, r=r)
    await _push_recent_job_id(task_id, r=r)

    async def _runner() -> None:
        try:
            await _run_provider_refresh_sync_job(task_id=task_id, redis_client=r)
        finally:
            current = asyncio.current_task()
            if current is not None:
                _running_tasks.discard(current)

    bg = asyncio.create_task(_runner(), name=f"provider-refresh-sync-all-{task_id}")
    _running_tasks.add(bg)
    return task_id


async def get_provider_refresh_sync_job(task_id: str) -> ProviderRefreshSyncJobStatusResponse | None:
    job = await _load_job(task_id)
    if job is None:
        return None
    return _to_response(job)


async def list_provider_refresh_sync_jobs(limit: int = 20) -> ProviderRefreshSyncJobListResponse:
    r = await get_redis_client(require_redis=False)
    if not r:
        return ProviderRefreshSyncJobListResponse()

    try:
        task_ids = await r.lrange(_REDIS_LIST_KEY, 0, max(limit, 1) - 1)
    except Exception as exc:
        logger.warning("Failed to load provider refresh/sync recent jobs list: {}", exc)
        return ProviderRefreshSyncJobListResponse()

    items: list[ProviderRefreshSyncJobStatusResponse] = []
    for raw_task_id in task_ids:
        task_id = raw_task_id.decode() if isinstance(raw_task_id, bytes) else str(raw_task_id)
        item = await get_provider_refresh_sync_job(task_id)
        if item is not None:
            items.append(item)
    return ProviderRefreshSyncJobListResponse(items=items, total=len(items))


async def _run_provider_refresh_sync_job(
    *,
    task_id: str,
    redis_client: aioredis.Redis | None = None,
) -> None:
    job = await _load_job(task_id, r=redis_client)
    if job is None:
        return

    await _update_job(
        task_id,
        r=redis_client,
        status=STATUS_RUNNING,
        stage=STAGE_REFRESHING,
        message="refreshing provider capabilities",
    )

    try:
        from src.api.admin import provider_query as provider_query_module

        if job.scope == SCOPE_SINGLE:
            with create_session() as db:
                provider = (
                    db.query(Provider)
                    .options(
                        joinedload(Provider.endpoints),
                        selectinload(Provider.api_keys),
                    )
                    .filter(Provider.id == job.provider_id)
                    .first()
                )
                if provider is None:
                    raise ValueError("Provider not found")
                job.provider_name = str(provider.name)
                result = await provider_query_module._refresh_provider_models_and_sync(
                    db=db,
                    provider=provider,
                    api_key_id=job.api_key_id,
                )
                data = result.get("data") or {}
                summary = [
                    "刷新 1/1 个渠道商",
                    f"补建 Endpoint {len(data.get('created_endpoint_formats') or [])} 个",
                    f"同步账号格式 {len(data.get('updated_key_ids') or [])} 个",
                ]
                await _update_job(
                    task_id,
                    r=redis_client,
                    provider_name=str(provider.name),
                    status=STATUS_COMPLETED,
                    stage=STAGE_COMPLETED,
                    message="；".join(summary),
                    result=data,
                )
                return

        with create_session() as db:
            providers = (
                db.query(Provider)
                .options(
                    joinedload(Provider.endpoints),
                    selectinload(Provider.api_keys),
                )
                .all()
            )
            if job.only_active:
                providers = [provider for provider in providers if provider.is_active]

            refreshed = 0
            skipped = 0
            created_endpoint_formats: list[str] = []
            updated_key_ids: list[str] = []
            errors: list[str] = []
            error_preview: list[str] = []
            failed_providers: list[dict[str, str]] = []
            total = len(providers)

            for index, provider in enumerate(providers, start=1):
                if not any(key.is_active for key in provider.api_keys):
                    skipped += 1
                    await _update_job(
                        task_id,
                        r=redis_client,
                        message=f"正在刷新 {index}/{total} 个渠道商（跳过无可用账号：{provider.name}）",
                    )
                    continue

                try:
                    result = await provider_query_module._refresh_provider_models_and_sync(
                        db=db,
                        provider=provider,
                    )
                    refreshed += 1
                    data = result.get("data") or {}
                    created_endpoint_formats.extend(data.get("created_endpoint_formats") or [])
                    updated_key_ids.extend(data.get("updated_key_ids") or [])
                    if data.get("error"):
                        errors.append(provider.name)
                        failed_providers.append(
                            {
                                "provider_name": provider.name,
                                "error": str(data.get("error") or "refresh failed"),
                            }
                        )
                        if len(error_preview) < 3:
                            error_preview.append(provider.name)
                except Exception:
                    skipped += 1
                    errors.append(provider.name)
                    failed_providers.append(
                        {
                            "provider_name": provider.name,
                            "error": "refresh failed",
                        }
                    )
                    if len(error_preview) < 3:
                        error_preview.append(provider.name)
                finally:
                    await _update_job(
                        task_id,
                        r=redis_client,
                        message=f"正在刷新 {index}/{total} 个渠道商",
                    )

            result = {
                "providers_total": total,
                "providers_refreshed": refreshed,
                "providers_skipped": skipped,
                "providers_with_errors": len(errors),
                "error_preview": error_preview,
                "failed_providers": failed_providers,
                "created_endpoint_formats": sorted(set(created_endpoint_formats)),
                "updated_key_ids": sorted(set(updated_key_ids)),
                "error": f"{len(errors)} 个渠道刷新未完全成功" if errors else None,
            }
            await _update_job(
                task_id,
                r=redis_client,
                status=STATUS_COMPLETED,
                stage=STAGE_COMPLETED,
                message=f"刷新 {refreshed}/{total} 个渠道商",
                result=result,
            )
    except Exception as exc:
        logger.error("provider refresh/sync job failed task_id={}: {}", task_id, exc)
        await _update_job(
            task_id,
            r=redis_client,
            status=STATUS_FAILED,
            stage=STAGE_FAILED,
            message=str(exc),
        )


__all__ = [
    "ProviderRefreshSyncJobListResponse",
    "ProviderRefreshSyncJobStartResponse",
    "ProviderRefreshSyncJobStatusResponse",
    "get_provider_refresh_sync_job",
    "list_provider_refresh_sync_jobs",
    "submit_provider_refresh_sync_all_job",
    "submit_provider_refresh_sync_job",
]
