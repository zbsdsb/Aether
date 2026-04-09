# Aether Model Playground Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Aether 中新增一个类似 metapi / New API Playground 的模型操练场页面，支持 `全局模型` / `渠道模型` 双来源测试、四类协议切换，以及右侧 `预览 / 请求 / 响应` 调试面板。

**Architecture:** 先落地 `P0` 前端页面与现有测试链路复用：新增共享 Playground 视图、三栏子组件、协议预览工具和执行编排，复用当前 `testModelFailover` 完成 `全局模型` 与 `渠道模型 + 已配置协议` 的真实测试。随后以 `P1` 增量方式补齐 `渠道模型 + 未配置协议` 的临时探测接口与 UI 分支，明确区分“正式配置测试”与“临时协议探测”。

**Tech Stack:** Vue 3, TypeScript, Vue Router, Vitest, FastAPI, Pydantic, pytest, 现有 `provider_query` 测试链路, 现有 GlobalModel / Provider 模型数据源

---

## File Map

- Create: `frontend/src/views/shared/ModelPlayground.vue`
- Create: `frontend/src/features/playground/types.ts`
- Create: `frontend/src/features/playground/components/PlaygroundSetupPanel.vue`
- Create: `frontend/src/features/playground/components/PlaygroundConversationPanel.vue`
- Create: `frontend/src/features/playground/components/PlaygroundDebugPanel.vue`
- Create: `frontend/src/features/playground/composables/useModelPlaygroundState.ts`
- Create: `frontend/src/features/playground/utils/playground-protocol-options.ts`
- Create: `frontend/src/features/playground/utils/playground-request-preview.ts`
- Create: `frontend/src/features/playground/utils/__tests__/playground-protocol-options.spec.ts`
- Create: `frontend/src/features/playground/utils/__tests__/playground-request-preview.spec.ts`
- Create: `tests/unit/test_provider_query_playground_probe.py`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`
- Modify: `frontend/src/api/endpoints/providers.ts`
- Modify: `frontend/src/api/endpoints/types/provider.ts` only if the new client types need to live with other provider-query response models
- Modify: `frontend/src/api/endpoints/models.ts` only if the playground needs a dedicated provider-model fetch shape instead of reusing `getProviderModels()`
- Modify: `src/api/admin/provider_query.py`
- Modify: `STATUS.md`

## Chunk 1: P0 Frontend Foundation

### Task 1: Lock protocol/source option rules in utility tests

**Files:**
- Create: `frontend/src/features/playground/types.ts`
- Create: `frontend/src/features/playground/utils/playground-protocol-options.ts`
- Create: `frontend/src/features/playground/utils/__tests__/playground-protocol-options.spec.ts`
- Reference: `docs/superpowers/specs/2026-04-09-aether-model-playground-design.md`

- [ ] **Step 1: Write the failing test**

Add tests covering:

```ts
import {
  buildProtocolOptionState,
  resolvePlaygroundSourceLabel,
} from '../playground-protocol-options'

test('global mode exposes all four protocol options without probe badges', () => {
  const result = buildProtocolOptionState({
    sourceMode: 'global',
    configuredFormats: ['openai:chat'],
    providerType: null,
  })

  expect(result.map(item => item.key)).toEqual([
    'openai-chat',
    'openai-responses',
    'claude',
    'gemini-native',
  ])
  expect(result.every(item => item.badge == null)).toBe(true)
})

test('provider mode marks configured and probe-capable protocol states separately', () => {
  const result = buildProtocolOptionState({
    sourceMode: 'provider',
    configuredFormats: ['openai:chat'],
    providerType: 'custom',
  })

  expect(result.find(item => item.key === 'openai-chat')?.badge).toBe('已配置')
  expect(result.find(item => item.key === 'claude')?.badge).toBe('未配置，可试测')
})
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-protocol-options.spec.ts
```

Expected: `FAIL` because the playground utility files do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create:

- `frontend/src/features/playground/types.ts` for:
  - `PlaygroundSourceMode`
  - `PlaygroundProtocolKey`
  - `PlaygroundProtocolBadge`
  - `PlaygroundProtocolOptionState`
- `frontend/src/features/playground/utils/playground-protocol-options.ts` for:
  - canonical protocol metadata
  - `buildProtocolOptionState()`
  - `resolvePlaygroundSourceLabel()`

Keep the first version conservative:

- global mode: all protocols available, no probe badge
- provider mode:
  - configured endpoint -> `已配置`
  - other supported/probeable families -> `未配置，可试测`
  - obviously risky combinations -> `高风险`

- [ ] **Step 4: Re-run the utility tests**

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-protocol-options.spec.ts
```

Expected: `PASS`.


### Task 2: Lock request preview generation in utility tests

**Files:**
- Create: `frontend/src/features/playground/utils/playground-request-preview.ts`
- Create: `frontend/src/features/playground/utils/__tests__/playground-request-preview.spec.ts`
- Modify: `frontend/src/features/playground/types.ts`

- [ ] **Step 1: Write the failing test**

Add tests covering:

```ts
import { buildPlaygroundRequestPreview } from '../playground-request-preview'

test('builds OpenAI Chat preview from conversation messages', () => {
  const preview = buildPlaygroundRequestPreview({
    protocol: 'openai-chat',
    systemPrompt: 'You are precise.',
    messages: [{ role: 'user', content: 'hello' }],
    stream: true,
    reasoningEffort: 'high',
  })

  expect(preview.transportLabel).toBe('OpenAI Chat')
  expect(preview.body.messages).toHaveLength(2)
  expect(preview.body.stream).toBe(true)
})

test('builds Gemini Native preview with systemInstruction and contents', () => {
  const preview = buildPlaygroundRequestPreview({
    protocol: 'gemini-native',
    systemPrompt: 'Stay concise.',
    messages: [{ role: 'user', content: 'hello' }],
    stream: false,
  })

  expect(preview.body.systemInstruction).toBeDefined()
  expect(preview.body.contents).toHaveLength(1)
})
```

- [ ] **Step 2: Run the preview tests and confirm they fail**

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-request-preview.spec.ts
```

Expected: `FAIL` because preview builder does not exist yet.

- [ ] **Step 3: Write the minimal preview builder**

Implement:

- a typed `PlaygroundRequestPreview`
- `buildPlaygroundRequestPreview()` that maps the same conversation state into:
  - OpenAI Chat request shape
  - OpenAI Responses request shape
  - Claude request shape
  - Gemini Native request shape

Support the shared parameters needed by the page:

- `systemPrompt`
- `messages`
- `stream`
- `reasoningEffort`
- `temperature`
- `maxOutputTokens`
- `topP`
- request override merge

- [ ] **Step 4: Re-run the preview tests**

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-request-preview.spec.ts
```

Expected: `PASS`.


### Task 3: Add the shared Playground page shell and route wiring

**Files:**
- Create: `frontend/src/views/shared/ModelPlayground.vue`
- Create: `frontend/src/features/playground/components/PlaygroundSetupPanel.vue`
- Create: `frontend/src/features/playground/components/PlaygroundConversationPanel.vue`
- Create: `frontend/src/features/playground/components/PlaygroundDebugPanel.vue`
- Create: `frontend/src/features/playground/composables/useModelPlaygroundState.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: Add the route entries first**

Modify `frontend/src/router/index.ts` to add:

- `/dashboard/playground`
- `/admin/playground`

Both should lazy-load the same shared page:

- `@/views/shared/ModelPlayground.vue`

- [ ] **Step 2: Add navigation entries**

Modify `frontend/src/layouts/MainLayout.vue` to surface `模型操练场` in both user and admin navigation groups.

- [ ] **Step 3: Build the page shell with static state**

Create the new page and three child panels with placeholder content for:

- top status cards
- left setup column
- center conversation column
- right debug tabs

Keep the first pass static and layout-only. Do not wire API calls in this task.

- [ ] **Step 4: Run a type check**

Run:

```bash
npm run type-check
```

Expected: `PASS`.


## Chunk 2: P0 Data Wiring And Existing Test Runner Integration

### Task 4: Wire the setup panel to real GlobalModel and Provider model data

**Files:**
- Modify: `frontend/src/views/shared/ModelPlayground.vue`
- Modify: `frontend/src/features/playground/composables/useModelPlaygroundState.ts`
- Modify: `frontend/src/features/playground/components/PlaygroundSetupPanel.vue`
- Reference: `frontend/src/api/endpoints/global-models.ts`
- Reference: `frontend/src/api/endpoints/providers.ts`
- Reference: `frontend/src/api/endpoints/models.ts`
- Reference: `frontend/src/api/admin.ts`

- [ ] **Step 1: Write failing utility/component-adjacent tests for source switching logic**

Extend the playground utility tests or add a small state test that covers:

- switching from `global` to `provider` clears the now-invalid selection
- provider mode can hold both `providerId` and `targetModelName`
- protocol badges refresh when provider summary / configured formats change

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-protocol-options.spec.ts
```

Expected: `FAIL` on the new state expectations.

- [ ] **Step 2: Implement minimal state/data loader logic**

In `useModelPlaygroundState.ts`, add:

- source mode state
- selected GlobalModel / Provider / Provider model
- provider search and model search state
- loaders for:
  - active global models
  - provider summary list
  - provider models / upstream models as needed

Prefer reusing:

- `getGlobalModels(...)`
- `getProvidersSummary(...)`
- `getProviderModels(...)`
- `adminApi.queryProviderModels(...)` when upstream-probeable model names are needed

- [ ] **Step 3: Bind the real selectors in `PlaygroundSetupPanel.vue`**

Replace placeholder dropdowns with:

- global model search/select
- provider search/select
- provider model search/select
- protocol state badges

- [ ] **Step 4: Re-run tests and type check**

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-protocol-options.spec.ts
npm run type-check
```

Expected: both `PASS`.


### Task 5: Reuse the existing failover runner for global and configured direct tests

**Files:**
- Modify: `frontend/src/views/shared/ModelPlayground.vue`
- Modify: `frontend/src/features/playground/composables/useModelPlaygroundState.ts`
- Modify: `frontend/src/features/playground/components/PlaygroundConversationPanel.vue`
- Modify: `frontend/src/features/playground/components/PlaygroundDebugPanel.vue`
- Reference: `frontend/src/composables/useModelTest.ts`
- Reference: `frontend/src/api/endpoints/providers.ts`

- [ ] **Step 1: Write a failing test for request preview to runner payload mapping**

Add a test that asserts:

- global mode maps to `mode=global`
- provider mode with configured protocol maps to `mode=direct`
- configured direct requests carry `endpoint_id` when selected / inferred

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-request-preview.spec.ts
```

Expected: `FAIL`.

- [ ] **Step 2: Implement the minimal runner adapter**

In `useModelPlaygroundState.ts`:

- create a `runCurrentPlaygroundRequest()` action
- reuse `testModelFailover(...)` directly or wrap the behavior already in `useModelTest.ts`
- persist:
  - `lastRequestPreview`
  - `lastRawRequest`
  - `lastRawResponse`
  - `lastAttempts`
  - `runStatus`

Only support in this task:

- `全局模型`
- `渠道模型 + 已配置协议`

If protocol is not formally configured, do not fake success; keep it blocked or marked as probe-only pending `P1`.

- [ ] **Step 3: Bind the action buttons and result rendering**

Wire:

- `发送`
- `停止`
- `清空`
- `重试上次`

Update:

- center conversation message flow
- right-side `预览 / 请求 / 响应`

- [ ] **Step 4: Run targeted tests and type check**

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-request-preview.spec.ts
npm run type-check
```

Expected: both `PASS`.


### Task 6: Lock P0 acceptance and document the remaining probe gap

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Run the full P0 verification set**

Run:

```bash
npm run test:run -- src/features/playground/utils/__tests__/playground-protocol-options.spec.ts src/features/playground/utils/__tests__/playground-request-preview.spec.ts
npm run type-check
```

Expected: `PASS`.

- [ ] **Step 2: Perform manual smoke verification**

Verify in the browser:

- `/dashboard/playground` opens
- `/admin/playground` opens
- global mode can send one configured request
- provider mode can send one configured request
- right debug panel updates after send
- unconfigured protocol is clearly marked as probe-only / not-yet-supported in P0

- [ ] **Step 3: Update `STATUS.md` with the P0 result**

Record:

- implemented files
- verification commands
- remaining `P1` probe work


## Chunk 3: P1 Temporary Protocol Probe For Unconfigured Provider Formats

### Task 7: Add failing backend unit tests for probe request validation and candidate selection

**Files:**
- Create: `tests/unit/test_provider_query_playground_probe.py`
- Modify: `src/api/admin/provider_query.py`
- Reference: `tests/unit/test_provider_query_failover_endpoint.py`

- [ ] **Step 1: Write failing backend unit tests**

Cover:

```python
def test_playground_probe_request_requires_provider_and_model() -> None:
    ...


def test_build_probe_candidates_uses_selected_api_format_even_when_endpoint_not_configured() -> None:
    ...


def test_probe_response_marks_mode_as_probe_when_protocol_is_not_configured() -> None:
    ...
```

- [ ] **Step 2: Run the new backend tests and confirm failure**

Run:

```bash
uv run python -m pytest tests/unit/test_provider_query_playground_probe.py -v
```

Expected: `FAIL` because the probe request model / helpers do not exist yet.

- [ ] **Step 3: Implement minimal probe request models and helper functions**

In `src/api/admin/provider_query.py`, add:

- playground probe request model
- helper to resolve configured vs unconfigured endpoint state
- helper to build a temporary probe target from:
  - provider
  - requested protocol
  - selected model

Do not save anything to DB in this task.

- [ ] **Step 4: Re-run the probe unit tests**

Run:

```bash
uv run python -m pytest tests/unit/test_provider_query_playground_probe.py -v
```

Expected: `PASS`.


### Task 8: Implement the probe API endpoint without persisting configuration

**Files:**
- Modify: `src/api/admin/provider_query.py`
- Modify: `frontend/src/api/endpoints/providers.ts`
- Modify: `frontend/src/views/shared/ModelPlayground.vue`
- Modify: `frontend/src/features/playground/composables/useModelPlaygroundState.ts`
- Modify: `frontend/src/features/playground/components/PlaygroundDebugPanel.vue`

- [ ] **Step 1: Add a failing backend test for the probe endpoint contract**

Add coverage for:

- request hits a new `/api/admin/provider-query/playground-probe` endpoint
- response carries:
  - `mode = "probe"`
  - selected protocol
  - raw request payload
  - raw response payload
  - `configured = false`

Run:

```bash
uv run python -m pytest tests/unit/test_provider_query_playground_probe.py -k endpoint -v
```

Expected: `FAIL`.

- [ ] **Step 2: Implement the endpoint**

Add a new provider-query endpoint that:

- authenticates admin user
- resolves provider and credentials
- builds a one-off request for the selected protocol
- runs the probe without saving endpoint configuration
- returns structured debug data for the Playground UI

Keep the behavior conservative:

- success means “probe succeeded”
- success does not mutate provider endpoints
- response explicitly says this is not a formal configuration change

- [ ] **Step 3: Add the frontend client and UI probe branch**

In `frontend/src/api/endpoints/providers.ts`, add:

- request/response types for playground probe
- `runPlaygroundProbe(...)`

In the playground state/UI:

- when source is `provider` and selected protocol is `未配置，可试测`
- call the probe API instead of the normal failover runner
- surface `临时协议探测` labels in the debug panel

- [ ] **Step 4: Re-run backend and frontend checks**

Run:

```bash
uv run python -m pytest tests/unit/test_provider_query_playground_probe.py tests/unit/test_provider_query_failover_endpoint.py -v
npm run test:run -- src/features/playground/utils/__tests__/playground-protocol-options.spec.ts src/features/playground/utils/__tests__/playground-request-preview.spec.ts
npm run type-check
```

Expected: all relevant checks `PASS`.


### Task 9: Add post-probe UX guidance and final verification

**Files:**
- Modify: `frontend/src/features/playground/components/PlaygroundDebugPanel.vue`
- Modify: `frontend/src/views/shared/ModelPlayground.vue`
- Modify: `STATUS.md`

- [ ] **Step 1: Add the success guidance UI**

When probe succeeds, render a secondary CTA:

- `去补协议配置`

The first version may:

- navigate to the relevant Provider detail/config page, or
- copy a suggested config summary

Do not auto-save configuration in this step.

- [ ] **Step 2: Run the full verification set**

Run:

```bash
uv run python -m pytest tests/unit/test_provider_query_playground_probe.py tests/unit/test_provider_query_failover_endpoint.py -v
npm run test:run -- src/features/playground/utils/__tests__/playground-protocol-options.spec.ts src/features/playground/utils/__tests__/playground-request-preview.spec.ts
npm run type-check
```

Expected: `PASS`.

- [ ] **Step 3: Perform manual browser verification**

Verify:

- global configured test succeeds
- provider configured test succeeds
- provider unconfigured probe succeeds or fails with clear mode labeling
- right-side request/response panel clearly distinguishes `正式配置测试` vs `临时协议探测`
- success probe exposes `去补协议配置`

- [ ] **Step 4: Update `STATUS.md` and prepare commit**

Record:

- final implemented scope
- verification commands
- any remaining follow-up work

Suggested commit message after approval:

```bash
git add frontend/src/router/index.ts frontend/src/layouts/MainLayout.vue frontend/src/views/shared/ModelPlayground.vue frontend/src/features/playground frontend/src/api/endpoints/providers.ts src/api/admin/provider_query.py tests/unit/test_provider_query_playground_probe.py STATUS.md
git commit -m "✨ feat(playground): 新增模型操练场"
```
