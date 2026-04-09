# Global Model Routing Overrides Design

**Date:** 2026-04-09

## Goal

让模型管理抽屉页的“链路控制”支持模型级优先级覆盖：

- `provider` 模式下，可针对当前 `GlobalModel` 单独覆盖 Provider 排序
- `global_key` 模式下，可针对当前 `GlobalModel` 单独覆盖当前链路中已有 Key 的格式优先级
- 未设置覆盖时，继续继承渠道商管理里的全局配置

## Scope

本次只支持编辑当前模型链路预览中已经出现的 Provider 和 Key，不新增候选，也不改变渠道商管理原有全局配置入口。

## Data Model

复用 `GlobalModel.config`，新增可选字段：

```json
{
  "routing_overrides": {
    "provider_priorities": {
      "provider-id": 1
    },
    "key_internal_priorities": {
      "key-id": 2
    },
    "key_priorities_by_format": {
      "key-id": {
        "openai:chat": 2
      }
    }
  }
}
```

语义：

- `provider_priorities[provider_id]`：当前模型下 Provider 覆盖优先级
- `key_internal_priorities[key_id]`：当前模型下 Key 内部优先级覆盖（`provider` 模式）
- `key_priorities_by_format[key_id][api_format]`：当前模型下 Key 在指定格式下的覆盖优先级
- 删除对应字段即恢复继承

## Backend Design

### Routing Preview

在 `src/api/admin/models/routing.py` 中：

- 读取 `GlobalModel.config.routing_overrides`
- 为 Provider 返回默认优先级、覆盖优先级、生效优先级
- 为 Key 返回当前格式下默认优先级、覆盖优先级、生效优先级
- Preview 内部排序改为按生效优先级展示，而不是只看全局配置

### Scheduler

在 `src/services/scheduling/candidate_sorter.py` 中：

- 为 `_apply_priority_mode_sort()` 和相关内部方法接入 `global_model_id`
- 在 `provider` 模式下优先读取模型级 `provider_priorities`
- 在 `provider` 模式下同组内优先读取模型级 `key_internal_priorities`
- 在 `global_key` 模式下优先读取模型级 `key_priorities_by_format`
- 没有覆盖时回退到现有 `provider_priority` / `global_priority_by_format`

### Persistence

复用现有 `PATCH /api/admin/models/global/{id}`：

- 前端保存时只更新 `config.routing_overrides`
- 不新增表、不新增专用后端接口

## Frontend Design

在模型抽屉的“链路控制”页内增加编辑能力：

- Provider 行支持编辑模型级 Provider 优先级
- `provider` 模式下的 Key 行支持编辑模型级内部优先级
- `global_key` 模式下的 Key 行支持编辑当前格式下的模型级 Key 优先级
- 明确展示“继承全局”还是“模型覆盖”
- 支持单项恢复默认
- 保存时只回写当前模型发生变更的覆盖项

## Testing

后端：

- `tests/unit/test_candidate_sorter_model_routing_overrides.py`
- `tests/api/test_global_model_routing_overrides.py`

前端：

- `frontend/src/features/models/utils/__tests__/routing-overrides.spec.ts`

## Risks

- `global_model_id` 必须在调度排序链路里保持透传，否则模型级覆盖只会影响预览，不会影响真实调度
- 现有前端 `RoutingTab.vue` 逻辑较重，本次优先抽一层小型 util，避免把编辑和排序判断全部堆进组件
