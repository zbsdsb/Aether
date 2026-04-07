from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis

from src.clients.redis_client import get_redis_client
from src.core.logger import logger
from src.database import create_session
from src.models.provider_import import (
    AllInHubImportJobStatusResponse,
    AllInHubImportResponse,
    AllInHubTaskExecutionResponse,
)
from src.services.provider_import.all_in_hub import execute_all_in_hub_import
from src.services.provider_import.reissue import execute_all_in_hub_import_tasks

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

STAGE_QUEUED = "queued"
STAGE_IMPORTING = "importing"
STAGE_EXECUTING_TASKS = "executing_tasks"
STAGE_COMPLETED = "completed"
STAGE_FAILED = "failed"

_TASK_RETAIN_SECONDS = 1800
_REDIS_KEY_PREFIX = "all_in_hub_import_job"
_running_tasks: set[asyncio.Task[None]] = set()


def _task_key(task_id: str) -> str:
    return f"{_REDIS_KEY_PREFIX}:{task_id}"


@dataclass
class AllInHubImportJobInfo:
    task_id: str
    status: str = STATUS_PENDING
    stage: str = STAGE_QUEUED
    message: str = ""
    import_result: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
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
    )
    await _save_job(job, ttl=_TASK_RETAIN_SECONDS * 2, r=r)

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
        import_result=import_result,
        execution_result=execution_result,
    )


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
        with create_session() as db:
            import_result = await execute_all_in_hub_import(
                content,
                db=db,
                schedule_model_fetch=False,
                created_key_ids_out=created_key_ids,
            )

        aggregate_execution = AllInHubTaskExecutionResponse()
        await _update_job(
            task_id,
            r=redis_client,
            status=STATUS_RUNNING,
            stage=STAGE_EXECUTING_TASKS,
            message="executing imported auth/key tasks",
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

        from src.services.provider_import.all_in_hub import _schedule_imported_key_model_fetches

        _schedule_imported_key_model_fetches(created_key_ids)

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
