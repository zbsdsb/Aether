import { describe, expect, it } from 'vitest'

import type { ProviderImportTaskOverview } from '@/api/endpoints'

import {
  buildImportTaskOverviewSignature,
  hasActionableImportTasks,
  isImportTaskOverviewPermanentlyDismissed,
  shouldResetImportTaskOverviewDismissed,
} from '../import-task-overview'

const emptyOverview: ProviderImportTaskOverview = {
  providers_with_import_tasks: 0,
  providers_with_pending_tasks: 0,
  providers_needing_manual_key_input: 0,
  providers_needing_manual_review: 0,
  tasks_pending: 0,
  tasks_waiting_plaintext: 0,
  tasks_failed: 0,
}

describe('import task overview utils', () => {
  it('detects whether the overview has actionable items', () => {
    expect(hasActionableImportTasks(emptyOverview)).toBe(false)
    expect(
      hasActionableImportTasks({
        ...emptyOverview,
        providers_needing_manual_key_input: 1,
      }),
    ).toBe(true)
    expect(
      hasActionableImportTasks({
        ...emptyOverview,
        providers_needing_manual_review: 1,
      }),
    ).toBe(true)
  })

  it('resets dismissed state only when actionable counts change', () => {
    const waitingOverview: ProviderImportTaskOverview = {
      ...emptyOverview,
      providers_needing_manual_key_input: 1,
      tasks_waiting_plaintext: 1,
    }

    expect(shouldResetImportTaskOverviewDismissed(waitingOverview, waitingOverview)).toBe(false)
    expect(shouldResetImportTaskOverviewDismissed(emptyOverview, waitingOverview)).toBe(true)
    expect(
      shouldResetImportTaskOverviewDismissed(waitingOverview, {
        ...waitingOverview,
        providers_needing_manual_review: 1,
        tasks_failed: 1,
      }),
    ).toBe(true)
    expect(buildImportTaskOverviewSignature(waitingOverview)).toBe('1:0:1:0')
  })

  it('treats matching actionable signature as permanently dismissed', () => {
    const waitingOverview: ProviderImportTaskOverview = {
      ...emptyOverview,
      providers_needing_manual_key_input: 1,
      tasks_waiting_plaintext: 1,
    }

    expect(isImportTaskOverviewPermanentlyDismissed('1:0:1:0', waitingOverview)).toBe(true)
    expect(isImportTaskOverviewPermanentlyDismissed('0:0:0:0', waitingOverview)).toBe(false)
    expect(isImportTaskOverviewPermanentlyDismissed('1:0:1:0', emptyOverview)).toBe(false)
  })
})
