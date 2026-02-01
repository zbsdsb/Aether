"""
AsyncTaskOrchestrator

提交阶段故障转移（多候选尝试）：
- 目标：拿到 external_task_id 后锁定 provider/endpoint/key，后续轮询不再切换。
- 仅覆盖“提交阶段”；轮询阶段由各 task poller 使用已锁定的信息执行。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

import httpx
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from src.config.settings import config
from src.core.exceptions import ProviderNotAvailableException
from src.core.logger import logger
from src.models.database import ApiKey, RequestCandidate
from src.services.billing.rule_service import BillingRuleLookupResult, BillingRuleService
from src.services.cache.aware_scheduler import ProviderCandidate, get_cache_aware_scheduler
from src.services.orchestration.candidate_resolver import CandidateResolver
from src.services.orchestration.error_classifier import ErrorClassifier
from src.services.system.config import SystemConfigService

_SENSITIVE_PATTERN = re.compile(
    r"(api[_-]?key|token|bearer|authorization)[=:\s]+\S+",
    re.IGNORECASE,
)


def _sanitize(message: str, max_length: int = 200) -> str:
    if not message:
        return "request_failed"
    return _SENSITIVE_PATTERN.sub("[REDACTED]", message)[:max_length]


@runtime_checkable
class SubmitFunc(Protocol):
    async def __call__(self, candidate: ProviderCandidate) -> httpx.Response: ...


@runtime_checkable
class ExtractExternalTaskIdFunc(Protocol):
    def __call__(self, payload: dict[str, Any]) -> str | None: ...


class UpstreamClientRequestError(RuntimeError):
    """可判定为客户端请求问题（不应 failover）的上游错误。"""

    def __init__(
        self,
        *,
        response: httpx.Response,
        candidate_keys: list[dict[str, Any]],
    ) -> None:
        self.response = response
        self.candidate_keys = candidate_keys
        super().__init__(f"Upstream client error: HTTP {response.status_code}")


class AllCandidatesFailedError(RuntimeError):
    def __init__(
        self,
        *,
        reason: str,
        candidate_keys: list[dict[str, Any]],
        last_status_code: int | None = None,
    ) -> None:
        self.reason = reason
        self.candidate_keys = candidate_keys
        self.last_status_code = last_status_code
        super().__init__(f"All candidates failed: {reason}")


class CandidateUnsupportedError(RuntimeError):
    """候选不被当前任务支持（如 auth_type/格式转换需求不支持）。"""


class CandidateSubmissionError(RuntimeError):
    """候选提交异常（网络/解密/解析等）。"""


@dataclass(slots=True)
class SubmitOutcome:
    candidate: ProviderCandidate
    candidate_keys: list[dict[str, Any]]
    external_task_id: str
    rule_lookup: BillingRuleLookupResult | None
    upstream_payload: dict[str, Any] | None = None


class AsyncTaskOrchestrator:
    """
    异步任务编排器：只负责提交阶段的候选遍历与错误处理策略。
    """

    def __init__(self, db: Session, *, redis_client: Redis | None = None) -> None:
        self.db = db
        self.redis = redis_client
        self._candidate_resolver: CandidateResolver | None = None
        self._error_classifier: ErrorClassifier | None = None

        self._cache_scheduler = None
        # 候选记录映射：{candidate_index: RequestCandidate}
        self._candidate_records: dict[int, RequestCandidate] = {}

    def _create_candidate_records(
        self,
        candidates: list[ProviderCandidate],
        request_id: str | None,
        user_api_key: ApiKey,
    ) -> dict[int, RequestCandidate]:
        """
        为所有候选预创建 RequestCandidate 记录。

        Args:
            candidates: 候选列表
            request_id: 请求 ID
            user_api_key: 用户 API Key

        Returns:
            {candidate_index: RequestCandidate} 映射
        """
        if not request_id:
            return {}

        now = datetime.now(timezone.utc)
        records: dict[int, RequestCandidate] = {}

        for idx, cand in enumerate(candidates):
            record = RequestCandidate(
                id=str(uuid.uuid4()),
                request_id=request_id,
                candidate_index=idx,
                retry_index=0,
                user_id=user_api_key.user_id if user_api_key else None,
                api_key_id=user_api_key.id if user_api_key else None,
                provider_id=cand.provider.id,
                endpoint_id=cand.endpoint.id,
                key_id=cand.key.id,
                status="available",
                is_cached=bool(getattr(cand, "is_cached", False)),
                created_at=now,
            )
            self.db.add(record)
            records[idx] = record

        try:
            self.db.flush()
        except Exception as exc:
            logger.warning(
                "[AsyncTaskOrchestrator] Failed to create candidate records: %s",
                str(exc),
            )
            self.db.rollback()
            return {}

        return records

    def _update_candidate_record(
        self,
        idx: int,
        *,
        status: str,
        skip_reason: str | None = None,
        status_code: int | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        """更新候选记录状态。"""
        record = self._candidate_records.get(idx)
        if not record:
            return

        record.status = status
        if skip_reason is not None:
            record.skip_reason = skip_reason
        if status_code is not None:
            record.status_code = status_code
        if error_type is not None:
            record.error_type = error_type
        if error_message is not None:
            record.error_message = error_message
        if started_at is not None:
            record.started_at = started_at
        if finished_at is not None:
            record.finished_at = finished_at

        try:
            self.db.flush()
        except Exception as exc:
            logger.warning(
                "[AsyncTaskOrchestrator] Failed to update candidate record %d: %s",
                idx,
                str(exc),
            )

    def _commit_candidate_records(self) -> None:
        """提交候选记录到数据库。"""
        if not self._candidate_records:
            return
        try:
            self.db.commit()
        except Exception as exc:
            logger.warning(
                "[AsyncTaskOrchestrator] Failed to commit candidate records: %s",
                str(exc),
            )
            self.db.rollback()

    async def _ensure_initialized(self) -> None:
        if self._cache_scheduler is not None:
            return

        # 使用 SystemConfigService 读取运行时调度策略（与 Chat/CLI 一致）
        priority_mode = SystemConfigService.get_config(
            self.db,
            "provider_priority_mode",
            "provider",
        )
        scheduling_mode = SystemConfigService.get_config(
            self.db,
            "scheduling_mode",
            "cache_affinity",
        )
        self._cache_scheduler = await get_cache_aware_scheduler(
            self.redis,
            priority_mode=priority_mode,
            scheduling_mode=scheduling_mode,
        )

        self._candidate_resolver = CandidateResolver(
            db=self.db,
            cache_scheduler=self._cache_scheduler,
        )
        self._error_classifier = ErrorClassifier(db=self.db, cache_scheduler=self._cache_scheduler)

    def _should_stop_on_http_error(self, *, status_code: int, error_text: str) -> bool:
        """
        判断某个上游 HTTP 错误是否为“客户端错误”（不应 failover）。

        规则：
        - 401/403/429：一般是 key/权限/限流问题，优先 failover
        - 其他 4xx：若 ErrorClassifier 判断为客户端请求错误，则停止
        """
        if status_code in (401, 403, 429):
            return False
        if 400 <= status_code < 500:
            assert self._error_classifier is not None
            return self._error_classifier.is_client_error(error_text)
        return False

    async def submit_with_failover(
        self,
        *,
        api_format: str,
        model_name: str,
        affinity_key: str,
        user_api_key: ApiKey,
        request_id: str | None,
        task_type: str,
        submit_func: SubmitFunc,
        extract_external_task_id: ExtractExternalTaskIdFunc,
        supported_auth_types: set[str] | None = None,
        allow_format_conversion: bool = False,
        capability_requirements: dict[str, bool] | None = None,
        max_candidates: int | None = None,
    ) -> SubmitOutcome:
        """
        提交异步任务并在失败时自动尝试下一个候选，直到拿到 external_task_id。

        Returns:
            SubmitOutcome（包含选中的候选 + external_task_id + candidate_keys + billing rule lookup）

        Raises:
            UpstreamClientRequestError: 判定为客户端请求错误（不应 failover）
            ProviderNotAvailableException: 没有可用候选（调度器层面）
            AllCandidatesFailedError: 有候选但全部提交失败
        """
        await self._ensure_initialized()
        assert self._candidate_resolver is not None

        logger.info(
            "[AsyncTaskOrchestrator] submit_with_failover: "
            "api_format=%s, model=%s, task_type=%s, request_id=%s",
            api_format,
            model_name,
            task_type,
            request_id,
        )

        candidates, _global_model_id = await self._candidate_resolver.fetch_candidates(
            api_format=api_format,
            model_name=model_name,
            affinity_key=affinity_key,
            user_api_key=user_api_key,
            request_id=request_id,
            is_stream=False,
            capability_requirements=capability_requirements,
        )

        logger.info(
            "[AsyncTaskOrchestrator] fetch_candidates returned %d candidates for model=%s",
            len(candidates),
            model_name,
        )

        # 如果没有候选，直接抛出异常
        if not candidates:
            logger.error(
                "[AsyncTaskOrchestrator] No candidates returned from fetch_candidates for model=%s",
                model_name,
            )
            raise ProviderNotAvailableException("No candidates available")

        if max_candidates is not None and max_candidates > 0:
            candidates = candidates[:max_candidates]

        # 创建候选记录（用于链路追踪）
        self._candidate_records = self._create_candidate_records(
            candidates=candidates,
            request_id=request_id,
            user_api_key=user_api_key,
        )

        candidate_keys: list[dict[str, Any]] = []
        eligible_count = 0
        last_status_code: int | None = None

        for idx, cand in enumerate(candidates):
            submit_started_at = datetime.now(timezone.utc)
            auth_type = getattr(cand.key, "auth_type", "api_key") or "api_key"
            candidate_info: dict[str, Any] = {
                "index": idx,
                "provider_id": cand.provider.id,
                "provider_name": cand.provider.name,
                "endpoint_id": cand.endpoint.id,
                "key_id": cand.key.id,
                "key_name": cand.key.name,
                "auth_type": auth_type,
                "priority": getattr(cand.key, "priority", 0) or 0,
                "is_cached": bool(getattr(cand, "is_cached", False)),
            }
            candidate_keys.append(candidate_info)

            logger.info(
                "[AsyncTaskOrchestrator] Checking candidate %d: provider=%s, is_skipped=%s, skip_reason=%s, needs_conversion=%s, auth_type=%s",
                idx,
                cand.provider.name,
                getattr(cand, "is_skipped", False),
                getattr(cand, "skip_reason", None),
                getattr(cand, "needs_conversion", False),
                auth_type,
            )

            # 调度器层面标记为跳过（健康/熔断/并发等）
            if getattr(cand, "is_skipped", False):
                skip_reason = getattr(cand, "skip_reason", None) or "skipped"
                candidate_info.update(
                    {
                        "skipped": True,
                        "skip_reason": skip_reason,
                    }
                )
                self._update_candidate_record(idx, status="skipped", skip_reason=skip_reason)
                logger.info(
                    "[AsyncTaskOrchestrator] Candidate %d skipped: is_skipped=True, reason=%s",
                    idx,
                    cand.skip_reason,
                )
                continue

            # 视频/图片等直连 upstream 的 handler 目前不支持跨格式转换
            if not allow_format_conversion and bool(getattr(cand, "needs_conversion", False)):
                candidate_info.update(
                    {"skipped": True, "skip_reason": "format_conversion_not_supported"}
                )
                self._update_candidate_record(
                    idx, status="skipped", skip_reason="format_conversion_not_supported"
                )
                logger.info("[AsyncTaskOrchestrator] Candidate %d skipped: needs_conversion", idx)
                continue

            # auth_type 过滤
            if supported_auth_types is not None and auth_type not in supported_auth_types:
                skip_reason = f"unsupported_auth_type:{auth_type}"
                candidate_info.update(
                    {
                        "skipped": True,
                        "skip_reason": skip_reason,
                    }
                )
                self._update_candidate_record(idx, status="skipped", skip_reason=skip_reason)
                logger.info(
                    "[AsyncTaskOrchestrator] Candidate %d skipped: unsupported_auth_type=%s",
                    idx,
                    auth_type,
                )
                continue

            # billing rule 过滤（可选）
            rule_lookup: BillingRuleLookupResult | None = None
            has_billing_rule = True
            if config.billing_require_rule:
                logger.info(
                    "[AsyncTaskOrchestrator] Checking billing rule for candidate %d (billing_require_rule=True)",
                    idx,
                )
                rule_lookup = BillingRuleService.find_rule(
                    self.db,
                    provider_id=cand.provider.id,
                    model_name=model_name,
                    task_type=task_type,
                )
                has_billing_rule = rule_lookup is not None
                logger.info(
                    "[AsyncTaskOrchestrator] Billing rule lookup result: has_rule=%s",
                    has_billing_rule,
                )
                if not has_billing_rule:
                    candidate_info.update(
                        {
                            "has_billing_rule": False,
                            "skipped": True,
                            "skip_reason": "billing_rule_missing",
                        }
                    )
                    self._update_candidate_record(
                        idx, status="skipped", skip_reason="billing_rule_missing"
                    )
                    logger.info(
                        "[AsyncTaskOrchestrator] Candidate %d skipped: billing_rule_missing", idx
                    )
                    continue
            candidate_info["has_billing_rule"] = has_billing_rule

            logger.info("[AsyncTaskOrchestrator] Candidate %d eligible, attempting submit", idx)
            eligible_count += 1

            # 更新记录为 pending 状态（开始尝试）
            self._update_candidate_record(idx, status="pending", started_at=submit_started_at)

            # 尝试提交
            try:
                response = await submit_func(cand)
            except Exception as exc:
                finished_at = datetime.now(timezone.utc)
                logger.error(
                    "[AsyncTaskOrchestrator] Candidate %d submit exception: %s: %s",
                    idx,
                    type(exc).__name__,
                    str(exc),
                )
                error_msg = _sanitize(str(exc))
                candidate_info.update(
                    {
                        "attempt_status": "exception",
                        "error_type": type(exc).__name__,
                        "error_message": error_msg,
                    }
                )
                self._update_candidate_record(
                    idx,
                    status="failed",
                    error_type=type(exc).__name__,
                    error_message=error_msg,
                    finished_at=finished_at,
                )
                continue

            logger.info(
                "[AsyncTaskOrchestrator] Candidate %d submit response: status_code=%d",
                idx,
                response.status_code,
            )

            last_status_code = int(getattr(response, "status_code", 0) or 0)

            # 上游错误：决定是否停止
            if response.status_code >= 400:
                finished_at = datetime.now(timezone.utc)
                error_text = ""
                try:
                    error_text = response.text or ""
                except Exception:
                    error_text = ""
                error_msg = _sanitize(error_text)
                candidate_info.update(
                    {
                        "attempt_status": "http_error",
                        "status_code": response.status_code,
                        "error_message": error_msg,
                    }
                )
                self._update_candidate_record(
                    idx,
                    status="failed",
                    status_code=response.status_code,
                    error_type="http_error",
                    error_message=error_msg,
                    finished_at=finished_at,
                )
                if self._should_stop_on_http_error(
                    status_code=response.status_code, error_text=error_text
                ):
                    self._commit_candidate_records()
                    raise UpstreamClientRequestError(
                        response=response,
                        candidate_keys=candidate_keys,
                    )
                continue

            # 解析任务 ID（200 但缺字段也视为失败并 failover）
            payload: dict[str, Any] | None = None
            try:
                data = response.json()
                if isinstance(data, dict):
                    payload = data
                logger.info(
                    "[AsyncTaskOrchestrator] Candidate %d response payload: %s",
                    idx,
                    str(payload)[:500] if payload else "None",
                )
            except Exception as exc:
                finished_at = datetime.now(timezone.utc)
                logger.error(
                    "[AsyncTaskOrchestrator] Candidate %d invalid JSON: %s",
                    idx,
                    str(exc),
                )
                error_msg = _sanitize(str(exc))
                candidate_info.update(
                    {
                        "attempt_status": "invalid_json",
                        "error_type": type(exc).__name__,
                        "error_message": error_msg,
                    }
                )
                self._update_candidate_record(
                    idx,
                    status="failed",
                    status_code=response.status_code,
                    error_type="invalid_json",
                    error_message=error_msg,
                    finished_at=finished_at,
                )
                continue

            external_task_id = extract_external_task_id(payload or {})
            logger.info(
                "[AsyncTaskOrchestrator] Candidate %d extracted task_id: %s",
                idx,
                external_task_id,
            )
            if not external_task_id:
                finished_at = datetime.now(timezone.utc)
                candidate_info.update(
                    {
                        "attempt_status": "empty_task_id",
                        "error_message": "Upstream returned empty task id",
                    }
                )
                self._update_candidate_record(
                    idx,
                    status="failed",
                    status_code=response.status_code,
                    error_type="empty_task_id",
                    error_message="Upstream returned empty task id",
                    finished_at=finished_at,
                )
                logger.warning(
                    "[AsyncTaskOrchestrator] Candidate %d: empty task_id, payload keys: %s",
                    idx,
                    list(payload.keys()) if payload else [],
                )
                continue

            # 成功
            finished_at = datetime.now(timezone.utc)
            candidate_info.update({"attempt_status": "success", "selected": True})
            self._update_candidate_record(
                idx,
                status="success",
                status_code=response.status_code,
                finished_at=finished_at,
            )
            self._commit_candidate_records()
            return SubmitOutcome(
                candidate=cand,
                candidate_keys=candidate_keys,
                external_task_id=str(external_task_id),
                rule_lookup=rule_lookup,
                upstream_payload=payload,
            )

        # 没有任何候选可尝试
        if not candidates:
            raise ProviderNotAvailableException("No candidates available")

        # 提交所有候选记录
        self._commit_candidate_records()

        if eligible_count == 0:
            reason = "no_eligible_candidates"
            if config.billing_require_rule:
                reason = "no_candidate_with_billing_rule"
            raise AllCandidatesFailedError(
                reason=reason,
                candidate_keys=candidate_keys,
                last_status_code=last_status_code,
            )

        raise AllCandidatesFailedError(
            reason="all_candidates_failed",
            candidate_keys=candidate_keys,
            last_status_code=last_status_code,
        )


__all__ = [
    "AsyncTaskOrchestrator",
    "SubmitOutcome",
    "AllCandidatesFailedError",
    "UpstreamClientRequestError",
    "CandidateUnsupportedError",
    "CandidateSubmissionError",
]
