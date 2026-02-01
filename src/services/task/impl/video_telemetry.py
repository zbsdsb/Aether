"""
VideoTelemetry（Phase3）

将 Video 异步任务的“终态计费 + Usage 写入 + required 缺失告警”从 poller 中抽离出来，
便于未来 Image/Audio 复用相同框架。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.api.handlers.base.video_handler_base import sanitize_error_message
from src.config.settings import config
from src.core.api_format.conversion.internal_video import VideoStatus
from src.core.logger import logger
from src.models.database import ApiKey, Provider, User, VideoTask
from src.services.billing.dimension_collector_service import DimensionCollectorService
from src.services.billing.formula_engine import BillingIncompleteError, FormulaEngine
from src.services.billing.rule_service import BillingRuleService
from src.services.usage.service import UsageService


class VideoTelemetry:
    def __init__(self, db: Session, *, redis_client: Any | None = None) -> None:
        self.db = db
        self.redis = redis_client
        self._formula_engine = FormulaEngine()

    async def record_terminal_usage(self, task: VideoTask) -> None:
        """
        为视频任务终态写入 Usage：
        - COMPLETED: 使用 FormulaEngine 计算 cost（或 no_rule / incomplete -> cost=0）
        - FAILED: cost=0

        该方法可能会在 strict_mode 缺失 required 维度时将任务降级为 FAILED 并隐藏产物。
        """
        request_id = None
        if isinstance(task.request_metadata, dict):
            request_id = task.request_metadata.get("request_id")
        request_id = request_id or task.id

        # 计算异步任务总耗时（ms）
        response_time_ms = None
        if task.submitted_at and task.completed_at:
            delta = task.completed_at - task.submitted_at
            response_time_ms = int(delta.total_seconds() * 1000)

        # 基础维度（无需 collectors 也可计费）
        base_dimensions: dict[str, Any] = {
            "duration_seconds": task.duration_seconds,
            "resolution": task.resolution,
            "aspect_ratio": task.aspect_ratio,
            "size": task.size or "",
            "retry_count": task.retry_count,
        }

        # collectors 可用的 metadata（结构稳定，便于配置 path）
        collector_metadata: dict[str, Any] = {
            "task": {
                "id": task.id,
                "external_task_id": task.external_task_id,
                "model": task.model,
                "duration_seconds": task.duration_seconds,
                "resolution": task.resolution,
                "aspect_ratio": task.aspect_ratio,
                "size": task.size,
                "retry_count": task.retry_count,
                "video_size_bytes": task.video_size_bytes,
            },
            "result": {
                "video_url": task.video_url,
                "video_urls": task.video_urls or [],
            },
        }

        # 维度采集：base + collectors 覆盖/补全
        dims = DimensionCollectorService(self.db).collect_dimensions(
            api_format=task.provider_api_format,
            task_type="video",
            request=task.original_request_body or {},
            response=(
                (task.request_metadata or {}).get("poll_raw_response")
                if isinstance(task.request_metadata, dict)
                else None
            ),
            metadata=collector_metadata,
            base_dimensions=base_dimensions,
        )

        # 取冻结的 rule_snapshot；若缺失则回退 DB 查找（兼容旧任务）
        rule_snapshot = None
        if isinstance(task.request_metadata, dict):
            rule_snapshot = task.request_metadata.get("billing_rule_snapshot")

        billing_snapshot: dict[str, Any] = {
            "status": "complete",
            "missing_required": [],
            "strict_mode": config.billing_strict_mode,
        }
        cost = 0.0

        if task.status == VideoStatus.FAILED.value:
            billing_snapshot["billed_reason"] = "task_failed"
        else:
            # COMPLETED：计算成本
            expression = None
            variables = None
            dimension_mappings = None
            rule_id = None
            rule_name = None
            rule_scope = None

            if isinstance(rule_snapshot, dict) and rule_snapshot.get("status") == "ok":
                rule_id = rule_snapshot.get("rule_id")
                rule_name = rule_snapshot.get("rule_name")
                rule_scope = rule_snapshot.get("scope")
                expression = rule_snapshot.get("expression")
                variables = rule_snapshot.get("variables")
                dimension_mappings = rule_snapshot.get("dimension_mappings")
            else:
                lookup = BillingRuleService.find_rule(
                    self.db,
                    provider_id=task.provider_id,
                    model_name=task.model,
                    task_type="video",
                )
                if lookup:
                    rule = lookup.rule
                    rule_id = rule.id
                    rule_name = rule.name
                    rule_scope = lookup.scope
                    expression = rule.expression
                    variables = rule.variables
                    dimension_mappings = rule.dimension_mappings

            if not expression:
                billing_snapshot["status"] = "no_rule"
                billing_snapshot["cost_breakdown"] = {"total": 0.0}
                logger.warning(
                    "No billing rule for video task (request_id=%s, model=%s, provider_id=%s)",
                    request_id,
                    task.model,
                    task.provider_id,
                )
            else:
                billing_snapshot.update(
                    {
                        "rule_id": rule_id,
                        "rule_name": rule_name,
                        "rule_scope": rule_scope,
                        "expression": expression,
                        "variables": variables or {},
                    }
                )
                try:
                    result = self._formula_engine.evaluate(
                        expression=expression,
                        variables=variables or {},
                        dimensions=dims,
                        dimension_mappings=dimension_mappings or {},
                        strict_mode=config.billing_strict_mode,
                    )
                    billing_snapshot["status"] = result.status
                    billing_snapshot["missing_required"] = result.missing_required
                    billing_snapshot["resolved_values"] = result.resolved_values
                    if result.status == "complete":
                        cost = result.cost
                    else:
                        logger.error(
                            "Billing incomplete due to missing required dimensions "
                            "(request_id=%s, model=%s, missing=%s)",
                            request_id,
                            task.model,
                            result.missing_required,
                        )
                        cost = 0.0
                        await self._maybe_alert_missing_required(
                            model=task.model,
                            missing_required=result.missing_required,
                        )
                    if result.error:
                        billing_snapshot["error"] = result.error
                except BillingIncompleteError as exc:
                    logger.error(
                        "Billing strict mode triggered (request_id=%s, model=%s, missing=%s)",
                        request_id,
                        task.model,
                        exc.missing_required,
                    )
                    billing_snapshot["status"] = "incomplete"
                    billing_snapshot["missing_required"] = exc.missing_required
                    billing_snapshot["resolved_values"] = {}
                    billing_snapshot["error"] = "strict_mode_missing_required"
                    cost = 0.0

                    # strict_mode=true：标记任务失败并隐藏产物，避免"免费放行"
                    task.status = VideoStatus.FAILED.value
                    task.error_code = "billing_incomplete"
                    task.error_message = f"Missing required dimensions: {exc.missing_required}"
                    task.video_url = None
                    task.video_urls = None

                    await self._maybe_alert_missing_required(
                        model=task.model,
                        missing_required=exc.missing_required,
                    )

                billing_snapshot["cost_breakdown"] = {"total": cost}

        # 将 billing_snapshot 回写到 task.request_metadata 便于对账（不会影响 usage 的单独存档）
        if task.request_metadata is None:
            task.request_metadata = {}
        if isinstance(task.request_metadata, dict):
            task.request_metadata["billing_snapshot"] = billing_snapshot

        usage_metadata: dict[str, Any] = {
            "billing_snapshot": billing_snapshot,
            "dimensions": dims,
            "raw_response_ref": {
                "video_task_id": task.id,
                "field": "video_tasks.request_metadata.poll_raw_response",
            },
        }

        # 查询关联对象（用于写入 usage.user_id/api_key_id 等）
        user_obj = self.db.query(User).filter(User.id == task.user_id).first()
        api_key_obj = (
            self.db.query(ApiKey).filter(ApiKey.id == task.api_key_id).first()
            if task.api_key_id
            else None
        )
        provider_obj = (
            self.db.query(Provider).filter(Provider.id == task.provider_id).first()
            if task.provider_id
            else None
        )
        provider_name = provider_obj.name if provider_obj else "unknown"

        await UsageService.record_usage_with_custom_cost(
            db=self.db,
            user=user_obj,
            api_key=api_key_obj,
            provider=provider_name,
            model=task.model,
            request_type="video",
            total_cost_usd=cost,
            request_cost_usd=cost,
            input_tokens=0,
            output_tokens=0,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
            api_format=task.client_api_format,
            endpoint_api_format=task.provider_api_format,
            has_format_conversion=bool(task.format_converted),
            is_stream=False,
            response_time_ms=response_time_ms,
            first_byte_time_ms=None,
            status_code=200 if task.status == VideoStatus.COMPLETED.value else 500,
            error_message=(
                None
                if task.status == VideoStatus.COMPLETED.value
                else (task.error_message or task.error_code or "video_task_failed")
            ),
            metadata=usage_metadata,
            request_headers=(
                (task.request_metadata or {}).get("request_headers")
                if isinstance(task.request_metadata, dict)
                else None
            ),
            request_body=task.original_request_body,
            provider_request_headers=None,
            response_headers=None,
            client_response_headers=None,
            response_body=None,
            request_id=request_id,
            provider_id=task.provider_id,
            provider_endpoint_id=task.endpoint_id,
            provider_api_key_id=task.key_id,
            status="completed" if task.status == VideoStatus.COMPLETED.value else "failed",
            target_model=None,
        )

    async def _maybe_alert_missing_required(
        self, *, model: str, missing_required: list[str]
    ) -> None:
        """required 维度缺失告警：同一 (model, dimension) 1 小时内 >= 10 次触发升级告警。"""
        if not missing_required:
            return
        if not self.redis:
            logger.error(
                "Missing required billing dimensions (model=%s): %s", model, missing_required
            )
            return

        # 按小时 bucket 聚合
        now = datetime.now(timezone.utc)
        hour_bucket = now.strftime("%Y%m%d%H")
        for dim in missing_required:
            key = f"billing:missing_required:{model}:{dim}:{hour_bucket}"
            try:
                count = await self.redis.incr(key)
                if count == 1:
                    await self.redis.expire(key, 3700)
                if count >= 10:
                    logger.warning(
                        "Billing required dimension missing frequently (model=%s, dim=%s, count=%s/hour)",
                        model,
                        dim,
                        count,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to record billing alert counter: %s", sanitize_error_message(str(exc))
                )


__all__ = ["VideoTelemetry"]
