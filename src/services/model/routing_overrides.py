from __future__ import annotations

from typing import Any, TypedDict, cast

from sqlalchemy.orm import Session

from src.models.database import GlobalModel


class GlobalModelRoutingOverrides(TypedDict):
    provider_priorities: dict[str, int]
    key_internal_priorities: dict[str, int]
    key_priorities_by_format: dict[str, dict[str, int]]


def empty_global_model_routing_overrides() -> GlobalModelRoutingOverrides:
    return {
        "provider_priorities": {},
        "key_internal_priorities": {},
        "key_priorities_by_format": {},
    }


def _normalize_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_global_model_routing_overrides(
    config: dict[str, Any] | None,
) -> GlobalModelRoutingOverrides:
    result = empty_global_model_routing_overrides()
    if not isinstance(config, dict):
        return result

    raw_overrides = config.get("routing_overrides")
    if not isinstance(raw_overrides, dict):
        return result

    raw_provider_priorities = raw_overrides.get("provider_priorities")
    if isinstance(raw_provider_priorities, dict):
        for provider_id, priority in raw_provider_priorities.items():
            normalized = _normalize_int(priority)
            if isinstance(provider_id, str) and normalized is not None:
                result["provider_priorities"][provider_id] = normalized

    raw_key_internal_priorities = raw_overrides.get("key_internal_priorities")
    if isinstance(raw_key_internal_priorities, dict):
        for key_id, priority in raw_key_internal_priorities.items():
            normalized = _normalize_int(priority)
            if isinstance(key_id, str) and normalized is not None:
                result["key_internal_priorities"][key_id] = normalized

    raw_key_priorities_by_format = raw_overrides.get("key_priorities_by_format")
    if isinstance(raw_key_priorities_by_format, dict):
        for key_id, priority_map in raw_key_priorities_by_format.items():
            if not isinstance(key_id, str) or not isinstance(priority_map, dict):
                continue
            normalized_map: dict[str, int] = {}
            for api_format, priority in priority_map.items():
                normalized = _normalize_int(priority)
                if isinstance(api_format, str) and normalized is not None:
                    normalized_map[api_format] = normalized
            if normalized_map:
                result["key_priorities_by_format"][key_id] = normalized_map

    return result


def load_global_model_routing_overrides(
    db: Session,
    global_model_id: str | None,
) -> GlobalModelRoutingOverrides:
    if not global_model_id:
        return empty_global_model_routing_overrides()

    global_model = (
        db.query(GlobalModel.config)
        .filter(GlobalModel.id == global_model_id)
        .first()
    )
    if not global_model:
        return empty_global_model_routing_overrides()

    config = cast(dict[str, Any] | None, global_model[0] if hasattr(global_model, "__getitem__") else None)
    return normalize_global_model_routing_overrides(config)


def get_effective_provider_priority(
    provider_id: str | None,
    default_priority: int | None,
    overrides: GlobalModelRoutingOverrides,
) -> int:
    if provider_id and provider_id in overrides["provider_priorities"]:
        return overrides["provider_priorities"][provider_id]
    return default_priority if default_priority is not None else 999999


def get_effective_key_internal_priority(
    key_id: str | None,
    default_priority: int | None,
    overrides: GlobalModelRoutingOverrides,
) -> int:
    if key_id and key_id in overrides["key_internal_priorities"]:
        return overrides["key_internal_priorities"][key_id]
    return default_priority if default_priority is not None else 999999


def get_effective_key_format_priority(
    key_id: str | None,
    api_format: str | None,
    default_priority: int | None,
    overrides: GlobalModelRoutingOverrides,
) -> int:
    if key_id and api_format:
        priority_map = overrides["key_priorities_by_format"].get(key_id) or {}
        if api_format in priority_map:
            return priority_map[api_format]
    return default_priority if default_priority is not None else 999999
