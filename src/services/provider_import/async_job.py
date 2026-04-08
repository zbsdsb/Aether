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
from src.models.provider_import import (
    AllInHubImportBackgroundTaskStatus,
    AllInHubImportJobListResponse,
    AllInHubImportProviderIssue,
    AllInHubImportJobStatusResponse,
    AllInHubImportResponse,
    AllInHubTaskExecutionResponse,
)
from src.services.provider_import.all_in_hub import (
    execute_all_in_hub_import,
    run_imported_key_model_fetch_batch,
)
from src.services.provider_ops.proxy_probe import probe_provider_proxies
from src.services.provider_import.reissue import execute_all_in_hub_import_tasks

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

STAGE_QUEUED = "queued"
STAGE_IMPORTING = "importing"
STAGE_EXECUTING_TASKS = "executing_tasks"
STAGE_FETCHING_MODELS = "fetching_models"
STAGE_PROBING_PROXIES = "probing_proxies"
STAGE_COMPLETED = "completed"
STAGE_FAILED = "failed"

_TASK_RETAIN_SECONDS = 1800
_REDIS_KEY_PREFIX = "all_in_hub_import_job"
_REDIS_LIST_KEY = "all_in_hub_import_jobs:recent"
_RECENT_TASK_LIMIT = 100
_running_tasks: set[asyncio.Task[None]] = set()
BACKGROUND_TASK_FETCH_MODELS = "fetch_models"
BACKGROUND_TASK_PROXY_PROBE = "proxy_probe"


def _default_background_tasks() -> list[dict[str, Any]]:
    return [
        AllInHubImportBackgroundTaskStatus(
            key=BACKGROUND_TASK_FETCH_MODELS,
            label="异步抓取上游模型",
            status="pending",
        ).model_dump(mode="json"),
        AllInHubImportBackgroundTaskStatus(
            key=BACKGROUND_TASK_PROXY_PROBE,
            label="代理检测",
            status="pending",
        ).model_dump(mode="json"),
    ]


def _upsert_background_task(
    items: list[dict[str, Any]] | None,
    *,
    key: str,
    **fields: Any,
) -> list[dict[str, Any]]:
    next_items = [dict(item) for item in (items or _default_background_tasks())]
    for index, item in enumerate(next_items):
        if str(item.get("key") or "") != key:
            continue
        updated = dict(item)
        updated.update(fields)
        next_items[index] = updated
        return next_items

    next_items.append({"key": key, **fields})
    return next_items


def _task_key(task_id: str) -> str:
    return f"{_REDIS_KEY_PREFIX}:{task_id}"


@dataclass
class AllInHubImportJobInfo:
    task_id: str
    status: str = STATUS_PENDING
    stage: str = STAGE_QUEUED
    message: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    background_tasks: list[dict[str, Any]] | None = None
    provider_issues: list[dict[str, Any]] | None = None
    import_result: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "background_tasks": list(self.background_tasks or _default_background_tasks()),
            "provider_issues": list(self.provider_issues or []),
            "import_result": self.import_result,
            "execution_result": self.execution_result,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AllInHubImportJobInfo":
        return cls(
            task_id=str(data["task_id"]),
            status=str(data.get("status", STATUS_PENDING)),
            stage=str(data.get("stage", STAGE_QUEUED)),
            message=str(data.get("message", "")),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            background_tasks=list(data.get("background_tasks") or _default_background_tasks()),
            provider_issues=list(data.get("provider_issues") or []),
            import_result=data.get("import_result"),
            execution_result=data.get("execution_result"),
        )


async def _save_job(
    job: AllInHubImportJobInfo,
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
        logger.warning("Failed to save all-in-hub import job: {}", exc)


async def _load_job(task_id: str, r: aioredis.Redis | None = None) -> AllInHubImportJobInfo | None:
    if r is None:
        r = await get_redis_client(require_redis=False)
    if not r:
        return None
    try:
        data = await r.get(_task_key(task_id))
        if data is None:
            return None
        return AllInHubImportJobInfo.from_dict(json.loads(data))
    except Exception as exc:
        logger.warning("Failed to load all-in-hub import job: {}", exc)
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


async def _update_background_task(
    task_id: str,
    *,
    key: str,
    r: aioredis.Redis | None = None,
    **fields: Any,
) -> None:
    job = await _load_job(task_id, r=r)
    if job is None:
        return
    job.background_tasks = _upsert_background_task(job.background_tasks, key=key, **fields)
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
        logger.warning("Failed to update all-in-hub import recent jobs list: {}", exc)


async def submit_all_in_hub_import_job(content: str) -> str:
    r = await get_redis_client(require_redis=False)
    if not r:
        raise RuntimeError("Redis is required for async all-in-hub import jobs but is not available")

    task_id = uuid.uuid4().hex[:16]
    job = AllInHubImportJobInfo(
        task_id=task_id,
        status=STATUS_PENDING,
        stage=STAGE_QUEUED,
        message="import job queued",
        background_tasks=_default_background_tasks(),
        provider_issues=[],
    )
    await _save_job(job, ttl=_TASK_RETAIN_SECONDS * 2, r=r)
    await _push_recent_job_id(task_id, r=r)

    async def _runner() -> None:
        try:
            await _run_all_in_hub_import_job(task_id=task_id, content=content, redis_client=r)
        finally:
            current = asyncio.current_task()
            if current is not None:
                _running_tasks.discard(current)

    bg = asyncio.create_task(_runner(), name=f"all-in-hub-import-{task_id}")
    _running_tasks.add(bg)
    return task_id


async def get_all_in_hub_import_job(task_id: str) -> AllInHubImportJobStatusResponse | None:
    job = await _load_job(task_id)
    if job is None:
        return None

    import_result = (
        AllInHubImportResponse.model_validate(job.import_result)
        if isinstance(job.import_result, dict)
        else None
    )
    execution_result = (
        AllInHubTaskExecutionResponse.model_validate(job.execution_result)
        if isinstance(job.execution_result, dict)
        else None
    )
    return AllInHubImportJobStatusResponse(
        task_id=job.task_id,
        status=job.status,
        stage=job.stage,
        message=job.message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        background_tasks=[
            AllInHubImportBackgroundTaskStatus.model_validate(item)
            for item in (job.background_tasks or [])
        ],
        provider_issues=[
            AllInHubImportProviderIssue.model_validate(item)
            for item in (job.provider_issues or [])
        ],
        import_result=import_result,
        execution_result=execution_result,
    )


async def list_all_in_hub_import_jobs(limit: int = 20) -> AllInHubImportJobListResponse:
    r = await get_redis_client(require_redis=False)
    if not r:
        return AllInHubImportJobListResponse()

    try:
        task_ids = await r.lrange(_REDIS_LIST_KEY, 0, max(limit, 1) - 1)
    except Exception as exc:
        logger.warning("Failed to load all-in-hub import recent jobs list: {}", exc)
        return AllInHubImportJobListResponse()

    items: list[AllInHubImportJobStatusResponse] = []
    for raw_task_id in task_ids:
        task_id = raw_task_id.decode() if isinstance(raw_task_id, bytes) else str(raw_task_id)
        item = await get_all_in_hub_import_job(task_id)
        if item is not None:
            items.append(item)
    return AllInHubImportJobListResponse(items=items, total=len(items))


async def _run_all_in_hub_import_job(
    *,
    task_id: str,
    content: str,
    redis_client: aioredis.Redis | None = None,
) -> None:
    await _update_job(
        task_id,
        r=redis_client,
        status=STATUS_RUNNING,
        stage=STAGE_IMPORTING,
        message="importing providers/endpoints/keys",
    )

    try:
        created_key_ids: list[str] = []
        touched_provider_ids: list[str] = []
        with create_session() as db:
            import_result = await execute_all_in_hub_import(
                content,
                db=db,
                schedule_model_fetch=False,
                created_key_ids_out=created_key_ids,
                touched_provider_ids_out=touched_provider_ids,
            )

        aggregate_execution = AllInHubTaskExecutionResponse()
        fetch_total = len(created_key_ids)
        proxy_total = len(touched_provider_ids)
        await _update_job(
            task_id,
            r=redis_client,
            status=STATUS_RUNNING,
            stage=STAGE_EXECUTING_TASKS,
            message="executing imported auth/key tasks",
            background_tasks=_upsert_background_task(
                _upsert_background_task(
                    _default_background_tasks(),
                    key=BACKGROUND_TASK_FETCH_MODELS,
                    total=fetch_total,
                    message="等待补钥与配置任务完成",
                ),
                key=BACKGROUND_TASK_PROXY_PROBE,
                total=proxy_total,
                message="等待上游模型抓取结束后执行",
            ),
            import_result=import_result.model_dump(mode="json"),
            execution_result=aggregate_execution.model_dump(mode="json"),
        )

        round_index = 0
        while True:
            round_index += 1
            with create_session() as db:
                execution = await execute_all_in_hub_import_tasks(db=db, limit=20)

            if execution.total_selected <= 0:
                break

            aggregate_execution.total_selected += execution.total_selected
            aggregate_execution.completed += execution.completed
            aggregate_execution.failed += execution.failed
            aggregate_execution.skipped += execution.skipped
            aggregate_execution.keys_created += execution.keys_created
            aggregate_execution.results.extend(execution.results)

            await _update_job(
                task_id,
                r=redis_client,
                status=STATUS_RUNNING,
                stage=STAGE_EXECUTING_TASKS,
                message=(
                    f"execution round {round_index}: selected {execution.total_selected}, "
                    f"completed {execution.completed}, failed {execution.failed}"
                ),
                import_result=import_result.model_dump(mode="json"),
                execution_result=aggregate_execution.model_dump(mode="json"),
            )

            if execution.total_selected < 20:
                continue

        if created_key_ids:
            await _update_job(
                task_id,
                r=redis_client,
                status=STATUS_RUNNING,
                stage=STAGE_FETCHING_MODELS,
                message="fetching upstream models for imported keys",
            )
            await _update_background_task(
                task_id,
                r=redis_client,
                key=BACKGROUND_TASK_FETCH_MODELS,
                status="running",
                total=len(created_key_ids),
                completed=0,
                failed=0,
                message=f"开始抓取，共 {len(created_key_ids)} 个 Key",
            )

            async def _on_fetch_progress(index: int, completed: int, failed: int, _key_id: str) -> None:
                await _update_background_task(
                    task_id,
                    r=redis_client,
                    key=BACKGROUND_TASK_FETCH_MODELS,
                    status="running",
                    total=len(created_key_ids),
                    completed=completed,
                    failed=failed,
                    message=f"正在抓取第 {index}/{len(created_key_ids)} 个 Key",
                )

            fetch_summary = await run_imported_key_model_fetch_batch(
                created_key_ids,
                progress_callback=_on_fetch_progress,
            )
            await _update_background_task(
                task_id,
                r=redis_client,
                key=BACKGROUND_TASK_FETCH_MODELS,
                status="completed",
                total=fetch_summary["total"],
                completed=fetch_summary["completed"],
                failed=fetch_summary["failed"],
                message=f"模型抓取完成，成功 {fetch_summary['completed']}，失败 {fetch_summary['failed']}",
            )
        else:
            await _update_background_task(
                task_id,
                r=redis_client,
                key=BACKGROUND_TASK_FETCH_MODELS,
                status="skipped",
                total=0,
                completed=0,
                failed=0,
                message="本次未创建需要抓取上游模型的 Key",
            )

        if touched_provider_ids:
            await _update_job(
                task_id,
                r=redis_client,
                status=STATUS_RUNNING,
                stage=STAGE_PROBING_PROXIES,
                message="probing proxy requirements for imported providers",
            )
            await _update_background_task(
                task_id,
                r=redis_client,
                key=BACKGROUND_TASK_PROXY_PROBE,
                status="running",
                total=len(touched_provider_ids),
                completed=0,
                failed=0,
                message=f"开始检测，共 {len(touched_provider_ids)} 个 Provider",
            )

            async def _on_probe_progress(index: int, summary, _result) -> None:
                await _update_background_task(
                    task_id,
                    r=redis_client,
                    key=BACKGROUND_TASK_PROXY_PROBE,
                    status="running",
                    total=summary.total_selected or len(touched_provider_ids),
                    completed=summary.completed,
                    failed=summary.failed,
                    message=f"正在检测第 {index}/{summary.total_selected or len(touched_provider_ids)} 个 Provider",
                )

            with create_session() as db:
                probe_summary = await probe_provider_proxies(
                    touched_provider_ids,
                    db=db,
                    progress_callback=_on_probe_progress,
                )

            await _update_background_task(
                task_id,
                r=redis_client,
                key=BACKGROUND_TASK_PROXY_PROBE,
                status="completed" if probe_summary.total_selected > 0 else "skipped",
                total=probe_summary.total_selected,
                completed=probe_summary.completed,
                failed=probe_summary.failed,
                message=(
                    f"代理检测完成，成功 {probe_summary.completed}，失败 {probe_summary.failed}，跳过 {probe_summary.skipped}"
                    if probe_summary.total_selected > 0
                    else "本次没有待检测的代理任务"
                ),
            )
            await _update_job(
                task_id,
                r=redis_client,
                provider_issues=[
                    {
                        "provider_id": item.get("provider_id"),
                        "provider_name": item.get("provider_name") or "Unknown Provider",
                        "status": item.get("status") or "unknown",
                        "mode": item.get("mode"),
                        "message": item.get("message"),
                    }
                    for item in probe_summary.results
                    if str(item.get("status") or "") != "completed"
                ],
            )
        else:
            await _update_background_task(
                task_id,
                r=redis_client,
                key=BACKGROUND_TASK_PROXY_PROBE,
                status="skipped",
                total=0,
                completed=0,
                failed=0,
                message="本次没有需要代理检测的 Provider",
            )
            await _update_job(task_id, r=redis_client, provider_issues=[])

        await _update_job(
            task_id,
            r=redis_client,
            status=STATUS_COMPLETED,
            stage=STAGE_COMPLETED,
            message="all-in-hub import completed",
            import_result=import_result.model_dump(mode="json"),
            execution_result=aggregate_execution.model_dump(mode="json"),
        )
    except Exception as exc:
        logger.error("all-in-hub import job failed task_id={}: {}", task_id, exc)
        await _update_job(
            task_id,
            r=redis_client,
            status=STATUS_FAILED,
            stage=STAGE_FAILED,
            message=str(exc),
        )
