"""
GlobalModel Admin API

提供 GlobalModel 的 CRUD 操作接口
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from sqlalchemy.orm import Session, selectinload

from src.api.base.admin_adapter import AdminApiAdapter
from src.api.base.context import ApiRequestContext
from src.api.base.models_service import invalidate_models_list_cache
from src.api.base.pipeline import get_pipeline
from src.core.logger import logger
from src.database import get_db
from src.models.pydantic_models import (
    BatchAssignToProvidersRequest,
    BatchAssignToProvidersResponse,
    GlobalModelCreate,
    GlobalModelListResponse,
    GlobalModelProviderCandidate,
    GlobalModelProviderCandidatesResponse,
    GlobalModelProvidersResponse,
    GlobalModelResponse,
    GlobalModelUpdate,
    GlobalModelWithStats,
    ModelCatalogProviderDetail,
    RefreshGlobalModelProviderCandidatesRequest,
)
from src.models.database import Provider, User
from src.services.model.global_model import GlobalModelService
from src.api.admin.provider_query import (
    ModelsQueryRequest,
    _aggregate_models_by_id,
    _get_provider_upstream_models_cache,
    query_available_models,
)
from src.utils.auth_utils import require_admin
from src.services.model.fetch_scheduler import get_upstream_models_from_cache

router = APIRouter(prefix="/global", tags=["Admin - Global Models"])
pipeline = get_pipeline()


def _normalize_cached_models(cached_models: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not cached_models:
        return []
    return [item for item in cached_models if isinstance(item, dict)]


def _compile_global_model_patterns(global_model: Any) -> list[re.Pattern[str]]:
    config = getattr(global_model, "config", None)
    if not isinstance(config, dict):
        return []
    raw_patterns = config.get("model_mappings")
    if not isinstance(raw_patterns, list):
        return []

    patterns: list[re.Pattern[str]] = []
    for item in raw_patterns:
        if not isinstance(item, str) or not item.strip():
            continue
        try:
            patterns.append(re.compile(item))
        except re.error:
            continue
    return patterns


def _match_global_model_against_cached_models(
    global_model: Any,
    cached_models: list[dict[str, Any]] | None,
) -> tuple[bool, list[dict[str, Any]]]:
    normalized_models = _normalize_cached_models(cached_models)
    if not normalized_models:
        return False, []

    target_name = str(getattr(global_model, "name", "") or "").strip()
    patterns = _compile_global_model_patterns(global_model)
    matches: list[dict[str, Any]] = []

    for item in normalized_models:
        model_id = str(item.get("id") or item.get("name") or "").strip()
        if not model_id:
            continue
        if model_id == target_name:
            matches.append(item)
            continue
        if any(pattern.search(model_id) for pattern in patterns):
            matches.append(item)

    return len(matches) > 0, matches


def _build_provider_candidate_item(
    *,
    provider: Any,
    global_model: Any,
    linked_provider_ids: set[str],
    cached_models: list[dict[str, Any]] | None,
) -> GlobalModelProviderCandidate:
    normalized_models = _normalize_cached_models(cached_models)
    if not normalized_models:
        match_status = "unknown"
    else:
        matched, _matched_models = _match_global_model_against_cached_models(global_model, normalized_models)
        match_status = "matched" if matched else "not_matched"

    return GlobalModelProviderCandidate(
        provider_id=str(getattr(provider, "id", "") or ""),
        provider_name=str(getattr(provider, "name", "") or ""),
        provider_website=getattr(provider, "website", None),
        provider_active=bool(getattr(provider, "is_active", False)),
        already_linked=str(getattr(provider, "id", "") or "") in linked_provider_ids,
        match_status=match_status,
        cached_models=normalized_models,
        cached_model_count=len(normalized_models),
    )


def _build_provider_candidates_payload(
    *,
    providers: list[Any],
    global_model: Any,
    linked_provider_ids: set[str],
    provider_cached_models: dict[str, list[dict[str, Any]] | None],
) -> list[GlobalModelProviderCandidate]:
    status_priority = {"matched": 0, "not_matched": 1, "unknown": 2}
    items = [
        _build_provider_candidate_item(
            provider=provider,
            global_model=global_model,
            linked_provider_ids=linked_provider_ids,
            cached_models=provider_cached_models.get(str(getattr(provider, "id", "") or "")),
        )
        for provider in providers
    ]
    items.sort(
        key=lambda item: (
            status_priority.get(item.match_status, 99),
            0 if item.already_linked else 1,
            item.provider_name.lower(),
        )
    )
    return items


async def _get_cached_models_for_provider(provider: Any) -> list[dict[str, Any]] | None:
    provider_id = str(getattr(provider, "id", "") or "")
    provider_cached = await _get_provider_upstream_models_cache(provider_id)
    normalized_provider_cached = _normalize_cached_models(provider_cached)
    if normalized_provider_cached:
        return _aggregate_models_by_id(normalized_provider_cached)

    api_keys = getattr(provider, "api_keys", None) or []
    aggregated: list[dict[str, Any]] = []
    for api_key in api_keys:
        if not bool(getattr(api_key, "is_active", False)):
            continue
        api_key_id = str(getattr(api_key, "id", "") or "")
        if not api_key_id:
            continue
        key_cached = await get_upstream_models_from_cache(provider_id, api_key_id)
        normalized_key_cached = _normalize_cached_models(key_cached)
        if normalized_key_cached:
            aggregated.extend(normalized_key_cached)

    return _aggregate_models_by_id(aggregated) if aggregated else None


@router.get("", response_model=GlobalModelListResponse)
async def list_global_models(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> GlobalModelListResponse:
    """
    获取 GlobalModel 列表

    查询系统中的全局模型列表，支持分页、过滤和搜索功能。

    **查询参数**:
    - `skip`: 跳过记录数，用于分页（默认 0）
    - `limit`: 返回记录数，用于分页（默认 100，最大 1000）
    - `is_active`: 过滤活跃状态（true/false/null，null 表示不过滤）
    - `search`: 搜索关键词，支持按名称或显示名称模糊搜索

    **返回字段**:
    - `models`: GlobalModel 列表，每个包含：
      - `id`: GlobalModel ID
      - `name`: 模型名称（唯一）
      - `display_name`: 显示名称
      - `is_active`: 是否活跃
      - `provider_count`: 关联提供商数量
      - 定价和能力配置等其他字段
    - `total`: 返回的模型总数
    """
    adapter = AdminListGlobalModelsAdapter(
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
    )
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get("/{global_model_id}", response_model=GlobalModelWithStats)
async def get_global_model(
    request: Request,
    global_model_id: str,
    db: Session = Depends(get_db),
) -> GlobalModelWithStats:
    """
    获取单个 GlobalModel 详情

    查询指定 GlobalModel 的详细信息，包含关联的提供商和价格统计数据。

    **路径参数**:
    - `global_model_id`: GlobalModel ID

    **返回字段**:
    - 基础字段：`id`, `name`, `display_name`, `is_active` 等
    - 统计字段：
      - `total_models`: 关联的 Model 实现数量
      - `total_providers`: 关联的提供商数量
      - `price_range`: 价格区间统计（最低/最高输入输出价格）
    """
    adapter = AdminGetGlobalModelAdapter(global_model_id=global_model_id)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.post("", response_model=GlobalModelResponse, status_code=201)
async def create_global_model(
    request: Request,
    payload: GlobalModelCreate,
    db: Session = Depends(get_db),
) -> GlobalModelResponse:
    """
    创建 GlobalModel

    创建一个新的全局模型定义，作为多个提供商实现的统一抽象。

    **请求体字段**:
    - `name`: 模型名称（唯一标识，如 "claude-3-5-sonnet-20241022"）
    - `display_name`: 显示名称（如 "Claude 3.5 Sonnet"）
    - `is_active`: 是否活跃（默认 true）
    - `default_price_per_request`: 默认按次计费价格（可选）
    - `default_tiered_pricing`: 默认阶梯定价配置（包含多个价格阶梯）
    - `supported_capabilities`: 支持的能力标志（vision、function_calling、streaming）
    - `config`: 额外配置（JSON 格式，如 description、context_window 等）

    **返回字段**:
    - `id`: 创建的 GlobalModel ID
    - 其他请求体中的所有字段
    """
    adapter = AdminCreateGlobalModelAdapter(payload=payload)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.patch("/{global_model_id}", response_model=GlobalModelResponse)
async def update_global_model(
    request: Request,
    global_model_id: str,
    payload: GlobalModelUpdate,
    db: Session = Depends(get_db),
) -> GlobalModelResponse:
    """
    更新 GlobalModel

    更新指定 GlobalModel 的配置信息，支持部分字段更新。
    更新后会自动失效相关缓存。

    **路径参数**:
    - `global_model_id`: GlobalModel ID

    **请求体字段**（均为可选）:
    - `display_name`: 显示名称
    - `is_active`: 是否活跃
    - `default_price_per_request`: 默认按次计费价格
    - `default_tiered_pricing`: 默认阶梯定价配置
    - `supported_capabilities`: 支持的能力标志
    - `config`: 额外配置

    **返回字段**:
    - 更新后的完整 GlobalModel 信息
    """
    adapter = AdminUpdateGlobalModelAdapter(global_model_id=global_model_id, payload=payload)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.delete("/{global_model_id}", status_code=204, response_class=Response)
async def delete_global_model(
    request: Request,
    global_model_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """
    删除 GlobalModel

    删除指定的 GlobalModel，会级联删除所有关联的 Provider 模型实现。
    删除后会自动失效相关缓存。

    **路径参数**:
    - `global_model_id`: GlobalModel ID

    **返回**:
    - 成功删除返回 204 状态码，无响应体
    """
    adapter = AdminDeleteGlobalModelAdapter(global_model_id=global_model_id)
    await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)
    return Response(status_code=204)


@router.post("/batch-delete")
async def batch_delete_global_models(
    request: Request,
    ids: list[str] = Body(..., embed=True, max_length=100),
    db: Session = Depends(get_db),
) -> dict:
    """
    批量删除 GlobalModel

    顺序删除多个 GlobalModel（每个独立提交），避免并行删除导致的锁竞争。
    """
    adapter = AdminBatchDeleteGlobalModelsAdapter(ids=ids)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.post(
    "/{global_model_id}/assign-to-providers", response_model=BatchAssignToProvidersResponse
)
async def batch_assign_to_providers(
    request: Request,
    global_model_id: str,
    payload: BatchAssignToProvidersRequest,
    db: Session = Depends(get_db),
) -> BatchAssignToProvidersResponse:
    """
    批量为提供商添加模型实现

    为指定的 GlobalModel 批量创建多个 Provider 的模型实现（Model 记录）。
    用于快速将一个统一模型分配给多个提供商。

    **路径参数**:
    - `global_model_id`: GlobalModel ID

    **请求体字段**:
    - `provider_ids`: 提供商 ID 列表
    - `create_models`: Model 创建配置列表，每个包含：
      - `provider_id`: 提供商 ID
      - `provider_model_name`: 提供商侧的模型名称（如 "claude-3-5-sonnet-20241022"）
      - 其他可选字段（价格覆盖、能力覆盖等）

    **返回字段**:
    - `success`: 成功创建的 Model 列表
    - `errors`: 失败的提供商及错误信息列表
    - `total_requested`: 请求处理的总数
    - `total_success`: 成功创建的数量
    - `total_errors`: 失败的数量
    """
    adapter = AdminBatchAssignToProvidersAdapter(global_model_id=global_model_id, payload=payload)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get("/{global_model_id}/providers", response_model=GlobalModelProvidersResponse)
async def get_global_model_providers(
    request: Request,
    global_model_id: str,
    db: Session = Depends(get_db),
) -> GlobalModelProvidersResponse:
    """
    获取 GlobalModel 的关联提供商

    查询指定 GlobalModel 的所有关联提供商及其模型实现详情，包括非活跃的提供商。
    用于查看某个统一模型在各个提供商上的具体配置。

    **路径参数**:
    - `global_model_id`: GlobalModel ID

    **返回字段**:
    - `providers`: 提供商列表，每个包含：
      - `provider_id`: 提供商 ID
      - `provider_name`: 提供商名称
      - `provider_display_name`: 提供商显示名称
      - `model_id`: Model 实现 ID
      - `target_model`: 提供商侧的模型名称
      - 价格信息（input_price_per_1m、output_price_per_1m 等）
      - 能力标志（supports_vision、supports_function_calling、supports_streaming）
      - `is_active`: 是否活跃
    - `total`: 关联提供商总数
    """
    adapter = AdminGetGlobalModelProvidersAdapter(global_model_id=global_model_id)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get(
    "/{global_model_id}/provider-candidates",
    response_model=GlobalModelProviderCandidatesResponse,
)
async def get_global_model_provider_candidates(
    global_model_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> GlobalModelProviderCandidatesResponse:
    global_model = GlobalModelService.get_global_model(db, global_model_id)
    providers = (
        db.query(Provider)
        .options(selectinload(Provider.api_keys))
        .order_by(Provider.name.asc())
        .all()
    )

    from src.models.database import Model

    linked_provider_ids = {
        str(item.provider_id)
        for item in db.query(Model.provider_id).filter(Model.global_model_id == global_model.id).all()
    }
    provider_cached_models = {
        str(provider.id): await _get_cached_models_for_provider(provider)
        for provider in providers
    }
    items = _build_provider_candidates_payload(
        providers=providers,
        global_model=global_model,
        linked_provider_ids=linked_provider_ids,
        provider_cached_models=provider_cached_models,
    )
    return GlobalModelProviderCandidatesResponse(items=items, total=len(items))


@router.post(
    "/{global_model_id}/provider-candidates/refresh",
    response_model=GlobalModelProviderCandidatesResponse,
)
async def refresh_global_model_provider_candidates(
    global_model_id: str,
    payload: RefreshGlobalModelProviderCandidatesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> GlobalModelProviderCandidatesResponse:
    global_model = GlobalModelService.get_global_model(db, global_model_id)
    provider_ids = [provider_id for provider_id in payload.provider_ids if str(provider_id).strip()]
    from src.models.database import Model

    providers = (
        db.query(Provider)
        .options(selectinload(Provider.api_keys))
        .filter(Provider.id.in_(provider_ids))
        .order_by(Provider.name.asc())
        .all()
    )
    providers_by_id = {str(provider.id): provider for provider in providers}
    for provider_id in provider_ids:
        provider = providers_by_id.get(provider_id)
        if provider is None:
            continue
        if not any(bool(getattr(api_key, "is_active", False)) for api_key in (getattr(provider, "api_keys", None) or [])):
            continue
        try:
            await query_available_models(
                ModelsQueryRequest(provider_id=provider_id, force_refresh=True),
                db=db,
                current_user=current_user,
            )
        except Exception:
            # Best-effort refresh: one provider failure must not fail the whole batch.
            continue
    linked_provider_ids = {
        str(item.provider_id)
        for item in db.query(Model.provider_id).filter(Model.global_model_id == global_model.id).all()
    }
    provider_cached_models = {
        str(provider.id): await _get_cached_models_for_provider(provider)
        for provider in providers
    }
    items = _build_provider_candidates_payload(
        providers=providers,
        global_model=global_model,
        linked_provider_ids=linked_provider_ids,
        provider_cached_models=provider_cached_models,
    )
    return GlobalModelProviderCandidatesResponse(items=items, total=len(items))


# ========== Adapters ==========


@dataclass
class AdminListGlobalModelsAdapter(AdminApiAdapter):
    """列出 GlobalModel"""

    skip: int
    limit: int
    is_active: bool | None
    search: str | None

    async def handle(self, context: ApiRequestContext) -> Any:  # type: ignore[override]
        from sqlalchemy import and_, case, func, or_

        from src.models.database import GlobalModel, Model, Provider

        query = context.db.query(GlobalModel)
        if self.is_active is not None:
            query = query.filter(GlobalModel.is_active == self.is_active)
        if self.search:
            search_pattern = f"%{self.search}%"
            query = query.filter(
                or_(
                    GlobalModel.name.ilike(search_pattern),
                    GlobalModel.display_name.ilike(search_pattern),
                )
            )

        total = int(query.with_entities(func.count(GlobalModel.id)).scalar() or 0)
        models = query.order_by(GlobalModel.name).offset(self.skip).limit(self.limit).all()

        # 一次性查询所有 GlobalModel 的 provider_count（优化 N+1 问题）
        # 用条件聚合同时获取总数和活跃数，减少一次 DB 往返
        model_ids = [gm.id for gm in models]
        provider_counts = {}
        active_provider_counts = {}
        if model_ids:
            count_results = (
                context.db.query(
                    Model.global_model_id,
                    func.count(func.distinct(Model.provider_id)),
                    func.count(
                        func.distinct(
                            case(
                                (
                                    and_(
                                        Model.is_active.is_(True),
                                        Provider.is_active.is_(True),
                                    ),
                                    Model.provider_id,
                                ),
                                else_=None,
                            )
                        )
                    ),
                )
                .join(Provider, Model.provider_id == Provider.id)
                .filter(Model.global_model_id.in_(model_ids))
                .group_by(Model.global_model_id)
                .all()
            )
            provider_counts = {gm_id: total for gm_id, total, _ in count_results}
            active_provider_counts = {gm_id: active for gm_id, _, active in count_results}

        # 构建响应
        model_responses = []
        for gm in models:
            response = GlobalModelResponse.model_validate(gm)
            response.provider_count = provider_counts.get(gm.id, 0)
            response.active_provider_count = active_provider_counts.get(gm.id, 0)
            model_responses.append(response)

        return GlobalModelListResponse(
            models=model_responses,
            total=total,
        )


@dataclass
class AdminGetGlobalModelAdapter(AdminApiAdapter):
    """获取单个 GlobalModel"""

    global_model_id: str

    async def handle(self, context: ApiRequestContext) -> Any:  # type: ignore[override]
        from sqlalchemy import and_, case, func

        from src.models.database import Model, Provider

        global_model = GlobalModelService.get_global_model(context.db, self.global_model_id)
        stats = GlobalModelService.get_global_model_stats(context.db, self.global_model_id)

        # total_providers 已由 stats 提供，这里只查询活跃 provider 数量
        active_count = (
            context.db.query(
                func.count(
                    func.distinct(
                        case(
                            (
                                and_(
                                    Model.is_active.is_(True),
                                    Provider.is_active.is_(True),
                                ),
                                Model.provider_id,
                            ),
                            else_=None,
                        )
                    )
                )
            )
            .join(Provider, Model.provider_id == Provider.id)
            .filter(Model.global_model_id == global_model.id)
            .scalar()
            or 0
        )

        response = GlobalModelResponse.model_validate(global_model)
        response.provider_count = stats["total_providers"]
        response.active_provider_count = int(active_count)

        return GlobalModelWithStats(
            **response.model_dump(),
            total_models=stats["total_models"],
            total_providers=stats["total_providers"],
            price_range=stats["price_range"],
        )


@dataclass
class AdminCreateGlobalModelAdapter(AdminApiAdapter):
    """创建 GlobalModel"""

    payload: GlobalModelCreate

    async def handle(self, context: ApiRequestContext) -> Any:  # type: ignore[override]
        from src.core.exceptions import InvalidRequestException
        from src.core.model_permissions import validate_and_extract_model_mappings

        # 验证 model_mappings（如果有）
        is_valid, error, _ = validate_and_extract_model_mappings(self.payload.config)
        if not is_valid:
            raise InvalidRequestException(f"映射规则验证失败: {error}", "model_mappings")

        # 将 TieredPricingConfig 转换为 dict
        tiered_pricing_dict = self.payload.default_tiered_pricing.model_dump()

        global_model = GlobalModelService.create_global_model(
            db=context.db,
            name=self.payload.name,
            display_name=self.payload.display_name,
            is_active=self.payload.is_active,
            # 按次计费配置
            default_price_per_request=self.payload.default_price_per_request,
            # 阶梯计费配置
            default_tiered_pricing=tiered_pricing_dict,
            # Key 能力配置
            supported_capabilities=self.payload.supported_capabilities,
            # 模型配置（JSON）
            config=self.payload.config,
        )

        logger.info(f"GlobalModel 已创建: id={global_model.id} name={global_model.name}")

        # 创建成功后失效缓存（避免 mapping-preview 在 TTL 内读到旧结果）
        from src.services.cache.invalidation import get_cache_invalidation_service

        cache_service = get_cache_invalidation_service()
        await cache_service.on_global_model_changed(global_model.name, str(global_model.id))

        return GlobalModelResponse.model_validate(global_model)


@dataclass
class AdminUpdateGlobalModelAdapter(AdminApiAdapter):
    """更新 GlobalModel"""

    global_model_id: str
    payload: GlobalModelUpdate

    async def handle(self, context: ApiRequestContext) -> Any:  # type: ignore[override]
        from src.core.exceptions import InvalidRequestException
        from src.core.model_permissions import validate_and_extract_model_mappings

        # 验证 model_mappings（如果有）
        is_valid, error, _ = validate_and_extract_model_mappings(self.payload.config)
        if not is_valid:
            raise InvalidRequestException(f"映射规则验证失败: {error}", "model_mappings")

        # 使用行级锁获取旧的 GlobalModel 信息，防止并发更新导致的竞态条件
        # 设置 2 秒锁超时，允许短暂等待而非立即失败，提升并发操作的成功率
        from sqlalchemy import text
        from sqlalchemy.exc import OperationalError

        from src.models.database import GlobalModel

        try:
            # 设置会话级别的锁超时（仅影响当前事务）
            context.db.execute(text("SET LOCAL lock_timeout = '2s'"))
            old_global_model = (
                context.db.query(GlobalModel)
                .filter(GlobalModel.id == self.global_model_id)
                .with_for_update()
                .first()
            )
        except OperationalError as e:
            # 锁超时或锁冲突时返回友好的错误提示
            error_msg = str(e).lower()
            if "lock" in error_msg or "timeout" in error_msg:
                raise InvalidRequestException("该模型正在被其他操作更新，请稍后重试")
            raise
        old_model_name = old_global_model.name if old_global_model else None

        # 执行更新（此时仍持有行锁）
        global_model = GlobalModelService.update_global_model(
            db=context.db,
            global_model_id=self.global_model_id,
            update_data=self.payload,
        )

        logger.info(f"GlobalModel 已更新: id={global_model.id} name={global_model.name}")

        # 更新成功后才失效缓存（避免回滚时缓存已被清除的竞态问题）
        # 注意：此时事务已提交（由 pipeline 管理），数据已持久化
        from src.services.cache.invalidation import get_cache_invalidation_service

        cache_service = get_cache_invalidation_service()
        if old_model_name:
            await cache_service.on_global_model_changed(old_model_name, self.global_model_id)

        return GlobalModelResponse.model_validate(global_model)


@dataclass
class AdminDeleteGlobalModelAdapter(AdminApiAdapter):
    """删除 GlobalModel（级联删除所有关联的 Provider 模型实现）"""

    global_model_id: str

    async def handle(self, context: ApiRequestContext) -> Any:  # type: ignore[override]
        # 使用行级锁获取 GlobalModel 信息，防止并发操作导致的竞态条件
        # 设置 2 秒锁超时，允许短暂等待而非立即失败
        from sqlalchemy import text
        from sqlalchemy.exc import OperationalError

        from src.core.exceptions import InvalidRequestException
        from src.models.database import GlobalModel

        try:
            # 设置会话级别的锁超时（仅影响当前事务）
            context.db.execute(text("SET LOCAL lock_timeout = '2s'"))
            global_model = (
                context.db.query(GlobalModel)
                .filter(GlobalModel.id == self.global_model_id)
                .with_for_update()
                .first()
            )
        except OperationalError as e:
            # 锁超时或锁冲突时返回友好的错误提示
            error_msg = str(e).lower()
            if "lock" in error_msg or "timeout" in error_msg:
                raise InvalidRequestException("该模型正在被其他操作处理，请稍后重试")
            raise
        model_name = global_model.name if global_model else None
        model_id = global_model.id if global_model else self.global_model_id

        # 执行删除（此时仍持有行锁）
        GlobalModelService.delete_global_model(context.db, self.global_model_id)

        logger.info(f"GlobalModel 已删除: id={self.global_model_id}")

        # 删除成功后才失效缓存（避免回滚时缓存已被清除的竞态问题）
        from src.services.cache.invalidation import get_cache_invalidation_service

        cache_service = get_cache_invalidation_service()
        if model_name:
            await cache_service.on_global_model_changed(model_name, model_id)

        return None


@dataclass
class AdminBatchDeleteGlobalModelsAdapter(AdminApiAdapter):
    """批量删除多个 GlobalModel（顺序执行，每个删除独立提交）"""

    ids: list[str]

    async def handle(self, context: ApiRequestContext) -> Any:  # type: ignore[override]
        from src.core.exceptions import NotFoundException
        from src.models.database import GlobalModel

        success_count = 0
        failed: list[dict] = []
        deleted_names: list[tuple[str, str]] = []  # (name, id)

        for gm_id in self.ids:
            try:
                gm = context.db.query(GlobalModel).filter(GlobalModel.id == gm_id).first()
                if gm:
                    name = gm.name
                    mid = gm.id
                    GlobalModelService.delete_global_model(context.db, gm_id)
                    deleted_names.append((name, mid))
                    success_count += 1
                else:
                    failed.append({"id": gm_id, "error": "not found"})
            except NotFoundException:
                failed.append({"id": gm_id, "error": "not found"})
            except Exception as e:
                context.db.rollback()
                failed.append({"id": gm_id, "error": str(e)})

        # 批量失效缓存
        if deleted_names:
            from src.services.cache.invalidation import get_cache_invalidation_service

            cache_service = get_cache_invalidation_service()
            for name, mid in deleted_names:
                await cache_service.on_global_model_changed(name, mid)

        logger.info("批量删除 GlobalModel: success={}, failed={}", success_count, len(failed))

        return {"success_count": success_count, "failed": failed}


@dataclass
class AdminBatchAssignToProvidersAdapter(AdminApiAdapter):
    """批量为 Provider 添加 GlobalModel 实现"""

    global_model_id: str
    payload: BatchAssignToProvidersRequest

    async def handle(self, context: ApiRequestContext) -> Any:  # type: ignore[override]
        result = GlobalModelService.batch_assign_to_providers(
            db=context.db,
            global_model_id=self.global_model_id,
            provider_ids=self.payload.provider_ids,
            create_models=self.payload.create_models,
        )

        # 如果有成功创建的关联，清除 /v1/models 列表缓存
        if result["success"]:
            await invalidate_models_list_cache()

        logger.info(
            f"批量为 Provider 添加 GlobalModel: global_model_id={self.global_model_id} success={len(result['success'])} errors={len(result['errors'])}"
        )

        return BatchAssignToProvidersResponse(**result)


@dataclass
class AdminGetGlobalModelProvidersAdapter(AdminApiAdapter):
    """获取 GlobalModel 的所有关联提供商（包括非活跃的）"""

    global_model_id: str

    async def handle(self, context: ApiRequestContext) -> Any:  # type: ignore[override]
        from sqlalchemy.orm import joinedload

        from src.models.database import Model

        global_model = GlobalModelService.get_global_model(context.db, self.global_model_id)

        # 获取所有关联的 Model（包括非活跃的）
        models = (
            context.db.query(Model)
            .options(joinedload(Model.provider), joinedload(Model.global_model))
            .filter(Model.global_model_id == global_model.id)
            .all()
        )

        provider_entries = []
        for model in models:
            provider = model.provider
            if not provider:
                continue

            effective_tiered = model.get_effective_tiered_pricing()
            tier_count = len(effective_tiered.get("tiers", [])) if effective_tiered else 1

            provider_entries.append(
                ModelCatalogProviderDetail(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    model_id=model.id,
                    target_model=model.provider_model_name,
                    input_price_per_1m=model.get_effective_input_price(),
                    output_price_per_1m=model.get_effective_output_price(),
                    cache_creation_price_per_1m=model.get_effective_cache_creation_price(),
                    cache_read_price_per_1m=model.get_effective_cache_read_price(),
                    cache_1h_creation_price_per_1m=model.get_effective_1h_cache_creation_price(),
                    price_per_request=model.get_effective_price_per_request(),
                    effective_tiered_pricing=effective_tiered,
                    tier_count=tier_count,
                    supports_vision=model.get_effective_supports_vision(),
                    supports_function_calling=model.get_effective_supports_function_calling(),
                    supports_streaming=model.get_effective_supports_streaming(),
                    is_active=bool(model.is_active),
                )
            )

        return GlobalModelProvidersResponse(
            providers=provider_entries,
            total=len(provider_entries),
        )
