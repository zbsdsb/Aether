from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.core.crypto import crypto_service
from src.core.logger import logger
from src.models.database import Provider
from src.services.provider_ops.service import ProviderOpsService
from src.services.provider_ops.types import ConnectorAuthType, ProviderOpsConfig
from src.services.proxy_node.resolver import get_system_proxy_config_async

_MANUAL_REVIEW_STATUS = "manual_review"
_CHALLENGE_MODE = "challenge"
_CHALLENGE_MESSAGE_MARKERS = (
    "cloudflare",
    "challenge",
    "cf-chl",
    "attention required",
    "just a moment",
    "arg1",
    "acw_sc__v2",
)

_MSG_DIRECT_SUCCEEDED = "直连探测成功"
_MSG_PROXY_FAILED = "代理探测失败"


@dataclass(slots=True)
class ProviderProxyProbeItem:
    provider_id: str
    provider_name: str
    status: str
    mode: str | None = None
    message: str | None = None


@dataclass(slots=True)
class ProviderProxyProbeSummary:
    total_selected: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)


def _all_providers(db: Session) -> list[Provider]:
    query = db.query(Provider)
    if hasattr(query, "all"):
        return list(query.all())
    return []


def _get_provider(provider_id: str, db: Session) -> Provider | None:
    for provider in _all_providers(db):
        if str(getattr(provider, "id", "") or "") == provider_id:
            return provider
    return None


def _provider_ops_config_dict(provider: Provider) -> dict[str, Any] | None:
    raw = dict(getattr(provider, "config", None) or {})
    cfg = raw.get("provider_ops")
    return cfg if isinstance(cfg, dict) else None


def _provider_ops_config(provider: Provider) -> ProviderOpsConfig | None:
    cfg = _provider_ops_config_dict(provider)
    return ProviderOpsConfig.from_dict(cfg) if cfg else None


def _is_pending_probe_candidate(provider: Provider) -> bool:
    cfg = _provider_ops_config_dict(provider)
    if not cfg or not bool(cfg.get("_auto_imported")):
        return False
    status = str(cfg.get("_proxy_probe_status") or "pending").strip().lower()
    connector_cfg = cfg.get("connector", {}).get("config", {})
    has_proxy_node = isinstance(connector_cfg, dict) and bool(connector_cfg.get("proxy_node_id"))
    return not has_proxy_node and status in {"pending", "failed"}


def _is_configured_probe_candidate(provider: Provider) -> bool:
    cfg = _provider_ops_config_dict(provider)
    return bool(cfg and cfg.get("connector"))


def _normalize_connector_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config or {})
    normalized.pop("proxy_node_id", None)
    normalized.pop("__disable_system_proxy_fallback__", None)
    return normalized


def _set_provider_proxy(provider: Provider, proxy_node_id: str | None) -> None:
    provider.proxy = {"node_id": proxy_node_id, "enabled": True} if proxy_node_id else None


def _persist_provider_ops_config(
    provider: Provider,
    *,
    config: ProviderOpsConfig,
    connector_config: dict[str, Any],
    credentials: dict[str, Any],
    service: ProviderOpsService,
) -> None:
    provider_config = dict(getattr(provider, "config", None) or {})
    previous_ops = dict(provider_config.get("provider_ops") or {})
    save_config = ProviderOpsConfig(
        architecture_id=config.architecture_id,
        base_url=config.base_url,
        connector_auth_type=config.connector_auth_type,
        connector_config=connector_config,
        connector_credentials=credentials,
        actions=config.actions,
        schedule=config.schedule,
    )
    save_dict = save_config.to_dict()
    save_dict["connector"]["credentials"] = {
        key: crypto_service.encrypt(value) if key in service.SENSITIVE_FIELDS else value
        for key, value in save_config.connector_credentials.items()
        if str(value).strip()
    }
    for key, value in previous_ops.items():
        if key.startswith("_"):
            save_dict[key] = value
    provider_config["provider_ops"] = save_dict
    provider.config = provider_config


def _resolve_manual_review(
    *messages: str | None,
) -> tuple[str | None, str | None]:
    for raw_message in messages:
        message = str(raw_message or "").strip()
        normalized = message.lower()
        if message and any(marker in normalized for marker in _CHALLENGE_MESSAGE_MARKERS):
            return _CHALLENGE_MODE, message
    return None, None


def _persist_probe_metadata(
    provider: Provider,
    *,
    status: str,
    mode: str | None,
    message: str | None,
) -> None:
    provider_config = dict(getattr(provider, "config", None) or {})
    ops = dict(provider_config.get("provider_ops") or {})
    ops["_proxy_probe_status"] = status
    ops["_proxy_probe_mode"] = mode
    ops["_proxy_probe_message"] = message
    ops["_proxy_probe_checked_at"] = datetime.now(timezone.utc).isoformat()
    provider_config["provider_ops"] = ops
    provider.config = provider_config


async def _probe_single_provider(provider: Provider, db: Session) -> ProviderProxyProbeItem:
    cfg_dict = _provider_ops_config_dict(provider)
    if not cfg_dict:
        return ProviderProxyProbeItem(
            provider_id=str(provider.id),
            provider_name=str(provider.name),
            status="skipped",
            message="未配置扩展操作",
        )

    service = ProviderOpsService(db)
    config = _provider_ops_config(provider)
    if config is None:
        return ProviderProxyProbeItem(
            provider_id=str(provider.id),
            provider_name=str(provider.name),
            status="skipped",
            message="未配置扩展操作",
        )

    credentials = service._decrypt_credentials(config.connector_credentials)  # noqa: SLF001
    base_url = config.base_url or getattr(provider, "website", None) or ""
    if not base_url:
        _persist_probe_metadata(provider, status="failed", mode=None, message="缺少 base_url")
        db.commit()
        return ProviderProxyProbeItem(
            provider_id=str(provider.id),
            provider_name=str(provider.name),
            status="failed",
            message="缺少 base_url",
        )

    direct_config = dict(config.connector_config)
    direct_config.pop("proxy_node_id", None)
    direct_config["__disable_system_proxy_fallback__"] = True
    normalized_direct_config = _normalize_connector_config(config.connector_config)
    direct_result = await service.verify_auth(
        base_url=base_url,
        architecture_id=config.architecture_id,
        auth_type=config.connector_auth_type,
        config=direct_config,
        credentials=credentials,
        provider_id=None,
    )
    if direct_result.get("success", False):
        _persist_provider_ops_config(
            provider,
            config=config,
            connector_config=normalized_direct_config,
            credentials=credentials,
            service=service,
        )
        _set_provider_proxy(provider, None)
        _persist_probe_metadata(provider, status="completed", mode="direct", message=_MSG_DIRECT_SUCCEEDED)
        db.commit()
        return ProviderProxyProbeItem(
            provider_id=str(provider.id),
            provider_name=str(provider.name),
            status="completed",
            mode="direct",
            message=_MSG_DIRECT_SUCCEEDED,
        )

    system_proxy = await get_system_proxy_config_async()
    proxy_node_id = str((system_proxy or {}).get("node_id") or "").strip()
    if not proxy_node_id:
        message = direct_result.get("message") or "直连探测失败"
        manual_review_mode, manual_review_message = _resolve_manual_review(message)
        if manual_review_mode:
            _persist_probe_metadata(
                provider,
                status=_MANUAL_REVIEW_STATUS,
                mode=manual_review_mode,
                message=manual_review_message,
            )
            db.commit()
            return ProviderProxyProbeItem(
                provider_id=str(provider.id),
                provider_name=str(provider.name),
                status=_MANUAL_REVIEW_STATUS,
                mode=manual_review_mode,
                message=manual_review_message,
            )
        _persist_probe_metadata(provider, status="failed", mode=None, message=message)
        db.commit()
        return ProviderProxyProbeItem(
            provider_id=str(provider.id),
            provider_name=str(provider.name),
            status="failed",
            message=message,
        )

    proxy_config = {"proxy_node_id": proxy_node_id}
    proxy_result = await service.verify_auth(
        base_url=base_url,
        architecture_id=config.architecture_id,
        auth_type=config.connector_auth_type,
        config=proxy_config,
        credentials=credentials,
        provider_id=None,
    )
    if not proxy_result.get("success", False):
        message = proxy_result.get("message") or direct_result.get("message") or _MSG_PROXY_FAILED
        manual_review_mode, manual_review_message = _resolve_manual_review(
            proxy_result.get("message"),
            direct_result.get("message"),
        )
        if manual_review_mode:
            _persist_probe_metadata(
                provider,
                status=_MANUAL_REVIEW_STATUS,
                mode=manual_review_mode,
                message=manual_review_message,
            )
            db.commit()
            return ProviderProxyProbeItem(
                provider_id=str(provider.id),
                provider_name=str(provider.name),
                status=_MANUAL_REVIEW_STATUS,
                mode=manual_review_mode,
                message=manual_review_message,
            )
        _persist_probe_metadata(provider, status="failed", mode="system_proxy", message=message)
        db.commit()
        return ProviderProxyProbeItem(
            provider_id=str(provider.id),
            provider_name=str(provider.name),
            status="failed",
            mode="system_proxy",
            message=message,
        )

    _persist_provider_ops_config(
        provider,
        config=config,
        connector_config=normalized_direct_config,
        credentials=credentials,
        service=service,
    )
    _set_provider_proxy(provider, proxy_node_id)
    _persist_probe_metadata(
        provider,
        status="completed",
        mode="system_proxy",
        message=f"已切换为系统代理节点 {proxy_node_id}",
    )
    db.commit()
    return ProviderProxyProbeItem(
        provider_id=str(provider.id),
        provider_name=str(provider.name),
        status="completed",
        mode="system_proxy",
        message=f"已切换为系统代理节点 {proxy_node_id}",
    )


async def probe_provider_proxy(provider_id: str, *, db: Session) -> dict[str, Any]:
    provider = _get_provider(provider_id, db)
    if provider is None:
        raise RuntimeError("provider not found")
    result = await _probe_single_provider(provider, db)
    return asdict(result)


async def probe_provider_proxies(
    provider_ids: list[str],
    *,
    db: Session,
    progress_callback: Callable[[int, ProviderProxyProbeSummary, ProviderProxyProbeItem], Awaitable[None]] | None = None,
) -> ProviderProxyProbeSummary:
    selected_ids = {provider_id for provider_id in provider_ids if str(provider_id).strip()}
    providers = [
        provider
        for provider in _all_providers(db)
        if str(getattr(provider, "id", "") or "") in selected_ids and _is_pending_probe_candidate(provider)
    ]
    summary = ProviderProxyProbeSummary(total_selected=len(providers))
    for index, provider in enumerate(providers, start=1):
        try:
            result = await _probe_single_provider(provider, db)
        except Exception as exc:
            logger.warning("provider proxy probe failed provider_id={}: {}", provider.id, exc)
            result = ProviderProxyProbeItem(
                provider_id=str(provider.id),
                provider_name=str(provider.name),
                status="failed",
                message=str(exc),
            )
        if result.status == "completed":
            summary.completed += 1
        elif result.status == "failed":
            summary.failed += 1
        else:
            summary.skipped += 1
        summary.results.append(asdict(result))
        if progress_callback is not None:
            await progress_callback(index, summary, result)
    return summary


async def probe_pending_provider_proxies(*, db: Session, limit: int = 20) -> ProviderProxyProbeSummary:
    providers = [provider for provider in _all_providers(db) if _is_pending_probe_candidate(provider)][: max(limit, 0)]
    summary = ProviderProxyProbeSummary(total_selected=len(providers))
    for provider in providers:
        try:
            result = await _probe_single_provider(provider, db)
        except Exception as exc:
            logger.warning("provider proxy probe failed provider_id={}: {}", provider.id, exc)
            result = ProviderProxyProbeItem(
                provider_id=str(provider.id),
                provider_name=str(provider.name),
                status="failed",
                message=str(exc),
            )
        if result.status == "completed":
            summary.completed += 1
        elif result.status == "failed":
            summary.failed += 1
        elif result.status == _MANUAL_REVIEW_STATUS:
            summary.skipped += 1
        else:
            summary.skipped += 1
        summary.results.append(asdict(result))
    return summary


async def probe_all_provider_proxies(*, db: Session, limit: int = 200) -> ProviderProxyProbeSummary:
    providers = [
        provider
        for provider in _all_providers(db)
        if _is_configured_probe_candidate(provider) and bool(getattr(provider, "is_active", True))
    ][: max(limit, 0)]
    summary = ProviderProxyProbeSummary(total_selected=len(providers))
    for provider in providers:
        try:
            result = await _probe_single_provider(provider, db)
        except Exception as exc:
            logger.warning("provider proxy probe failed provider_id={}: {}", provider.id, exc)
            result = ProviderProxyProbeItem(
                provider_id=str(provider.id),
                provider_name=str(provider.name),
                status="failed",
                message=str(exc),
            )
        if result.status == "completed":
            summary.completed += 1
        elif result.status == "failed":
            summary.failed += 1
        else:
            summary.skipped += 1
        summary.results.append(asdict(result))
    return summary
