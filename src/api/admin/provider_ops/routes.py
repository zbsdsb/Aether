"""
Provider 操作 API 路由

提供 Provider 操作相关的 API 端点：
- 架构列表
- 连接管理
- 操作执行（余额查询、签到等）
- 配置管理
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.crypto import crypto_service
from src.database import get_db
from src.models.database import Provider, ProviderImportTask, User
from src.services.provider_ops import (
    ConnectorAuthType,
    ProviderActionType,
    ProviderOpsConfig,
    ProviderOpsService,
    get_registry,
)
from src.services.provider_ops.proxy_probe import probe_pending_provider_proxies, probe_provider_proxy
from src.utils.auth_utils import require_admin

router = APIRouter(prefix="/api/admin/provider-ops", tags=["Provider Operations"])


# ==================== Request/Response Models ====================


class ArchitectureInfo(BaseModel):
    """架构信息"""

    architecture_id: str
    display_name: str
    description: str
    credentials_schema: dict[str, Any]
    supported_auth_types: list[dict[str, Any]]
    supported_actions: list[dict[str, Any]]
    default_connector: str | None


class ConnectorConfigRequest(BaseModel):
    """连接器配置请求"""

    auth_type: str = Field(..., description="认证类型")
    config: dict[str, Any] = Field(default_factory=dict, description="连接器配置")
    credentials: dict[str, Any] = Field(default_factory=dict, description="凭据信息")


class ActionConfigRequest(BaseModel):
    """操作配置请求"""

    enabled: bool = Field(True, description="是否启用")
    config: dict[str, Any] = Field(default_factory=dict, description="操作配置")


class SaveConfigRequest(BaseModel):
    """保存配置请求"""

    architecture_id: str = Field("generic_api", description="架构 ID")
    base_url: str | None = Field(None, description="API 基础地址")
    connector: ConnectorConfigRequest
    actions: dict[str, ActionConfigRequest] = Field(default_factory=dict)
    schedule: dict[str, str] = Field(default_factory=dict, description="定时任务配置")


class ConnectRequest(BaseModel):
    """连接请求"""

    credentials: dict[str, Any] | None = Field(None, description="凭据（可选，使用已保存的）")


class ExecuteActionRequest(BaseModel):
    """执行操作请求"""

    config: dict[str, Any] | None = Field(None, description="操作配置（覆盖默认）")


class ConnectionStatusResponse(BaseModel):
    """连接状态响应"""

    status: str
    auth_type: str
    connected_at: str | None
    expires_at: str | None
    last_error: str | None


class ActionResultResponse(BaseModel):
    """操作结果响应"""

    status: str
    action_type: str
    data: Any | None
    message: str | None
    executed_at: str
    response_time_ms: int | None
    cache_ttl_seconds: int


class ProviderOpsStatusResponse(BaseModel):
    """Provider 操作状态响应"""

    provider_id: str
    is_configured: bool
    architecture_id: str | None
    connection_status: ConnectionStatusResponse
    enabled_actions: list[str]


class ProviderOpsConfigResponse(BaseModel):
    """Provider 操作配置响应（脱敏）"""

    provider_id: str
    is_configured: bool
    architecture_id: str | None = None
    base_url: str | None = None
    connector: dict[str, Any] | None = None  # 脱敏后的连接器配置


class VerifyAuthResponse(BaseModel):
    """验证认证响应"""

    success: bool
    message: str | None = None
    data: dict[str, Any] | None = None
    updated_credentials: dict[str, Any] | None = None


class ImportedAuthPrefillResponse(BaseModel):
    """导入凭证预填充响应。"""

    available: bool
    architecture_id: str | None = None
    base_url: str | None = None
    connector: dict[str, Any] | None = None
    source_summary: dict[str, Any] | None = None


class ProxyProbeRunRequest(BaseModel):
    limit: int = Field(20, ge=1, le=200)


class ProxyProbeRunResponse(BaseModel):
    total_selected: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)


# ==================== Helper Functions ====================


def _serialize_data(data: Any) -> Any:
    """序列化 dataclass 为字典，用于 JSON 响应"""
    if data is None:
        return None
    if is_dataclass(data) and not isinstance(data, type):
        return asdict(data)
    return data


def _normalize_site_type(value: Any) -> str:
    return str(value or "").strip().lower()


def _infer_architecture_id(task: ProviderImportTask, metadata: dict[str, Any], payload: dict[str, Any]) -> str | None:
    site_type = _normalize_site_type(metadata.get("site_type"))
    source_name = str(getattr(task, "source_name", "") or "").strip().lower()
    source_origin = str(getattr(task, "source_origin", "") or "").strip().lower()
    values = " ".join(
        value
        for value in (
            site_type,
            source_name,
            source_origin,
        )
        if value
    )

    if "sub2api" in values:
        return "sub2api"
    if "anyrouter" in values:
        return "anyrouter"
    if "cubence" in values:
        return "cubence"
    if "nekocode" in values:
        return "nekocode"
    if "yescode" in values:
        return "yescode"
    if "new-api" in values or "new_api" in values:
        return "new_api"
    if payload.get("access_token") or payload.get("session_cookie"):
        return "new_api"
    return None


def _load_imported_auth_prefill(task: ProviderImportTask) -> ImportedAuthPrefillResponse:
    metadata = getattr(task, "source_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}

    decrypted_payload = crypto_service.decrypt(getattr(task, "credential_payload", ""))
    payload = {}
    if decrypted_payload:
        try:
            import json

            raw_payload = json.loads(decrypted_payload)
            if isinstance(raw_payload, dict):
                payload = raw_payload
        except Exception:
            payload = {}

    architecture_id = _infer_architecture_id(task, metadata, payload)
    if architecture_id is None:
        return ImportedAuthPrefillResponse(available=False)

    if architecture_id == "sub2api":
        connector = {
            "auth_type": ConnectorAuthType.API_KEY.value,
            "config": {},
            "credentials": {
                "refresh_token": str(payload.get("refresh_token") or "").strip(),
            },
        }
    elif architecture_id == "new_api":
        connector = {
            "auth_type": ConnectorAuthType.API_KEY.value,
            "config": {},
            "credentials": {
                "cookie": str(payload.get("session_cookie") or "").strip(),
                "api_key": str(payload.get("access_token") or "").strip(),
                "user_id": str(metadata.get("account_id") or "").strip(),
            },
        }
    elif architecture_id in {"anyrouter", "nekocode"}:
        connector = {
            "auth_type": ConnectorAuthType.COOKIE.value,
            "config": {},
            "credentials": {
                "session_cookie": str(payload.get("session_cookie") or "").strip(),
            },
        }
    elif architecture_id == "cubence":
        connector = {
            "auth_type": ConnectorAuthType.COOKIE.value,
            "config": {},
            "credentials": {
                "token_cookie": str(payload.get("session_cookie") or "").strip(),
            },
        }
    elif architecture_id == "yescode":
        connector = {
            "auth_type": ConnectorAuthType.COOKIE.value,
            "config": {},
            "credentials": {
                "auth_cookie": str(payload.get("session_cookie") or "").strip(),
            },
        }
    else:
        return ImportedAuthPrefillResponse(available=False)

    return ImportedAuthPrefillResponse(
        available=True,
        architecture_id=architecture_id,
        base_url=str(metadata.get("endpoint_base_url") or getattr(task, "source_origin", "") or "").strip()
        or None,
        connector=connector,
        source_summary={
            "task_type": getattr(task, "task_type", None),
            "site_type": metadata.get("site_type"),
            "source_id": getattr(task, "source_id", None),
            "source_name": getattr(task, "source_name", None),
            "has_access_token": bool(metadata.get("has_access_token")),
            "has_refresh_token": bool(metadata.get("has_refresh_token")),
            "has_session_cookie": bool(metadata.get("has_session_cookie")),
        },
    )


# ==================== Routes ====================


@router.get("/architectures", response_model=list[ArchitectureInfo])
async def list_architectures(_: User = Depends(require_admin)) -> Any:
    """获取所有可用的架构"""
    registry = get_registry()
    return registry.to_dict_list()


@router.get("/architectures/{architecture_id}", response_model=ArchitectureInfo)
async def get_architecture(architecture_id: str, _: User = Depends(require_admin)) -> Any:
    """获取指定架构的详情"""
    registry = get_registry()
    arch = registry.get(architecture_id)
    if not arch:
        raise HTTPException(status_code=404, detail=f"架构 {architecture_id} 不存在")
    return arch.to_dict()


@router.get("/providers/{provider_id}/status", response_model=ProviderOpsStatusResponse)
async def get_provider_ops_status(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """获取 Provider 的操作状态"""
    service = ProviderOpsService(db)

    config = service.get_config(provider_id)
    conn_state = service.get_connection_status(provider_id)

    enabled_actions = []
    if config:
        for action_type, action_config in config.actions.items():
            if action_config.get("enabled", True):
                enabled_actions.append(action_type)

    return ProviderOpsStatusResponse(
        provider_id=provider_id,
        is_configured=config is not None,
        architecture_id=config.architecture_id if config else None,
        connection_status=ConnectionStatusResponse(
            status=conn_state.status.value,
            auth_type=conn_state.auth_type.value,
            connected_at=conn_state.connected_at.isoformat() if conn_state.connected_at else None,
            expires_at=conn_state.expires_at.isoformat() if conn_state.expires_at else None,
            last_error=conn_state.last_error,
        ),
        enabled_actions=enabled_actions,
    )


@router.get("/providers/{provider_id}/config", response_model=ProviderOpsConfigResponse)
async def get_provider_ops_config(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """
    获取 Provider 的操作配置（脱敏）

    返回已保存的配置，但敏感字段（如 api_key）会被脱敏处理。
    """
    service = ProviderOpsService(db)
    config = service.get_config(provider_id)

    if not config:
        return ProviderOpsConfigResponse(
            provider_id=provider_id,
            is_configured=False,
        )

    # 获取 base_url：优先从 provider_ops 配置读取，否则回退到 endpoint/provider
    base_url = config.base_url
    if not base_url:
        provider = db.query(Provider).filter(Provider.id == provider_id).first()
        if provider:
            if provider.endpoints:
                for endpoint in provider.endpoints:
                    if endpoint.base_url:
                        base_url = endpoint.base_url
                        break
            if not base_url:
                provider_config = provider.config or {}
                base_url = provider_config.get("base_url") or provider.website

    # 获取脱敏后的凭据
    masked_credentials = service.get_masked_credentials(config.connector_credentials)

    return ProviderOpsConfigResponse(
        provider_id=provider_id,
        is_configured=True,
        architecture_id=config.architecture_id,
        base_url=base_url,
        connector={
            "auth_type": config.connector_auth_type.value,
            "config": config.connector_config,
            "credentials": masked_credentials,
        },
    )


@router.get(
    "/providers/{provider_id}/imported-auth-prefill",
    response_model=ImportedAuthPrefillResponse,
)
async def get_provider_imported_auth_prefill(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """从最新导入任务构建用户认证预填充草稿。"""
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider 不存在")

    task = (
        db.query(ProviderImportTask)
        .filter(ProviderImportTask.provider_id == provider_id)
        .order_by(ProviderImportTask.updated_at.desc(), ProviderImportTask.created_at.desc())
        .first()
    )
    if task is None:
        return ImportedAuthPrefillResponse(available=False)

    return _load_imported_auth_prefill(task)


@router.put("/providers/{provider_id}/config")
async def save_provider_ops_config(
    provider_id: str,
    request: SaveConfigRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """保存 Provider 的操作配置"""
    service = ProviderOpsService(db)

    # 合并凭据：如果请求中的敏感字段为空，使用已保存的凭据
    credentials = service.merge_credentials_with_saved(
        provider_id, dict(request.connector.credentials)
    )

    # 构建配置对象
    config = ProviderOpsConfig(
        architecture_id=request.architecture_id,
        base_url=request.base_url,
        connector_auth_type=ConnectorAuthType(request.connector.auth_type),
        connector_config=request.connector.config,
        connector_credentials=credentials,
        actions={
            action_type: {"enabled": action_config.enabled, "config": action_config.config}
            for action_type, action_config in request.actions.items()
        },
        schedule=request.schedule,
    )

    success = service.save_config(provider_id, config)
    if not success:
        raise HTTPException(status_code=404, detail="Provider 不存在")

    return {"success": True, "message": "配置保存成功"}


@router.post("/providers/{provider_id}/verify", response_model=VerifyAuthResponse)
async def verify_provider_auth(
    provider_id: str,
    request: SaveConfigRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """
    验证 Provider 认证配置

    在保存前测试认证是否有效。
    如果凭据中的敏感字段为空，会使用已保存的凭据。
    """
    service = ProviderOpsService(db)

    # 获取 base_url
    base_url = request.base_url
    if not base_url:
        # 尝试从 Provider 获取
        provider = db.query(Provider).filter(Provider.id == provider_id).first()
        if provider:
            # 从 endpoints 或 config 获取
            if provider.endpoints:
                for endpoint in provider.endpoints:
                    if endpoint.base_url:
                        base_url = endpoint.base_url
                        break
            if not base_url and provider.config:
                base_url = provider.config.get("base_url")

    if not base_url:
        return VerifyAuthResponse(
            success=False,
            message="请提供 API 地址",
        )

    # 合并凭据：如果请求中的敏感字段为空，使用已保存的凭据
    credentials = service.merge_credentials_with_saved(
        provider_id, dict(request.connector.credentials)
    )

    result = await service.verify_auth(
        base_url=base_url,
        architecture_id=request.architecture_id,
        auth_type=ConnectorAuthType(request.connector.auth_type),
        config=request.connector.config,
        credentials=credentials,
        provider_id=provider_id,
    )

    return VerifyAuthResponse(
        success=result.get("success", False),
        message=result.get("message"),
        data=result.get("data"),
        updated_credentials=result.get("updated_credentials"),
    )


@router.delete("/providers/{provider_id}/config")
async def delete_provider_ops_config(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """删除 Provider 的操作配置"""
    service = ProviderOpsService(db)
    success = service.delete_config(provider_id)

    if not success:
        raise HTTPException(status_code=404, detail="Provider 不存在")

    return {"success": True, "message": "配置已删除"}


@router.post("/providers/{provider_id}/proxy-probe", response_model=ProxyProbeRunResponse)
async def run_provider_proxy_probe(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    result = await probe_provider_proxy(provider_id, db=db)
    summary = {
        "total_selected": 1,
        "completed": 1 if result.get("status") == "completed" else 0,
        "failed": 1 if result.get("status") == "failed" else 0,
        "skipped": 1 if result.get("status") == "skipped" else 0,
        "results": [result],
    }
    return ProxyProbeRunResponse(**summary)


@router.post("/proxy-probe/run", response_model=ProxyProbeRunResponse)
async def run_pending_proxy_probe(
    request: ProxyProbeRunRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    result = await probe_pending_provider_proxies(db=db, limit=request.limit)
    return ProxyProbeRunResponse(
        total_selected=result.total_selected,
        completed=result.completed,
        failed=result.failed,
        skipped=result.skipped,
        results=result.results,
    )


@router.post("/providers/{provider_id}/connect")
async def connect_provider(
    provider_id: str,
    request: ConnectRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """建立与 Provider 的连接"""
    service = ProviderOpsService(db)

    success, message = await service.connect(provider_id, request.credentials)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


@router.post("/providers/{provider_id}/disconnect")
async def disconnect_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """断开与 Provider 的连接"""
    service = ProviderOpsService(db)
    await service.disconnect(provider_id)

    return {"success": True, "message": "已断开连接"}


@router.post(
    "/providers/{provider_id}/actions/{action_type}",
    response_model=ActionResultResponse,
)
async def execute_action(
    provider_id: str,
    action_type: str,
    request: ExecuteActionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """执行指定操作"""
    service = ProviderOpsService(db)

    try:
        action_type_enum = ProviderActionType(action_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的操作类型: {action_type}")

    result = await service.execute_action(provider_id, action_type_enum, request.config)

    return ActionResultResponse(
        status=result.status.value,
        action_type=result.action_type.value,
        data=_serialize_data(result.data),
        message=result.message,
        executed_at=result.executed_at.isoformat(),
        response_time_ms=result.response_time_ms,
        cache_ttl_seconds=result.cache_ttl_seconds,
    )


@router.get("/providers/{provider_id}/balance", response_model=ActionResultResponse)
async def get_balance(
    provider_id: str,
    refresh: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """
    获取余额（优先返回缓存，后台异步刷新）

    - refresh=True（默认）：返回缓存并触发后台刷新
    - refresh=False：仅返回缓存，不触发刷新
    """
    service = ProviderOpsService(db)
    result = await service.query_balance_with_cache(provider_id, trigger_refresh=refresh)

    return ActionResultResponse(
        status=result.status.value,
        action_type=result.action_type.value,
        data=_serialize_data(result.data),
        message=result.message,
        executed_at=result.executed_at.isoformat(),
        response_time_ms=result.response_time_ms,
        cache_ttl_seconds=result.cache_ttl_seconds,
    )


@router.post("/providers/{provider_id}/balance", response_model=ActionResultResponse)
async def refresh_balance(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """立即刷新余额（同步等待结果）"""
    service = ProviderOpsService(db)
    result = await service.query_balance(provider_id)

    return ActionResultResponse(
        status=result.status.value,
        action_type=result.action_type.value,
        data=_serialize_data(result.data),
        message=result.message,
        executed_at=result.executed_at.isoformat(),
        response_time_ms=result.response_time_ms,
        cache_ttl_seconds=result.cache_ttl_seconds,
    )


@router.post("/providers/{provider_id}/checkin", response_model=ActionResultResponse)
async def checkin(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """签到（快捷方法）"""
    service = ProviderOpsService(db)
    result = await service.checkin(provider_id)

    return ActionResultResponse(
        status=result.status.value,
        action_type=result.action_type.value,
        data=_serialize_data(result.data),
        message=result.message,
        executed_at=result.executed_at.isoformat(),
        response_time_ms=result.response_time_ms,
        cache_ttl_seconds=result.cache_ttl_seconds,
    )


@router.post("/batch/balance")
async def batch_query_balance(
    provider_ids: list[str] | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Any:
    """批量查询余额"""
    service = ProviderOpsService(db)
    results = await service.batch_query_balance(provider_ids)

    return {
        provider_id: ActionResultResponse(
            status=result.status.value,
            action_type=result.action_type.value,
            data=_serialize_data(result.data),
            message=result.message,
            executed_at=result.executed_at.isoformat(),
            response_time_ms=result.response_time_ms,
            cache_ttl_seconds=result.cache_ttl_seconds,
        )
        for provider_id, result in results.items()
    }
