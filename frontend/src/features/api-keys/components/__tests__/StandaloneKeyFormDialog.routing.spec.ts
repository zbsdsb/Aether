import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'

import type { RoutingGroupBindingRecord, RoutingGroupRecord } from '@/api/routing-profiles'
import StandaloneKeyFormDialog, { type StandaloneKeyFormData } from '../StandaloneKeyFormDialog.vue'

const optionApiMocks = vi.hoisted(() => ({
  getProvidersSummary: vi.fn(),
  getGlobalModels: vi.fn(),
  getApiFormats: vi.fn(),
}))

vi.mock('@/api/endpoints/providers', () => ({
  getProvidersSummary: optionApiMocks.getProvidersSummary,
}))

vi.mock('@/api/global-models', () => ({
  getGlobalModels: optionApiMocks.getGlobalModels,
}))

vi.mock('@/api/admin', () => ({
  adminApi: {
    getApiFormats: optionApiMocks.getApiFormats,
  },
}))

vi.mock('@/components/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/ui')>()
  const empty = (name: string) => defineComponent({
    name,
    inheritAttrs: false,
    setup: () => () => null,
  })

  return {
    ...actual,
    Select: defineComponent({
      name: 'SelectStub',
      props: {
        modelValue: String,
        disabled: Boolean,
      },
      emits: ['update:modelValue'],
      setup: (props, { emit, slots }) => () => h('select', {
        'data-testid': 'routing-group-native-select',
        value: props.modelValue,
        disabled: props.disabled,
        onChange: (event: Event) => emit(
          'update:modelValue',
          (event.target as HTMLSelectElement).value,
        ),
      }, slots.default?.()),
    }),
    SelectTrigger: empty('SelectTriggerStub'),
    SelectValue: empty('SelectValueStub'),
    SelectContent: defineComponent({
      name: 'SelectContentStub',
      setup: (_props, { slots }) => () => slots.default?.(),
    }),
    SelectItem: defineComponent({
      name: 'SelectItemStub',
      props: {
        value: { type: String, required: true },
        disabled: Boolean,
      },
      setup: (props, { slots }) => () => h('option', {
        value: props.value,
        disabled: props.disabled,
      }, slots.default?.()),
    }),
  }
})

vi.mock('@/utils/logger', () => ({
  log: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
  },
}))

const mountedApps: Array<{ app: App; root: HTMLElement }> = []

function group(overrides: Partial<RoutingGroupRecord> = {}): RoutingGroupRecord {
  return {
    id: 'group-1',
    name: '策略一',
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
    id: 'binding-1',
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

function apiKey(overrides: Partial<StandaloneKeyFormData> = {}): StandaloneKeyFormData {
  return {
    id: 'api-key-db-id',
    name: '测试 Key',
    initial_balance_usd: 10,
    unlimited_balance: false,
    auto_delete_on_expiry: false,
    allowed_providers: null,
    allowed_api_formats: null,
    allowed_models: null,
    feature_settings: null,
    ...overrides,
  }
}

async function mountDialog(overrides: Record<string, unknown> = {}) {
  const root = document.createElement('div')
  document.body.appendChild(root)
  const onSubmit = vi.fn()
  const onRetryRoutingLoad = vi.fn()
  const app = createApp(StandaloneKeyFormDialog, {
    open: true,
    apiKey: null,
    routingGroups: [],
    routingBinding: null,
    routingLoading: false,
    routingStateReady: true,
    routingLoadError: null,
    routingSaveError: null,
    onSubmit,
    onRetryRoutingLoad,
    ...overrides,
  })
  app.mount(root)
  mountedApps.push({ app, root })
  await settle()
  return { root, onSubmit, onRetryRoutingLoad }
}

async function settle() {
  for (let index = 0; index < 4; index += 1) {
    await Promise.resolve()
    await nextTick()
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  optionApiMocks.getProvidersSummary.mockResolvedValue({ items: [] })
  optionApiMocks.getGlobalModels.mockResolvedValue({ models: [] })
  optionApiMocks.getApiFormats.mockResolvedValue({ formats: [] })
})

afterEach(() => {
  for (const { app, root } of mountedApps.splice(0)) {
    app.unmount()
    root.remove()
  }
  document.body.innerHTML = ''
})

describe('StandaloneKeyFormDialog routing selection', () => {
  it('shows follow-system plus enabled groups by name and omits disabled groups', async () => {
    await mountDialog({
      routingGroups: [
        group({ id: 'z', name: 'Zulu' }),
        group({ id: 'disabled', name: 'Aardvark', enabled: false }),
        group({ id: 'a', name: 'Alpha' }),
      ],
    })

    const options = [...document.body.querySelectorAll<HTMLOptionElement>(
      '[data-testid="routing-group-native-select"] option',
    )]
    expect(options.map(option => option.textContent?.trim())).toEqual([
      '跟随系统默认（不单独绑定）',
      'Alpha',
      'Zulu',
    ])
    expect(options.map(option => option.value)).not.toContain('disabled')
  })

  it('shows an intelligible disabled current binding and allows replacement or removal', async () => {
    await mountDialog({
      apiKey: apiKey(),
      routingGroups: [
        group({ id: 'group-disabled', name: '旧策略', enabled: false }),
        group({ id: 'group-active', name: '新策略' }),
      ],
      routingBinding: binding({ group_id: 'group-disabled' }),
    })

    expect(document.body.querySelector('[data-testid="routing-binding-unavailable"]')?.textContent)
      .toContain('当前绑定的调度策略“旧策略”已停用')

    const select = document.body.querySelector<HTMLSelectElement>(
      '[data-testid="routing-group-native-select"]',
    )
    expect(select?.value).toBe('group-disabled')
    expect(select?.disabled).toBe(false)
    expect(select?.querySelector<HTMLOptionElement>('option[value="group-disabled"]')?.disabled).toBe(true)
    expect(select?.querySelector('option[value="group-active"]')).not.toBeNull()
    expect(select?.querySelector('option[value="__follow_system_default__"]')).not.toBeNull()
  })

  it('shows an intelligible missing current binding and keeps replace/remove available', async () => {
    await mountDialog({
      apiKey: apiKey(),
      routingGroups: [group({ id: 'group-active', name: '新策略' })],
      routingBinding: binding({ group_id: 'deleted-group' }),
    })

    expect(document.body.querySelector('[data-testid="routing-binding-unavailable"]')?.textContent)
      .toContain('当前绑定的调度策略已不存在（deleted-group）')

    const select = document.body.querySelector<HTMLSelectElement>(
      '[data-testid="routing-group-native-select"]',
    )
    expect(select?.value).toBe('deleted-group')
    expect(select?.querySelector('option[value="group-active"]')).not.toBeNull()
    expect(select?.querySelector('option[value="__follow_system_default__"]')).not.toBeNull()
  })

  it('submits the selected group and follows system default when cleared', async () => {
    const { onSubmit } = await mountDialog({
      routingGroups: [group({ id: 'group-selected', name: '专用策略' })],
    })
    const select = document.body.querySelector<HTMLSelectElement>(
      '[data-testid="routing-group-native-select"]',
    )
    if (!select) throw new Error('Missing routing group select')

    select.value = 'group-selected'
    select.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    document.body.querySelectorAll<HTMLButtonElement>('button')
      .values()
      .find(button => button.textContent?.trim() === '创建')
      ?.click()
    await nextTick()
    expect(onSubmit).toHaveBeenLastCalledWith(expect.objectContaining({
      routing_group_id: 'group-selected',
    }))

    select.value = '__follow_system_default__'
    select.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    document.body.querySelectorAll<HTMLButtonElement>('button')
      .values()
      .find(button => button.textContent?.trim() === '创建')
      ?.click()
    await nextTick()
    expect(onSubmit).toHaveBeenLastCalledWith(expect.objectContaining({
      routing_group_id: null,
    }))
  })

  it('renders read/write errors clearly and exposes retry without blocking Key-only save', async () => {
    const { onRetryRoutingLoad } = await mountDialog({
      routingStateReady: false,
      routingLoadError: '没有调度策略权限',
      routingSaveError: 'API Key 已更新，但调度策略绑定失败：写入失败',
    })

    expect(document.body.querySelector('[data-testid="routing-binding-load-error"]')?.textContent)
      .toContain('没有调度策略权限。API Key 仍可保存，但本次不会修改调度策略绑定。')
    expect(document.body.querySelector('[data-testid="routing-binding-save-error"]')?.textContent)
      .toContain('API Key 已更新，但调度策略绑定失败：写入失败')

    const select = document.body.querySelector<HTMLSelectElement>(
      '[data-testid="routing-group-native-select"]',
    )
    expect(select?.disabled).toBe(true)

    const retry = [...document.body.querySelectorAll<HTMLButtonElement>('button')]
      .find(button => button.textContent?.trim() === '重试')
    retry?.click()
    expect(onRetryRoutingLoad).toHaveBeenCalledTimes(1)

    const submit = [...document.body.querySelectorAll<HTMLButtonElement>('button')]
      .find(button => button.textContent?.trim() === '创建')
    expect(submit?.disabled).toBe(false)
  })

  it('keeps Key-only submit available while routing state is still loading', async () => {
    await mountDialog({
      routingLoading: true,
      routingStateReady: false,
    })

    expect(document.body.querySelector('[data-testid="routing-binding-loading"]')?.textContent)
      .toContain('正在加载调度策略与当前绑定')
    const submit = [...document.body.querySelectorAll<HTMLButtonElement>('button')]
      .find(button => button.textContent?.trim() === '创建')
    expect(submit?.disabled).toBe(false)
  })

})
