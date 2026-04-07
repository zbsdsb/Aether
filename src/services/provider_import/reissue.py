from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import ceil
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx
from sqlalchemy.orm import Session

from src.core.crypto import crypto_service
from src.core.logger import logger
from src.models.database import ProviderAPIKey, ProviderImportTask
from src.services.provider.fingerprint import generate_fingerprint
from src.services.provider_keys.key_side_effects import run_create_key_side_effects

TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_WAITING_PLAINTEXT = "waiting_plaintext"
PENDING_REISSUE_TASK_TYPE = "pending_reissue"
SUPPORTED_SITE_TYPE_NEW_API = "new-api"
SUPPORTED_SITE_TYPE_SUB2API = "sub2api"
SUPPORTED_SITE_TYPE_UNKNOWN = "unknown"
DEFAULT_PAGE_SIZE = 100
ACTION_REQUIRED_SUBMIT_PLAINTEXT = "submit_plaintext"
PLAINTEXT_CAPTURE_PENDING = "pending"
PLAINTEXT_CAPTURE_CONSUMED = "consumed"


@dataclass(slots=True)
class AllInHubTaskExecutionSummary:
    total_selected: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    keys_created: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)


class MaskedTokenRequiresPlaintext(RuntimeError):
    def __init__(self, masked_key_preview: str):
        super().__init__("new-api token list returned masked key")
        self.masked_key_preview = masked_key_preview


class PlaintextSubmissionRetryableError(RuntimeError):
    """明文回填失败但任务仍可继续重试。"""


RESULT_STAGE_COMPLETED = "completed"
RESULT_STAGE_SKIPPED = "skipped"
RESULT_STAGE_PROBE = "probe"
RESULT_STAGE_CREATE_KEY = "create_key"
RESULT_STAGE_VERIFY_MODELS = "verify_models"
RESULT_STAGE_UNSUPPORTED = "unsupported"


def _task_note(task_id: str) -> str:
    return f"Reissued from all-in-hub task {task_id}"


def _sanitize_token_name(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-").lower()
    return cleaned[:40] or "import"


def _build_upstream_token_name(task: ProviderImportTask) -> str:
    return f"aether-{_sanitize_token_name(str(task.source_id or task.id))}"


def _task_metadata(task: ProviderImportTask) -> dict[str, Any]:
    data = getattr(task, "source_metadata", None)
    return dict(data) if isinstance(data, dict) else {}


def _normalize_waiting_plaintext_metadata(task: ProviderImportTask, metadata: dict[str, Any]) -> dict[str, Any]:
    if str(getattr(task, "status", "") or "") != TASK_STATUS_WAITING_PLAINTEXT:
        return metadata

    normalized = dict(metadata)
    if not str(normalized.get("plaintext_capture_status") or "").strip():
        normalized["plaintext_capture_status"] = PLAINTEXT_CAPTURE_PENDING
    if not str(normalized.get("action_required") or "").strip():
        normalized["action_required"] = ACTION_REQUIRED_SUBMIT_PLAINTEXT
    return normalized


def _task_payload(task: ProviderImportTask) -> dict[str, Any]:
    decrypted = crypto_service.decrypt(task.credential_payload)
    parsed = json.loads(decrypted)
    return parsed if isinstance(parsed, dict) else {}


def _find_task_by_id(*, db: Session, task_id: str) -> ProviderImportTask | None:
    for task in list(db.query(ProviderImportTask).all()):
        if str(getattr(task, "id", "") or "") == task_id:
            return task
    return None


def detect_import_task_strategy(task: ProviderImportTask) -> str | None:
    meta = _task_metadata(task)
    if (
        str(getattr(task, "task_type", "") or "") == PENDING_REISSUE_TASK_TYPE
        and str(meta.get("site_type") or "").strip().lower() == SUPPORTED_SITE_TYPE_NEW_API
    ):
        return "new_api_access_token"
    if (
        str(getattr(task, "task_type", "") or "") == PENDING_REISSUE_TASK_TYPE
        and str(meta.get("site_type") or "").strip().lower() == SUPPORTED_SITE_TYPE_SUB2API
    ):
        return "sub2api_access_token"
    if (
        str(getattr(task, "task_type", "") or "") == PENDING_REISSUE_TASK_TYPE
        and str(meta.get("site_type") or "").strip().lower() == SUPPORTED_SITE_TYPE_UNKNOWN
    ):
        return "probe_new_api_access_token"
    return None


async def _probe_new_api_compatibility(*, task: ProviderImportTask) -> bool:
    payload = _task_payload(task)
    metadata = _task_metadata(task)
    access_token = str(payload.get("access_token") or "").strip()
    account_id = str(metadata.get("account_id") or "").strip()
    base_url = str(metadata.get("endpoint_base_url") or task.source_origin or "").strip()
    if not access_token or not account_id or not base_url:
        return False

    try:
        payload = await _new_api_request(
            method="GET",
            base_url=base_url,
            access_token=access_token,
            account_id=account_id,
            path=f"api/token/?{urlencode({'p': 1, 'size': 1})}",
        )
    except Exception:
        return False

    data = payload.get("data")
    if isinstance(data, dict):
        return (
            "items" in data
            or "total" in data
            or "data" in data
            or "total_count" in data
        )
    if isinstance(data, list):
        return True
    return False


def _find_existing_key_for_task(
    task: ProviderImportTask,
    keys: list[ProviderAPIKey],
) -> ProviderAPIKey | None:
    task_key_id = str(_task_metadata(task).get("result_key_id") or "").strip()
    for key in keys:
        if task_key_id and str(getattr(key, "id", "") or "") == task_key_id:
            return key

    expected_note = _task_note(str(task.id))
    for key in keys:
        if key.provider_id == task.provider_id and str(getattr(key, "note", "") or "") == expected_note:
            return key
    return None


def _find_existing_key_by_hash(
    *,
    provider_id: str,
    plaintext_key: str,
    keys: list[ProviderAPIKey],
) -> ProviderAPIKey | None:
    target_hash = crypto_service.hash_api_key(plaintext_key)
    for key in keys:
        if key.provider_id != provider_id or str(getattr(key, "auth_type", "") or "") != "api_key":
            continue
        try:
            existing = crypto_service.decrypt(str(key.api_key), silent=True)
        except Exception:
            continue
        if existing and existing != "__placeholder__" and crypto_service.hash_api_key(existing) == target_hash:
            return key
    return None


async def _new_api_request(
    *,
    method: str,
    base_url: str,
    access_token: str,
    account_id: str,
    path: str,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "New-Api-User": account_id,
        "Accept": "application/json, text/plain, */*",
    }
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=False) as client:
        response = await client.request(
            method=method,
            url=urljoin(f"{base_url.rstrip('/')}/", path),
            headers=headers,
            json=json_body,
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected new-api payload from {path}")
    if not payload.get("success", False):
        raise RuntimeError(str(payload.get("message") or f"new-api request failed: {path}"))
    return payload


async def _find_new_api_token(
    *,
    base_url: str,
    access_token: str,
    account_id: str,
    token_name: str,
) -> dict[str, Any] | None:
    def _extract_page(payload: dict[str, Any]) -> tuple[list[Any], int]:
        data = payload.get("data") or {}
        if isinstance(data, dict):
            if isinstance(data.get("items"), list):
                return data.get("items") or [], int(data.get("total") or 0)
            if isinstance(data.get("data"), list):
                return data.get("data") or [], int(data.get("total_count") or 0)
        if isinstance(data, list):
            return data, len(data)
        return [], 0

    first_page = await _new_api_request(
        method="GET",
        base_url=base_url,
        access_token=access_token,
        account_id=account_id,
        path=f"api/token/?{urlencode({'p': 1, 'size': DEFAULT_PAGE_SIZE})}",
    )
    first_items, total = _extract_page(first_page)
    pages = max(1, min(ceil(total / DEFAULT_PAGE_SIZE) if total else 1, 10))

    def _scan(items: list[Any]) -> dict[str, Any] | None:
        for item in items:
            if isinstance(item, dict) and str(item.get("name") or "") == token_name:
                return item
        return None

    found = _scan(first_items if isinstance(first_items, list) else [])
    if found is not None:
        return found

    for page in range(2, pages + 1):
        payload = await _new_api_request(
            method="GET",
            base_url=base_url,
            access_token=access_token,
            account_id=account_id,
            path=f"api/token/?{urlencode({'p': page, 'size': DEFAULT_PAGE_SIZE})}",
        )
        items, _ = _extract_page(payload)
        found = _scan(items if isinstance(items, list) else [])
        if found is not None:
            return found
    return None


async def _create_new_api_token(
    *,
    base_url: str,
    access_token: str,
    account_id: str,
    token_name: str,
) -> dict[str, Any]:
    payload = {
        "name": token_name,
        "expired_time": -1,
        "remain_quota": 500000,
        "unlimited_quota": True,
        "model_limits_enabled": False,
        "model_limits": "",
        "allow_ips": "",
        "group": "default",
    }
    return await _new_api_request(
        method="POST",
        base_url=base_url,
        access_token=access_token,
        account_id=account_id,
        path="api/token/",
        json_body=payload,
    )


def _looks_like_masked_key(value: str) -> bool:
    trimmed = value.strip()
    return "*" in trimmed


def _extract_new_api_plaintext_from_create_response(payload: dict[str, Any]) -> tuple[str, str] | None:
    data = payload.get("data")
    candidates: list[dict[str, Any]] = []
    if isinstance(data, dict):
        candidates.append(data)
        nested = data.get("data")
        if isinstance(nested, dict):
            candidates.append(nested)
    for candidate in candidates:
        api_key = str(candidate.get("key") or candidate.get("token") or "").strip()
        token_id = str(candidate.get("id") or "").strip()
        if api_key and not _looks_like_masked_key(api_key):
            return api_key, token_id
    return None


async def _reissue_new_api_key(*, task: ProviderImportTask) -> dict[str, str]:
    payload = _task_payload(task)
    metadata = _task_metadata(task)
    access_token = str(payload.get("access_token") or "").strip()
    account_id = str(metadata.get("account_id") or "").strip()
    base_url = str(metadata.get("endpoint_base_url") or task.source_origin or "").strip()
    if not access_token:
        raise RuntimeError("missing access_token")
    if not account_id:
        raise RuntimeError("missing account_id")
    if not base_url:
        raise RuntimeError("missing base_url")

    token_name = _build_upstream_token_name(task)
    token = await _find_new_api_token(
        base_url=base_url,
        access_token=access_token,
        account_id=account_id,
        token_name=token_name,
    )
    if token is None:
        created_payload = await _create_new_api_token(
            base_url=base_url,
            access_token=access_token,
            account_id=account_id,
            token_name=token_name,
        )
        created_plaintext = _extract_new_api_plaintext_from_create_response(created_payload)
        if created_plaintext is not None:
            api_key, token_id = created_plaintext
            return {
                "token_name": token_name,
                "token_id": token_id,
                "api_key": api_key,
            }
        token = await _find_new_api_token(
            base_url=base_url,
            access_token=access_token,
            account_id=account_id,
            token_name=token_name,
        )

    if not isinstance(token, dict):
        raise RuntimeError("new-api token creation succeeded but token lookup failed")

    api_key = str(token.get("key") or "").strip()
    token_id = str(token.get("id") or "").strip()
    if not api_key:
        raise RuntimeError("new-api token lookup returned empty key")
    if _looks_like_masked_key(api_key):
        raise MaskedTokenRequiresPlaintext(api_key)
    return {
        "token_name": token_name,
        "token_id": token_id,
        "api_key": api_key,
    }


async def _probe_sub2api_access_token(*, task: ProviderImportTask) -> None:
    payload = _task_payload(task)
    metadata = _task_metadata(task)
    access_token = str(payload.get("access_token") or "").strip()
    base_url = str(metadata.get("endpoint_base_url") or task.source_origin or "").strip()
    if not access_token:
        raise RuntimeError("missing access_token")
    if not base_url:
        raise RuntimeError("missing base_url")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json, text/plain, */*",
    }
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=False) as client:
        response = await client.get(urljoin(f"{base_url.rstrip('/')}/", "api/v1/auth/me"), headers=headers)

    content_type = str(response.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        raise RuntimeError(f"sub2api auth probe unexpected response: {response.status_code}")

    payload = response.json()
    if response.status_code == 401 and isinstance(payload, dict):
        code = str(payload.get("code") or "").strip().upper()
        message = str(payload.get("message") or "").strip()
        if code == "TOKEN_EXPIRED":
            raise RuntimeError("sub2api access token expired")
        if code == "UNAUTHORIZED":
            raise RuntimeError("sub2api access token unauthorized")
        raise RuntimeError(message or f"sub2api auth probe failed: {code or response.status_code}")

    if response.status_code != 200:
        raise RuntimeError(f"sub2api auth probe failed: {response.status_code}")


async def _sub2api_request(
    *,
    method: str,
    base_url: str,
    access_token: str,
    path: str,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json, text/plain, */*",
    }
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=False) as client:
        response = await client.request(
            method=method,
            url=urljoin(f"{base_url.rstrip('/')}/", path),
            headers=headers,
            json=json_body,
        )

    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected sub2api payload from {path}")
    if response.status_code >= 400:
        code = str(payload.get("code") or "").strip().upper()
        message = str(payload.get("message") or "").strip()
        if response.status_code == 401 and code == "TOKEN_EXPIRED":
            raise RuntimeError("sub2api access token expired")
        if response.status_code == 401 and code == "UNAUTHORIZED":
            raise RuntimeError("sub2api access token unauthorized")
        raise RuntimeError(message or f"sub2api request failed: {path}")
    code = payload.get("code")
    if code not in (None, 0, 200, "0", "200"):
        raise RuntimeError(str(payload.get("message") or f"sub2api request failed: {path}"))
    return payload


def _extract_sub2api_token_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    source = data if isinstance(data, (dict, list)) else payload
    if isinstance(source, list):
        return [item for item in source if isinstance(item, dict)]
    if isinstance(source, dict):
        for key in ("items", "list", "data"):
            value = source.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


async def _find_sub2api_token(
    *,
    base_url: str,
    access_token: str,
    token_name: str,
) -> dict[str, Any] | None:
    for path in (
        "api/v1/keys?page=1&page_size=100",
        "api/v1/api-keys?page=1&page_size=100",
        "api/v1/keys",
        "api/v1/api-keys",
    ):
        try:
            payload = await _sub2api_request(
                method="GET",
                base_url=base_url,
                access_token=access_token,
                path=path,
            )
        except Exception:
            continue
        for item in _extract_sub2api_token_items(payload):
            if str(item.get("name") or "").strip() == token_name:
                return item
    return None


async def _create_sub2api_token(
    *,
    base_url: str,
    access_token: str,
    token_name: str,
) -> None:
    payload = {"name": token_name}
    for path in ("api/v1/keys", "api/v1/api-keys"):
        try:
            await _sub2api_request(
                method="POST",
                base_url=base_url,
                access_token=access_token,
                path=path,
                json_body=payload,
            )
            return
        except Exception:
            continue
    raise RuntimeError("sub2api token creation failed")


async def _reissue_sub2api_key(*, task: ProviderImportTask) -> dict[str, str]:
    payload = _task_payload(task)
    metadata = _task_metadata(task)
    access_token = str(payload.get("access_token") or "").strip()
    base_url = str(metadata.get("endpoint_base_url") or task.source_origin or "").strip()
    if not access_token:
        raise RuntimeError("missing access_token")
    if not base_url:
        raise RuntimeError("missing base_url")

    token_name = _build_upstream_token_name(task)
    token = await _find_sub2api_token(
        base_url=base_url,
        access_token=access_token,
        token_name=token_name,
    )
    if token is None:
        await _create_sub2api_token(
            base_url=base_url,
            access_token=access_token,
            token_name=token_name,
        )
        token = await _find_sub2api_token(
            base_url=base_url,
            access_token=access_token,
            token_name=token_name,
        )

    if not isinstance(token, dict):
        raise RuntimeError("sub2api token creation succeeded but token lookup failed")

    api_key = str(token.get("key") or "").strip()
    token_id = str(token.get("id") or "").strip()
    if not api_key:
        raise RuntimeError("sub2api token lookup returned empty key")
    return {
        "token_name": str(token.get("name") or token_name).strip() or token_name,
        "token_id": token_id,
        "api_key": api_key,
    }


def _build_reissued_key(task: ProviderImportTask, api_key_value: str) -> ProviderAPIKey:
    now = datetime.now(timezone.utc)
    key_id = str(uuid.uuid4())
    metadata = _task_metadata(task)
    return ProviderAPIKey(
        id=key_id,
        provider_id=task.provider_id,
        api_formats=["openai:chat"],
        auth_type="api_key",
        api_key=crypto_service.encrypt(api_key_value),
        auth_config=None,
        name=str(metadata.get("result_token_name") or _build_upstream_token_name(task))[:100],
        note=_task_note(str(task.id)),
        rate_multipliers=None,
        internal_priority=50,
        rpm_limit=None,
        allowed_models=None,
        capabilities=None,
        cache_ttl_minutes=5,
        max_probe_interval_minutes=32,
        auto_fetch_models=True,
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


def _prepare_existing_key_for_verification(
    *,
    db: Session,
    key: ProviderAPIKey,
) -> tuple[bool, bool]:
    was_inactive = not bool(getattr(key, "is_active", False))
    was_auto_fetch_disabled = not bool(getattr(key, "auto_fetch_models", False))
    if was_inactive:
        key.is_active = True
    if was_auto_fetch_disabled:
        key.auto_fetch_models = True
    if was_inactive or was_auto_fetch_disabled:
        db.commit()
    return was_inactive, was_auto_fetch_disabled


def _restore_existing_key_after_failed_verification(
    *,
    db: Session,
    key: ProviderAPIKey,
    was_inactive: bool,
    was_auto_fetch_disabled: bool,
) -> None:
    if was_inactive:
        key.is_active = False
    if was_auto_fetch_disabled:
        key.auto_fetch_models = False
    if was_inactive or was_auto_fetch_disabled:
        db.commit()


async def _verify_reissued_key_models(key_id: str) -> str:
    from src.services.model.fetch_scheduler import get_model_fetch_scheduler

    scheduler = get_model_fetch_scheduler()
    return await scheduler._fetch_models_for_key_by_id(key_id)


async def _execute_task(
    *,
    task: ProviderImportTask,
    db: Session,
    keys: list[ProviderAPIKey],
) -> tuple[str, bool, str]:
    now = datetime.now(timezone.utc)
    metadata = _task_metadata(task)
    created = False
    if str(getattr(task, "task_type", "") or "") != PENDING_REISSUE_TASK_TYPE:
        return "skipped", False, RESULT_STAGE_SKIPPED

    existing_key = _find_existing_key_for_task(task, keys)
    if existing_key is not None:
        metadata["result_key_id"] = str(existing_key.id)
        task.source_metadata = metadata
        task.status = TASK_STATUS_COMPLETED
        task.last_error = None
        task.last_attempt_at = now
        task.completed_at = now
        db.commit()
        return "completed", False, RESULT_STAGE_COMPLETED

    strategy = detect_import_task_strategy(task)
    if strategy == "sub2api_access_token":
        try:
            await _probe_sub2api_access_token(task=task)
        except Exception as exc:
            task.status = TASK_STATUS_FAILED
            task.last_error = str(exc)
            task.last_attempt_at = now
            task.retry_count = int(getattr(task, "retry_count", 0) or 0) + 1
            db.commit()
            return "failed", False, RESULT_STAGE_PROBE

    if strategy == "probe_new_api_access_token":
        if await _probe_new_api_compatibility(task=task):
            strategy = "new_api_access_token"
        else:
            task.status = TASK_STATUS_FAILED
            task.last_error = "unknown site is not compatible with new-api reissue"
            task.last_attempt_at = now
            task.retry_count = int(getattr(task, "retry_count", 0) or 0) + 1
            db.commit()
            return "failed", False, RESULT_STAGE_PROBE

    reissue_fn = None
    if strategy == "new_api_access_token":
        reissue_fn = _reissue_new_api_key
    elif strategy == "sub2api_access_token":
        reissue_fn = _reissue_sub2api_key
    else:
        task.status = TASK_STATUS_FAILED
        task.last_error = f"unsupported import task strategy: {strategy or 'unknown'}"
        task.last_attempt_at = now
        task.retry_count = int(getattr(task, "retry_count", 0) or 0) + 1
        db.commit()
        return "failed", False, RESULT_STAGE_UNSUPPORTED

    task.status = TASK_STATUS_PROCESSING
    task.last_attempt_at = now
    db.commit()
    stage = RESULT_STAGE_CREATE_KEY

    try:
        reissued = await reissue_fn(task=task)
        metadata["result_token_id"] = reissued["token_id"]
        metadata["result_token_name"] = reissued["token_name"]
        task.source_metadata = metadata

        existing_by_hash = _find_existing_key_by_hash(
            provider_id=task.provider_id,
            plaintext_key=reissued["api_key"],
            keys=keys,
        )
        if existing_by_hash is None:
            new_key = _build_reissued_key(task, reissued["api_key"])
            new_key.name = reissued["token_name"][:100]
            db.add(new_key)
            keys.append(new_key)
            db.commit()
            created = True
            metadata["result_key_id"] = str(new_key.id)
            task.source_metadata = metadata
            await run_create_key_side_effects(db=db, provider_id=task.provider_id, key=new_key)
            stage = RESULT_STAGE_VERIFY_MODELS
            verification_status = await _verify_reissued_key_models(str(new_key.id))
            if verification_status != "success":
                new_key.is_active = False
                db.commit()
                raise RuntimeError(f"model verification failed: {verification_status}")
        else:
            metadata["result_key_id"] = str(existing_by_hash.id)
            task.source_metadata = metadata
            was_inactive, was_auto_fetch_disabled = _prepare_existing_key_for_verification(
                db=db,
                key=existing_by_hash,
            )
            stage = RESULT_STAGE_VERIFY_MODELS
            verification_status = await _verify_reissued_key_models(str(existing_by_hash.id))
            if verification_status != "success":
                _restore_existing_key_after_failed_verification(
                    db=db,
                    key=existing_by_hash,
                    was_inactive=was_inactive,
                    was_auto_fetch_disabled=was_auto_fetch_disabled,
                )
                raise RuntimeError(f"model verification failed: {verification_status}")

        task.status = TASK_STATUS_COMPLETED
        task.last_error = None
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        return "completed", created, RESULT_STAGE_COMPLETED
    except MaskedTokenRequiresPlaintext as exc:
        db.rollback()
        metadata["action_required"] = ACTION_REQUIRED_SUBMIT_PLAINTEXT
        metadata["plaintext_capture_status"] = PLAINTEXT_CAPTURE_PENDING
        metadata["masked_key_preview"] = exc.masked_key_preview
        task.source_metadata = metadata
        task.status = TASK_STATUS_WAITING_PLAINTEXT
        task.last_error = None
        task.last_attempt_at = datetime.now(timezone.utc)
        db.commit()
        return "waiting_plaintext", False, RESULT_STAGE_CREATE_KEY
    except Exception as exc:
        logger.warning("all-in-hub reissue task failed task_id={}: {}", task.id, exc)
        db.rollback()
        task.status = TASK_STATUS_FAILED
        task.last_error = str(exc)
        task.last_attempt_at = datetime.now(timezone.utc)
        task.retry_count = int(getattr(task, "retry_count", 0) or 0) + 1
        db.commit()
        return "failed", created, stage


async def execute_all_in_hub_import_tasks(
    *,
    db: Session,
    limit: int = 20,
) -> AllInHubTaskExecutionSummary:
    tasks = list(db.query(ProviderImportTask).all())
    keys = list(db.query(ProviderAPIKey).all())
    selected = [
        task
        for task in tasks
        if str(getattr(task, "status", "") or "") == TASK_STATUS_PENDING
        and str(getattr(task, "task_type", "") or "") == PENDING_REISSUE_TASK_TYPE
    ][: max(0, limit)]
    summary = AllInHubTaskExecutionSummary(total_selected=len(selected))

    for task in selected:
        status, created, stage = await _execute_task(task=task, db=db, keys=keys)
        if status == "completed":
            summary.completed += 1
        elif status == "failed":
            summary.failed += 1
        else:
            summary.skipped += 1
        if created:
            summary.keys_created += 1
        metadata = _task_metadata(task)
        summary.results.append(
            {
                "task_id": str(task.id),
                "status": str(task.status),
                "provider_name": metadata.get("provider_name") or getattr(task, "source_name", None),
                "provider_website": getattr(task, "source_origin", None),
                "endpoint_base_url": metadata.get("endpoint_base_url"),
                "source_id": getattr(task, "source_id", None),
                "stage": stage,
                "last_error": getattr(task, "last_error", None),
                "key_created": created,
                "result_key_id": metadata.get("result_key_id"),
                "task_type": str(getattr(task, "task_type", "") or "") or None,
                "site_type": metadata.get("site_type"),
                "auth_type": metadata.get("auth_type"),
                "has_access_token": bool(metadata.get("has_access_token")),
                "has_session_cookie": bool(metadata.get("has_session_cookie")),
                "action_required": metadata.get("action_required"),
                "plaintext_capture_status": metadata.get("plaintext_capture_status"),
                "masked_key_preview": metadata.get("masked_key_preview"),
            }
        )
    return summary


async def submit_all_in_hub_task_plaintext(
    *,
    db: Session,
    task_id: str,
    plaintext_api_key: str,
    token_name: str | None = None,
    token_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    task = _find_task_by_id(db=db, task_id=task_id)
    if task is None:
        raise RuntimeError("import task not found")

    metadata = _normalize_waiting_plaintext_metadata(task, _task_metadata(task))
    if str(getattr(task, "status", "") or "") != TASK_STATUS_WAITING_PLAINTEXT or (
        str(metadata.get("plaintext_capture_status") or "") != PLAINTEXT_CAPTURE_PENDING
    ):
        raise RuntimeError("task is not waiting for plaintext submission")

    keys = list(db.query(ProviderAPIKey).all())
    created = False
    now = datetime.now(timezone.utc)
    normalized_plaintext = plaintext_api_key.strip()
    if not normalized_plaintext:
        raise RuntimeError("plaintext api key is empty")

    resolved_token_name = (token_name or metadata.get("result_token_name") or _build_upstream_token_name(task))
    resolved_token_id = str(token_id or metadata.get("result_token_id") or "").strip()
    metadata["result_token_name"] = resolved_token_name
    if resolved_token_id:
        metadata["result_token_id"] = resolved_token_id

    try:
        existing_by_hash = _find_existing_key_by_hash(
            provider_id=task.provider_id,
            plaintext_key=normalized_plaintext,
            keys=keys,
        )
        if existing_by_hash is None:
            new_key = _build_reissued_key(task, normalized_plaintext)
            new_key.name = str(resolved_token_name)[:100]
            db.add(new_key)
            keys.append(new_key)
            db.commit()
            created = True
            metadata["result_key_id"] = str(new_key.id)
            task.source_metadata = metadata
            await run_create_key_side_effects(db=db, provider_id=task.provider_id, key=new_key)
            verification_status = await _verify_reissued_key_models(str(new_key.id))
            if verification_status != "success":
                new_key.is_active = False
                db.commit()
                raise RuntimeError(f"model verification failed: {verification_status}")
        else:
            metadata["result_key_id"] = str(existing_by_hash.id)
            task.source_metadata = metadata
            was_inactive, was_auto_fetch_disabled = _prepare_existing_key_for_verification(
                db=db,
                key=existing_by_hash,
            )
            verification_status = await _verify_reissued_key_models(str(existing_by_hash.id))
            if verification_status != "success":
                _restore_existing_key_after_failed_verification(
                    db=db,
                    key=existing_by_hash,
                    was_inactive=was_inactive,
                    was_auto_fetch_disabled=was_auto_fetch_disabled,
                )
                raise RuntimeError(f"model verification failed: {verification_status}")

        metadata["plaintext_capture_status"] = PLAINTEXT_CAPTURE_CONSUMED
        metadata["action_required"] = None
        metadata["plaintext_submission_note"] = note
        task.source_metadata = metadata
        task.status = TASK_STATUS_COMPLETED
        task.last_error = None
        task.last_attempt_at = now
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "task_id": str(task.id),
            "status": str(task.status),
            "provider_name": metadata.get("provider_name") or getattr(task, "source_name", None),
            "provider_website": getattr(task, "source_origin", None),
            "endpoint_base_url": metadata.get("endpoint_base_url"),
            "source_id": getattr(task, "source_id", None),
            "stage": RESULT_STAGE_COMPLETED,
            "last_error": None,
            "key_created": created,
            "result_key_id": metadata.get("result_key_id"),
            "task_type": str(getattr(task, "task_type", "") or "") or None,
            "site_type": metadata.get("site_type"),
            "auth_type": metadata.get("auth_type"),
            "has_access_token": bool(metadata.get("has_access_token")),
            "has_session_cookie": bool(metadata.get("has_session_cookie")),
            "action_required": metadata.get("action_required"),
            "plaintext_capture_status": metadata.get("plaintext_capture_status"),
            "masked_key_preview": metadata.get("masked_key_preview"),
        }
    except Exception as exc:
        logger.warning("all-in-hub plaintext submit failed task_id={}: {}", task.id, exc)
        db.rollback()
        metadata["plaintext_capture_status"] = PLAINTEXT_CAPTURE_PENDING
        metadata["action_required"] = ACTION_REQUIRED_SUBMIT_PLAINTEXT
        task.source_metadata = metadata
        task.status = TASK_STATUS_WAITING_PLAINTEXT
        task.last_error = str(exc)
        task.last_attempt_at = datetime.now(timezone.utc)
        task.retry_count = int(getattr(task, "retry_count", 0) or 0) + 1
        db.commit()
        raise PlaintextSubmissionRetryableError(str(exc)) from exc
