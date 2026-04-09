# 缺陷清单

## 2026-04-09 Aether 模型操练场

| 缺陷 ID | 发现阶段 | 功能 ID | 严重级别 | 状态 | 复现步骤 | 预期结果 | 实际结果 | 负责人 | 复验用例 |
|---|---|---|---|---|---|---|---|---|---|
| D-PG-01 | `final` | `F-PG-03` | `medium` | `open` | 1. 在浏览器上下文用当前 `aether_client_device_id` 以管理员身份登录 2. 写入 `access_token` 后访问 `http://127.0.0.1:5173/admin/playground` | 已登录态应进入后台 `模型操练场` 并可继续做页面交互验收 | 前端随后调用 `/api/users/me` 返回 `401`，后端日志报错 `设备标识与登录会话不匹配`，浏览器被重定向回首页，导致无法完成真实后台页面验收 | `product/auth` | `TC-PG-03` |

当前无新增产品缺陷。

本轮仅发现 1 个验收工具问题，未归类为产品缺陷：

| 缺陷 ID | 发现阶段 | 功能 ID | 严重级别 | 状态 | 复现步骤 | 预期结果 | 实际结果 | 负责人 | 复验用例 |
|---|---|---|---|---|---|---|---|---|---|
| D-TOOL-01 | `final` | `F-01` | `low` | `open` | 执行 `proofshot start ...` 后完成若干 `proofshot exec`，再执行 `proofshot stop` | proofshot 正常收尾并产出 `session.webm`、`server.log` | `proofshot stop` 返回 `No active session found`，留证退化为截图 + metadata | `tooling` | `TC-01` `TC-02` `TC-03` |

## 关闭规则

仅在满足以下条件后才能关闭缺陷：

1. 目标修复已落地
2. 定向测试已通过
3. proofshot 或独立验收者已完成复验
