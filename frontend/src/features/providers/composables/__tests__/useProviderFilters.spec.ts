import { beforeEach, describe, expect, it } from 'vitest'

import { useProviderFilters } from '../useProviderFilters'

describe('useProviderFilters', () => {
  const storage = new Map<string, string>()

  beforeEach(() => {
    storage.clear()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, value: string) => {
          storage.set(key, value)
        },
        removeItem: (key: string) => {
          storage.delete(key)
        },
        clear: () => {
          storage.clear()
        },
      },
    })
  })

  it('includes import task filter in query params and active filter detection', () => {
    const filters = useProviderFilters(() => [])

    expect(filters.queryParams.value.import_task_status).toBeUndefined()
    expect(filters.hasActiveFilters.value).toBe(false)

    filters.filterImportTaskStatus.value = 'needs_key'

    expect(filters.queryParams.value.import_task_status).toBe('needs_key')
    expect(filters.hasActiveFilters.value).toBe(true)

    filters.resetFilters()

    expect(filters.filterImportTaskStatus.value).toBe('all')
    expect(filters.queryParams.value.import_task_status).toBeUndefined()
    expect(filters.hasActiveFilters.value).toBe(false)
  })

  it('includes proxy filter in query params and active filter detection', () => {
    const filters = useProviderFilters(() => [])

    expect(filters.queryParams.value.proxy_enabled).toBeUndefined()
    expect(filters.hasActiveFilters.value).toBe(false)

    filters.filterProxyEnabled.value = 'enabled'

    expect(filters.queryParams.value.proxy_enabled).toBe('enabled')
    expect(filters.hasActiveFilters.value).toBe(true)

    filters.resetFilters()

    expect(filters.filterProxyEnabled.value).toBe('all')
    expect(filters.queryParams.value.proxy_enabled).toBeUndefined()
  })

  it('persists visible filters and clears value when a filter is hidden', () => {
    const filters = useProviderFilters(() => [])

    filters.filterProxyEnabled.value = 'disabled'
    filters.setFilterVisible('proxyEnabled', false)

    expect(filters.visibleFilterKeys.value.includes('proxyEnabled')).toBe(false)
    expect(filters.filterProxyEnabled.value).toBe('all')

    const stored = window.localStorage.getItem('provider-management-visible-filters')
    expect(stored).toContain('status')
    expect(stored).not.toContain('proxyEnabled')

    const next = useProviderFilters(() => [])
    expect(next.visibleFilterKeys.value.includes('proxyEnabled')).toBe(false)
  })
})
