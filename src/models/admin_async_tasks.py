from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderRefreshSyncJobStartResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    message: str = ""


class ProviderRefreshSyncJobStatusResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    message: str = ""
    scope: str
    provider_id: str | None = None
    provider_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    result: dict | None = None


class ProviderRefreshSyncJobListResponse(BaseModel):
    items: list[ProviderRefreshSyncJobStatusResponse] = Field(default_factory=list)
    total: int = 0


class ProviderProxyProbeJobStartResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    message: str = ""


class ProviderProxyProbeJobStatusResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    message: str = ""
    scope: str
    provider_id: str | None = None
    provider_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    result: dict | None = None


class ProviderProxyProbeJobListResponse(BaseModel):
    items: list[ProviderProxyProbeJobStatusResponse] = Field(default_factory=list)
    total: int = 0


class AdminAsyncTaskItem(BaseModel):
    id: str
    task_type: str
    status: str
    stage: str
    title: str
    summary: str = ""
    provider_id: str | None = None
    provider_name: str | None = None
    model: str | None = None
    progress_percent: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    source_task_id: str


class AdminAsyncTaskDetail(AdminAsyncTaskItem):
    detail: dict | None = None


class AdminAsyncTaskListResponse(BaseModel):
    items: list[AdminAsyncTaskItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 0


class AdminAsyncTaskStatsResponse(BaseModel):
    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_task_type: dict[str, int] = Field(default_factory=dict)
    today_count: int = 0
    processing_count: int = 0
