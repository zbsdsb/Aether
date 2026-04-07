# Aether All-in-Hub Reissue Metapi Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Aether 的 all-in-hub 第二阶段执行链路对齐 metapi 的平台适配思路，先修正任务选择口径，再补齐 `new-api` / `sub2api` / `pending_import` 的关键能力，并把“创建成功但验证失败”与“真正创建失败”拆开。

**Architecture:** 保持现有 `all_in_hub.py` 负责“解析 + 预览 + 静态导入”的职责不变，把第二阶段能力集中收敛到 `reissue.py` 里的平台适配层。参考 metapi 的 `backupService.ts + platforms/*.ts` 分层，先引入 Aether 内部的 adapter/fallback 结构，再逐步把任务执行状态和验证状态解耦，避免把所有上游数据质量问题都压成单一 `failed`。

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, httpx, pytest, PostgreSQL, existing Aether provider import services

---

## Scope and decisions

- 本计划只覆盖 Aether 的 all-in-hub **导入后二阶段**：`pending_reissue` / `pending_import` 执行、站点平台适配、验证结果口径。
- 本计划**不**重做第一阶段静态导入（`Provider / Endpoint / direct key / task` 的解析与落库逻辑）。
- 本计划优先解决这次真实验证里最有收益的 4 个问题：
  1. `tasks/execute` 没有先筛 `pending_reissue`
  2. `sub2api` 只有 probe，没有真正 create token
  3. `new-api` 只用固定 `group=default` + 单一路径，缺少 group / cookie fallback
  4. “创建 key 成功但 models 校验失败”被直接算成最终失败，信息损失太大
- 本计划默认继续使用现有 verify 环境与真实样例：`/Users/zbs/Downloads/all-api-hub-backup-2026-04-05.json`。

## Files map

**Existing files to modify**
- `src/services/provider_import/reissue.py`
  - 现有 all-in-hub 二阶段执行主入口
  - 将拆出更明确的平台 adapter/fallback 结构
  - 将修正任务筛选、状态语义、token name、new-api/sub2api 处理
- `src/services/provider_import/all_in_hub.py`
  - 现有静态导入与 task metadata 构建入口
  - 将补充 task metadata / task_type 判定，使二阶段平台适配有足够上下文
- `src/models/provider_import.py`
  - 若要暴露更细状态/结果字段，需要扩充 response model
- `src/api/admin/providers/routes.py`
  - 若执行结果口径变更，需要同步 response / audit metadata
- `tests/services/test_all_in_hub_reissue.py`
  - 二阶段主测试文件，补齐 metapi 对齐后的行为
- `tests/api/test_admin_all_in_hub_import_routes.py`
  - 二阶段执行接口返回合同测试

**New files to create**
- `src/services/provider_import/platform_adapters.py`
  - 封装平台识别、group 探测、token 创建、token 列表 fallback 等共享逻辑
  - 先覆盖 `new-api` / `sub2api` / `unknown->new-api probe` / `pending_import candidates`
- `tests/services/test_all_in_hub_platform_adapters.py`
  - 平台 adapter 层单测，避免所有逻辑都堆在 `reissue.py` 的集成测试里

**Reference-only files (do not modify in this phase)**
- `/Users/zbs/projectwork/github-project/metapi/src/server/services/backupService.ts`
- `/Users/zbs/projectwork/github-project/metapi/src/server/services/platforms/newApi.ts`
- `/Users/zbs/projectwork/github-project/metapi/src/server/services/platforms/sub2api.ts`
- `/Users/zbs/projectwork/github-project/metapi/src/server/services/platforms/oneApi.ts`
- `/Users/zbs/projectwork/github-project/metapi/src/server/routes/api/accountTokens.ts`

---

## Chunk 1: 修正执行入口的任务选择与结果口径

### Task 1: 只执行真正应该执行的任务

**Files:**
- Modify: `src/services/provider_import/reissue.py`
- Test: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写 failing test，证明当前 execute 会把 pending_import 也选进去**

```python
def test_execute_tasks_selects_only_pending_reissue_tasks() -> None:
    # given: pending_import + pending_reissue + completed/failed tasks
    # when: execute_all_in_hub_import_tasks(limit=10)
    # then: total_selected 只统计 pending_reissue
    ...
```

- [ ] **Step 2: 运行单测，确认当前失败**

Run: `pytest tests/services/test_all_in_hub_reissue.py -k selects_only_pending_reissue -v`
Expected: FAIL，当前实现会把 `all()` 后的前 N 条都选进去。

- [ ] **Step 3: 最小修改 execute 选择逻辑**

目标行为：
- 只选 `status == pending`
- 只选 `task_type == pending_reissue`
- `limit` 作用于筛选后的结果

建议实现：
- 用 SQLAlchemy query 直接过滤，而不是 `all()` 后 Python 切片
- 保留 `keys = list(db.query(ProviderAPIKey).all())` 这种缓存方式，先不做性能重构

- [ ] **Step 4: 补一个回归测试，确认 completed/failed/pending_import 不再污染统计**

```python
def test_execute_tasks_summary_excludes_pending_import_and_terminal_tasks() -> None:
    ...
```

- [ ] **Step 5: 运行该测试文件**

Run: `pytest tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/provider_import/reissue.py tests/services/test_all_in_hub_reissue.py
git commit -m "feat(import): 收紧 all-in-hub 二阶段任务选择口径"
```

### Task 2: 把“创建成功但验证失败”从纯失败里拆出来

**Files:**
- Modify: `src/services/provider_import/reissue.py`
- Modify: `src/models/provider_import.py`
- Modify: `src/api/admin/providers/routes.py`
- Test: `tests/services/test_all_in_hub_reissue.py`
- Test: `tests/api/test_admin_all_in_hub_import_routes.py`

- [ ] **Step 1: 写 failing test，表达期望的结果字段**

```python
def test_execute_task_reports_key_created_before_verification_failure() -> None:
    # when verify models fails after new key persisted
    # then result should expose created key id and a richer status/reason
    ...
```

- [ ] **Step 2: 定义结果口径，不先改数据库 schema**

本阶段建议先不新增 DB 状态枚举，先在 API result 中补充：
- `status`: 保持 `failed/completed/skipped`
- 新增 `stage`: `create_key` / `verify_models` / `probe` / `unsupported`
- 新增 `key_created`: bool
- 保留 `result_key_id`

这样先把信息暴露出来，再决定是否引入数据库级新状态。

- [ ] **Step 3: 在 `_execute_task()` 中细分失败来源**

最小目标：
- upstream create 成功但 models 校验失败 -> `stage = verify_models`
- probe 失败 -> `stage = probe`
- strategy 不支持 -> `stage = unsupported`

- [ ] **Step 4: 同步 response model / route contract**

更新：
- `src/models/provider_import.py`
- `src/api/admin/providers/routes.py`
- 对应 API tests

- [ ] **Step 5: 跑服务层和 API 合同测试**

Run: `pytest tests/services/test_all_in_hub_reissue.py tests/api/test_admin_all_in_hub_import_routes.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/provider_import/reissue.py src/models/provider_import.py src/api/admin/providers/routes.py tests/services/test_all_in_hub_reissue.py tests/api/test_admin_all_in_hub_import_routes.py
git commit -m "feat(import): 细化 all-in-hub 二阶段执行结果口径"
```

---

## Chunk 2: 引入平台 adapter，对齐 metapi 的 new-api / sub2api 思路

### Task 3: 抽出平台 adapter 骨架

**Files:**
- Create: `src/services/provider_import/platform_adapters.py`
- Modify: `src/services/provider_import/reissue.py`
- Test: `tests/services/test_all_in_hub_platform_adapters.py`
- Test: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 新建 adapter 测试文件，先定义接口形状**

建议先定义：
- `resolve_import_task_adapter(task) -> adapter`
- `NewApiImportAdapter`
- `Sub2ApiImportAdapter`
- `UnknownImportAdapter`

测试关注：
- site_type -> adapter 的映射
- adapter 需要哪些 metadata/payload 字段

- [ ] **Step 2: 创建最小 adapter 文件与协议**

建议内容：
- 平台常量
- metadata / payload 读取 helper
- `ImportTaskAdapter` 基类或 Protocol
- `resolve_import_task_adapter()`

- [ ] **Step 3: 把 reissue.py 中平台判断从 if/else 挪到 adapter 层**

当前这些逻辑要迁移/封装：
- `detect_import_task_strategy()`
- `_probe_new_api_compatibility()`
- `_probe_sub2api_access_token()`
- `_reissue_new_api_key()`

- [ ] **Step 4: 跑新老测试**

Run: `pytest tests/services/test_all_in_hub_platform_adapters.py tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/provider_import/platform_adapters.py src/services/provider_import/reissue.py tests/services/test_all_in_hub_platform_adapters.py tests/services/test_all_in_hub_reissue.py
git commit -m "refactor(import): 抽离 all-in-hub 平台 adapter"
```

### Task 4: 对齐 metapi 的 new-api fallback 能力

**Files:**
- Modify: `src/services/provider_import/platform_adapters.py`
- Modify: `src/services/provider_import/reissue.py`
- Test: `tests/services/test_all_in_hub_platform_adapters.py`
- Test: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写 failing tests，覆盖 metapi 式 fallback**

至少覆盖：
- group 不是 `default` 时仍能创建 token
- token list 支持不同 data shape
- auth header 失败后允许 cookie fallback（如当前 payload 有 session_cookie）
- unknown site 可以先 probe，再落到 new-api adapter

- [ ] **Step 2: 引入 new-api group 探测**

参考 metapi：
- `/api/user/self/groups`
- `/api/user_group_map`
- 失败时 cookie fallback
- 都失败才回退 `default`

Aether 最小实现可先：
- 优先探 group
- create token 时将 `group` 作为可选入参，而不是死写 `default`

- [ ] **Step 3: 引入 new-api cookie fallback**

最小实现：
- 如果 access token 请求失败且 payload 有 session_cookie
- 允许切换 Cookie 头再次请求 token create / token list
- 不要求一步复制 metapi 全部 user-id probing，但要留可扩展结构

- [ ] **Step 4: 收紧 token name 生成规则**

修复当前 `aether-` 前缀 + 40 位截断仍可能过长的问题。
目标：
- 给总长度上限常量
- prefix + sanitized suffix 一起截断

- [ ] **Step 5: 运行测试**

Run: `pytest tests/services/test_all_in_hub_platform_adapters.py tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/provider_import/platform_adapters.py src/services/provider_import/reissue.py tests/services/test_all_in_hub_platform_adapters.py tests/services/test_all_in_hub_reissue.py
git commit -m "feat(import): 对齐 metapi 增强 new-api reissue fallback"
```

### Task 5: 参考 metapi 补齐 sub2api createApiToken 路径

**Files:**
- Modify: `src/services/provider_import/platform_adapters.py`
- Modify: `src/services/provider_import/reissue.py`
- Test: `tests/services/test_all_in_hub_platform_adapters.py`
- Test: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写 failing tests，描述 sub2api createApiToken 行为**

至少覆盖：
- 尝试 `/api/v1/keys`
- fallback `/api/v1/api-keys`
- access token 过期 -> 返回清晰错误
- create 成功后可以继续进入 key 持久化流程

- [ ] **Step 2: 在 adapter 中实现 metapi 风格 sub2api create token**

参考 metapi：
- `buildAuthHeader(accessToken)`
- payload 最少包含 `name`
- 可选 group / expires / quota
- endpoints 两段 fallback

- [ ] **Step 3: 保留当前 probe 逻辑，但 probe 不再是最终终点**

新的目标：
- token expired / unauthorized -> 明确失败
- token still valid -> 继续尝试 create token

- [ ] **Step 4: 跑测试**

Run: `pytest tests/services/test_all_in_hub_platform_adapters.py tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/provider_import/platform_adapters.py src/services/provider_import/reissue.py tests/services/test_all_in_hub_platform_adapters.py tests/services/test_all_in_hub_reissue.py
git commit -m "feat(import): 参考 metapi 实现 sub2api reissue"
```

---

## Chunk 3: 让 pending_import 与真实样例更可操作

### Task 6: 调整 task_type / metadata，让 Anyrouter 与 cookie-only new-api 不再被粗暴卡死

**Files:**
- Modify: `src/services/provider_import/all_in_hub.py`
- Modify: `src/services/provider_import/platform_adapters.py`
- Modify: `src/services/provider_import/reissue.py`
- Test: `tests/services/test_all_in_hub_import.py`
- Test: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写 failing tests，覆盖真实遗留 pending_import 样例**

用这次真实样例建 fixture：
- Anyrouter: `site_type=anyrouter`, `auth_type=cookie`, `has_access_token=true`, `has_session_cookie=true`
- Ciprohtna: `site_type=new-api`, `auth_type=cookie`, `has_access_token=false`, `has_session_cookie=true`
- 黑与白公益站NEXT: `site_type=done-hub`, `auth_type=cookie`, `has_access_token=false`, `has_session_cookie=true`

- [ ] **Step 2: 重新定义 `_build_pending_task_type()` 的最小规则**

建议规则：
- `new-api + has_access_token`：优先 `pending_reissue`
- `sub2api + has_access_token`：`pending_reissue`
- `anyrouter / done-hub / cookie-only new-api`：仍可先保留 `pending_import`，但 metadata 要足够让后续 adapter 识别

不要一次性把所有 cookie 都硬改成 reissue，避免扩大范围。

- [ ] **Step 3: 给 pending_import 执行提供最小扩展点**

本阶段不要求彻底实现 anyrouter / done-hub 自动补完，但要做到：
- `execute` 能明确区分“未实现平台适配” vs “普通失败”
- result 中带 `site_type` / `auth_type` / `has_access_token` 的辅助信息

- [ ] **Step 4: 跑测试**

Run: `pytest tests/services/test_all_in_hub_import.py tests/services/test_all_in_hub_reissue.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/provider_import/all_in_hub.py src/services/provider_import/platform_adapters.py src/services/provider_import/reissue.py tests/services/test_all_in_hub_import.py tests/services/test_all_in_hub_reissue.py
git commit -m "feat(import): 收紧 pending task 分类并保留平台扩展点"
```

### Task 7: 用真实备份回归 verify 环境，形成验收脚本

**Files:**
- Modify: `docs/superpowers/plans/2026-04-05-aether-all-in-hub-metapi-alignment.md` (勾选执行记录或补验收备注)
- Optional Create: `scripts/verify_all_in_hub_import.sh`

- [ ] **Step 1: 准备 verify 环境**

Run:
```bash
docker compose -f docker-compose.verify.yml --env-file .env.verify up -d --build
```
Expected: `aether-verify-app`, `aether-verify-postgres`, `aether-verify-redis` healthy

- [ ] **Step 2: 登录并获取 admin token**

Run:
```bash
curl -X POST http://127.0.0.1:18084/api/auth/login \
  -H 'Content-Type: application/json' \
  -H 'X-Client-Device-Id: device-admin-verify-001' \
  -d '{"email":"admin@example.com","password":"admin123456"}'
```
Expected: 返回 `access_token`

- [ ] **Step 3: 对真实样例跑 preview/import/task execute**

样例文件：
```bash
/Users/zbs/Downloads/all-api-hub-backup-2026-04-05.json
```

Expected baseline（当前旧实现）：
- preview: 54 providers, 1 direct key, 53 pending
- import: 54 providers created, 54 endpoints created, 1 key, 53 tasks

修改后重点观察：
- `tasks/execute` 不再选中 `pending_import`
- `sub2api` 不再统一报“未实现”
- `new-api` 的 `default group` 问题下降
- `results` 中能看到更细阶段信息

- [ ] **Step 4: 直接查库验证**

Run:
```bash
docker exec aether-verify-postgres psql -U postgres -d aether -c "select task_type, status, count(*) from provider_import_tasks group by task_type, status order by task_type, status;"
docker exec aether-verify-postgres psql -U postgres -d aether -c "select is_active, count(*) from provider_api_keys group by is_active order by is_active;"
```

- [ ] **Step 5: 记录回归结论**

至少记录：
- completed / failed / skipped / pending_import remaining
- keys_created / active_keys
- failure buckets 是否从“纯 failed”转成更可解释的阶段化错误

- [ ] **Step 6: Commit（如果脚本或文档有变更）**

```bash
git add scripts/verify_all_in_hub_import.sh docs/superpowers/plans/2026-04-05-aether-all-in-hub-metapi-alignment.md
git commit -m "test(import): 补充 all-in-hub verify 验收脚本与记录"
```

---

## Acceptance checklist

- [ ] `tasks/execute` 只处理 `pending_reissue`
- [ ] `sub2api` 不再停留在“probe 后直接报未实现”
- [ ] `new-api` 支持 group 探测或至少不死写 `default`
- [ ] `new-api` 的 token list / create 有基本 fallback
- [ ] `pending_import` 与 `pending_reissue` 的边界对真实样例更合理
- [ ] API 返回能区分“创建成功但验证失败”与“根本没创建成功”
- [ ] 真实样例 `/Users/zbs/Downloads/all-api-hub-backup-2026-04-05.json` 在 verify 环境完成一轮回归并记录结果

## Risks

- metapi 的 adapter 能力比 Aether 细很多，不能一次性全抄；本计划要求“最小可用迁移”，避免过度重构。
- `new-api` / `sub2api` 站点现实差异大，即使 adapter 对齐，仍会有站点级失败；本计划的重点是把“能力缺口”和“站点坏数据”拆开，而不是承诺所有站点都成功。
- 如果需要数据库层新增任务状态枚举，需另起 migration；本计划先通过 API result 字段增强来降低范围。

## Recommended execution order

1. Chunk 1（先修统计口径和结果可解释性）
2. Chunk 2（补 platform adapter，优先 sub2api + new-api）
3. Chunk 3（再处理 pending_import 边界和真实样例回归）

Plan complete and saved to `docs/superpowers/plans/2026-04-05-aether-all-in-hub-metapi-alignment.md`. Ready to execute?
