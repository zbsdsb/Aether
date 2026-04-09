from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from src.api.base.models_service import (
    AccessRestrictions,
    get_available_provider_ids,
    get_compatible_provider_formats,
    sanitize_public_global_model_config,
)
from src.models.api import (
    UserModelMarketplaceItem,
    UserModelMarketplaceProviderItem,
    UserModelMarketplaceResponse,
    UserModelMarketplaceSummary,
)
from src.models.database import (
    GlobalModel,
    Model,
    Provider,
    ProviderEndpoint,
    Usage,
    User,
    UserModelUsageCount,
)
from src.services.system.config import SystemConfigService

_LOOKBACK_HOURS = 24
_ALL_FORMATS = [
    "openai:chat",
    "openai:cli",
    "openai:compact",
    "claude:chat",
    "gemini:chat",
]
_EMBEDDING_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"embedding", r"\bembed\b", r"text-embedding", r"\bbge\b", r"\be5\b"]]
_CODING_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"\bcoder\b", r"\bcoding\b", r"\bcode\b", r"devstral"]]
_THINKING_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"\bo1\b", r"\bo3\b", r"\bo4\b", r"reason", r"thinking", r"\br1\b"]]
_IMAGE_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"\bimage\b", r"\bvision\b", r"\bvl\b", r"flux", r"stable[- ]?diffusion"]]
_AUDIO_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"\baudio\b", r"\bspeech\b", r"\btts\b", r"whisper", r"transcri"]]
_RERANK_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"rerank", r"reranker"]]
_ALLOWED_SORT_FIELDS = {
    "provider_count",
    "active_provider_count",
    "success_rate",
    "avg_latency_ms",
    "usage_count",
    "name",
}


def derive_marketplace_tags(
    *,
    name: str,
    display_name: str | None = None,
    supported_capabilities: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> list[str]:
    tags: list[str] = []
    text = " ".join(
        str(part).strip()
        for part in [
            name,
            display_name or "",
            (config or {}).get("category", ""),
            (config or {}).get("family", ""),
        ]
        if str(part).strip()
    )
    capabilities = {str(item).strip().lower() for item in (supported_capabilities or []) if item}

    def _append(tag: str) -> None:
        if tag not in tags:
            tags.append(tag)

    if any(pattern.search(text) for pattern in _EMBEDDING_PATTERNS):
        _append("embedding")
    if any(pattern.search(text) for pattern in _CODING_PATTERNS):
        _append("coding")
    if any(pattern.search(text) for pattern in _THINKING_PATTERNS):
        _append("thinking")
    if any(pattern.search(text) for pattern in _IMAGE_PATTERNS) or "vision" in capabilities:
        _append("image")
    if any(pattern.search(text) for pattern in _AUDIO_PATTERNS):
        _append("audio")
    if any(pattern.search(text) for pattern in _RERANK_PATTERNS):
        _append("rerank")

    return tags


def mark_marketplace_badges(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [dict(item) for item in items]
    for item in result:
        item["is_recommended"] = False
        item["recommendation_reason"] = None
        item["is_most_stable"] = False
        item["stability_reason"] = None

    stable_candidates = [
        item
        for item in result
        if item.get("success_rate") is not None and item.get("avg_latency_ms") is not None
    ]
    if stable_candidates:
        stable_item = sorted(
            stable_candidates,
            key=lambda item: (
                -(float(item.get("success_rate") or 0)),
                int(item.get("avg_latency_ms") or 0),
                -int(item.get("active_provider_count") or 0),
                -int(item.get("provider_count") or 0),
                str(item.get("name") or ""),
            ),
        )[0]
        stable_item["is_most_stable"] = True
        stable_item["stability_reason"] = (
            f"最近窗口成功率 {round(float(stable_item.get('success_rate') or 0) * 100)}%，"
            f"平均延迟 {int(stable_item.get('avg_latency_ms') or 0)}ms。"
        )

    recommended_candidates = [
        item
        for item in result
        if (
            int(item.get("active_provider_count") or 0) > 0
            and item.get("success_rate") is not None
            and float(item.get("success_rate") or 0) >= 0.9
        )
    ]
    if not recommended_candidates:
        recommended_candidates = [
            item
            for item in result
            if int(item.get("active_provider_count") or 0) > 0 and item.get("success_rate") is not None
        ]
    if recommended_candidates:
        recommended_item = sorted(
            recommended_candidates,
            key=lambda item: (
                -int(item.get("active_provider_count") or 0),
                -int(item.get("provider_count") or 0),
                -(float(item.get("success_rate") or 0)),
                int(item.get("avg_latency_ms") or 10**9),
                str(item.get("name") or ""),
            ),
        )[0]
        recommended_item["is_recommended"] = True
        recommended_item["recommendation_reason"] = (
            f"当前有 {int(recommended_item.get('active_provider_count') or 0)} 个活跃来源，"
            f"最近成功率 {round(float(recommended_item.get('success_rate') or 0) * 100)}%。"
        )

    return result


def filter_and_sort_marketplace_items(
    items: list[dict[str, Any]],
    *,
    brand: str | None = None,
    tag: str | None = None,
    capability: str | None = None,
    only_available: bool = False,
    sort_by: str = "provider_count",
    sort_dir: str = "desc",
) -> list[dict[str, Any]]:
    normalized_brand = (brand or "").strip().lower()
    normalized_tag = (tag or "").strip().lower()
    normalized_capability = (capability or "").strip().lower()
    sort_field = sort_by if sort_by in _ALLOWED_SORT_FIELDS else "provider_count"
    descending = str(sort_dir).lower() != "asc"

    filtered: list[dict[str, Any]] = []
    for item in items:
        if normalized_brand and str(item.get("brand") or "").lower() != normalized_brand:
            continue
        if normalized_tag:
            tags = [str(value).lower() for value in item.get("tags") or []]
            if normalized_tag not in tags:
                continue
        if normalized_capability:
            capabilities = [str(value).lower() for value in item.get("supported_capabilities") or []]
            if normalized_capability not in capabilities:
                continue
        if only_available and int(item.get("active_provider_count") or 0) <= 0:
            continue
        filtered.append(item)

    def _sort_value(item: dict[str, Any]) -> Any:
        if sort_field == "name":
            return str(item.get("name") or "")
        value = item.get(sort_field)
        return -1 if value is None else value

    filtered.sort(
        key=lambda item: (
            _sort_value(item),
            str(item.get("name") or ""),
        ),
        reverse=descending,
    )
    return filtered


def build_marketplace_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    total_models = len(items)
    total_provider_count = sum(int(item.get("provider_count") or 0) for item in items)
    active_provider_count = sum(int(item.get("active_provider_count") or 0) for item in items)

    numerator = 0.0
    denominator = 0
    for item in items:
        success_rate = item.get("success_rate")
        provider_count = int(item.get("provider_count") or 0)
        if success_rate is None or provider_count <= 0:
            continue
        numerator += float(success_rate) * provider_count
        denominator += provider_count

    overall_success_rate = round(numerator / denominator, 2) if denominator > 0 else None

    return {
        "total_models": total_models,
        "total_provider_count": total_provider_count,
        "active_provider_count": active_provider_count,
        "overall_success_rate": overall_success_rate,
    }


def _resolve_brand(name: str, display_name: str | None, config: dict[str, Any] | None) -> str:
    text = " ".join(
        str(part).strip().lower()
        for part in [
            name,
            display_name or "",
            (config or {}).get("family", ""),
            (config or {}).get("icon_url", ""),
        ]
        if str(part).strip()
    )
    if any(token in text for token in ["gpt", "openai"]):
        return "openai"
    if any(token in text for token in ["claude", "anthropic"]):
        return "anthropic"
    if any(token in text for token in ["gemini", "google", "vertex"]):
        return "google"
    if "deepseek" in text:
        return "deepseek"
    return "other"


def _get_all_available_provider_ids(db: Session, global_conversion_enabled: bool) -> set[str]:
    provider_to_formats = get_compatible_provider_formats(
        db=db,
        client_format="openai:chat",
        api_formats=_ALL_FORMATS,
        global_conversion_enabled=global_conversion_enabled,
    )
    return get_available_provider_ids(
        db=db,
        api_formats=_ALL_FORMATS,
        provider_to_formats=provider_to_formats,
    )


def build_user_model_marketplace_response(
    *,
    db: Session,
    user: User,
    search: str | None = None,
    brand: str | None = None,
    tag: str | None = None,
    capability: str | None = None,
    only_available: bool = False,
    sort_by: str = "provider_count",
    sort_dir: str = "desc",
) -> UserModelMarketplaceResponse:
    restrictions = AccessRestrictions.from_api_key_and_user(api_key=None, user=user)
    global_conversion_enabled = SystemConfigService.is_format_conversion_enabled(db)
    available_provider_ids = _get_all_available_provider_ids(db, global_conversion_enabled)

    base_query = (
        db.query(GlobalModel.id, GlobalModel.name, Model.provider_id)
        .join(Model, Model.global_model_id == GlobalModel.id)
        .join(Provider, Model.provider_id == Provider.id)
        .filter(
            GlobalModel.is_active.is_(True),
            Model.is_active.is_(True),
            Provider.is_active.is_(True),
        )
    )
    if search:
        search_term = f"%{search}%"
        base_query = base_query.filter(
            or_(
                GlobalModel.name.ilike(search_term),
                GlobalModel.display_name.ilike(search_term),
            )
        )

    all_matches = base_query.all()
    allowed_pairs: set[tuple[str, str]] = set()
    allowed_global_model_ids: set[str] = set()
    for global_model_id, model_name, provider_id in all_matches:
        if restrictions.is_model_allowed(model_name, provider_id):
            allowed_pairs.add((str(global_model_id), str(provider_id)))
            allowed_global_model_ids.add(str(global_model_id))

    if not allowed_global_model_ids:
        return UserModelMarketplaceResponse(
            summary=UserModelMarketplaceSummary(),
            models=[],
            total=0,
            generated_at=datetime.now(timezone.utc),
        )

    global_models = (
        db.query(GlobalModel)
        .filter(GlobalModel.id.in_(allowed_global_model_ids))
        .order_by(GlobalModel.name)
        .all()
    )

    provider_models = (
        db.query(Model)
        .options(joinedload(Model.provider), joinedload(Model.global_model))
        .join(Provider, Model.provider_id == Provider.id)
        .filter(
            Model.global_model_id.in_(allowed_global_model_ids),
            Model.is_active.is_(True),
            Provider.is_active.is_(True),
        )
        .all()
    )
    provider_models = [
        model
        for model in provider_models
        if (str(model.global_model_id), str(model.provider_id)) in allowed_pairs
    ]

    provider_ids = sorted({str(model.provider_id) for model in provider_models if model.provider_id})
    endpoint_rows = (
        db.query(ProviderEndpoint).filter(ProviderEndpoint.provider_id.in_(provider_ids)).all()
        if provider_ids
        else []
    )
    endpoints_by_provider: dict[str, list[ProviderEndpoint]] = {}
    for endpoint in endpoint_rows:
        endpoints_by_provider.setdefault(str(endpoint.provider_id), []).append(endpoint)

    user_usage_rows = (
        db.query(UserModelUsageCount.model, UserModelUsageCount.usage_count)
        .filter(UserModelUsageCount.user_id == user.id)
        .all()
    )
    user_usage_map = {str(row.model): int(row.usage_count or 0) for row in user_usage_rows}

    since = datetime.now(timezone.utc) - timedelta(hours=_LOOKBACK_HOURS)
    usage_rows = (
        db.query(Usage)
        .filter(
            Usage.created_at >= since,
            Usage.status.in_(["completed", "failed"]),
        )
        .all()
    )

    allowed_names = {str(model.name) for model in global_models}
    usage_by_model_name: dict[str, list[Usage]] = {}
    for usage in usage_rows:
        model_name = str(usage.model or usage.target_model or "").strip()
        if not model_name or model_name not in allowed_names:
            continue
        usage_by_model_name.setdefault(model_name, []).append(usage)

    models_by_global_id: dict[str, list[Model]] = {}
    for model in provider_models:
        if model.global_model_id:
            models_by_global_id.setdefault(str(model.global_model_id), []).append(model)

    items: list[dict[str, Any]] = []
    for global_model in global_models:
        model_rows = models_by_global_id.get(str(global_model.id), [])
        provider_items: list[UserModelMarketplaceProviderItem] = []
        seen_provider_ids: set[str] = set()
        endpoint_count = 0
        active_endpoint_count = 0
        supported_api_formats: set[str] = set()

        for model_row in model_rows:
            provider = model_row.provider
            if not provider or not provider.id:
                continue
            provider_id = str(provider.id)
            if provider_id in seen_provider_ids:
                continue
            seen_provider_ids.add(provider_id)
            provider_endpoints = endpoints_by_provider.get(provider_id, [])
            endpoint_count += len(provider_endpoints)
            active_endpoint_count += sum(1 for endpoint in provider_endpoints if endpoint.is_active)
            provider_formats = sorted(
                {str(endpoint.api_format) for endpoint in provider_endpoints if endpoint.api_format}
            )
            supported_api_formats.update(provider_formats)
            provider_items.append(
                UserModelMarketplaceProviderItem(
                    provider_id=provider_id,
                    provider_name=provider.name,
                    provider_website=provider.website,
                    is_active=provider_id in available_provider_ids,
                    endpoint_count=len(provider_endpoints),
                    active_endpoint_count=sum(1 for endpoint in provider_endpoints if endpoint.is_active),
                    supported_api_formats=provider_formats,
                )
            )

        recent_rows = usage_by_model_name.get(str(global_model.name), [])
        success_rows = [row for row in recent_rows if str(row.status) == "completed"]
        failed_rows = [row for row in recent_rows if str(row.status) == "failed"]
        success_rate = None
        if success_rows or failed_rows:
            success_rate = round(len(success_rows) / (len(success_rows) + len(failed_rows)), 2)

        latency_samples = [int(row.response_time_ms) for row in success_rows if row.response_time_ms is not None]
        if not latency_samples:
            latency_samples = [int(row.response_time_ms) for row in failed_rows if row.response_time_ms is not None]
        avg_latency_ms = round(sum(latency_samples) / len(latency_samples)) if latency_samples else None

        safe_config = sanitize_public_global_model_config(global_model.config)
        items.append(
            UserModelMarketplaceItem(
                id=str(global_model.id),
                name=global_model.name,
                display_name=global_model.display_name,
                description=(safe_config or {}).get("description"),
                brand=_resolve_brand(global_model.name, global_model.display_name, safe_config),
                icon_url=(safe_config or {}).get("icon_url"),
                is_active=bool(global_model.is_active),
                supported_capabilities=global_model.supported_capabilities,
                tags=derive_marketplace_tags(
                    name=global_model.name,
                    display_name=global_model.display_name,
                    supported_capabilities=global_model.supported_capabilities,
                    config=safe_config,
                ),
                usage_count=user_usage_map.get(global_model.name, 0),
                provider_count=len(seen_provider_ids),
                active_provider_count=sum(1 for provider_id in seen_provider_ids if provider_id in available_provider_ids),
                endpoint_count=endpoint_count,
                active_endpoint_count=active_endpoint_count,
                supported_api_formats=sorted(supported_api_formats),
                success_rate=success_rate,
                avg_latency_ms=avg_latency_ms,
                default_price_per_request=float(global_model.default_price_per_request) if global_model.default_price_per_request is not None else None,
                default_tiered_pricing=global_model.default_tiered_pricing,
                providers=provider_items,
            ).model_dump()
        )

    marked_items = mark_marketplace_badges(items)
    visible_items = filter_and_sort_marketplace_items(
        marked_items,
        brand=brand,
        tag=tag,
        capability=capability,
        only_available=only_available,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    summary = build_marketplace_summary(visible_items)

    return UserModelMarketplaceResponse(
        summary=UserModelMarketplaceSummary(**summary),
        models=[UserModelMarketplaceItem(**item) for item in visible_items],
        total=len(visible_items),
        generated_at=datetime.now(timezone.utc),
    )
