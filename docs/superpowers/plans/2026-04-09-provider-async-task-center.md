# Provider Async Task Center Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 provider import 与 provider refresh/sync 统一纳入管理端异步任务中心，并提供顶部通知入口。

**Architecture:** 保留现有 `video_tasks` 表与 All-in-Hub Redis job，不做数据库迁移；新增一层“管理端异步任务聚合模型 + API”，把视频任务、导入任务、Provider 刷新并适配任务汇总成同一份列表/统计/通知数据。Provider 刷新并适配新增 Redis 后台 job，与现有导入 job 采用一致的 task status/stage 语义，前端 `AsyncTasks.vue` 与 `MainLayout.vue` 只消费聚合后的通用任务接口。

**Tech Stack:** FastAPI, SQLAlchemy, Redis, Vue 3, TypeScript, Vitest, pytest

---

### Task 1: 定义统一异步任务聚合契约

**Files:**
- Create: `src/models/admin_async_tasks.py`
- Modify: `frontend/src/api/async-tasks.ts`
- Test: `tests/api/test_admin_async_tasks_routes.py`

- [ ] **Step 1: 写失败测试，锁定聚合任务响应结构**

Run: `uv run python -m pytest tests/api/test_admin_async_tasks_routes.py -q`
Expected: FAIL because unified async task route/model does not exist yet.

- [ ] **Step 2: 定义后端聚合 Pydantic 模型**

Create a focused response contract for:
- task list item
- task stats
- provider-task specific detail payload

- [ ] **Step 3: 扩展前端 async task 类型定义**

Add provider-import / provider-refresh-sync task types and their metadata shape.

- [ ] **Step 4: 运行测试确认契约落地**

Run: `uv run python -m pytest tests/api/test_admin_async_tasks_routes.py -q`
Expected: route/model contract tests pass.

### Task 2: 为 Provider refresh/sync 引入后台任务

**Files:**
- Create: `src/services/provider_query/async_job.py`
- Modify: `src/api/admin/provider_query.py`
- Test: `tests/api/test_admin_provider_query_async_tasks.py`

- [ ] **Step 1: 写失败测试，覆盖单 Provider 与批量 refresh-sync submit/status/list**

Run: `uv run python -m pytest tests/api/test_admin_provider_query_async_tasks.py -q`
Expected: FAIL because submit/list/status endpoints are missing.

- [ ] **Step 2: 实现 Redis 后台 job runner**

Mirror the existing all-in-hub job lifecycle:
- submit returns `task_id`
- runner stores `status/stage/message`
- single/all refresh share one task type with different scope metadata

- [ ] **Step 3: 将现有同步 refresh 接口改为 submit/poll 模式**

Keep the current refresh logic reusable internally, but expose async submit endpoints for admin UI.

- [ ] **Step 4: 运行测试确认 submit/status/list 行为**

Run: `uv run python -m pytest tests/api/test_admin_provider_query_async_tasks.py -q`
Expected: PASS

### Task 3: 提供统一异步任务聚合 API

**Files:**
- Create: `src/api/admin/async_tasks/routes.py`
- Modify: `src/api/admin/video_tasks/routes.py`
- Modify: `src/api/admin/__init__.py` or router registration site
- Test: `tests/api/test_admin_async_tasks_routes.py`

- [ ] **Step 1: 写失败测试，覆盖 unified list/stats/detail 聚合**

Run: `uv run python -m pytest tests/api/test_admin_async_tasks_routes.py -q`
Expected: FAIL because provider import/provider refresh tasks are absent from admin async task API.

- [ ] **Step 2: 实现聚合器**

Aggregate:
- video tasks from DB
- all-in-hub import jobs from Redis
- provider refresh/sync jobs from Redis

- [ ] **Step 3: 保持旧页面兼容**

Do not remove `/api/admin/video-tasks`; the new `/api/admin/async-tasks` becomes the admin unified source.

- [ ] **Step 4: 跑后端聚合测试**

Run: `uv run python -m pytest tests/api/test_admin_async_tasks_routes.py tests/api/test_admin_provider_query_async_tasks.py -q`
Expected: PASS

### Task 4: 接入管理端页面与通知入口

**Files:**
- Modify: `frontend/src/views/admin/AsyncTasks.vue`
- Modify: `frontend/src/api/async-tasks.ts`
- Modify: `frontend/src/features/providers/components/ProviderDetailDrawer.vue`
- Modify: `frontend/src/views/admin/ProviderManagement.vue`
- Modify: `frontend/src/layouts/MainLayout.vue`
- Test: `frontend/src/features/providers/utils/__tests__/upstream-refresh.spec.ts`
- Test: `frontend/src/views/admin/__tests__/async-task-center.spec.ts`

- [ ] **Step 1: 写失败测试，覆盖 provider task 显示与通知摘要**

Run: `cd frontend && npm run test:run -- src/views/admin/__tests__/async-task-center.spec.ts`
Expected: FAIL because unified async task/task notification rendering does not exist.

- [ ] **Step 2: 改造 AsyncTasks 页面消费统一接口**

Render task type label, stage, provider-specific metadata, and links back to Provider / Import Task page.

- [ ] **Step 3: 将 Provider refresh 按钮改成异步 submit + poll/toast**

`刷新并适配` 与 `刷新全部渠道能力` should no longer block for the full server-side run.

- [ ] **Step 4: 在 MainLayout 增加顶部任务通知入口**

Show running/failed provider tasks and links to `/admin/async-tasks` or task-specific destinations.

- [ ] **Step 5: 跑前端测试与 type-check**

Run:
- `cd frontend && npm run test:run -- src/features/providers/utils/__tests__/upstream-refresh.spec.ts src/views/admin/__tests__/async-task-center.spec.ts`
- `cd frontend && npm exec --yes vue-tsc -- --noEmit`
Expected: PASS

### Task 5: 回归验证与状态更新

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: 跑后端针对性验证**

Run:
- `uv run python -m pytest tests/api/test_admin_async_tasks_routes.py tests/api/test_admin_provider_query_async_tasks.py tests/api/test_admin_all_in_hub_import_routes.py tests/services/test_provider_summary_import_tasks.py -q`

- [ ] **Step 2: 跑前端针对性验证**

Run:
- `cd frontend && npm run test:run -- src/features/providers/utils/__tests__/upstream-refresh.spec.ts src/views/admin/__tests__/async-task-center.spec.ts`
- `cd frontend && npm exec --yes vue-tsc -- --noEmit`

- [ ] **Step 3: 更新 `STATUS.md`**

Record:
- 完成的 phase 1 统一任务中心范围
- 仍未覆盖的边界
- 验证结果
