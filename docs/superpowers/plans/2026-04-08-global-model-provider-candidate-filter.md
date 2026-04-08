# GlobalModel Provider Candidate Filter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让模型管理页在给某个 GlobalModel 关联 Provider 时，能够按缓存上游模型判断候选 Provider 的支持情况，并提供按渠道商/按模型双视角筛选与手动刷新。

**Architecture:** 新增一个 GlobalModel 专用 Provider 候选接口和刷新接口，前端新增独立候选器弹窗组件，`ModelManagement.vue` 只负责打开弹窗和提交关联。默认只读缓存，不自动刷新；点击“刷新支持情况”后再批量刷新当前候选 Provider 的上游模型支持情况。

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, TypeScript, 现有 admin API client, 现有 Provider 上游模型缓存能力

---

## Chunk 1: Backend Candidate API

### Task 1: 定义候选 Provider 的后端响应模型

**Files:**
- Modify: `src/models/pydantic_models.py`
- Test: `tests/api/test_global_model_provider_candidates.py`

- [ ] **Step 1: 写失败测试，定义候选接口的返回结构**

Run: `uv run python -m pytest tests/api/test_global_model_provider_candidates.py -k structure`
Expected: FAIL，缺少接口或响应字段

- [ ] **Step 2: 在 `src/models/pydantic_models.py` 新增候选响应模型**

新增：
- `GlobalModelProviderCandidate`
- `GlobalModelProviderCandidatesResponse`
- `RefreshGlobalModelProviderCandidatesRequest`

- [ ] **Step 3: 运行测试确认仍按预期失败或进入下一缺口**

Run: `uv run python -m pytest tests/api/test_global_model_provider_candidates.py -k structure`
Expected: FAIL 从“缺少模型”推进到“缺少接口实现”


### Task 2: 实现 GlobalModel Provider 候选接口

**Files:**
- Modify: `src/api/admin/models/global_models.py`
- Test: `tests/api/test_global_model_provider_candidates.py`

- [ ] **Step 1: 写失败测试，覆盖 `matched/not_matched/unknown/already_linked`**

场景：
- Provider 已关联当前 GlobalModel
- Provider 有缓存上游模型且命中当前模型
- Provider 有缓存但不命中
- Provider 没有缓存

- [ ] **Step 2: 为 `global_models.py` 增加 `GET /{global_model_id}/provider-candidates`**

实现要求：
- 拉取 Provider 列表
- 拉取当前 GlobalModel 已关联的 Provider 集合
- 读取 Provider 的缓存上游模型
- 计算 `already_linked` 和 `match_status`

- [ ] **Step 3: 运行定向测试确认通过**

Run: `uv run python -m pytest tests/api/test_global_model_provider_candidates.py -k candidates`
Expected: PASS


### Task 3: 实现“刷新支持情况”接口

**Files:**
- Modify: `src/api/admin/models/global_models.py`
- Test: `tests/api/test_global_model_provider_candidates.py`

- [ ] **Step 1: 写失败测试，覆盖只刷新指定 Provider**

Run: `uv run python -m pytest tests/api/test_global_model_provider_candidates.py -k refresh`
Expected: FAIL

- [ ] **Step 2: 增加 `POST /{global_model_id}/provider-candidates/refresh`**

实现要求：
- 接收 `provider_ids`
- 仅刷新指定 Provider 的上游模型支持情况
- 返回更新后的候选结果

- [ ] **Step 3: 运行定向测试确认通过**

Run: `uv run python -m pytest tests/api/test_global_model_provider_candidates.py -k refresh`
Expected: PASS

## Chunk 2: Frontend Candidate Dialog

### Task 4: 定义前端候选器类型与 API client

**Files:**
- Modify: `frontend/src/api/endpoints/types/model.ts`
- Modify: `frontend/src/api/endpoints/global-models.ts`
- Test: `frontend/src/features/models/utils/__tests__/global-model-provider-candidates.spec.ts`

- [ ] **Step 1: 写失败测试，定义筛选和分组需要的最小类型输入**

Run: `npm run test:run -- src/features/models/utils/__tests__/global-model-provider-candidates.spec.ts`
Expected: FAIL

- [ ] **Step 2: 新增前端候选器类型与 API 方法**

新增：
- 候选 Provider 类型
- 候选结果响应类型
- 获取候选接口 client
- 刷新候选接口 client

- [ ] **Step 3: 运行测试确认进入下一缺口**

Run: `npm run test:run -- src/features/models/utils/__tests__/global-model-provider-candidates.spec.ts`
Expected: FAIL 从“缺少类型”推进到“缺少过滤逻辑”


### Task 5: 抽离候选器过滤与分组工具

**Files:**
- Create: `frontend/src/features/models/utils/global-model-provider-candidates.ts`
- Create: `frontend/src/features/models/utils/__tests__/global-model-provider-candidates.spec.ts`

- [ ] **Step 1: 写失败测试，覆盖以下逻辑**

覆盖：
- 普通搜索命中 Provider 名 / URL / 缓存模型名
- 正则搜索命中
- 非法正则返回错误
- `按渠道商` 视角下的过滤结果
- `按模型` 视角下的分组结果
- 全选只作用于当前筛选结果

- [ ] **Step 2: 写最小实现**

实现：
- `buildProviderCandidateSearchText`
- `filterProviderCandidates`
- `groupCandidatesByModel`
- `getSelectableCandidateIds`

- [ ] **Step 3: 运行测试确认通过**

Run: `npm run test:run -- src/features/models/utils/__tests__/global-model-provider-candidates.spec.ts`
Expected: PASS


### Task 6: 新建候选器弹窗组件

**Files:**
- Create: `frontend/src/features/models/components/GlobalModelProviderCandidatesDialog.vue`
- Modify: `frontend/src/features/models/components/index.ts`（如存在导出入口）
- Modify: `frontend/src/views/admin/ModelManagement.vue`

- [ ] **Step 1: 先在组件中接入静态/假数据渲染骨架**

内容：
- 搜索框
- 视角切换
- 正则开关
- 刷新按钮
- 全选按钮
- Provider 行展开

- [ ] **Step 2: 接入真实候选接口**

要求：
- 打开弹窗时加载缓存候选数据
- 不自动刷新远端支持情况
- 维护本地选择状态

- [ ] **Step 3: 接入“刷新支持情况”按钮**

要求：
- 默认只刷新当前筛选结果
- 刷新中给按钮 loading 态

- [ ] **Step 4: 把 `ModelManagement.vue` 的旧 Provider 选择列表替换为新组件**

要求：
- 仍复用现有 `batchAssignToProviders()` 提交
- 保持已有“保存 / 关闭 / 同步选择状态”语义

- [ ] **Step 5: 跑类型检查**

Run: `npm run type-check`
Expected: PASS

## Chunk 3: Integration and Verification

### Task 7: 补后端集成验证

**Files:**
- Test: `tests/api/test_global_model_provider_candidates.py`

- [ ] **Step 1: 跑完整后端定向测试**

Run: `uv run python -m pytest tests/api/test_global_model_provider_candidates.py`
Expected: PASS


### Task 8: 补前端集成验证

**Files:**
- Modify: `frontend/src/views/admin/ModelManagement.vue`
- Test: `frontend/src/features/models/utils/__tests__/global-model-provider-candidates.spec.ts`

- [ ] **Step 1: 跑前端定向测试**

Run: `npm run test:run -- src/features/models/utils/__tests__/global-model-provider-candidates.spec.ts`
Expected: PASS

- [ ] **Step 2: 跑类型检查**

Run: `npm run type-check`
Expected: PASS


### Task 9: 更新状态文档并提交

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: 更新 `STATUS.md`**

补充：
- 本轮目标
- 已完成项
- 验证命令
- 剩余边界

- [ ] **Step 2: 提交本轮改动**

建议消息：
`✨ feat(model-management): 增强全局模型关联 Provider 候选筛选`
