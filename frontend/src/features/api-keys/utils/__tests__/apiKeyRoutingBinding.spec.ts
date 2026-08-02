import { describe, expect, it, vi } from 'vitest'

import type {
  RoutingGroupBindingRecord,
  RoutingGroupRecord,
} from '@/api/routing-profiles'
import {
  createApiKeyWithRoutingBinding,
  describeCurrentRoutingGroup,
  enabledRoutingGroupsByName,
  readApiKeyDefaultRoutingBinding,
  saveApiKeyDefaultRoutingBinding,
  type ApiKeyRoutingBindingApi,
} from '@/features/api-keys/utils/apiKeyRoutingBinding'

function group(overrides: Partial<RoutingGroupRecord> = {}): RoutingGroupRecord {
  return {
    id: 'group-1',
    name: '默认策略',
    description: null,
    enabled: true,
    is_system_default: false,
    config_json: {
      allowed_models: [],
      default_policy: {
        priority_mode: 'provider',
        scheduling_mode: 'cache_affinity',
        keep_priority_on_conversion: false,
      },
      model_policies: [],
      rules: [],
    },
    version: 1,
    created_at: 1,
    updated_at: 1,
    published_at: null,
    ...overrides,
  }
}

function binding(overrides: Partial<RoutingGroupBindingRecord> = {}): RoutingGroupBindingRecord {
  return {
    id: 'binding-default',
    group_id: 'group-1',
    subject_type: 'api_key',
    subject_id: 'api-key-db-id',
    is_default: true,
    allow_explicit_select: false,
    created_at: 1,
    updated_at: 1,
    ...overrides,
  }
}

function bindingApi(): ApiKeyRoutingBindingApi & {
  listBindings: ReturnType<typeof vi.fn>
  createBinding: ReturnType<typeof vi.fn>
  updateBinding: ReturnType<typeof vi.fn>
  deleteBinding: ReturnType<typeof vi.fn>
} {
  return {
    listBindings: vi.fn(),
    createBinding: vi.fn(),
    updateBinding: vi.fn(),
    deleteBinding: vi.fn(),
  }
}

describe('API Key routing binding behavior', () => {
  it('lists only enabled routing groups ordered by name', () => {
    const result = enabledRoutingGroupsByName([
      group({ id: 'z', name: 'Zulu' }),
      group({ id: 'disabled', name: 'Aardvark', enabled: false }),
      group({ id: 'a', name: 'Alpha' }),
    ])

    expect(result.map(item => [item.id, item.name])).toEqual([
      ['a', 'Alpha'],
      ['z', 'Zulu'],
    ])
  })

  it('reads only the API Key default binding and preserves non-default records', async () => {
    const api = bindingApi()
    const nonDefault = binding({ id: 'binding-explicit', is_default: false })
    const unrelated = binding({ id: 'other-key', subject_id: 'other-api-key' })
    const current = binding()
    api.listBindings.mockResolvedValue({
      items: [nonDefault, unrelated, current],
      total: 3,
    })

    await expect(readApiKeyDefaultRoutingBinding('api-key-db-id', api)).resolves.toEqual(current)
    expect(api.listBindings).toHaveBeenCalledWith({
      subject_type: 'api_key',
      subject_id: 'api-key-db-id',
    })
    expect(api.updateBinding).not.toHaveBeenCalled()
    expect(api.deleteBinding).not.toHaveBeenCalled()
  })

  it('uses the most recently updated record if inconsistent data contains multiple defaults', async () => {
    const api = bindingApi()
    const older = binding({ id: 'binding-older', group_id: 'group-old', updated_at: 10 })
    const newer = binding({ id: 'binding-newer', group_id: 'group-new', updated_at: 20 })
    api.listBindings.mockResolvedValue({ items: [older, newer], total: 2 })

    await expect(readApiKeyDefaultRoutingBinding('api-key-db-id', api)).resolves.toEqual(newer)
  })

  it('creates a dedicated default binding with the required fixed flags', async () => {
    const api = bindingApi()
    const created = binding({ group_id: 'group-selected' })
    api.createBinding.mockResolvedValue(created)

    await expect(saveApiKeyDefaultRoutingBinding({
      apiKeyId: 'api-key-db-id',
      selectedGroupId: 'group-selected',
      currentBinding: null,
    }, api)).resolves.toEqual({ action: 'created', binding: created })

    expect(api.createBinding).toHaveBeenCalledWith({
      group_id: 'group-selected',
      subject_type: 'api_key',
      subject_id: 'api-key-db-id',
      is_default: true,
      allow_explicit_select: false,
    })
  })

  it('switches an existing default binding without touching non-default bindings', async () => {
    const api = bindingApi()
    const current = binding({ group_id: 'group-old' })
    const updated = binding({ group_id: 'group-new' })
    api.updateBinding.mockResolvedValue(updated)

    await expect(saveApiKeyDefaultRoutingBinding({
      apiKeyId: 'api-key-db-id',
      selectedGroupId: 'group-new',
      currentBinding: current,
    }, api)).resolves.toEqual({ action: 'updated', binding: updated })

    expect(api.updateBinding).toHaveBeenCalledWith('binding-default', {
      group_id: 'group-new',
    })
    expect(api.createBinding).not.toHaveBeenCalled()
    expect(api.deleteBinding).not.toHaveBeenCalled()
  })

  it('does not mutate when the selected default binding is unchanged', async () => {
    const api = bindingApi()
    const current = binding({ group_id: 'group-selected' })

    await expect(saveApiKeyDefaultRoutingBinding({
      apiKeyId: 'api-key-db-id',
      selectedGroupId: 'group-selected',
      currentBinding: current,
    }, api)).resolves.toEqual({ action: 'unchanged', binding: current })

    expect(api.createBinding).not.toHaveBeenCalled()
    expect(api.updateBinding).not.toHaveBeenCalled()
    expect(api.deleteBinding).not.toHaveBeenCalled()
  })

  it('removes the current default binding when following the system default', async () => {
    const api = bindingApi()
    api.deleteBinding.mockResolvedValue(undefined)

    await expect(saveApiKeyDefaultRoutingBinding({
      apiKeyId: 'api-key-db-id',
      selectedGroupId: null,
      currentBinding: binding(),
    }, api)).resolves.toEqual({ action: 'deleted', binding: null })

    expect(api.deleteBinding).toHaveBeenCalledWith('binding-default')
    expect(api.updateBinding).not.toHaveBeenCalled()
    expect(api.createBinding).not.toHaveBeenCalled()
  })

  it('does not delete a non-default binding when clearing the selection', async () => {
    const api = bindingApi()

    await expect(saveApiKeyDefaultRoutingBinding({
      apiKeyId: 'api-key-db-id',
      selectedGroupId: null,
      currentBinding: binding({ id: 'binding-explicit', is_default: false }),
    }, api)).resolves.toEqual({ action: 'unchanged', binding: null })

    expect(api.deleteBinding).not.toHaveBeenCalled()
  })

  it('describes disabled and missing current groups without hiding the binding', () => {
    expect(describeCurrentRoutingGroup(binding(), [
      group({ enabled: false, name: '旧策略' }),
    ])).toMatchObject({
      kind: 'disabled',
      label: '当前绑定的调度策略“旧策略”已停用',
    })

    expect(describeCurrentRoutingGroup(binding({ group_id: 'deleted-group' }), [])).toEqual({
      kind: 'missing',
      group: null,
      label: '当前绑定的调度策略已不存在（deleted-group）',
    })
  })

  it('propagates read and write errors for clear UI feedback', async () => {
    const readApi = bindingApi()
    const readError = new Error('binding read failed')
    readApi.listBindings.mockRejectedValue(readError)
    await expect(readApiKeyDefaultRoutingBinding('api-key-db-id', readApi)).rejects.toBe(readError)

    const writeApi = bindingApi()
    const writeError = new Error('binding write failed')
    writeApi.createBinding.mockRejectedValue(writeError)
    await expect(saveApiKeyDefaultRoutingBinding({
      apiKeyId: 'api-key-db-id',
      selectedGroupId: 'group-selected',
      currentBinding: null,
    }, writeApi)).rejects.toBe(writeError)
  })

  it('preserves the one-time key before reporting binding partial success', async () => {
    const api = bindingApi()
    const events: string[] = []
    const writeError = new Error('binding write failed')
    api.createBinding.mockImplementation(async () => {
      events.push('binding-started')
      throw writeError
    })
    const created = { id: 'api-key-db-id', key: 'sk-one-time-plaintext', name: '新 Key' }

    const result = await createApiKeyWithRoutingBinding({
      request: { name: '新 Key' },
      selectedGroupId: 'group-selected',
      createApiKey: vi.fn(async () => created),
      onApiKeyCreated: (apiKey) => {
        events.push(`key-preserved:${apiKey.key}`)
      },
      bindingApi: api,
    })

    expect(events).toEqual([
      'key-preserved:sk-one-time-plaintext',
      'binding-started',
    ])
    expect(api.createBinding).toHaveBeenCalledWith(expect.objectContaining({
      subject_id: 'api-key-db-id',
    }))
    expect(api.createBinding).not.toHaveBeenCalledWith(expect.objectContaining({
      subject_id: 'sk-one-time-plaintext',
    }))
    expect(result).toEqual({
      apiKey: created,
      bindingStatus: 'failed',
      bindingError: writeError,
    })
  })

  it('skips binding when the Key follows the system default', async () => {
    const api = bindingApi()
    const created = { id: 'api-key-db-id', key: 'sk-one-time-plaintext' }

    await expect(createApiKeyWithRoutingBinding({
      request: { name: '跟随默认' },
      selectedGroupId: null,
      createApiKey: vi.fn(async () => created),
      onApiKeyCreated: vi.fn(),
      bindingApi: api,
    })).resolves.toEqual({
      apiKey: created,
      bindingStatus: 'not_requested',
    })

    expect(api.createBinding).not.toHaveBeenCalled()
  })
})
