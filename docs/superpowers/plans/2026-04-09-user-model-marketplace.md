# User Model Marketplace Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在用户侧新增一个基于真实数据的模型广场页面 `/dashboard/model-marketplace`，展示用户可访问模型的来源覆盖、成功率、平均延迟、能力、标签、推荐/最稳徽标与价格摘要。

**Architecture:** 后端新增一个用户侧模型广场聚合服务，复用现有可访问模型权限判定，再按模型聚合 Provider / Endpoint / RequestCandidate 指标，并生成标签与轻量推荐结论；前端新增独立卡片页与详情抽屉，不替换现有模型目录页，而是在导航中并列提供“模型广场”和“模型目录”两个入口。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, TypeScript, Vitest, 现有用户中心路由与 Aether 设计系统

---

## Chunk 1: Backend Marketplace Contract

### Task 1: 为用户侧模型广场定义后端响应模型

**Files:**
- Modify: `src/models/api.py`
- Test: `tests/api/test_user_model_marketplace.py`

- [ ] **Step 1: 写失败测试，定义模型广场响应结构**

Run: `uv run python -m pytest tests/api/test_user_model_marketplace.py -k schema`
Expected: FAIL，缺少新响应模型或接口

- [ ] **Step 2: 在 `src/models/api.py` 新增模型广场 schema**

新增：
- `UserModelMarketplaceProviderItem`
- `UserModelMarketplaceItem`
- `UserModelMarketplaceSummary`
- `UserModelMarketplaceResponse`

- [ ] **Step 3: 运行定向测试确认缺口推进**

Run: `uv run python -m pytest tests/api/test_user_model_marketplace.py -k schema`
Expected: FAIL 从“缺少 schema”推进到“缺少聚合实现”


### Task 2: 抽离用户侧模型广场聚合服务

**Files:**
- Create: `src/services/user/model_marketplace.py`
- Test: `tests/api/test_user_model_marketplace.py`

- [ ] **Step 1: 写失败测试，覆盖用户可见范围和聚合口径**

场景：
- 用户只允许访问部分 Provider / 模型
- 同一 GlobalModel 关联多个 Provider
- 不同 Provider 的 Endpoint 活跃状态不同
- 最近请求记录存在 success / failed / 无样本 三种情况

- [ ] **Step 2: 在 `src/services/user/model_marketplace.py` 写最小聚合实现**

实现要求：
- 复用用户可访问模型判定逻辑
- 聚合 `provider_count / active_provider_count`
- 聚合 `endpoint_count / active_endpoint_count`
- 聚合 `success_rate / avg_latency_ms`
- 生成 `tags`
- 计算 `is_recommended / is_most_stable`
- 构造页面摘要 `summary`

- [ ] **Step 3: 跑后端定向测试确认进入下一缺口**

Run: `uv run python -m pytest tests/api/test_user_model_marketplace.py -k aggregation`
Expected: FAIL 从“缺少服务”推进到“缺少路由”


### Task 3: 暴露用户侧模型广场认证接口

**Files:**
- Modify: `src/api/user_me/routes.py`
- Test: `tests/api/test_user_model_marketplace.py`

- [ ] **Step 1: 写失败测试，覆盖 `GET /api/users/me/model-marketplace`**

Run: `uv run python -m pytest tests/api/test_user_model_marketplace.py -k route`
Expected: FAIL，接口不存在或响应不符

- [ ] **Step 2: 在 `src/api/user_me/routes.py` 新增模型广场路由与适配器**

实现要求：
- 新增 `GET /api/users/me/model-marketplace`
- 支持 `search`
- 保留后端响应中的 `summary / models / total / generated_at`

- [ ] **Step 3: 运行完整后端定向测试**

Run: `uv run python -m pytest tests/api/test_user_model_marketplace.py`
Expected: PASS

## Chunk 2: Frontend Data and Page

### Task 4: 新增模型广场前端 API client 与类型

**Files:**
- Create: `frontend/src/api/model-marketplace.ts`
- Test: `frontend/src/views/user/utils/__tests__/model-marketplace.spec.ts`

- [ ] **Step 1: 写失败测试，定义页面需要的最小字段**

Run: `npm run test:run -- src/views/user/utils/__tests__/model-marketplace.spec.ts`
Expected: FAIL，缺少类型或工具函数

- [ ] **Step 2: 新增页面专用 API client**

实现：
- 定义 `UserModelMarketplaceResponse` 及相关前端类型
- 新增 `getUserModelMarketplace()` 方法

- [ ] **Step 3: 运行测试确认缺口推进**

Run: `npm run test:run -- src/views/user/utils/__tests__/model-marketplace.spec.ts`
Expected: FAIL 从“缺少类型”推进到“缺少筛选/排序工具”


### Task 5: 抽离筛选、排序与品牌归类工具

**Files:**
- Create: `frontend/src/views/user/utils/model-marketplace.ts`
- Create: `frontend/src/views/user/utils/__tests__/model-marketplace.spec.ts`

- [ ] **Step 1: 写失败测试，覆盖以下逻辑**

覆盖：
- 搜索命中 `name / display_name / description`
- 品牌归类
- 标签筛选
- 能力筛选
- `only_available` 过滤
- 排序逻辑
- 推荐/最稳徽标展示逻辑

- [ ] **Step 2: 写最小实现**

实现：
- `resolveMarketplaceBrand`
- `filterMarketplaceModels`
- `sortMarketplaceModels`
- `buildMarketplaceSummaryCards`
- `resolveMarketplaceBadges`

- [ ] **Step 3: 运行测试确认通过**

Run: `npm run test:run -- src/views/user/utils/__tests__/model-marketplace.spec.ts`
Expected: PASS


### Task 6: 新建模型广场页面与详情抽屉

**Files:**
- Create: `frontend/src/views/user/ModelMarketplace.vue`
- Create: `frontend/src/views/user/components/ModelMarketplaceDetailDrawer.vue`
- Modify: `frontend/src/views/user/components/index.ts`（如无导出需求可跳过）

- [ ] **Step 1: 先搭页面骨架**

内容：
- 顶部标题与副标题
- 4 个摘要卡
- 搜索与筛选栏
- 卡片网格
- 空态 / 加载态 / 错误态
- 标签筛选与推荐/最稳徽标位

- [ ] **Step 2: 接入真实模型广场接口**

要求：
- 页面加载时拉取真实数据
- 刷新按钮可重新拉取
- 默认使用本地筛选与排序

- [ ] **Step 3: 实现详情抽屉**

要求：
- 展示描述、能力、价格、来源列表、API 格式
- 支持桌面/移动端阅读

- [ ] **Step 4: 跑类型检查**

Run: `npm run type-check`
Expected: PASS

## Chunk 3: Route, Navigation, Verification

### Task 7: 新增用户侧路由和导航入口

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: 新增 `/dashboard/model-marketplace` 路由**

要求：
- 页面名与 import 路径清晰
- 不影响原 `/dashboard/models`

- [ ] **Step 2: 在侧边栏资源区新增“模型广场”入口**

要求：
- 与“模型目录”并列
- 图标与文案风格保持一致

- [ ] **Step 3: 跑类型检查**

Run: `npm run type-check`
Expected: PASS


### Task 8: 做后端与前端联合验证

**Files:**
- Test: `tests/api/test_user_model_marketplace.py`
- Test: `frontend/src/views/user/utils/__tests__/model-marketplace.spec.ts`

- [ ] **Step 1: 跑后端定向测试**

Run: `uv run python -m pytest tests/api/test_user_model_marketplace.py`
Expected: PASS

- [ ] **Step 2: 跑前端定向测试**

Run: `npm run test:run -- src/views/user/utils/__tests__/model-marketplace.spec.ts`
Expected: PASS

- [ ] **Step 3: 跑前端类型检查**

Run: `npm run type-check`
Expected: PASS


### Task 9: 更新状态文档并准备提交

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: 更新 `STATUS.md`**

补充：
- 模型广场目标
- 已完成前后端项
- 验证命令
- 剩余边界

- [ ] **Step 2: 准备提交**

建议提交消息：
`✨ feat(user-models): 新增用户侧模型广场`
