"""管理员代理节点（ProxyNode）管理端点

用于 aether-proxy 在 VPS 上注册、心跳、注销节点，以及管理员查看/删除节点记录。
"""

from __future__ import annotations

import ipaddress
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from src.api.base.admin_adapter import AdminApiAdapter
from src.api.base.context import ApiRequestContext
from src.api.base.pipeline import ApiRequestPipeline
from src.core.exceptions import InvalidRequestException, NotFoundException
from src.database import get_db
from src.models.database import ProxyNode, ProxyNodeStatus

router = APIRouter(prefix="/api/admin/proxy-nodes", tags=["Admin - Proxy Nodes"])
pipeline = ApiRequestPipeline()


def _node_to_dict(node: ProxyNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "name": node.name,
        "ip": node.ip,
        "port": node.port,
        "region": node.region,
        "status": node.status.value if node.status else None,
        "registered_by": node.registered_by,
        "last_heartbeat_at": node.last_heartbeat_at,
        "heartbeat_interval": node.heartbeat_interval,
        "active_connections": node.active_connections,
        "total_requests": node.total_requests,
        "avg_latency_ms": node.avg_latency_ms,
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }


class ProxyNodeRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="节点名")
    ip: str = Field(..., description="公网 IP（IPv4/IPv6）")
    port: int = Field(..., ge=1, le=65535, description="代理端口")
    region: str | None = Field(None, max_length=100, description="区域标签")
    heartbeat_interval: int = Field(30, ge=5, le=600, description="心跳间隔（秒）")

    # 指标（可选）
    active_connections: int | None = Field(None, ge=0, description="当前活跃连接数")
    total_requests: int | None = Field(None, ge=0, description="累计请求数")
    avg_latency_ms: float | None = Field(None, ge=0, description="平均延迟（毫秒）")

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        v = v.strip()
        try:
            ipaddress.ip_address(v)
        except ValueError as exc:
            raise ValueError("ip 必须是合法的 IPv4/IPv6 地址") from exc
        return v


class ProxyNodeHeartbeatRequest(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=36, description="节点 ID")
    heartbeat_interval: int | None = Field(None, ge=5, le=600, description="心跳间隔（秒）")

    active_connections: int | None = Field(None, ge=0, description="当前活跃连接数")
    total_requests: int | None = Field(None, ge=0, description="累计请求数")
    avg_latency_ms: float | None = Field(None, ge=0, description="平均延迟（毫秒）")


class ProxyNodeUnregisterRequest(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=36, description="节点 ID")


@router.post("/register")
async def register_proxy_node(request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = AdminRegisterProxyNodeAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.post("/heartbeat")
async def heartbeat_proxy_node(request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = AdminHeartbeatProxyNodeAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.post("/unregister")
async def unregister_proxy_node(request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = AdminUnregisterProxyNodeAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get("")
async def list_proxy_nodes(
    request: Request,
    status: str | None = Query(None, description="按状态筛选：online/unhealthy/offline"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> Any:
    adapter = AdminListProxyNodesAdapter(status=status, skip=skip, limit=limit)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.delete("/{node_id}")
async def delete_proxy_node(node_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = AdminDeleteProxyNodeAdapter(node_id=node_id)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        field = " -> ".join(str(x) for x in err.get("loc", []))
        msg = str(err.get("msg", "invalid"))
        parts.append(f"{field}: {msg}")
    return "; ".join(parts) or "输入验证失败"


@dataclass
class AdminRegisterProxyNodeAdapter(AdminApiAdapter):
    name: str = "admin_register_proxy_node"

    async def handle(self, context: ApiRequestContext) -> Any:
        payload = context.ensure_json_body()
        try:
            req = ProxyNodeRegisterRequest.model_validate(payload)
        except ValidationError as exc:
            raise InvalidRequestException("输入验证失败: " + _format_validation_error(exc))

        now = datetime.now(timezone.utc)

        node = (
            context.db.query(ProxyNode)
            .filter(ProxyNode.ip == req.ip, ProxyNode.port == req.port)
            .first()
        )
        if node:
            node.name = req.name
            node.region = req.region
            node.status = ProxyNodeStatus.ONLINE
            node.last_heartbeat_at = now
            node.heartbeat_interval = req.heartbeat_interval
            if req.active_connections is not None:
                node.active_connections = req.active_connections
            if req.total_requests is not None:
                node.total_requests = req.total_requests
            if req.avg_latency_ms is not None:
                node.avg_latency_ms = req.avg_latency_ms
        else:
            node = ProxyNode(
                id=str(uuid.uuid4()),
                name=req.name,
                ip=req.ip,
                port=req.port,
                region=req.region,
                status=ProxyNodeStatus.ONLINE,
                registered_by=context.user.id if context.user else None,
                last_heartbeat_at=now,
                heartbeat_interval=req.heartbeat_interval,
                active_connections=req.active_connections or 0,
                total_requests=req.total_requests or 0,
                avg_latency_ms=req.avg_latency_ms,
                created_at=now,
                updated_at=now,
            )
            context.db.add(node)

        context.db.commit()
        context.db.refresh(node)

        context.add_audit_metadata(
            action="proxy_node_register",
            proxy_node_id=node.id,
            proxy_node_ip=node.ip,
            proxy_node_port=node.port,
        )

        return {"node_id": node.id, "node": _node_to_dict(node)}


@dataclass
class AdminHeartbeatProxyNodeAdapter(AdminApiAdapter):
    name: str = "admin_heartbeat_proxy_node"

    async def handle(self, context: ApiRequestContext) -> Any:
        payload = context.ensure_json_body()
        try:
            req = ProxyNodeHeartbeatRequest.model_validate(payload)
        except ValidationError as exc:
            raise InvalidRequestException("输入验证失败: " + _format_validation_error(exc))

        node = context.db.query(ProxyNode).filter(ProxyNode.id == req.node_id).first()
        if not node:
            raise NotFoundException(f"ProxyNode {req.node_id} 不存在", "proxy_node")

        now = datetime.now(timezone.utc)
        node.status = ProxyNodeStatus.ONLINE
        node.last_heartbeat_at = now
        if req.heartbeat_interval is not None:
            node.heartbeat_interval = req.heartbeat_interval
        if req.active_connections is not None:
            node.active_connections = req.active_connections
        if req.total_requests is not None:
            node.total_requests = req.total_requests
        if req.avg_latency_ms is not None:
            node.avg_latency_ms = req.avg_latency_ms

        context.db.commit()
        context.db.refresh(node)

        context.add_audit_metadata(
            action="proxy_node_heartbeat",
            proxy_node_id=node.id,
        )

        return {"message": "heartbeat ok", "node": _node_to_dict(node)}


@dataclass
class AdminUnregisterProxyNodeAdapter(AdminApiAdapter):
    name: str = "admin_unregister_proxy_node"

    async def handle(self, context: ApiRequestContext) -> Any:
        payload = context.ensure_json_body()
        try:
            req = ProxyNodeUnregisterRequest.model_validate(payload)
        except ValidationError as exc:
            raise InvalidRequestException("输入验证失败: " + _format_validation_error(exc))

        node = context.db.query(ProxyNode).filter(ProxyNode.id == req.node_id).first()
        if not node:
            raise NotFoundException(f"ProxyNode {req.node_id} 不存在", "proxy_node")

        node.status = ProxyNodeStatus.OFFLINE
        node.updated_at = datetime.now(timezone.utc)
        context.db.commit()

        context.add_audit_metadata(
            action="proxy_node_unregister",
            proxy_node_id=node.id,
        )

        return {"message": "unregistered", "node_id": node.id}


@dataclass
class AdminListProxyNodesAdapter(AdminApiAdapter):
    name: str = "admin_list_proxy_nodes"
    status: str | None = None
    skip: int = 0
    limit: int = 100

    async def handle(self, context: ApiRequestContext) -> Any:
        query = context.db.query(ProxyNode)
        if self.status:
            normalized = self.status.strip().lower()
            allowed = {"online", "unhealthy", "offline"}
            if normalized not in allowed:
                raise InvalidRequestException(f"status 必须是以下之一: {sorted(allowed)}", "status")
            query = query.filter(ProxyNode.status == ProxyNodeStatus(normalized))

        total = query.count()
        nodes = (
            query.order_by(ProxyNode.updated_at.desc()).offset(self.skip).limit(self.limit).all()
        )
        return {
            "items": [_node_to_dict(n) for n in nodes],
            "total": total,
            "skip": self.skip,
            "limit": self.limit,
        }


@dataclass
class AdminDeleteProxyNodeAdapter(AdminApiAdapter):
    name: str = "admin_delete_proxy_node"
    node_id: str = ""

    async def handle(self, context: ApiRequestContext) -> Any:
        node = context.db.query(ProxyNode).filter(ProxyNode.id == self.node_id).first()
        if not node:
            raise NotFoundException(f"ProxyNode {self.node_id} 不存在", "proxy_node")

        context.add_audit_metadata(
            action="proxy_node_delete",
            proxy_node_id=node.id,
            proxy_node_ip=node.ip,
            proxy_node_port=node.port,
        )

        context.db.delete(node)
        context.db.commit()

        return {"message": "deleted", "node_id": self.node_id}
