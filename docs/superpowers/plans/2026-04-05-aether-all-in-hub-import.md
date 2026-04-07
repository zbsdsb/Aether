# Aether All-in-Hub Import Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Aether 增加第一阶段 `all-in-hub` 静态导入能力，支持预览与正式导入，并把缺少明文 Key 的来源显式报告出来。

**Architecture:** 后端新增一个独立的 `all-in-hub` 解析与导入服务，先把真实 v1/v2 导出格式收敛为统一的导入记录，再执行“按站点聚合 Provider、创建 `openai:chat` Endpoint、导入明文 API Key、报告待补钥来源”的流程。前端在 Provider 管理页增加一个导入对话框，复用现有 JSON 导入组件与确认式预览交互。

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, Vue 3, TypeScript, pytest

---

## Chunk 1: Backend Import Service

### Task 1: 先写解析与预览测试

**Files:**
- Create: `tests/services/test_all_in_hub_import.py`
- Create: `src/services/provider_import/all_in_hub.py`

- [ ] **Step 1: 写 v2 导出解析与预览统计失败测试**

```python
def test_preview_counts_direct_and_pending_records() -> None:
    ...
```

- [ ] **Step 2: 跑单测确认失败**

Run: `pytest tests/services/test_all_in_hub_import.py -q`
Expected: FAIL with missing import service / missing parser behavior

- [ ] **Step 3: 写最小解析与预览实现**

```python
def preview_all_in_hub_import(...):
    ...
```

- [ ] **Step 4: 跑单测确认转绿**

Run: `pytest tests/services/test_all_in_hub_import.py -q`
Expected: PASS

### Task 2: 实现正式导入与幂等逻辑

**Files:**
- Modify: `src/services/provider_import/all_in_hub.py`
- Modify: `tests/services/test_all_in_hub_import.py`

- [ ] **Step 1: 写 Provider/Endpoint/Key 创建与幂等跳过失败测试**

```python
def test_execute_import_creates_provider_endpoint_and_key_once() -> None:
    ...
```

- [ ] **Step 2: 跑单测确认失败**

Run: `pytest tests/services/test_all_in_hub_import.py -q`
Expected: FAIL with missing execution behavior

- [ ] **Step 3: 写最小导入执行实现**

```python
def execute_all_in_hub_import(...):
    ...
```

- [ ] **Step 4: 跑单测确认转绿**

Run: `pytest tests/services/test_all_in_hub_import.py -q`
Expected: PASS

## Chunk 2: Admin API

### Task 3: 增加 preview/import 路由

**Files:**
- Create: `src/models/provider_import.py`
- Modify: `src/api/admin/providers/routes.py`
- Create: `tests/api/test_admin_all_in_hub_import_routes.py`

- [ ] **Step 1: 写 preview/import 路由失败测试**

```python
def test_preview_all_in_hub_import_route_returns_service_payload() -> None:
    ...
```

- [ ] **Step 2: 跑路由测试确认失败**

Run: `pytest tests/api/test_admin_all_in_hub_import_routes.py -q`
Expected: FAIL with missing route

- [ ] **Step 3: 实现请求/响应模型与路由适配器**

```python
@router.post("/imports/all-in-hub/preview")
async def preview_all_in_hub_import(...):
    ...
```

- [ ] **Step 4: 跑路由测试确认转绿**

Run: `pytest tests/api/test_admin_all_in_hub_import_routes.py -q`
Expected: PASS

## Chunk 3: Frontend Entry

### Task 4: Provider 管理页导入入口

**Files:**
- Create: `frontend/src/features/providers/components/AllInHubImportDialog.vue`
- Modify: `frontend/src/features/providers/components/index.ts`
- Modify: `frontend/src/features/providers/components/ProviderTableHeader.vue`
- Modify: `frontend/src/views/admin/ProviderManagement.vue`
- Modify: `frontend/src/api/endpoints/providers.ts`

- [ ] **Step 1: 补前端 API 调用**

```ts
export async function previewAllInHubImport(...)
export async function importAllInHub(...)
```

- [ ] **Step 2: 新增导入对话框**

```vue
<JsonImportInput ... />
```

- [ ] **Step 3: 在 Provider 管理页接入按钮、预览与确认导入**

```ts
const allInHubImportDialogOpen = ref(false)
```

- [ ] **Step 4: 跑前端类型检查或最小构建校验**

Run: `cd frontend && npm run type-check`
Expected: PASS

## Chunk 4: Verification

### Task 5: 做最终验证

**Files:**
- Modify: `src/services/provider_import/all_in_hub.py`
- Modify: `src/api/admin/providers/routes.py`
- Modify: `frontend/src/features/providers/components/AllInHubImportDialog.vue`
- Modify: `frontend/src/views/admin/ProviderManagement.vue`

- [ ] **Step 1: 跑后端测试**

Run: `pytest tests/services/test_all_in_hub_import.py tests/api/test_admin_all_in_hub_import_routes.py -q`
Expected: PASS

- [ ] **Step 2: 跑前端类型检查**

Run: `cd frontend && npm run type-check`
Expected: PASS

- [ ] **Step 3: 回读实现边界**

Run: `rg -n "all-in-hub|AllInHub" src frontend/src tests`
Expected: 能看到 service、route、dialog 与 tests 全部落地
