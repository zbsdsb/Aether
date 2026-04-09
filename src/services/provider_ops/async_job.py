from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from src.clients.redis_client import get_redis_client
from src.core.logger import logger
from src.database import create_session
from src.models.admin_async_tasks import (
    ProviderProxyProbeJobListResponse,
    ProviderProxyProbeJobStatusResponse,
)
from src.models.database import Provider
from src.services.provider_ops.proxy_probe import (
    probe_all_provider_proxies,
    probe_provider_proxy,
)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

STAGE_QUEUED = "queued"
STAGE_PROBING = "probing"
STAGE_COMPLETED = "completed"
STAGE_FAILED = "failed"

SCOPE_SINGLE = "single"
SCOPE_ALL = "all"

_TASK_RETAIN_SECONDS = 1800
_REDIS_KEY_PREFIX = "provider_proxy_probe_job"
_REDIS_LIST_KEY = "provider_proxy_probe_jobs:recent"
_RECENT_TASK_LIMIT = 100
_running_tasks: set[asyncio.Task[None]] = set()


def _task_key(task_id: str) -> str:
    return f"{_REDIS_KEY_PREFIX}:{task_id}"


@dataclass
class ProviderProxyProbeJobInfo:
    task_id: str
    scope: str
    provider_id: str | None = None
    provider_name: str | None = None
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
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderProxyProbeJobInfo":
        return cls(
            task_id=str(data["task_id"]),
            scope=str(data.get("scope") or SCOPE_SINGLE),
            provider_id=data.get("provider_id"),
            provider_name=data.get("provider_name"),
            status=str(data.get("status") or STATUS_PENDING),
            stage=str(data.get("stage") or STAGE_QUEUED),
            message=str(data.get("message") or ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            result=data.get("result"),
        )


async def _save_job(job: ProviderProxyProbeJobInfo, ttl: int = _TASK_RETAIN_SECONDS, r: aioredis.Redis | None = None) -> None:
    if r is None:
        r = await get_redis_client(require_redis=False)
    if not r:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    if not job.created_at:
        job.created_at = now_iso
    job.updated_at = now_iso
    await r.setex(_task_key(job.task_id), ttl, json.dumps(job.to_dict()))


async def _load_job(task_id: str, r: aioredis.Redis | None = None) -> ProviderProxyProbeJobInfo | None:
    if r is None:
        r = await get_redis_client(require_redis=False)
    if not r:
        return None
    data = await r.get(_task_key(task_id))
    if data is None:
        return None
    return ProviderProxyProbeJobInfo.from_dict(json.loads(data))


async def _update_job(task_id: str, *, r: aioredis.Redis | None = None, **fields: Any) -> None:
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
    await r.lrem(_REDIS_LIST_KEY, 0, task_id)
    await r.lpush(_REDIS_LIST_KEY, task_id)
    await r.ltrim(_REDIS_LIST_KEY, 0, _RECENT_TASK_LIMIT - 1)
    await r.expire(_REDIS_LIST_KEY, _TASK_RETAIN_SECONDS * 2)


def _to_response(job: ProviderProxyProbeJobInfo) -> ProviderProxyProbeJobStatusResponse:
    return ProviderProxyProbeJobStatusResponse(
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


async def submit_provider_proxy_probe_job(provider_id: str) -> str:
    r = await get_redis_client(require_redis=False)
    if not r:
        raise RuntimeError("Redis is required for provider proxy probe jobs but is not available")

    provider_name: str | None = None
    with create_session() as db:
        provider = db.query(Provider).filter(Provider.id == provider_id).first()
        if provider is not None:
            provider_name = str(provider.name)

    task_id = uuid.uuid4().hex[:16]
    job = ProviderProxyProbeJobInfo(
        task_id=task_id,
        scope=SCOPE_SINGLE,
        provider_id=provider_id,
        provider_name=provider_name,
        status=STATUS_PENDING,
        stage=STAGE_QUEUED,
        message="代理检测任务已排队",
    )
    await _save_job(job, ttl=_TASK_RETAIN_SECONDS * 2, r=r)
    await _push_recent_job_id(task_id, r=r)

    async def _runner() -> None:
        try:
            await _run_provider_proxy_probe_job(task_id=task_id, redis_client=r)
        finally:
            current = asyncio.current_task()
            if current is not None:
                _running_tasks.discard(current)

    bg = asyncio.create_task(_runner(), name=f"provider-proxy-probe-{task_id}")
    _running_tasks.add(bg)
    return task_id


async def submit_provider_proxy_probe_all_job(limit: int = 200) -> str:
    r = await get_redis_client(require_redis=False)
    if not r:
        raise RuntimeError("Redis is required for provider proxy probe jobs but is not available")

    task_id = uuid.uuid4().hex[:16]
    job = ProviderProxyProbeJobInfo(
        task_id=task_id,
        scope=SCOPE_ALL,
        status=STATUS_PENDING,
        stage=STAGE_QUEUED,
        message="全局代理检测任务已排队",
        result={"limit": limit},
    )
    await _save_job(job, ttl=_TASK_RETAIN_SECONDS * 2, r=r)
    await _push_recent_job_id(task_id, r=r)

    async def _runner() -> None:
        try:
            await _run_provider_proxy_probe_job(task_id=task_id, redis_client=r)
        finally:
            current = asyncio.current_task()
            if current is not None:
                _running_tasks.discard(current)

    bg = asyncio.create_task(_runner(), name=f"provider-proxy-probe-all-{task_id}")
    _running_tasks.add(bg)
    return task_id


async def get_provider_proxy_probe_job(task_id: str) -> ProviderProxyProbeJobStatusResponse | None:
    job = await _load_job(task_id)
    return _to_response(job) if job is not None else None


async def list_provider_proxy_probe_jobs(limit: int = 20) -> ProviderProxyProbeJobListResponse:
    r = await get_redis_client(require_redis=False)
    if not r:
        return ProviderProxyProbeJobListResponse()
    task_ids = await r.lrange(_REDIS_LIST_KEY, 0, max(limit, 1) - 1)
    items: list[ProviderProxyProbeJobStatusResponse] = []
    for raw_task_id in task_ids:
        task_id = raw_task_id.decode() if isinstance(raw_task_id, bytes) else str(raw_task_id)
        item = await get_provider_proxy_probe_job(task_id)
        if item is not None:
            items.append(item)
    return ProviderProxyProbeJobListResponse(items=items, total=len(items))


async def _run_provider_proxy_probe_job(*, task_id: str, redis_client: aioredis.Redis | None = None) -> None:
    job = await _load_job(task_id, r=redis_client)
    if job is None:
        return
    await _update_job(task_id, r=redis_client, status=STATUS_RUNNING, stage=STAGE_PROBING, message="正在执行代理检测")
    try:
        with create_session() as db:
            if job.scope == SCOPE_SINGLE:
                result = await probe_provider_proxy(str(job.provider_id), db=db)
                summary = {
                    "total_selected": 1,
                    "completed": 1 if result.get("status") == "completed" else 0,
                    "failed": 1 if result.get("status") == "failed" else 0,
                    "skipped": 1 if result.get("status") not in {"completed", "failed"} else 0,
                    "results": [result],
                }
                await _update_job(
                    task_id,
                    r=redis_client,
                    status=STATUS_COMPLETED,
                    stage=STAGE_COMPLETED,
                    message=str(result.get("message") or "代理检测完成"),
                    result=summary,
                )
                return

            limit = int((job.result or {}).get("limit") or 200)
            summary = await probe_all_provider_proxies(db=db, limit=limit)
            result = {
                "total_selected": summary.total_selected,
                "completed": summary.completed,
                "failed": summary.failed,
                "skipped": summary.skipped,
                "results": summary.results,
            }
            await _update_job(
                task_id,
                r=redis_client,
                status=STATUS_COMPLETED,
                stage=STAGE_COMPLETED,
                message=f"代理检测完成 {summary.completed}/{summary.total_selected}",
                result=result,
            )
    except Exception as exc:
        logger.error("provider proxy probe job failed task_id={}: {}", task_id, exc)
        await _update_job(task_id, r=redis_client, status=STATUS_FAILED, stage=STAGE_FAILED, message=str(exc))
