# 用户侧模型广场设计

## 背景

当前 Aether 用户侧只有“模型目录”页面，入口位于 `/dashboard/models`，主要提供：

- 模型名称搜索
- 简单价格展示
- 用户个人调用次数
- 基础详情抽屉

这个页面更像“可用模型清单”，还不是 metapi 那种“模型广场”：

- 缺少全局摘要区，用户无法一眼看出当前模型池规模
- 缺少来源覆盖信息，用户不知道某个模型背后有多少真实 Provider / Endpoint 支撑
- 缺少最近表现指标，用户无法按成功率、延迟筛选“更稳”的模型
- 缺少品牌/能力/状态等多维筛选

用户已明确要“类似 metapi 模型广场”的页面，而且要求优先接真实数据，不接受只做样子页。

另外，参考了 `Yoan98/ai-key-manage` 之后，可以确认其中有两类体验值得吸收进本页：

- 基于模型名称规则生成的标签化浏览体验
- 用“推荐 / 最稳”这类结论性徽标帮助用户快速选模型

但其“本地 Key 仓库 / 导入解析 / CC Switch 联动”不属于本页范围。

## 目标

在用户侧新增独立页面 `/dashboard/model-marketplace`，提供一个卡片式模型广场，帮助用户快速判断：

- 当前有哪些模型可用
- 每个模型有多少真实来源覆盖
- 最近请求表现是否稳定
- 支持哪些能力
- 价格和说明是什么

页面目标是“模型可用性广场”，不是后台配置页，也不是纯价格目录页。

## 非目标

- 不替换现有 `/dashboard/models` 模型目录页
- 不做跨站点价格对比矩阵
- 不做复杂趋势图、热力图或时间线
- 不做“推荐模型”算法
- 不在一期内引入新的品牌素材资源体系

## 用户体验设计

### 1. 路由与入口

新增用户侧路由：

- `/dashboard/model-marketplace`

侧边栏资源区新增菜单项：

- `模型广场`

保留现有：

- `模型目录`

这样用户可以区分：

- `模型广场`：偏发现、对比、筛选
- `模型目录`：偏列表、查看、复制模型 ID

### 2. 页面首屏结构

页面首屏分为两层：

#### 摘要区

展示 4 个摘要卡：

- `模型总数`
- `可用来源总数`
- `活跃来源总数`
- `最近总体成功率`

右侧提供：

- 搜索框
- 刷新按钮

#### 筛选区

提供以下控件：

- 搜索
- 品牌筛选
- 模型标签筛选
- 能力筛选
- 排序方式
- 仅看有可用来源

默认排序：

- 按 `来源覆盖数` 倒序

可选排序：

- `来源覆盖数`
- `活跃来源数`
- `成功率`
- `平均延迟`
- `调用次数`
- `名称`

### 3. 模型卡片

每张卡片展示：

- 模型主名称
- 显示名称（如存在）
- 品牌标识或品牌文字
- 描述摘要
- 标签
- 能力标签
- `来源覆盖数`
- `活跃来源数`
- `成功率`
- `平均延迟`
- `调用次数`
- 价格摘要

在满足条件时，卡片右上或标题区允许出现轻量徽标：

- `推荐`
- `最稳`

卡片交互：

- 点击整卡打开详情抽屉
- 支持 hover 高亮
- 支持移动端单列与桌面端多列自适应

视觉方向：

- 参考 metapi 的“卡片广场 + 摘要指标 + 多筛选”
- 保持 Aether 现有设计系统和色彩语言
- 不直接照搬 metapi 的 React 结构或样式

### 4. 详情抽屉

点击卡片后打开详情抽屉，展示：

- 模型基础信息
- 描述全文
- 能力标签
- 默认价格配置
- 来源 Provider 列表
- 支持的 API 格式
- 最近表现概览

来源列表中的每项至少展示：

- Provider 名称
- Provider URL
- 是否活跃
- Endpoint 数
- 活跃 Endpoint 数
- 支持的 API 格式

## 数据设计

### 页面真源

本页只展示“当前用户有权限访问”的模型，因此不能直接复用公开目录接口，也不能把后台全部模型暴露给用户。

建议新增一个用户侧认证接口，复用现有 `/api/users/me/available-models` 的权限判定逻辑，再扩展聚合统计字段。

建议接口：

- `GET /api/users/me/model-marketplace`

建议查询参数：

- `search`
- `sort_by`
- `sort_dir`
- `only_available`

前端首版可先本地做筛选排序，但后端响应结构要允许后续平滑下沉到服务端过滤。

### 返回结构

建议响应包含：

- `summary`
- `models`
- `total`
- `generated_at`

其中 `summary` 包含：

- `total_models`
- `total_provider_count`
- `active_provider_count`
- `overall_success_rate`

每个模型项建议包含：

- `id`
- `name`
- `display_name`
- `description`
- `brand`
- `icon_url`
- `is_active`
- `supported_capabilities`
- `tags`
- `usage_count`
- `provider_count`
- `active_provider_count`
- `endpoint_count`
- `active_endpoint_count`
- `supported_api_formats`
- `success_rate`
- `avg_latency_ms`
- `is_recommended`
- `is_most_stable`
- `default_price_per_request`
- `default_tiered_pricing`
- `providers`

### 统计口径

#### 1. 模型可见范围

必须沿用当前用户模型目录的权限判定逻辑：

- 只统计用户当前可以访问的 GlobalModel
- 同时考虑 `allowed_providers`
- 同时考虑 `allowed_models`
- 同时考虑格式转换后的可访问 Provider 集合

#### 2. 来源覆盖数

来源覆盖以 Provider 为粒度聚合：

- `provider_count`：支持该模型的 Provider 总数
- `active_provider_count`：其中当前活跃的 Provider 数

必要时补充：

- `endpoint_count`
- `active_endpoint_count`

#### 3. 成功率

成功率来自最近窗口内的真实请求记录，按当前仓库里稳定可用的模型维度真源实现，优先使用 `Usage`：

- 只统计最终态：`completed` / `failed`
- `success_rate = success / (success + failed)`
- 当窗口内没有完成请求时，返回 `null`，不要假装 100%

时间窗口建议首版固定为：

- 最近 24 小时

#### 4. 平均延迟

延迟同样来自最近窗口内的 `Usage.response_time_ms`：

- 仅统计存在延迟值的最终态请求
- 建议优先基于 `success` 样本计算
- 若窗口内没有成功样本，再回退到带 `latency_ms` 的失败样本
- 若仍没有，则返回 `null`

#### 5. 价格

价格使用 GlobalModel 默认有效价格作为卡片摘要：

- `default_price_per_request`
- `default_tiered_pricing`

一期不做每个 Provider 的价格横向对比表。

#### 6. 品牌

品牌不依赖猜测能力，也不依赖手工维护一整套映射表。

首版建议从以下字段保守推断展示品牌：

- `GlobalModel.config.icon_url`
- `GlobalModel.display_name`
- `GlobalModel.name`

如果无法可靠识别，统一归为：

- `other`

这只是 UI 分组标签，不作为能力真源。

#### 7. 标签

标签用于帮助用户浏览，不作为权限和能力真源。

首版建议保守生成以下浏览标签：

- `thinking`
- `coding`
- `image`
- `embedding`
- `audio`
- `rerank`

标签生成依据建议优先使用：

- `GlobalModel.supported_capabilities`
- `GlobalModel.name`
- `GlobalModel.display_name`
- `GlobalModel.config` 中已存在的结构化提示

如果命中规则不足，则允许标签为空。

#### 8. 推荐与最稳

一期只引入轻量结论性标识，不引入主动 benchmark 子系统。

- `is_most_stable`
  - 建议口径：最近窗口内成功率高于阈值，且平均延迟不为空
  - 作用：帮助用户快速挑“更稳”的模型

- `is_recommended`
  - 建议口径：在可用来源数、成功率、延迟三项之间做保守排序后，给出少量推荐模型
  - 作用：帮助用户快速挑一个日常默认模型

这两个标识都属于“页面导购辅助结论”，必须基于真实聚合数据生成，不允许写死。

## 后端实现设计

### 1. 新增用户侧模型广场聚合服务

建议新增服务文件：

- `src/services/user/model_marketplace.py`

职责：

- 复用用户可用模型判定逻辑
- 聚合 Provider / Endpoint 统计
- 聚合最近窗口成功率与平均延迟
- 生成浏览标签
- 计算 `推荐 / 最稳` 这类轻量页面徽标
- 输出稳定的页面响应结构

不建议把所有聚合 SQL 和口径判断直接堆进 `src/api/user_me/routes.py`。

### 2. 新增 API 响应模型

建议在 `src/models/api.py` 为用户侧模型广场新增专用 schema，例如：

- `UserModelMarketplaceProviderItem`
- `UserModelMarketplaceItem`
- `UserModelMarketplaceSummary`
- `UserModelMarketplaceResponse`

这样不会污染现有 `PublicGlobalModelResponse` 的含义。

### 3. 新增认证接口

在 `src/api/user_me/routes.py` 新增：

- `GET /api/users/me/model-marketplace`

路由适配器负责：

- 校验用户身份
- 读取 query 参数
- 调用聚合服务
- 返回响应 schema

## 前端实现设计

### 1. 独立页面，不复用旧目录页模板

建议新增：

- `frontend/src/views/user/ModelMarketplace.vue`

原因：

- “目录页”和“广场页”目标不同
- 现有 `ModelCatalog.vue` 偏表格，不适合继续堆卡片广场逻辑

### 2. API client

建议新增独立 API 文件：

- `frontend/src/api/model-marketplace.ts`

职责：

- 定义页面响应类型
- 提供 `getUserModelMarketplace()` 请求方法

不建议继续把这个页面特定响应塞进 `frontend/src/api/me.ts`，否则会让 `me.ts` 继续膨胀。

### 3. 前端组件拆分

建议至少拆成：

- `frontend/src/views/user/ModelMarketplace.vue`
- `frontend/src/views/user/components/ModelMarketplaceDetailDrawer.vue`
- `frontend/src/views/user/utils/model-marketplace.ts`

其中：

- 页面负责数据加载、筛选状态和布局
- 抽屉负责详情展示
- utils 负责筛选、排序、品牌归类、推荐徽标展示等纯函数

### 4. 路由与导航

需要修改：

- `frontend/src/router/index.ts`
- `frontend/src/layouts/MainLayout.vue`

新增菜单项：

- `模型广场`

保留原菜单项：

- `模型目录`

## 测试设计

### 后端

建议新增：

- `tests/api/test_user_model_marketplace.py`

至少覆盖：

- 仅返回用户有权限访问的模型
- `provider_count / active_provider_count` 聚合正确
- 成功率按最近窗口真实记录计算
- 无样本时 `success_rate` 返回 `null`
- 平均延迟按预期回退

### 前端

建议新增：

- `frontend/src/views/user/utils/__tests__/model-marketplace.spec.ts`

至少覆盖：

- 搜索
- 品牌筛选
- 标签筛选
- 能力筛选
- 排序
- `only_available` 过滤
- 品牌归类辅助函数
- 推荐/最稳徽标展示条件

页面级验证至少包含：

- `npm run type-check`

## 风险与边界

- Aether 当前没有现成的“按模型聚合成功率/延迟”用户侧接口，一期必须补后端聚合。
- 当前仓库里的 `RequestCandidate` 不带稳定的模型维度字段，因此这期实现改为基于 `Usage` 做模型表现聚合。
- `Usage` 侧同样要注意 `model` 与 `target_model` 的统一键问题，避免把同一模型拆散统计。
- 没有最近样本时不能把成功率渲染成“100%”，否则会误导用户。
- 品牌展示只能作为 UI 辅助标签，不应被当成权限或能力真源。
- 标签和推荐徽标都必须基于真实字段或真实统计生成，不能因为想“看起来丰富”就硬猜。
- 一期先做“模型可用性广场”，不做复杂价格矩阵，避免页面失控。
