import type { ImportedAuthPrefillResponse } from '@/api/providerOps'

export interface ImportedAuthPrefillConfig {
  architecture_id: string
  base_url?: string
  connector: {
    auth_type: string
    config: Record<string, unknown>
    credentials: Record<string, unknown>
  }
}

export function buildImportedAuthPrefillConfig(
  prefill: ImportedAuthPrefillResponse,
): ImportedAuthPrefillConfig | null {
  if (!prefill.available || !prefill.architecture_id || !prefill.connector) {
    return null
  }

  return {
    architecture_id: prefill.architecture_id,
    base_url: prefill.base_url || undefined,
    connector: {
      auth_type: prefill.connector.auth_type,
      config: prefill.connector.config || {},
      credentials: prefill.connector.credentials || {},
    },
  }
}
