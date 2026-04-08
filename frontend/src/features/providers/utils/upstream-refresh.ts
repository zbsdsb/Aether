import type { ProviderModelsQueryResponse } from '@/api/admin'
import type { UpstreamModel } from '@/features/providers/composables/useUpstreamModelsCache'

export interface UpstreamRefreshPayload {
  models: UpstreamModel[]
  error: string
  fromCache: boolean
  createdEndpointFormats: string[]
  updatedKeyIds: string[]
  keyErrorCount: number
}

export function extractUpstreamRefreshPayload(
  result:
    | {
        models: UpstreamModel[]
        error?: string
        fromCache?: boolean
      }
    | ProviderModelsQueryResponse,
  forceRefresh: boolean,
): UpstreamRefreshPayload {
  if (!forceRefresh) {
    const cached = result as {
      models: UpstreamModel[]
      error?: string
      fromCache?: boolean
    }
    return {
      models: cached.models || [],
      error: cached.error || '',
      fromCache: Boolean(cached.fromCache),
      createdEndpointFormats: [],
      updatedKeyIds: [],
      keyErrorCount: 0,
    }
  }

  const response = result as ProviderModelsQueryResponse
  return {
    models: response.data?.models || [],
    error: response.data?.error || '',
    fromCache: Boolean(response.data?.from_cache),
    createdEndpointFormats: response.data?.created_endpoint_formats || [],
    updatedKeyIds: response.data?.updated_key_ids || [],
    keyErrorCount: response.data?.key_error_count || 0,
  }
}
