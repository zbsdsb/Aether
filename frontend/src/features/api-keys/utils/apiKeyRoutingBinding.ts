import {
  createRoutingGroupBinding,
  deleteRoutingGroupBinding,
  listRoutingGroupBindings,
  updateRoutingGroupBinding,
  type RoutingGroupBindingCreateRequest,
  type RoutingGroupBindingListResponse,
  type RoutingGroupBindingRecord,
  type RoutingGroupBindingUpdateRequest,
  type RoutingGroupRecord,
} from '@/api/routing-profiles'

export const FOLLOW_SYSTEM_ROUTING_GROUP_VALUE = '__follow_system_default__'

export interface ApiKeyRoutingBindingApi {
  listBindings: (params: {
    subject_type: 'api_key'
    subject_id: string
  }) => Promise<RoutingGroupBindingListResponse>
  createBinding: (data: RoutingGroupBindingCreateRequest) => Promise<RoutingGroupBindingRecord>
  updateBinding: (
    bindingId: string,
    data: RoutingGroupBindingUpdateRequest,
  ) => Promise<RoutingGroupBindingRecord>
  deleteBinding: (bindingId: string) => Promise<void>
}

export type ApiKeyDefaultBindingMutation =
  | { action: 'unchanged'; binding: RoutingGroupBindingRecord | null }
  | { action: 'created'; binding: RoutingGroupBindingRecord }
  | { action: 'updated'; binding: RoutingGroupBindingRecord }
  | { action: 'deleted'; binding: null }

export type CurrentRoutingGroupState =
  | { kind: 'active'; group: RoutingGroupRecord; label: string }
  | { kind: 'disabled'; group: RoutingGroupRecord; label: string }
  | { kind: 'missing'; group: null; label: string }

const defaultBindingApi: ApiKeyRoutingBindingApi = {
  listBindings: listRoutingGroupBindings,
  createBinding: createRoutingGroupBinding,
  updateBinding: updateRoutingGroupBinding,
  deleteBinding: deleteRoutingGroupBinding,
}

export function enabledRoutingGroupsByName(
  groups: readonly RoutingGroupRecord[],
): RoutingGroupRecord[] {
  return groups
    .filter(group => group.enabled)
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'))
}

export function findApiKeyDefaultRoutingBinding(
  bindings: readonly RoutingGroupBindingRecord[],
  apiKeyId: string,
): RoutingGroupBindingRecord | null {
  const defaults = bindings
    .filter(binding => isManagedDefaultBinding(binding, apiKeyId))
    .sort((left, right) => right.updated_at - left.updated_at || left.id.localeCompare(right.id))
  return defaults[0] ?? null
}

export async function readApiKeyDefaultRoutingBinding(
  apiKeyId: string,
  api: ApiKeyRoutingBindingApi = defaultBindingApi,
): Promise<RoutingGroupBindingRecord | null> {
  const response = await api.listBindings({
    subject_type: 'api_key',
    subject_id: apiKeyId,
  })
  return findApiKeyDefaultRoutingBinding(response.items, apiKeyId)
}

export async function saveApiKeyDefaultRoutingBinding(
  input: {
    apiKeyId: string
    selectedGroupId: string | null
    currentBinding: RoutingGroupBindingRecord | null
  },
  api: ApiKeyRoutingBindingApi = defaultBindingApi,
): Promise<ApiKeyDefaultBindingMutation> {
  const selectedGroupId = normalizedGroupId(input.selectedGroupId)
  const currentBinding = input.currentBinding
    && isManagedDefaultBinding(input.currentBinding, input.apiKeyId)
    ? input.currentBinding
    : null

  if (!selectedGroupId) {
    if (!currentBinding) {
      return { action: 'unchanged', binding: null }
    }
    await api.deleteBinding(currentBinding.id)
    return { action: 'deleted', binding: null }
  }

  if (currentBinding?.group_id === selectedGroupId) {
    return { action: 'unchanged', binding: currentBinding }
  }

  if (currentBinding) {
    const binding = await api.updateBinding(currentBinding.id, {
      group_id: selectedGroupId,
    })
    return { action: 'updated', binding }
  }

  const binding = await api.createBinding({
    group_id: selectedGroupId,
    subject_type: 'api_key',
    subject_id: input.apiKeyId,
    is_default: true,
    allow_explicit_select: false,
  })
  return { action: 'created', binding }
}

export function describeCurrentRoutingGroup(
  binding: RoutingGroupBindingRecord,
  groups: readonly RoutingGroupRecord[],
): CurrentRoutingGroupState {
  const group = groups.find(item => item.id === binding.group_id)
  if (!group) {
    return {
      kind: 'missing',
      group: null,
      label: `当前绑定的调度策略已不存在（${binding.group_id}）`,
    }
  }
  if (!group.enabled) {
    return {
      kind: 'disabled',
      group,
      label: `当前绑定的调度策略“${group.name}”已停用`,
    }
  }
  return {
    kind: 'active',
    group,
    label: group.name,
  }
}

export interface CreatedStandaloneApiKey {
  id: string
  key: string
}

export type CreateApiKeyWithRoutingResult<T extends CreatedStandaloneApiKey> = {
  apiKey: T
  bindingStatus: 'not_requested' | 'saved' | 'failed'
  bindingError?: unknown
}

export async function createApiKeyWithRoutingBinding<
  TRequest,
  TCreated extends CreatedStandaloneApiKey,
>(input: {
  request: TRequest
  selectedGroupId: string | null
  createApiKey: (request: TRequest) => Promise<TCreated>
  onApiKeyCreated: (apiKey: TCreated) => void
  bindingApi?: ApiKeyRoutingBindingApi
}): Promise<CreateApiKeyWithRoutingResult<TCreated>> {
  const apiKey = await input.createApiKey(input.request)

  // 必须在任何后续网络请求前同步保存一次性明文 Key，避免绑定失败时丢失。
  input.onApiKeyCreated(apiKey)

  if (!normalizedGroupId(input.selectedGroupId)) {
    return { apiKey, bindingStatus: 'not_requested' }
  }

  try {
    await saveApiKeyDefaultRoutingBinding({
      apiKeyId: apiKey.id,
      selectedGroupId: input.selectedGroupId,
      currentBinding: null,
    }, input.bindingApi ?? defaultBindingApi)
    return { apiKey, bindingStatus: 'saved' }
  } catch (bindingError) {
    return { apiKey, bindingStatus: 'failed', bindingError }
  }
}

function normalizedGroupId(groupId: string | null): string | null {
  const normalized = groupId?.trim()
  return normalized || null
}

function isManagedDefaultBinding(
  binding: RoutingGroupBindingRecord,
  apiKeyId: string,
): boolean {
  return binding.subject_type === 'api_key'
    && binding.subject_id === apiKeyId
    && binding.is_default === true
}
