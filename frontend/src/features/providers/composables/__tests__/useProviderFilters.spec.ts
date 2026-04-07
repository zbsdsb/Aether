import { describe, expect, it } from 'vitest'

import { useProviderFilters } from '../useProviderFilters'

describe('useProviderFilters', () => {
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
})
