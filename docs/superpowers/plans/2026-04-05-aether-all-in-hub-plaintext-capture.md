# Aether All-in-Hub Plaintext Capture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 all-in-hub `pending_reissue` 增加“外部/浏览器补抓明文后回填并继续验证”的后端闭环，解决 new-api 掩码 key 无法自动导入的问题。

**Architecture:** 保持现有 `pending_reissue` 主线不变；当站点只返回 masked key 时，不再落库无效 Key，而是把任务切换到 `waiting_plaintext` 状态并暴露结构化 action-required 信息。新增后台回填接口，在收到明文后创建 `ProviderAPIKey`、执行副作用与模型验证，并回写任务状态。

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, pytest

---

## Chunk 1: Task state and execution payload

### Task 1: 扩展任务执行返回，暴露待补钥状态

**Files:**
- Modify: `src/models/provider_import.py`
- Modify: `src/services/provider_import/reissue.py`
- Test: `tests/services/test_all_in_hub_reissue.py`
- Test: `tests/api/test_admin_all_in_hub_import_routes.py`

- [ ] **Step 1: 写 masked key 任务进入 waiting_plaintext 的失败测试**
- [ ] **Step 2: 跑单测确认失败**
- [ ] **Step 3: 在执行结果里增加 `action_required/plaintext_capture_status/masked_key_preview` 字段，并让 masked key 切到 waiting_plaintext**
- [ ] **Step 4: 跑定向单测确认转绿**

## Chunk 2: Plaintext submit service

### Task 2: 增加明文回填服务逻辑

**Files:**
- Modify: `src/services/provider_import/reissue.py`
- Test: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写“回填明文后创建 Key 并完成任务”的失败测试**
- [ ] **Step 2: 跑单测确认失败**
- [ ] **Step 3: 实现 `submit_all_in_hub_task_plaintext(...)` 最小逻辑**
- [ ] **Step 4: 跑定向单测确认转绿**

### Task 3: 补非法状态/无效 task 的保护

**Files:**
- Modify: `src/services/provider_import/reissue.py`
- Test: `tests/services/test_all_in_hub_reissue.py`

- [ ] **Step 1: 写“非 waiting_plaintext task 不允许回填”的失败测试**
- [ ] **Step 2: 跑单测确认失败**
- [ ] **Step 3: 写最小校验实现**
- [ ] **Step 4: 跑定向单测确认转绿**

## Chunk 3: Admin route

### Task 4: 增加后台回填接口

**Files:**
- Modify: `src/models/provider_import.py`
- Modify: `src/api/admin/providers/routes.py`
- Test: `tests/api/test_admin_all_in_hub_import_routes.py`

- [ ] **Step 1: 写回填接口失败测试**
- [ ] **Step 2: 跑路由测试确认失败**
- [ ] **Step 3: 实现 `POST /api/admin/providers/imports/all-in-hub/tasks/{task_id}/submit-plaintext`**
- [ ] **Step 4: 跑路由测试确认转绿**

## Chunk 4: Verification

### Task 5: 完整验证

**Files:**
- Modify: `tests/services/test_all_in_hub_reissue.py`
- Modify: `tests/api/test_admin_all_in_hub_import_routes.py`

- [ ] **Step 1: 跑后端测试**
Run: `uv run pytest -q tests/services/test_all_in_hub_import.py tests/services/test_all_in_hub_reissue.py tests/api/test_admin_all_in_hub_import_routes.py`
Expected: PASS

- [ ] **Step 2: 跑前端类型检查**
Run: `cd frontend && npm exec vue-tsc -- --noEmit`
Expected: PASS

- [ ] **Step 3: 用 verify 环境做真实最小闭环**
Run: 导入真实备份 -> execute 5 个 task，确认 `new-api` masked key 进入 `waiting_plaintext`；再任选一个 task 调 submit-plaintext 验证回填链路
Expected: 运行态不再错误落库 masked key，并能通过回填接口推进任务
