from __future__ import annotations

from pydantic import BaseModel, Field


class AllInHubImportRequest(BaseModel):
    content: str = Field(..., min_length=1, description="all-in-hub 导出内容（JSON 字符串）")


class AllInHubTaskExecuteRequest(BaseModel):
    limit: int = Field(20, ge=1, le=200, description="本次最多执行的 pending task 数量")


class AllInHubTaskSubmitPlaintextRequest(BaseModel):
    api_key: str = Field(..., min_length=1, description="外部补抓到的明文 Key")
    token_name: str | None = Field(default=None, description="上游 token 名称（可选）")
    token_id: str | None = Field(default=None, description="上游 token ID（可选）")
    note: str | None = Field(default=None, description="补抓说明（可选）")


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
    task_type: str | None = None
    site_type: str | None = None
    auth_type: str | None = None
    has_access_token: bool = False
    has_session_cookie: bool = False
    action_required: str | None = None
    plaintext_capture_status: str | None = None
    masked_key_preview: str | None = None


class AllInHubTaskExecutionResponse(BaseModel):
    total_selected: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    keys_created: int = 0
    results: list[AllInHubTaskExecutionItem] = Field(default_factory=list)
