# GlobalModel 关联 Provider 候选器增强设计

## 背景

当前模型管理页中，给某个 GlobalModel 关联 Provider 的流程只提供一个按 Provider 名称搜索的勾选列表。用户在关联模型时无法直接判断：

- 哪些 Provider 当前缓存里已经出现目标模型
- 哪些 Provider 尚未抓取过上游模型，只能视为未知
- 哪些 Provider 虽然存在，但当前上游模型缓存里并不支持目标模型

这会导致典型场景体验较差，例如用户想把 `gpt-5.4` 关联给支持它的 Provider，但当前弹窗无法从“模型能力”角度筛选 Provider。

## 目标

在“模型管理页 -> GlobalModel 详情 -> 添加关联 Provider”流程中，提供一个更可判定的候选器：

- 默认基于缓存展示 Provider 的已知上游模型，不在弹窗打开时自动刷新
- 支持两种筛选视角：按 Provider / 按模型
- 支持展示每个 Provider 的“命中 / 未命中 / 未知”状态
- Provider 行支持展开查看缓存中的上游模型
- 支持普通搜索与可选正则搜索
- 支持“刷新支持情况”按钮与“全选当前结果”按钮

## 非目标

- 不改 Provider 侧的批量关联模型弹窗
- 不重构现有上游模型抓取体系
- 不在首次打开弹窗时强制刷新所有 Provider 的上游模型
- 不做矩阵式重型权限面板

## 用户体验设计

### 1. 入口位置

保持现有入口不变，仍然从模型管理页的 GlobalModel 详情抽屉进入“添加关联 Provider”弹窗。

### 2. 弹窗顶部控件

新增以下控件：

- 搜索框
- 视角切换：
  - `按渠道商`
  - `按模型`
- 搜索模式：
  - 默认普通搜索
  - 可选“正则”
- `刷新支持情况` 按钮
- `全选当前结果` 按钮

### 3. 候选状态

每个 Provider 计算一个与当前 GlobalModel 相关的支持状态：

- `matched`：缓存中的上游模型命中当前 GlobalModel
- `not_matched`：已存在缓存，但未命中当前 GlobalModel
- `unknown`：当前没有可用上游模型缓存，无法判断

对应 UI 文案建议：

- `已命中`
- `未命中`
- `未知`

### 4. 按渠道商视角

列表以 Provider 为主，每行显示：

- Provider 名称
- 站点 URL
- 活跃 / 停用状态
- 当前是否已关联
- 支持状态徽标
- 已知上游模型数量

支持展开后查看该 Provider 的缓存上游模型列表，用于人工确认。

### 5. 按模型视角

列表按“命中的上游模型名”分组展示：

- 组标题是缓存中的上游模型名
- 每组下面列出命中该模型的 Provider

这样更适合“我要找支持 `gpt-5.4` 的 Provider”这种用法。

### 6. 搜索行为

普通搜索下，匹配：

- Provider 名
- Provider URL
- 缓存上游模型名

正则搜索下：

- 只在用户显式启用后生效
- 编译失败时给出轻量错误提示，不中断现有选择状态

### 7. 刷新行为

默认使用缓存，不在弹窗打开时自动刷新。

点击 `刷新支持情况` 时：

- 仅刷新当前候选集中的 Provider 支持情况
- 优先刷新当前筛选结果；若无筛选，则刷新当前弹窗的候选 Provider 列表
- 刷新完成后更新命中状态和上游模型展示

## 后端设计

### 新接口

为 GlobalModel 提供一个专用候选接口，而不是让前端对每个 Provider 做 N+1 请求。

建议新增：

- `GET /api/admin/models/global/{global_model_id}/provider-candidates`

返回内容应包含：

- Provider 基础信息
- 是否已关联当前 GlobalModel
- 当前缓存中的上游模型列表
- 支持状态：`matched | not_matched | unknown`

可选查询参数：

- `include_inactive`
- `provider_search`

### 刷新接口

建议新增：

- `POST /api/admin/models/global/{global_model_id}/provider-candidates/refresh`

请求体：

- `provider_ids: string[]`

行为：

- 对指定 Provider 调用现有上游模型查询能力并强制刷新
- 刷新完成后重新计算候选状态

### 命中判定

判定规则先保持保守：

- 先看缓存中的上游模型名是否与当前 GlobalModel 的 `name` 完全相等
- 再结合 GlobalModel 的 `config.model_mappings`（若存在）做额外命中判定

这样可以兼容“统一模型名”与“正则映射规则”两类场景。

## 前端实现设计

### 新增候选器数据模型

在前端为候选器定义单独类型，避免直接复用 `ProviderWithEndpointsSummary`。

建议字段包括：

- `provider_id`
- `provider_name`
- `provider_website`
- `provider_active`
- `already_linked`
- `match_status`
- `cached_models`
- `cached_model_count`
- `last_refreshed_at`

### 组件拆分

不建议把所有逻辑继续堆在 `ModelManagement.vue` 里。

建议拆出一个专门弹窗组件，例如：

- `frontend/src/features/models/components/GlobalModelProviderCandidatesDialog.vue`

它只负责：

- 候选器视图
- 搜索 / 正则 / 全选
- 刷新支持情况
- 返回最终选中的 Provider IDs

`ModelManagement.vue` 继续负责：

- 打开/关闭弹窗
- 提交关联
- 刷新 GlobalModel 详情与关联 Provider 列表

## 测试设计

### 前端

至少覆盖：

- 普通搜索命中 Provider 名 / URL / 缓存模型名
- 正则搜索命中与非法正则报错
- `matched / not_matched / unknown` 分组逻辑
- `按渠道商 / 按模型` 视角切换后的过滤结果
- `全选当前结果` 仅作用于当前筛选结果

### 后端

至少覆盖：

- 候选接口返回已关联 / 未关联 Provider
- 有缓存命中时返回 `matched`
- 有缓存但不命中时返回 `not_matched`
- 无缓存时返回 `unknown`
- 刷新接口仅刷新指定 Provider，并返回更新后的候选状态

## 风险与边界

- 现有 Provider 上游模型缓存可能不全，因此 `unknown` 必须作为一等状态暴露给用户
- 正则搜索必须是显式开关，否则容易把普通搜索体验复杂化
- 刷新支持情况不能默认全量触发，否则在 Provider 数量较多时会明显拖慢弹窗响应

## 推荐结论

采用“默认用缓存 + 手动刷新支持情况 + 双视角候选器”的方案。

这是当前改动范围下最平衡的路线：

- 能解决“我不知道哪个 Provider 支持目标模型”的核心问题
- 不会把页面打开变成重型联机操作
- 复用现有上游模型能力，避免大范围重构
