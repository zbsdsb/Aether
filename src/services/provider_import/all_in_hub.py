from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import asyncio

from sqlalchemy.orm import Session

from src.api.base.models_service import invalidate_models_list_cache
from src.core.api_format.metadata import get_default_body_rules_for_endpoint
from src.core.crypto import crypto_service
from src.core.enums import ProviderBillingType
from src.core.exceptions import InvalidRequestException
from src.core.logger import logger
from src.database import create_session
from src.models.database import Provider, ProviderAPIKey, ProviderEndpoint, ProviderImportTask
from src.models.provider_import import (
    AllInHubImportManualItem,
    AllInHubImportProviderSummary,
    AllInHubImportResponse,
    AllInHubImportStats,
)
from src.services.provider_import.endpoint_candidates import (
    EndpointCandidate,
    resolve_endpoint_candidates,
)
from src.services.provider.fingerprint import generate_fingerprint
from src.services.provider_keys.key_side_effects import run_create_key_side_effects
from src.utils.async_utils import safe_create_task

PENDING_IMPORT_TASK_TYPE = "pending_import"
PENDING_REISSUE_TASK_TYPE = "pending_reissue"
IMPORTED_AUTH_PREFILL_TASK_TYPE = "imported_auth_prefill"
ACTION_REQUIRED_PREFILL_ONLY = "prefill_only"
TASK_STATUS_PENDING = "pending"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_CANCELLED = "cancelled"
TASK_SOURCE_KIND = "all_in_hub"
_IMPORTED_KEY_MODEL_FETCH_SEMAPHORE = asyncio.Semaphore(3)


@dataclass(slots=True)
class _ImportRecord:
    provider_origin: str
    endpoint_base_url: str
    provider_name: str
    source_id: str
    display_name: str | None = None
    site_type: str | None = None
    auth_type: str | None = None
    account_id: str | None = None
    username: str | None = None
    direct_api_key: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    session_cookie: str | None = None


@dataclass(slots=True)
class _ProviderBucket:
    provider_origin: str
    provider_name: str
    endpoint_base_url: str
    direct_records: list[_ImportRecord] = field(default_factory=list)
    pending_records: list[_ImportRecord] = field(default_factory=list)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def _normalize_pending_endpoint_base_url(url: str) -> str:
    normalized = _normalize_base_url(url)
    parsed = urlsplit(normalized)
    host = parsed.netloc.lower()
    if host != "nih.cc":
        return normalized
    return urlunsplit(
        (
            parsed.scheme.lower(),
            "api.nih.cc",
            parsed.path.rstrip("/"),
            parsed.query,
            parsed.fragment,
        )
    ).rstrip("/")


def _normalize_origin(url: str) -> str | None:
    raw = _optional_str(url)
    if not raw:
        return None
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _default_provider_name(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.netloc or url
    return host.split(":")[0]


def _parse_json_content(content: str | dict[str, Any] | list[Any]) -> tuple[Any, str]:
    if isinstance(content, (dict, list)):
        data = content
    else:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidRequestException(f"all-in-hub 导入内容不是合法 JSON: {exc}") from exc

    version = ""
    if isinstance(data, dict):
        version = str(data.get("version") or "")
    return data, version


def _extract_v2_account_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    accounts_wrapper = data.get("accounts", {})
    if isinstance(accounts_wrapper, dict):
        raw_accounts = accounts_wrapper.get("accounts", [])
    elif isinstance(accounts_wrapper, list):
        raw_accounts = accounts_wrapper
    else:
        raw_accounts = []

    if not isinstance(raw_accounts, list):
        return []
    return [item for item in raw_accounts if isinstance(item, dict)]


def _looks_like_masked_secret(value: str | None) -> bool:
    return "*" in str(value or "")


def _extract_v2_snapshot_direct_records(data: dict[str, Any]) -> tuple[list[_ImportRecord], set[str]]:
    account_items = _extract_v2_account_items(data)
    account_map = {
        _optional_str(item.get("id")) or "": item
        for item in account_items
        if _optional_str(item.get("id"))
    }
    raw_snapshots = data.get("accountKeySnapshots") or []
    if not isinstance(raw_snapshots, list):
        return [], set()

    records: list[_ImportRecord] = []
    covered_account_ids: set[str] = set()
    seen: set[tuple[str, str]] = set()

    for snapshot in raw_snapshots:
        if not isinstance(snapshot, dict):
            continue
        account_id = _optional_str(snapshot.get("accountId"))
        account = account_map.get(account_id or "")
        if account is not None and bool(account.get("disabled")):
            continue

        base_url = _optional_str(snapshot.get("baseUrl")) or _optional_str(
            account.get("site_url") if isinstance(account, dict) else None
        )
        origin = _normalize_origin(base_url or "")
        if not base_url or not origin:
            continue

        provider_name = (
            _optional_str(account.get("site_name") if isinstance(account, dict) else None)
            or _optional_str(snapshot.get("accountName"))
            or _default_provider_name(origin)
        )
        site_type = _optional_str(snapshot.get("siteType")) or _optional_str(
            account.get("site_type") if isinstance(account, dict) else None
        )
        auth_type = _optional_str(account.get("authType") if isinstance(account, dict) else None)
        username = _optional_str(
            (account.get("account_info") or {}).get("username") if isinstance(account, dict) else None
        )

        tokens = snapshot.get("tokens") or []
        if not isinstance(tokens, list):
            continue

        added_for_account = False
        for token in tokens:
            if not isinstance(token, dict):
                continue
            api_key = _optional_str(
                token.get("key") or token.get("apiKey") or token.get("api_key") or token.get("token")
            )
            if not api_key or _looks_like_masked_secret(api_key):
                continue
            signature = (_normalize_base_url(base_url), crypto_service.hash_api_key(api_key))
            if signature in seen:
                continue
            seen.add(signature)
            token_name = _optional_str(token.get("name"))
            token_id = _optional_str(token.get("id"))
            records.append(
                _ImportRecord(
                    provider_origin=origin,
                    endpoint_base_url=_normalize_pending_endpoint_base_url(base_url),
                    provider_name=provider_name,
                    source_id=token_id or token_name or account_id or str(len(records)),
                    display_name=token_name,
                    site_type=site_type,
                    auth_type=auth_type,
                    account_id=account_id,
                    username=username,
                    direct_api_key=api_key,
                )
            )
            added_for_account = True
        if added_for_account and account_id:
            covered_account_ids.add(account_id)

    return records, covered_account_ids


def _extract_v2_records(data: dict[str, Any], *, skip_account_ids: set[str] | None = None) -> list[_ImportRecord]:
    account_items = _extract_v2_account_items(data)
    skip_ids = skip_account_ids or set()

    records: list[_ImportRecord] = []
    for item in account_items:
        if bool(item.get("disabled")):
            continue
        source_id = _optional_str(item.get("id")) or str(len(records))
        if source_id in skip_ids:
            continue
        site_url = _optional_str(item.get("site_url"))
        origin = _normalize_origin(site_url or "")
        if not site_url or not origin:
            continue

        account_info = item.get("account_info") or {}
        cookie_auth = item.get("cookieAuth") or {}
        sub2api_auth = item.get("sub2apiAuth") or {}
        access_token = _optional_str(
            account_info.get("access_token") if isinstance(account_info, dict) else None
        ) or _optional_str(item.get("access_token") or item.get("token"))
        refresh_token = _optional_str(
            sub2api_auth.get("refreshToken") if isinstance(sub2api_auth, dict) else None
        ) or _optional_str(item.get("refresh_token"))
        session_cookie = _optional_str(
            cookie_auth.get("sessionCookie") if isinstance(cookie_auth, dict) else None
        ) or _optional_str(cookie_auth.get("cookie") if isinstance(cookie_auth, dict) else None)
        if not access_token and not refresh_token and not session_cookie:
            continue

        records.append(
            _ImportRecord(
                provider_origin=origin,
                endpoint_base_url=_normalize_pending_endpoint_base_url(site_url),
                provider_name=_optional_str(item.get("site_name")) or _default_provider_name(origin),
                source_id=source_id,
                site_type=_optional_str(item.get("site_type")),
                auth_type=_optional_str(item.get("authType")),
                account_id=_optional_str(account_info.get("id") if isinstance(account_info, dict) else None),
                username=_optional_str(
                    account_info.get("username") if isinstance(account_info, dict) else None
                ),
                access_token=access_token,
                refresh_token=refresh_token,
                session_cookie=session_cookie,
            )
        )
    return records


def _extract_v1_records(data: dict[str, Any]) -> list[_ImportRecord]:
    raw_sites = data.get("sites")
    raw_accounts = data.get("accounts")
    if not isinstance(raw_sites, list) or not isinstance(raw_accounts, list):
        return []

    site_map: dict[str, dict[str, str]] = {}
    for item in raw_sites:
        if not isinstance(item, dict):
            continue
        site_id = _optional_str(item.get("id"))
        site_url = _optional_str(item.get("url"))
        origin = _normalize_origin(site_url or "")
        if not site_id or not site_url or not origin:
            continue
        site_map[site_id] = {
            "origin": origin,
            "site_url": _normalize_base_url(site_url),
            "name": _optional_str(item.get("name")) or _default_provider_name(origin),
        }

    records: list[_ImportRecord] = []
    for item in raw_accounts:
        if not isinstance(item, dict):
            continue
        site_id = _optional_str(item.get("site_id"))
        token = _optional_str(item.get("token"))
        if not site_id or not token or site_id not in site_map:
            continue
        site = site_map[site_id]
        records.append(
            _ImportRecord(
                provider_origin=site["origin"],
                endpoint_base_url=_normalize_pending_endpoint_base_url(site["site_url"]),
                provider_name=site["name"],
                source_id=_optional_str(item.get("id")) or site_id,
                site_type="legacy-v1",
                auth_type="access_token",
                access_token=token,
            )
        )
    return records


def _extract_direct_records(node: Any, *, seen: set[tuple[str, str]]) -> list[_ImportRecord]:
    records: list[_ImportRecord] = []

    if isinstance(node, dict):
        base_url = _optional_str(node.get("baseUrl") or node.get("base_url"))
        api_key = _optional_str(node.get("apiKey") or node.get("api_key"))
        origin = _normalize_origin(base_url or "")
        if base_url and api_key and origin:
            signature = (_normalize_base_url(base_url), crypto_service.hash_api_key(api_key))
            if signature not in seen:
                seen.add(signature)
                records.append(
                    _ImportRecord(
                        provider_origin=origin,
                        endpoint_base_url=_normalize_base_url(base_url),
                        provider_name=_optional_str(node.get("site_name") or node.get("name"))
                        or _default_provider_name(origin),
                        source_id=_optional_str(node.get("id") or node.get("name"))
                        or str(len(seen)),
                        direct_api_key=api_key,
                    )
                )
        for value in node.values():
            records.extend(_extract_direct_records(value, seen=seen))
        return records

    if isinstance(node, list):
        for item in node:
            records.extend(_extract_direct_records(item, seen=seen))
    return records


def _collect_records(content: str | dict[str, Any] | list[Any]) -> tuple[list[_ImportRecord], str]:
    data, version = _parse_json_content(content)

    records: list[_ImportRecord] = []
    if isinstance(data, dict):
        if version.startswith("2"):
            snapshot_records, _snapshot_account_ids = _extract_v2_snapshot_direct_records(data)
            records.extend(_extract_v2_records(data))
            records.extend(snapshot_records)
        else:
            records.extend(_extract_v1_records(data))
        records.extend(_extract_direct_records(data, seen=set()))
    elif isinstance(data, list):
        records.extend(_extract_direct_records(data, seen=set()))

    return records, version


def _bucket_records(records: list[_ImportRecord]) -> list[_ProviderBucket]:
    buckets_by_origin: dict[str, _ProviderBucket] = {}
    for record in records:
        bucket = buckets_by_origin.get(record.provider_origin)
        if bucket is None:
            bucket = _ProviderBucket(
                provider_origin=record.provider_origin,
                provider_name=record.provider_name,
                endpoint_base_url=record.endpoint_base_url,
            )
            buckets_by_origin[record.provider_origin] = bucket
        if record.direct_api_key and "/v1" in record.endpoint_base_url:
            bucket.endpoint_base_url = record.endpoint_base_url
        if record.direct_api_key:
            bucket.direct_records.append(record)
        else:
            bucket.pending_records.append(record)
    return list(buckets_by_origin.values())


def _find_existing_provider(
    provider_origin: str,
    providers: list[Provider],
    endpoints: list[ProviderEndpoint],
) -> Provider | None:
    for provider in providers:
        if _normalize_origin(getattr(provider, "website", "") or "") == provider_origin:
            return provider
    for provider in providers:
        provider_endpoints = [ep for ep in endpoints if ep.provider_id == provider.id]
        if any(_normalize_origin(ep.base_url) == provider_origin for ep in provider_endpoints):
            return provider
    return None


def _find_existing_endpoint(provider_id: str, endpoints: list[ProviderEndpoint]) -> ProviderEndpoint | None:
    for endpoint in endpoints:
        if endpoint.provider_id == provider_id and endpoint.api_format == "openai:chat":
            return endpoint
    return None


def _find_existing_endpoint_by_format(
    provider_id: str,
    api_format: str,
    endpoints: list[ProviderEndpoint],
) -> ProviderEndpoint | None:
    for endpoint in endpoints:
        if endpoint.provider_id == provider_id and endpoint.api_format == api_format:
            return endpoint
    return None


def _collect_candidate_inputs(bucket: _ProviderBucket) -> tuple[list[str], list[str]]:
    site_types: list[str] = []
    labels: list[str] = []
    for record in [*bucket.direct_records, *bucket.pending_records]:
        site_type = _optional_str(record.site_type)
        if site_type:
            site_types.append(site_type)
        display_name = _optional_str(record.display_name)
        if display_name:
            labels.append(display_name)
        username = _optional_str(record.username)
        if username:
            labels.append(username)
    return site_types, labels


def _resolve_bucket_endpoint_candidates(bucket: _ProviderBucket) -> list[EndpointCandidate]:
    site_types, labels = _collect_candidate_inputs(bucket)
    return resolve_endpoint_candidates(
        provider_name=bucket.provider_name,
        endpoint_base_url=bucket.endpoint_base_url,
        site_types=site_types,
        labels=labels,
    )


def _pick_primary_candidate(candidates: list[EndpointCandidate]) -> EndpointCandidate:
    for candidate in candidates:
        if candidate.api_format == "openai:chat":
            return candidate
    return candidates[0]


def _decrypt_existing_key_hashes(provider_id: str, keys: list[ProviderAPIKey]) -> set[str]:
    hashes: set[str] = set()
    for key in keys:
        if key.provider_id != provider_id or key.auth_type != "api_key":
            continue
        try:
            plaintext = crypto_service.decrypt(key.api_key, silent=True)
        except Exception:
            continue
        if plaintext and plaintext != "__placeholder__":
            hashes.add(crypto_service.hash_api_key(plaintext))
    return hashes


def _build_unique_provider_name(candidate: str, providers: list[Provider]) -> str:
    existing_names = {str(provider.name) for provider in providers}
    base = candidate.strip()[:100] or "Imported Provider"
    if base not in existing_names:
        return base
    index = 2
    while True:
        suffix = f" ({index})"
        name = f"{base[: max(1, 100 - len(suffix))]}{suffix}"
        if name not in existing_names:
            return name
        index += 1


def _build_pending_task_type(record: _ImportRecord) -> str:
    auth_type = str(record.auth_type or "").strip().lower()
    if record.access_token and auth_type not in {"cookie", "session_cookie"}:
        return PENDING_REISSUE_TASK_TYPE
    return PENDING_IMPORT_TASK_TYPE


def _build_task_type_for_record(bucket: _ProviderBucket, record: _ImportRecord) -> str:
    task_type = _build_pending_task_type(record)
    if any(direct_record.account_id == record.source_id for direct_record in bucket.direct_records):
        return IMPORTED_AUTH_PREFILL_TASK_TYPE
    if task_type == PENDING_IMPORT_TASK_TYPE and _can_generate_auth_setup_task(record):
        return IMPORTED_AUTH_PREFILL_TASK_TYPE
    return task_type


def _is_actionable_task_type(task_type: str) -> bool:
    return task_type in {PENDING_IMPORT_TASK_TYPE, PENDING_REISSUE_TASK_TYPE}


def _build_pending_task_payload(record: _ImportRecord) -> str:
    payload = {
        "access_token": record.access_token,
        "refresh_token": record.refresh_token,
        "session_cookie": record.session_cookie,
    }
    return crypto_service.encrypt(json.dumps(payload, sort_keys=True))


def _build_pending_task_metadata(record: _ImportRecord) -> dict[str, Any]:
    return {
        "provider_name": record.provider_name,
        "endpoint_base_url": record.endpoint_base_url,
        "site_type": record.site_type,
        "auth_type": record.auth_type,
        "account_id": record.account_id,
        "username": record.username,
        "has_access_token": bool(record.access_token),
        "has_refresh_token": bool(record.refresh_token),
        "has_session_cookie": bool(record.session_cookie),
    }


def _can_generate_auth_setup_task(record: _ImportRecord) -> bool:
    site_type = str(record.site_type or "").strip().lower()
    if site_type in {"new-api", "new_api"}:
        return bool(record.access_token or record.session_cookie)
    if site_type == "sub2api":
        return bool(record.refresh_token)
    if site_type in {"anyrouter", "nekocode"}:
        return bool(record.session_cookie)
    if site_type == "cubence":
        return bool(record.session_cookie)
    if site_type == "yescode":
        return bool(record.session_cookie)
    return False


def _mark_task_as_prefill_only(task: ProviderImportTask, *, endpoint_id: str, now: datetime) -> None:
    metadata = getattr(task, "source_metadata", None)
    normalized_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    normalized_metadata["action_required"] = ACTION_REQUIRED_PREFILL_ONLY
    task.task_type = IMPORTED_AUTH_PREFILL_TASK_TYPE
    task.endpoint_id = endpoint_id
    task.status = TASK_STATUS_PENDING
    task.last_error = None
    task.completed_at = None
    task.source_metadata = normalized_metadata
    task.updated_at = now


def _mark_legacy_task_as_prefill_only_shadow(task: ProviderImportTask, *, now: datetime) -> None:
    metadata = getattr(task, "source_metadata", None)
    normalized_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    normalized_metadata["action_required"] = ACTION_REQUIRED_PREFILL_ONLY
    task.status = "completed"
    task.last_error = None
    task.completed_at = now
    task.source_metadata = normalized_metadata
    task.updated_at = now


def _find_existing_import_task(
    provider_id: str,
    source_id: str,
    task_type: str,
    tasks: list[ProviderImportTask],
) -> ProviderImportTask | None:
    for task in tasks:
        if (
            task.provider_id == provider_id
            and task.source_id == source_id
            and task.task_type == task_type
        ):
            return task
    return None


def _find_existing_import_task_by_source(
    provider_id: str,
    source_id: str,
    tasks: list[ProviderImportTask],
    *,
    task_types: set[str] | None = None,
) -> ProviderImportTask | None:
    for task in tasks:
        if task.provider_id != provider_id or task.source_id != source_id:
            continue
        if task_types is not None and task.task_type not in task_types:
            continue
        return task
    return None


def _upsert_auth_setup_task(
    *,
    provider: Provider,
    endpoint: ProviderEndpoint,
    record: _ImportRecord,
    db: Session,
    tasks: list[ProviderImportTask],
    now: datetime,
) -> ProviderImportTask | None:
    if not _can_generate_auth_setup_task(record):
        return None

    existing_task = _find_existing_import_task(
        provider.id,
        record.source_id,
        IMPORTED_AUTH_PREFILL_TASK_TYPE,
        tasks,
    )
    encrypted_payload = _build_pending_task_payload(record)
    source_metadata = _build_pending_task_metadata(record)
    source_metadata["action_required"] = ACTION_REQUIRED_PREFILL_ONLY

    if existing_task is not None:
        existing_task.endpoint_id = endpoint.id
        existing_task.source_name = record.provider_name[:100] or provider.name
        existing_task.source_origin = record.provider_origin
        existing_task.source_kind = TASK_SOURCE_KIND
        existing_task.credential_payload = encrypted_payload
        existing_task.source_metadata = source_metadata
        existing_task.status = TASK_STATUS_PENDING
        existing_task.last_error = None
        existing_task.completed_at = None
        existing_task.updated_at = now
        return existing_task

    new_task = ProviderImportTask(
        id=str(uuid.uuid4()),
        provider_id=provider.id,
        endpoint_id=endpoint.id,
        task_type=IMPORTED_AUTH_PREFILL_TASK_TYPE,
        status=TASK_STATUS_PENDING,
        source_kind=TASK_SOURCE_KIND,
        source_id=record.source_id[:120],
        source_name=record.provider_name[:100] or provider.name,
        source_origin=record.provider_origin,
        credential_payload=encrypted_payload,
        source_metadata=source_metadata,
        retry_count=0,
        last_error=None,
        last_attempt_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(new_task)
    tasks.append(new_task)
    return new_task


def _build_preview_response(
    *,
    buckets: list[_ProviderBucket],
    providers: list[Provider],
    endpoints: list[ProviderEndpoint],
    keys: list[ProviderAPIKey],
    tasks: list[ProviderImportTask],
    version: str,
    dry_run: bool,
) -> AllInHubImportResponse:
    warnings: list[str] = []
    provider_summaries: list[AllInHubImportProviderSummary] = []
    manual_items: list[AllInHubImportManualItem] = []
    stats = AllInHubImportStats()
    stats.providers_total = len(buckets)

    for bucket in buckets:
        existing_provider = _find_existing_provider(bucket.provider_origin, providers, endpoints)
        candidate_endpoints = _resolve_bucket_endpoint_candidates(bucket)
        existing_endpoint = None
        if existing_provider:
            for candidate in candidate_endpoints:
                existing_endpoint = _find_existing_endpoint_by_format(
                    existing_provider.id, candidate.api_format, endpoints
                )
                if existing_endpoint is not None:
                    break
        if existing_provider is None:
            stats.providers_to_create += 1
        else:
            stats.providers_reused += 1

        for candidate in candidate_endpoints:
            existing_candidate_endpoint = (
                _find_existing_endpoint_by_format(existing_provider.id, candidate.api_format, endpoints)
                if existing_provider
                else None
            )
            if existing_candidate_endpoint is None:
                stats.endpoints_to_create += 1
            else:
                stats.endpoints_reused += 1

        existing_hashes = (
            _decrypt_existing_key_hashes(existing_provider.id, keys) if existing_provider else set()
        )
        batch_hashes: set[str] = set()
        ready_direct = 0
        for record in bucket.direct_records:
            if not record.direct_api_key:
                continue
            key_hash = crypto_service.hash_api_key(record.direct_api_key)
            if key_hash in existing_hashes or key_hash in batch_hashes:
                warnings.append(
                    f"{bucket.provider_origin} 的直导 Key 已存在，已在预览中跳过: {record.source_id}"
                )
                continue
            batch_hashes.add(key_hash)
            ready_direct += 1

        stats.direct_keys_ready += ready_direct
        batch_pending_signatures: set[tuple[str, str]] = set()
        for record in bucket.pending_records:
            task_type = _build_task_type_for_record(bucket, record)
            if existing_provider and _find_existing_import_task(
                existing_provider.id, record.source_id, task_type, tasks
            ):
                if _is_actionable_task_type(task_type):
                    stats.pending_tasks_reused += 1
                    manual_items.append(
                        AllInHubImportManualItem(
                            item_type="pending_task",
                            status="reused",
                            provider_name=bucket.provider_name,
                            provider_website=bucket.provider_origin,
                            endpoint_base_url=record.endpoint_base_url,
                            source_id=record.source_id,
                            task_type=task_type,
                            auth_type=record.auth_type,
                            site_type=record.site_type,
                            reason="已存在待处理任务，等待人工补抓或补录",
                        )
                    )
                continue
            signature = (task_type, record.source_id)
            if signature in batch_pending_signatures:
                continue
            batch_pending_signatures.add(signature)
            if _is_actionable_task_type(task_type):
                stats.pending_sources += 1
                stats.pending_tasks_to_create += 1
                manual_items.append(
                    AllInHubImportManualItem(
                        item_type="pending_task",
                        status="pending",
                        provider_name=bucket.provider_name,
                        provider_website=bucket.provider_origin,
                        endpoint_base_url=record.endpoint_base_url,
                        source_id=record.source_id,
                        task_type=task_type,
                        auth_type=record.auth_type,
                        site_type=record.site_type,
                        reason="缺少明文 Key，等待人工补抓或补录",
                    )
                )
        provider_summaries.append(
            AllInHubImportProviderSummary(
                provider_name=bucket.provider_name,
                provider_website=bucket.provider_origin,
                endpoint_base_url=bucket.endpoint_base_url,
                direct_key_count=ready_direct,
                pending_source_count=sum(
                    1
                    for record in bucket.pending_records
                    if _is_actionable_task_type(_build_task_type_for_record(bucket, record))
                ),
                existing_provider=existing_provider is not None,
                existing_endpoint=existing_endpoint is not None,
            )
        )

    return AllInHubImportResponse(
        dry_run=dry_run,
        version=version,
        stats=stats,
        warnings=warnings,
        providers=provider_summaries,
        manual_items=manual_items,
    )


async def _verify_imported_key_models(
    *,
    db: Session,
    key: ProviderAPIKey,
) -> str:
    from src.services.model.fetch_scheduler import get_model_fetch_scheduler

    key.auto_fetch_models = True
    db.commit()
    scheduler = get_model_fetch_scheduler()
    try:
        return await scheduler._fetch_models_for_key_by_id(str(key.id))
    finally:
        key.auto_fetch_models = False
        db.commit()


async def _run_imported_key_model_fetch(key_id: str) -> None:
    async with _IMPORTED_KEY_MODEL_FETCH_SEMAPHORE:
        db = create_session()
        try:
            key = db.query(ProviderAPIKey).filter(ProviderAPIKey.id == key_id).first()
            if key is None:
                return
            key.auto_fetch_models = True
            db.commit()
            status = await _verify_imported_key_models(db=db, key=key)
            if status != "success":
                key.is_active = False
                db.commit()
                logger.warning("all-in-hub 后台模型抓取失败 key_id={} status={}", key_id, status)
        except Exception as exc:
            try:
                key = db.query(ProviderAPIKey).filter(ProviderAPIKey.id == key_id).first()
                if key is not None:
                    key.is_active = False
                    db.commit()
            except Exception:
                pass
            logger.warning("all-in-hub 后台模型抓取异常 key_id={}: {}", key_id, exc)
        finally:
            try:
                key = db.query(ProviderAPIKey).filter(ProviderAPIKey.id == key_id).first()
                if key is not None:
                    key.auto_fetch_models = False
                    db.commit()
            except Exception:
                pass
            db.close()


async def _run_imported_key_model_fetch_batch(key_ids: list[str]) -> None:
    for key_id in key_ids:
        await _run_imported_key_model_fetch(key_id)


def _schedule_imported_key_model_fetches(key_ids: list[str]) -> None:
    if not key_ids:
        return
    task = safe_create_task(_run_imported_key_model_fetch_batch(list(key_ids)))
    if task is None:
        logger.warning(
            "all-in-hub 无运行中的事件循环，未能调度后台模型抓取 batch size={}",
            len(key_ids),
        )


def preview_all_in_hub_import(
    content: str | dict[str, Any] | list[Any],
    *,
    db: Session,
) -> AllInHubImportResponse:
    records, version = _collect_records(content)
    buckets = _bucket_records(records)
    providers = list(db.query(Provider).all())
    endpoints = list(db.query(ProviderEndpoint).all())
    keys = list(db.query(ProviderAPIKey).all())
    tasks = list(db.query(ProviderImportTask).all())
    return _build_preview_response(
        buckets=buckets,
        providers=providers,
        endpoints=endpoints,
        keys=keys,
        tasks=tasks,
        version=version,
        dry_run=True,
    )


async def execute_all_in_hub_import(
    content: str | dict[str, Any] | list[Any],
    *,
    db: Session,
    schedule_model_fetch: bool = True,
    created_key_ids_out: list[str] | None = None,
) -> AllInHubImportResponse:
    records, version = _collect_records(content)
    buckets = _bucket_records(records)
    providers = list(db.query(Provider).all())
    endpoints = list(db.query(ProviderEndpoint).all())
    keys = list(db.query(ProviderAPIKey).all())
    tasks = list(db.query(ProviderImportTask).all())
    preview = _build_preview_response(
        buckets=buckets,
        providers=providers,
        endpoints=endpoints,
        keys=keys,
        tasks=tasks,
        version=version,
        dry_run=False,
    )
    preview.stats.pending_tasks_to_create = 0
    preview.stats.pending_tasks_created = 0
    preview.stats.pending_tasks_reused = 0

    created_keys: list[tuple[Provider, ProviderEndpoint, ProviderAPIKey, _ImportRecord]] = []
    now = datetime.now(timezone.utc)

    try:
        for bucket in buckets:
            provider = _find_existing_provider(bucket.provider_origin, providers, endpoints)
            if provider is None:
                provider = Provider(
                    id=str(uuid.uuid4()),
                    name=_build_unique_provider_name(bucket.provider_name, providers),
                    description="Imported from all-in-hub",
                    website=bucket.provider_origin,
                provider_type="custom",
                billing_type=ProviderBillingType.PAY_AS_YOU_GO,
                provider_priority=100,
                keep_priority_on_conversion=False,
                enable_format_conversion=True,
                is_active=True,
                max_retries=2,
                created_at=now,
                updated_at=now,
            )
                db.add(provider)
                providers.append(provider)
                preview.stats.providers_created += 1

            candidate_endpoints = _resolve_bucket_endpoint_candidates(bucket)
            created_or_existing_endpoints: dict[str, ProviderEndpoint] = {}
            for candidate in candidate_endpoints:
                endpoint = _find_existing_endpoint_by_format(provider.id, candidate.api_format, endpoints)
                if endpoint is None:
                    endpoint = ProviderEndpoint(
                        id=str(uuid.uuid4()),
                        provider_id=provider.id,
                        api_format=candidate.api_format,
                        api_family=candidate.api_family,
                        endpoint_kind=candidate.endpoint_kind,
                        base_url=bucket.endpoint_base_url,
                        header_rules=None,
                        body_rules=(
                            get_default_body_rules_for_endpoint(
                                candidate.api_format,
                                provider_type=provider.provider_type,
                            )
                            or None
                        ),
                        max_retries=getattr(provider, "max_retries", 2) or 2,
                        is_active=True,
                        custom_path=None,
                        config={"import_candidate_reason": candidate.reason},
                        format_acceptance_config=None,
                        proxy=None,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(endpoint)
                    endpoints.append(endpoint)
                    preview.stats.endpoints_created += 1
                created_or_existing_endpoints[candidate.api_format] = endpoint

            primary_candidate = _pick_primary_candidate(candidate_endpoints)
            endpoint = created_or_existing_endpoints[primary_candidate.api_format]
            candidate_api_formats = [candidate.api_format for candidate in candidate_endpoints]

            existing_hashes = _decrypt_existing_key_hashes(provider.id, keys)
            batch_hashes: set[str] = set()
            for record in bucket.direct_records:
                if not record.direct_api_key:
                    continue
                key_hash = crypto_service.hash_api_key(record.direct_api_key)
                if key_hash in existing_hashes or key_hash in batch_hashes:
                    preview.stats.keys_skipped += 1
                    continue
                batch_hashes.add(key_hash)
                encrypted_key = crypto_service.encrypt(record.direct_api_key)
                key_id = str(uuid.uuid4())
                new_key = ProviderAPIKey(
                    id=key_id,
                    provider_id=provider.id,
                    api_formats=candidate_api_formats,
                    auth_type="api_key",
                    api_key=encrypted_key,
                    auth_config=None,
                    name=(record.display_name or record.source_id or f"imported-{key_id[:8]}")[:100],
                    note="Imported from all-in-hub",
                    rate_multipliers=None,
                    internal_priority=50,
                    rpm_limit=None,
                    allowed_models=None,
                    capabilities=None,
                    cache_ttl_minutes=5,
                    max_probe_interval_minutes=32,
                    auto_fetch_models=False,
                    locked_models=None,
                    model_include_patterns=None,
                    model_exclude_patterns=None,
                    fingerprint=generate_fingerprint(seed=key_id),
                    request_count=0,
                    success_count=0,
                    error_count=0,
                    total_response_time_ms=0,
                    health_by_format={},
                    circuit_breaker_by_format={},
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_key)
                keys.append(new_key)
                existing_hashes.add(key_hash)
                preview.stats.keys_created += 1
                created_keys.append((provider, endpoint, new_key, record))
                if created_key_ids_out is not None:
                    created_key_ids_out.append(str(new_key.id))

            for record in bucket.pending_records:
                task_type = _build_task_type_for_record(bucket, record)
                existing_task = _find_existing_import_task(
                    provider.id, record.source_id, task_type, tasks
                )
                if existing_task is None and task_type == IMPORTED_AUTH_PREFILL_TASK_TYPE:
                    existing_task = _find_existing_import_task_by_source(
                        provider.id,
                        record.source_id,
                        tasks,
                        task_types={PENDING_IMPORT_TASK_TYPE, PENDING_REISSUE_TASK_TYPE},
                    )
                encrypted_payload = _build_pending_task_payload(record)
                source_metadata = _build_pending_task_metadata(record)
                if existing_task is not None:
                    if task_type == IMPORTED_AUTH_PREFILL_TASK_TYPE:
                        _mark_task_as_prefill_only(existing_task, endpoint_id=endpoint.id, now=now)
                        stale_actionable_task = _find_existing_import_task_by_source(
                            provider.id,
                            record.source_id,
                            tasks,
                            task_types={PENDING_IMPORT_TASK_TYPE, PENDING_REISSUE_TASK_TYPE},
                        )
                        if stale_actionable_task is not None and stale_actionable_task.id != existing_task.id:
                            _mark_legacy_task_as_prefill_only_shadow(stale_actionable_task, now=now)
                    existing_task.endpoint_id = endpoint.id
                    existing_task.source_name = record.provider_name[:100] or provider.name
                    existing_task.source_origin = record.provider_origin
                    existing_task.source_kind = TASK_SOURCE_KIND
                    existing_task.credential_payload = encrypted_payload
                    existing_task.source_metadata = source_metadata
                    existing_task.updated_at = now
                    if _is_actionable_task_type(task_type) and existing_task.status in {
                        TASK_STATUS_FAILED,
                        TASK_STATUS_CANCELLED,
                    }:
                        existing_task.status = TASK_STATUS_PENDING
                        existing_task.last_error = None
                        existing_task.completed_at = None
                    if _is_actionable_task_type(task_type):
                        preview.stats.pending_tasks_reused += 1
                        if _can_generate_auth_setup_task(record):
                            _upsert_auth_setup_task(
                                provider=provider,
                                endpoint=endpoint,
                                record=record,
                                db=db,
                                tasks=tasks,
                                now=now,
                            )
                    continue

                new_task = ProviderImportTask(
                    id=str(uuid.uuid4()),
                    provider_id=provider.id,
                    endpoint_id=endpoint.id,
                    task_type=task_type,
                    status=TASK_STATUS_PENDING,
                    source_kind=TASK_SOURCE_KIND,
                    source_id=record.source_id[:120],
                    source_name=record.provider_name[:100] or provider.name,
                    source_origin=record.provider_origin,
                    credential_payload=encrypted_payload,
                    source_metadata=source_metadata,
                    retry_count=0,
                    last_error=None,
                    last_attempt_at=None,
                    completed_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_task)
                tasks.append(new_task)
                if _is_actionable_task_type(task_type):
                    preview.stats.pending_tasks_created += 1
                    if _can_generate_auth_setup_task(record):
                        _upsert_auth_setup_task(
                            provider=provider,
                            endpoint=endpoint,
                            record=record,
                            db=db,
                            tasks=tasks,
                            now=now,
                        )

        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise

    for provider, endpoint, key, record in created_keys:
        try:
            await run_create_key_side_effects(db=db, provider_id=provider.id, key=key)
        except Exception as exc:
            logger.warning("all-in-hub 导入后执行 Key 副作用失败: {}", exc)
        _ = endpoint, record

    if schedule_model_fetch:
        _schedule_imported_key_model_fetches([str(key.id) for _, _, key, _ in created_keys])

    try:
        await invalidate_models_list_cache()
    except Exception as exc:
        logger.warning("all-in-hub 导入后清理 models 缓存失败: {}", exc)

    return preview
