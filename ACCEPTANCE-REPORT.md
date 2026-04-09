# 验收报告

## 2026-04-09 Aether 模型操练场验收

### 摘要

- 任务：`aether-model-playground-browser-acceptance`
- 阶段：`final`
- 验收角色：`Codex browser verifier`
- 日期：`2026-04-09 09:56 CST`
- 结论：`未通过（降级留证）`

### 证据明细

| 用例 ID | 功能 ID | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| TC-PG-01 | `F-PG-01` | `02-home-redirected.png` 定向前端测试 `9 passed` `npm run build` | 通过 | 当前 worktree 前端已包含 `模型操练场` 页面实现，新增路由 `/dashboard/playground`、`/admin/playground`，且生产构建成功产出 `dist/assets/ModelPlayground-*.js` |
| TC-PG-02 | `F-PG-02` | `uv run python -m pytest tests/api/test_admin_global_model_playground_routes.py tests/api/test_admin_provider_playground_probe_routes.py tests/unit/test_provider_query_failover_endpoint.py -v` | 通过 | 后端全局模型测试接口与渠道未配置协议 probe 接口均通过定向测试，结果 `15 passed` |
| TC-PG-03 | `F-PG-03` | 后端日志留证 `设备标识与登录会话不匹配` `03-admin-playground-blank.png` | 未通过 | 浏览器级验收被认证链路拦截：在浏览器上下文获取 token 后访问 `/admin/playground` 仍触发 `/api/users/me -> 401`，后端明确返回 `设备标识与登录会话不匹配`，导致无法稳定进入真实后台页面完成交互验收 |

### Proofshot / Browser 执行记录

- 命令：
  - `proofshot start --url http://127.0.0.1:5173 --port 5173 --description "Aether 模型操练场页面验收" --output /Users/zbs/.codex/worktrees/710b/Aether/proofshot-artifacts/2026-04-09-model-playground --force`
  - `agent-browser screenshot /Users/zbs/.codex/worktrees/710b/Aether/proofshot-artifacts/2026-04-09-model-playground/02-home-redirected.png`
  - `agent-browser screenshot /Users/zbs/.codex/worktrees/710b/Aether/proofshot-artifacts/2026-04-09-model-playground/03-admin-playground-blank.png`
- 证据目录：`/Users/zbs/.codex/worktrees/710b/Aether/proofshot-artifacts/2026-04-09-model-playground`
- 录屏状态：`降级`

降级说明：

- proofshot 成功启动并生成了多次 `session.webm` / `metadata.json`
- 但 `proofshot exec` 与本机 `agent-browser` 默认 socket 存在冲突，导致会话控制不稳定
- 浏览器最终未能完成“后台已登录态进入模型操练场”的稳定交互，因此本次只能基于截图、构建结果、定向测试结果和后端日志给出降级结论

### 当前结论

- 代码层面：`模型操练场` 的前后端实现、路由、构建和定向测试均已通过
- 浏览器层面：未完成最终“已登录后台真实交互”验收
- 当前阻塞点不是页面编译失败或路由缺失，而是浏览器登录态与设备绑定会话不匹配

### 未关闭缺陷

- 见 `DEFECTS.md` 中的 `D-PG-01`

## 摘要

- 任务：`aether-imported-auth-prefill-browser-acceptance`
- 阶段：`final`
- 验收角色：`Codex browser verifier`
- 日期：`2026-04-07 18:18 CST`
- 结论：`通过（降级留证）`

## 证据明细

| 用例 ID | 功能 ID | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| TC-01 | `F-01` | `01-home.png` `02-login-form.png` `03-login-ready.png` | 通过 | 成功进入 `http://127.0.0.1:18084/` 并以 `admin` 登录后台 |
| TC-02 | `F-01` | `04-admin-dashboard.png` `05-provider-list.png` `06-provider-drawer.png` | 通过 | 后台 Provider 列表可打开真实带导入任务的 `https://wzw.pp.ua` Provider 详情抽屉，且出现“使用导入凭证填充用户认证”按钮 |
| TC-03 | `F-01` | `07-prefill-dialog.png` 浏览器 DOM 抓取值 数据库解密对照 | 通过 | 点击按钮后弹出“用户认证”对话框，模板显示 `New API`，并预填 `站点地址=https://wzw.pp.ua`、`访问令牌 (API Key)=p8bic0J5enL3imVdO84BfMn0kOSJ`、`用户 ID=14495`；`Cookie` 为空，和 `ProviderImportTask` 的 `credential_payload/source_metadata` 一致 |

## Proofshot 执行记录

- 命令：`proofshot start --url http://127.0.0.1:18084 --port 18084 --description "Aether Provider 导入凭证预填充浏览器级验收" --output /Users/zbs/projectwork/zbs/Aether/proofshot-artifacts/2026-04-07-imported-auth-prefill --force`
- 证据目录：`/Users/zbs/projectwork/zbs/Aether/proofshot-artifacts/2026-04-07-imported-auth-prefill`
- 录屏状态：`降级`

降级说明：

- `proofshot start` 成功启动浏览器并写入 `.session.json` 与 `metadata.json`
- `proofshot exec screenshot ...` 生成了 7 张截图证据
- `proofshot exec console` 与 `proofshot exec errors` 均为空
- 但 `proofshot stop` 返回 `No active session found`，导致 `session.webm` 与 `server.log` 未实际落盘
- 因此本次验收以截图、DOM 抓取值、数据库对照和命令日志作为降级证据，不宣称拿到了完整录屏 bundle

## 未关闭缺陷

- 无新增产品缺陷
