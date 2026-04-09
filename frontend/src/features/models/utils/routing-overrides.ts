import type { ModelRoutingPreviewResponse } from '@/api/endpoints/types/routing'

export interface RoutingOverrideDraft {
  provider_priorities: Record<string, number>
  key_internal_priorities: Record<string, number>
  key_priorities_by_format: Record<string, Record<string, number>>
}

function clonePriorityMap<T extends Record<string, unknown>>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function createEmptyRoutingOverrideDraft(): RoutingOverrideDraft {
  return {
    provider_priorities: {},
    key_internal_priorities: {},
    key_priorities_by_format: {},
  }
}

export function cloneRoutingOverrideDraft(draft: RoutingOverrideDraft): RoutingOverrideDraft {
  return clonePriorityMap(draft)
}

export function extractRoutingOverrideDraft(
  routingData: ModelRoutingPreviewResponse | null | undefined,
): RoutingOverrideDraft {
  const draft = createEmptyRoutingOverrideDraft()
  if (!routingData) return draft

  for (const provider of routingData.providers || []) {
    if (typeof provider.override_provider_priority === 'number') {
      draft.provider_priorities[provider.id] = provider.override_provider_priority
    }
    for (const endpoint of provider.endpoints || []) {
      for (const key of endpoint.keys || []) {
        if (typeof key.override_internal_priority === 'number') {
          draft.key_internal_priorities[key.id] = key.override_internal_priority
        }
        if (typeof key.override_global_priority === 'number') {
          draft.key_priorities_by_format[key.id] = {
            ...(draft.key_priorities_by_format[key.id] || {}),
            [endpoint.api_format]: key.override_global_priority,
          }
        }
      }
    }
  }

  return draft
}

function pruneEmptyDraft(draft: RoutingOverrideDraft): Partial<RoutingOverrideDraft> {
  const result: Partial<RoutingOverrideDraft> = {}
  if (Object.keys(draft.provider_priorities).length > 0) {
    result.provider_priorities = clonePriorityMap(draft.provider_priorities)
  }
  if (Object.keys(draft.key_internal_priorities).length > 0) {
    result.key_internal_priorities = clonePriorityMap(draft.key_internal_priorities)
  }

  const normalizedKeyPrioritiesByFormat: Record<string, Record<string, number>> = {}
  for (const [keyId, priorityMap] of Object.entries(draft.key_priorities_by_format)) {
    const entries = Object.entries(priorityMap || {}).filter(([, value]) => typeof value === 'number')
    if (entries.length > 0) {
      normalizedKeyPrioritiesByFormat[keyId] = Object.fromEntries(entries)
    }
  }
  if (Object.keys(normalizedKeyPrioritiesByFormat).length > 0) {
    result.key_priorities_by_format = normalizedKeyPrioritiesByFormat
  }

  return result
}

export function buildGlobalModelConfigWithRoutingOverrides(
  currentConfig: Record<string, unknown> | null | undefined,
  draft: RoutingOverrideDraft,
): Record<string, unknown> {
  const nextConfig = isPlainRecord(currentConfig) ? clonePriorityMap(currentConfig) : {}
  const normalizedOverrides = pruneEmptyDraft(draft)

  if (Object.keys(normalizedOverrides).length === 0) {
    delete nextConfig.routing_overrides
    return nextConfig
  }

  nextConfig.routing_overrides = normalizedOverrides
  return nextConfig
}

export function routingOverrideDraftEquals(
  left: RoutingOverrideDraft,
  right: RoutingOverrideDraft,
): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}
