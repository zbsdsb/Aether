import type { ProviderImportTaskOverview } from '@/api/endpoints'

export function hasActionableImportTasks(overview: ProviderImportTaskOverview): boolean {
  return (
    overview.providers_needing_manual_key_input > 0 ||
    overview.providers_needing_manual_review > 0
  )
}

export function buildImportTaskOverviewSignature(overview: ProviderImportTaskOverview): string {
  return [
    overview.providers_needing_manual_key_input,
    overview.providers_needing_manual_review,
    overview.tasks_waiting_plaintext,
    overview.tasks_failed,
  ].join(':')
}

export function shouldResetImportTaskOverviewDismissed(
  previousOverview: ProviderImportTaskOverview,
  nextOverview: ProviderImportTaskOverview,
): boolean {
  return (
    hasActionableImportTasks(nextOverview) &&
    buildImportTaskOverviewSignature(previousOverview) !== buildImportTaskOverviewSignature(nextOverview)
  )
}

export function isImportTaskOverviewPermanentlyDismissed(
  savedSignature: string | null | undefined,
  overview: ProviderImportTaskOverview,
): boolean {
  if (!savedSignature) return false
  return (
    hasActionableImportTasks(overview) &&
    savedSignature === buildImportTaskOverviewSignature(overview)
  )
}
