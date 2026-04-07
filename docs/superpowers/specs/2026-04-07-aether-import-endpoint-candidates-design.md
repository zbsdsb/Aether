# Aether all-in-hub 导入器候选端点扩展与导入凭证复用设计

日期: 2026-04-07
状态: 已确认设计，待实现

## 1. 背景

当前 all-in-hub importer 已能完成基础导入，但 endpoint 创建策略过于保守：

- 每个 provider 只创建一个 `openai:chat` endpoint
- `provider_type="custom"`
- `enable_format_conversion=False`
- `access_token` / `session_cookie` 会被提取并落到 `ProviderImportTask`，但不会进入现有的 Provider 用户认证配置链路

这导致两个问题：

- 导入后 endpoint 协议能力信息不足，仍需较多手工补配
- 导入得到的站点控制面凭证虽然已进库，但前台没有直接复用到现有“用户认证”弹窗，用户仍需重复录入

## 2. 目标

- 扩展 importer 的 endpoint 创建规则，让导入结果更接近 Aether 当前真实可用的协议层结构
- 不引入主动探测，不增加后台验证任务
- 复用现有 Provider 用户认证 UI / 模板链路，而不是新做一套站点凭证页面
- 让导入得到的 `access_token` / `session_cookie` / `user_id` / `base_url` 等信息可被用户快速接入现有 Provider 认证能力

## 3. 非目标

- 不做导入后的自动协议探测
- 不做按模型发请求的协议验证
- 不做新的异步任务中心改造
- 不做自动补发 API key / 自动补钥工作流扩展
- 不做新的一套“站点令牌详情页”

## 4. 已确认决策

### 4.1 Endpoint 候选创建规则

导入时不再只建一个 `openai:chat` endpoint，而是按以下规则直接创建候选 endpoint。

默认固定创建：

- `openai:chat`
- `openai:cli`
- `openai:compact`

当离线证据中出现 `claude` / `anthropic` 相关模型名、协议线索或站点类型信号时，追加：

- `claude:chat`
- `claude:cli`

当离线证据中出现 `gemini` 相关模型名、协议线索或站点类型信号时，追加：

- `gemini:chat`
- `gemini:cli`

本期不新增：

- `openai:video`
- `gemini:video`

### 4.2 不做主动探测

本期 importer 只按离线证据建候选 endpoint，不主动请求上游验证协议能力。

原因：

- 用户已明确收缩范围，不希望把导入器扩成探测器
- 主动探测会引入频控、退避、误判与更多运行态复杂度
- 当前需求的核心价值是减少手工配置，而不是自动判定所有协议真值

### 4.3 导入凭证复用现有“用户认证”弹窗

不新做站点凭证页面，复用现有 `ProviderAuthDialog` 和后端 provider ops 架构模板。

目标行为：

- importer 继续像现在一样解析并保存 `access_token`、`session_cookie` 等导入凭证
- 在 Provider 详情中增加一个轻量入口，允许用户将最新导入凭证映射到现有“用户认证”配置
- 对已知模板（优先 New API）直接映射到现有字段
- 对无法完全映射的模板，只做预填充，不阻止用户手工修改

## 5. 设计方案

### 5.1 导入记录分层

现有 importer 继续区分两类数据：

- 直导明文 key：直接创建 `ProviderAPIKey`
- 站点控制面凭证：继续写入 `ProviderImportTask`

本期不改变这个大分层。

调整点在于：

- endpoint 不再只生成一个 `openai:chat`
- `ProviderImportTask` 中的导入凭证将被用于后续“填充用户认证配置”

### 5.2 候选 endpoint 生成器

从 `all_in_hub.py` 中抽出独立的候选 endpoint 解析逻辑，输入为导入 bucket / record，输出为 endpoint signature 列表。

建议新增类似模块：

- `src/services/provider_import/endpoint_candidates.py`

输出结构建议至少包含：

- `api_format`
- `api_family`
- `endpoint_kind`
- `reason`

其中 `reason` 为轻量字段，用于说明该 endpoint 的来源，例如：

- `default_openai`
- `matched_claude_hint`
- `matched_gemini_hint`

该字段本期可先仅用于后端调试或保存在 endpoint 的 `config` 中，不强制前端展示。

### 5.3 Imported custom provider 的格式转换默认开启

当前 importer 创建 provider 时写死：

- `provider_type="custom"`
- `enable_format_conversion=False`

本期改为：

- 导入创建的 `custom provider` 默认 `enable_format_conversion=True`

原因：

- 本期将为同一 provider 建立多个 endpoint signature
- Aether 现有格式转换能力可减少协议差异带来的手工配置成本
- 若继续默认关闭转换，则新增 endpoint 的收益会被削弱

注意：

- 这里表示“允许 Aether 在调度时做格式协助转换”
- 不表示“系统已经确认这些协议一定真实可用”

### 5.4 Provider 详情中的导入凭证复用入口

复用现有：

- `ProviderDetailDrawer`
- `ProviderAuthDialog`
- provider ops 架构模板

在 Provider 详情中新增一个轻量入口，例如：

- “使用导入凭证填充用户认证”

点击后行为：

1. 读取该 provider 最新、最相关的一条导入任务
2. 解密 `credential_payload`
3. 读取 `source_metadata`
4. 根据目标认证模板将可映射字段写入现有认证表单

本期优先支持 `New API` 模板字段映射：

- `base_url` <- `source_metadata.endpoint_base_url`
- `cookie` <- `credential_payload.session_cookie`
- `api_key` <- `credential_payload.access_token` 或导入记录中的访问令牌
- `user_id` <- `source_metadata.account_id`，若模板逻辑支持，也允许前端继续从 cookie 自动解析覆盖

对其他模板：

- 若字段可明确映射，则做同样预填充
- 若只能部分映射，则仅填可确定字段，其余保留空值给用户手工补

### 5.5 UI 边界

本期 UI 只做两处小范围增强：

1. Provider 详情顶部 / 认证相关区域增加“使用导入凭证填充用户认证”入口
2. Provider 详情中可增加一条轻量提示，说明当前是否存在可复用的导入凭证

本期不新增：

- 新页面
- 新抽屉
- 新任务列表

## 6. 数据流

### 6.1 导入流程

1. 解析 all-in-hub 内容
2. 按 origin / provider 聚合
3. 生成 provider
4. 按候选规则生成多个 endpoint
5. 直导明文 key -> 创建 `ProviderAPIKey`
6. `access_token` / `session_cookie` -> 创建或更新 `ProviderImportTask`

### 6.2 认证复用流程

1. 用户打开 Provider 详情
2. 点击“使用导入凭证填充用户认证”
3. 后端或前端读取最新导入任务
4. 将导入凭证映射到现有认证模板表单
5. 用户确认后保存到现有 provider auth config

## 7. 兼容性与风险

### 7.1 兼容性

- 已有导入任务模型可继续复用，无需推倒重做
- 已有 `ProviderAuthDialog` 和 provider ops 架构模板继续沿用
- 现有 UI 入口无需大改，只需在 Provider 详情中补一个入口

### 7.2 风险

- 离线证据误判可能导致创建出部分实际上用不到的 endpoint
- `custom provider` 默认开启格式转换后，候选集合会比现在更大
- 导入任务与认证模板字段名可能存在不完全对齐，需要为 New API 先打通最清晰路径

### 7.3 风险控制

- 不跨族无依据泛化：Claude/Gemini 只在命中离线线索时创建
- 不做自动探测，避免新增运行态噪音
- 认证复用仅做“预填充”，最终仍由用户确认保存

## 8. 实现建议

### 8.1 后端

- 修改 `src/services/provider_import/all_in_hub.py`
  - 用候选 endpoint 生成逻辑替换当前单一 `openai:chat` 创建逻辑
  - 导入创建 provider 时默认 `enable_format_conversion=True`
- 新增或抽取候选规则模块
  - 如 `src/services/provider_import/endpoint_candidates.py`
- 补一条“从导入任务填充 provider auth config”的后端接口，或扩展现有 provider auth 读取流程

### 8.2 前端

- 在 `ProviderDetailDrawer` 增加“使用导入凭证填充用户认证”入口
- 复用 `ProviderAuthDialog`，不新增独立凭证编辑页面
- 若需要，可在详情中显示“存在可复用导入凭证”的轻量状态提示

## 9. 验证建议

实现完成后至少验证以下场景：

1. 仅 OpenAI 线索的 provider
   - 成功创建 `openai:chat`、`openai:cli`、`openai:compact`
2. 命中 Claude 线索的 provider
   - 在 OpenAI 三件套基础上追加 `claude:chat`、`claude:cli`
3. 命中 Gemini 线索的 provider
   - 在 OpenAI 三件套基础上追加 `gemini:chat`、`gemini:cli`
4. 导入后打开 Provider 详情
   - 能看到并触发“使用导入凭证填充用户认证”
5. New API 模板预填充
   - `base_url`、`cookie`、`api_key`、`user_id` 能按预期映射
6. 老数据兼容
   - 没有导入凭证的 provider 不应受影响

## 10. 结论

本期不做协议探测，也不重做站点凭证系统。

直接把 importer 扩成“按离线规则创建候选 endpoint”，并把现有导入凭证接到已有 `用户认证` 模板链路，是当前成本最低、收益最直接、也最符合用户预期的方案。
