import { ref, computed, watch } from 'vue'
import type { ProviderSummaryQuery } from '@/api/endpoints'

export interface FilterOption {
  value: string
  label: string
}

export type ProviderFilterKey =
  | 'status'
  | 'apiFormat'
  | 'model'
  | 'importTaskStatus'
  | 'proxyEnabled'

const VISIBLE_FILTERS_STORAGE_KEY = 'provider-management-visible-filters'
const ALL_FILTER_KEYS: ProviderFilterKey[] = [
  'status',
  'apiFormat',
  'model',
  'importTaskStatus',
  'proxyEnabled',
]
const DEFAULT_VISIBLE_FILTER_KEYS: ProviderFilterKey[] = [
  'status',
  'model',
  'proxyEnabled',
]

function getLocalStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  return window.localStorage ?? null
}

function loadVisibleFilterKeys(): ProviderFilterKey[] {
  const storage = getLocalStorage()
  if (!storage) return [...DEFAULT_VISIBLE_FILTER_KEYS]
  try {
    const raw = storage.getItem(VISIBLE_FILTERS_STORAGE_KEY)
    if (!raw) return [...DEFAULT_VISIBLE_FILTER_KEYS]
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return [...DEFAULT_VISIBLE_FILTER_KEYS]
    const valid = parsed.filter((item): item is ProviderFilterKey =>
      ALL_FILTER_KEYS.includes(item as ProviderFilterKey),
    )
    return valid.length > 0 ? valid : [...DEFAULT_VISIBLE_FILTER_KEYS]
  } catch {
    return [...DEFAULT_VISIBLE_FILTER_KEYS]
  }
}

function saveVisibleFilterKeys(keys: ProviderFilterKey[]) {
  const storage = getLocalStorage()
  if (!storage) return
  storage.setItem(VISIBLE_FILTERS_STORAGE_KEY, JSON.stringify(keys))
}

export function useProviderFilters(
  globalModels: () => { id: string; name: string }[],
) {
  // 搜索与筛选
  const searchQuery = ref('')
  const filterStatus = ref('all')
  const filterApiFormat = ref('all')
  const filterModel = ref('all')
  const filterImportTaskStatus = ref('all')
  const filterProxyEnabled = ref('all')
  const visibleFilterKeys = ref<ProviderFilterKey[]>(loadVisibleFilterKeys())

  const statusFilters: FilterOption[] = [
    { value: 'all', label: '全部状态' },
    { value: 'active', label: '活跃' },
    { value: 'inactive', label: '停用' },
  ]

  const apiFormatFilters: FilterOption[] = [
    { value: 'all', label: '全部格式' },
    { value: 'claude:chat', label: 'Claude Chat' },
    { value: 'claude:cli', label: 'Claude CLI' },
    { value: 'openai:chat', label: 'OpenAI Chat' },
    { value: 'openai:cli', label: 'OpenAI CLI' },
    { value: 'openai:compact', label: 'OpenAI Compact' },
    { value: 'gemini:chat', label: 'Gemini Chat' },
    { value: 'gemini:cli', label: 'Gemini CLI' },
  ]

  const importTaskFilters: FilterOption[] = [
    { value: 'all', label: '全部导入状态' },
    { value: 'needs_key', label: '待补钥' },
    { value: 'manual_review', label: '待复核' },
  ]

  const proxyFilters: FilterOption[] = [
    { value: 'all', label: '全部代理状态' },
    { value: 'enabled', label: '已启用代理' },
    { value: 'disabled', label: '未启用代理' },
  ]

  const modelFilters = computed<FilterOption[]>(() => {
    const items = globalModels()
      .map(m => ({ value: m.id, label: m.name }))
      .sort((a, b) => a.label.localeCompare(b.label))
    return [{ value: 'all', label: '全部模型' }, ...items]
  })

  const hasActiveFilters = computed(() => {
    return (
      searchQuery.value !== '' ||
      filterStatus.value !== 'all' ||
      filterApiFormat.value !== 'all' ||
      filterModel.value !== 'all' ||
      filterImportTaskStatus.value !== 'all' ||
      filterProxyEnabled.value !== 'all'
    )
  })

  // 分页
  const currentPage = ref(1)
  const pageSize = ref(20)
  const total = ref(0)

  // 服务端分页查询参数
  const queryParams = computed<ProviderSummaryQuery>(() => ({
    page: currentPage.value,
    page_size: pageSize.value,
    search: searchQuery.value.trim() || undefined,
    status: filterStatus.value !== 'all' ? filterStatus.value : undefined,
    api_format: filterApiFormat.value !== 'all' ? filterApiFormat.value : undefined,
    model_id: filterModel.value !== 'all' ? filterModel.value : undefined,
    import_task_status:
      filterImportTaskStatus.value !== 'all' ? filterImportTaskStatus.value : undefined,
    proxy_enabled: filterProxyEnabled.value !== 'all' ? filterProxyEnabled.value : undefined,
  }))

  // 搜索/筛选变化时重置分页到第1页
  watch([
    searchQuery,
    filterStatus,
    filterApiFormat,
    filterModel,
    filterImportTaskStatus,
    filterProxyEnabled,
  ], () => {
    currentPage.value = 1
  })

  watch(
    visibleFilterKeys,
    (keys) => {
      saveVisibleFilterKeys(keys)
      if (!keys.includes('status')) filterStatus.value = 'all'
      if (!keys.includes('apiFormat')) filterApiFormat.value = 'all'
      if (!keys.includes('model')) filterModel.value = 'all'
      if (!keys.includes('importTaskStatus')) filterImportTaskStatus.value = 'all'
      if (!keys.includes('proxyEnabled')) filterProxyEnabled.value = 'all'
    },
    { deep: true },
  )

  function resetFilters() {
    searchQuery.value = ''
    filterStatus.value = 'all'
    filterApiFormat.value = 'all'
    filterModel.value = 'all'
    filterImportTaskStatus.value = 'all'
    filterProxyEnabled.value = 'all'
  }

  function setFilterVisible(filterKey: ProviderFilterKey, visible: boolean) {
    const next = new Set(visibleFilterKeys.value)
    if (visible) {
      next.add(filterKey)
    } else {
      if (filterKey === 'status') filterStatus.value = 'all'
      if (filterKey === 'apiFormat') filterApiFormat.value = 'all'
      if (filterKey === 'model') filterModel.value = 'all'
      if (filterKey === 'importTaskStatus') filterImportTaskStatus.value = 'all'
      if (filterKey === 'proxyEnabled') filterProxyEnabled.value = 'all'
      next.delete(filterKey)
    }
    const normalized = ALL_FILTER_KEYS.filter(key => next.has(key))
    visibleFilterKeys.value = normalized
    saveVisibleFilterKeys(normalized)
  }

  return {
    searchQuery,
    filterStatus,
    filterApiFormat,
    filterModel,
    filterImportTaskStatus,
    filterProxyEnabled,
    visibleFilterKeys,
    statusFilters,
    apiFormatFilters,
    modelFilters,
    importTaskFilters,
    proxyFilters,
    hasActiveFilters,
    currentPage,
    pageSize,
    total,
    queryParams,
    resetFilters,
    setFilterVisible,
  }
}
