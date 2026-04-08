import { describe, expect, it } from 'vitest'

import { extractUpstreamRefreshPayload } from '../upstream-refresh'

describe('extractUpstreamRefreshPayload', () => {
  it('reads legacy cached fetch shape for non-force refresh', () => {
    const payload = extractUpstreamRefreshPayload(
      {
        models: [{ id: 'gpt-5', api_formats: ['openai:chat'] }],
        error: '',
        fromCache: true,
      },
      false,
    )

    expect(payload.models).toHaveLength(1)
    expect(payload.fromCache).toBe(true)
    expect(payload.createdEndpointFormats).toEqual([])
    expect(payload.updatedKeyIds).toEqual([])
  })

  it('reads refresh-sync response from nested data payload', () => {
    const payload = extractUpstreamRefreshPayload(
      {
        success: true,
        data: {
          models: [{ id: 'gpt-5.4', api_formats: ['openai:chat'] }],
          error: null as unknown as string,
          from_cache: false,
          key_error_count: 2,
          created_endpoint_formats: ['openai:cli'],
          updated_key_ids: ['key-1'],
        },
        provider: {
          id: 'provider-1',
          name: 'Provider One',
          display_name: 'Provider One',
        },
      },
      true,
    )

    expect(payload.models).toHaveLength(1)
    expect(payload.models[0].id).toBe('gpt-5.4')
    expect(payload.fromCache).toBe(false)
    expect(payload.keyErrorCount).toBe(2)
    expect(payload.createdEndpointFormats).toEqual(['openai:cli'])
    expect(payload.updatedKeyIds).toEqual(['key-1'])
  })
})
