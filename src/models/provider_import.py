from __future__ import annotations

from pydantic import BaseModel, Field


class AllInHubImportRequest(BaseModel):
    content: str = Field(..., min_length=1, description="all-in-hub 导出内容（JSON 字符串）")


class AllInHubTaskExecuteRequest(BaseModel):
    limit: int = Field(20, ge=1, le=200, description="本次最多执行的 pending task 数量")


class AllInHubImportStats(BaseModel):
    providers_total: int = 0
    providers_to_create: int = 0
    providers_created: int = 0
    providers_reused: int = 0
    endpoints_to_create: int = 0
    endpoints_created: int = 0
    endpoints_reused: int = 0
    direct_keys_ready: int = 0
    pending_sources: int = 0
    pending_tasks_to_create: int = 0
    pending_tasks_created: int = 0
    pending_tasks_reused: int = 0
    keys_created: int = 0
    keys_skipped: int = 0


class AllInHubImportProviderSummary(BaseModel):
    provider_name: str
    provider_website: str
    endpoint_base_url: str
    direct_key_count: int = 0
    pending_source_count: int = 0
    existing_provider: bool = False
    existing_endpoint: bool = False


class AllInHubImportResponse(BaseModel):
    dry_run: bool
    version: str = ""
    stats: AllInHubImportStats = Field(default_factory=AllInHubImportStats)
    warnings: list[str] = Field(default_factory=list)
    providers: list[AllInHubImportProviderSummary] = Field(default_factory=list)


class AllInHubTaskExecutionItem(BaseModel):
    task_id: str
    status: str
    stage: str | None = None
    last_error: str | None = None
    key_created: bool = False
    result_key_id: str | None = None


class AllInHubTaskExecutionResponse(BaseModel):
    total_selected: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    keys_created: int = 0
    results: list[AllInHubTaskExecutionItem] = Field(default_factory=list)
