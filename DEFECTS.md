# 缺陷清单

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
