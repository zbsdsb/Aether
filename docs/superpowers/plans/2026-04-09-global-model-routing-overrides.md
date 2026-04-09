# Global Model Routing Overrides Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在模型管理抽屉页为当前 `GlobalModel` 增加 Provider/Key 优先级覆盖，并让真实调度优先读取模型覆盖、缺失时回退全局配置；其中 `provider` 模式覆盖 Provider 优先级与 Key 内部优先级，`global_key` 模式覆盖格式级 Key 优先级。

**Architecture:** 复用 `GlobalModel.config.routing_overrides` 作为模型级持久化容器，不新建表。后端扩展 routing preview 与 scheduler 排序逻辑，前端在现有 `RoutingTab` 内增加编辑/恢复默认/保存能力，并区分 `provider`/`global_key` 两种模式下的不同编辑字段。

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, TypeScript, Vitest, Pytest

---

## Chunk 1: Backend Override Semantics

### Task 1: 锁定 candidate sorter 的模型级覆盖排序

**Files:**
- Modify: `src/services/scheduling/candidate_sorter.py`
- Test: `tests/unit/test_candidate_sorter_model_routing_overrides.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

### Task 2: 锁定 routing preview 的覆盖值与生效值

**Files:**
- Modify: `src/api/admin/models/routing.py`
- Modify: `frontend/src/api/endpoints/types/routing.ts`
- Test: `tests/api/test_global_model_routing_overrides.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

## Chunk 2: Frontend Editing Flow

### Task 3: 抽取模型级覆盖编辑工具函数

**Files:**
- Create: `frontend/src/features/models/utils/routing-overrides.ts`
- Test: `frontend/src/features/models/utils/__tests__/routing-overrides.spec.ts`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

### Task 4: 在模型链路控制页接入编辑/保存

**Files:**
- Modify: `frontend/src/features/models/components/RoutingTab.vue`
- Modify: `frontend/src/features/models/components/ModelDetailDrawer.vue`
- Modify: `frontend/src/api/endpoints/global-models.ts`

- [ ] **Step 1: 接入编辑态与恢复默认交互**
- [ ] **Step 2: 接入保存 payload 到 `updateGlobalModel()`**
- [ ] **Step 3: Run targeted frontend tests and type-check**

## Chunk 3: Verification And State

### Task 5: 运行定向验证并更新状态文件

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Run `uv run python -m pytest tests/unit/test_candidate_sorter_model_routing_overrides.py tests/api/test_global_model_routing_overrides.py`**
- [ ] **Step 2: Run `npm run test:run -- src/features/models/utils/__tests__/routing-overrides.spec.ts`**
- [ ] **Step 3: Run `npm exec --yes vue-tsc -- --noEmit`**
- [ ] **Step 4: 更新 `STATUS.md` 记录结果**
