import { describe, expect, it } from 'vitest'

import { buildImportedAuthPrefillConfig } from '../imported-auth-prefill'

describe('buildImportedAuthPrefillConfig', () => {
  it('maps imported new_api draft into dialog config shape', () => {
    const draft = buildImportedAuthPrefillConfig({
      available: true,
      architecture_id: 'new_api',
      base_url: 'https://demo.example',
      connector: {
        auth_type: 'api_key',
        config: {},
        credentials: {
          cookie: 'session=abc',
          api_key: 'tok-123',
          user_id: '42',
        },
      },
      source_summary: {
        task_type: 'pending_reissue',
        site_type: 'new-api',
      },
    })

    expect(draft).toEqual({
      architecture_id: 'new_api',
      base_url: 'https://demo.example',
      connector: {
        auth_type: 'api_key',
        config: {},
        credentials: {
          cookie: 'session=abc',
          api_key: 'tok-123',
          user_id: '42',
        },
      },
    })
  })

  it('returns null when imported draft is unavailable', () => {
    expect(
      buildImportedAuthPrefillConfig({
        available: false,
        architecture_id: null,
        base_url: null,
        connector: null,
        source_summary: null,
      }),
    ).toBeNull()
  })
})
