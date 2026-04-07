# Aether All-in-Hub Reissue Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 围绕真实 `all-in-hub` 备份文件，把 `pending_import` / `pending_reissue` 任务尽可能补成可用的 Aether 渠道，并在成功后自动回填真实 Key 与上游模型。

**Architecture:** 保持现有“静态导入 + pending task”主线不变，新增一个独立的任务执行服务，先从 `ProviderImportTask` 读取待处理来源，按站点识别控制面类型，通过 API 或站点管理接口创建 replacement Key，再把明文 Key 回填成 `ProviderAPIKey` 并执行模型获取。第一阶段只围绕这份真实备份文件覆盖最常见站点，不先抽象成通用浏览器自动化平台。

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, httpx, pytest

---

## Chunk 1: Site Inventory

### Task 1: 先识别这份真实备份文件里的主流站点模式

**Files:**
- Create: `tests/services/test_all_in_hub_reissue.py`
- Modify: `src/services/provider_import/all_in_hub.py`
- Create: `src/services/provider_import/reissue.py`

- [ ] **Step 1: 写站点识别失败测试**

```python
def test_detect_site_strategy_for_real_backup_patterns() -> None:
    ...
```

- [ ] **Step 2: 跑单测确认失败**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: FAIL with missing reissue strategy detection

- [ ] **Step 3: 写最小站点策略识别实现**

```python
def detect_reissue_strategy(task: ProviderImportTask) -> SiteStrategy:
    ...
```

- [ ] **Step 4: 跑单测确认转绿**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

## Chunk 2: Reissue Execution

### Task 2: 先把 pending task 执行成真实 ProviderAPIKey

**Files:**
- Modify: `src/services/provider_import/reissue.py`
- Modify: `src/models/database.py`
- Modify: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写 pending_reissue 成功回填真实 Key 的失败测试**

```python
async def test_execute_pending_reissue_creates_provider_api_key() -> None:
    ...
```

- [ ] **Step 2: 跑单测确认失败**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: FAIL with missing executor behavior

- [ ] **Step 3: 写最小执行器实现**

```python
async def execute_import_task(...):
    ...
```

- [ ] **Step 4: 跑单测确认转绿**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

### Task 3: 补幂等与失败状态

**Files:**
- Modify: `src/services/provider_import/reissue.py`
- Modify: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写“重复执行不重复建 Key、失败会写 last_error”失败测试**

```python
async def test_execute_import_task_is_idempotent_and_records_failures() -> None:
    ...
```

- [ ] **Step 2: 跑单测确认失败**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: FAIL with duplicate handling / error state missing

- [ ] **Step 3: 写最小幂等和失败状态实现**

```python
if existing_key:
    ...
task.status = "failed"
```

- [ ] **Step 4: 跑单测确认转绿**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

## Chunk 3: Model Verification

### Task 4: Key 回填后立即拉上游模型

**Files:**
- Modify: `src/services/provider_import/reissue.py`
- Modify: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写“成功补钥后会触发模型获取并更新任务状态”失败测试**

```python
async def test_execute_import_task_fetches_models_after_key_creation() -> None:
    ...
```

- [ ] **Step 2: 跑单测确认失败**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: FAIL with missing model verification

- [ ] **Step 3: 写最小模型拉取与成功状态实现**

```python
await run_create_key_side_effects(...)
task.status = "completed"
```

- [ ] **Step 4: 跑单测确认转绿**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

## Chunk 4: Admin Trigger

### Task 5: 增加后台执行入口

**Files:**
- Modify: `src/api/admin/providers/routes.py`
- Modify: `src/models/provider_import.py`
- Modify: `tests/api/test_admin_all_in_hub_import_routes.py`

- [ ] **Step 1: 写执行 pending task 的路由失败测试**

```python
def test_execute_all_in_hub_pending_tasks_route_returns_service_payload() -> None:
    ...
```

- [ ] **Step 2: 跑路由测试确认失败**

Run: `pytest tests/api/test_admin_all_in_hub_import_routes.py -q`
Expected: FAIL with missing execute route

- [ ] **Step 3: 实现最小后台触发入口**

```python
@router.post("/imports/all-in-hub/tasks/execute")
async def execute_all_in_hub_tasks(...):
    ...
```

- [ ] **Step 4: 跑路由测试确认转绿**

Run: `pytest tests/api/test_admin_all_in_hub_import_routes.py -q`
Expected: PASS

## Chunk 5: Verification

### Task 6: 做最终验证

**Files:**
- Modify: `src/services/provider_import/reissue.py`
- Modify: `src/api/admin/providers/routes.py`
- Modify: `tests/services/test_all_in_hub_reissue.py`
- Modify: `tests/api/test_admin_all_in_hub_import_routes.py`

- [ ] **Step 1: 跑后端定向测试**

Run: `pytest tests/services/test_all_in_hub_import.py tests/services/test_all_in_hub_reissue.py tests/api/test_admin_all_in_hub_import_routes.py -q`
Expected: PASS

- [ ] **Step 2: 跑前端类型检查**

Run: `cd frontend && npm exec --yes vue-tsc -- --noEmit`
Expected: PASS

- [ ] **Step 3: 用真实备份文件做一次最小实操**

Run: 针对 `/Users/zbs/Downloads/all-api-hub-backup-2026-04-05.json` 跑 preview/import/task execute，并记录成功补钥数、失败数、模型获取数
Expected: 能输出真实成功/失败分布，而不是只给静态统计
