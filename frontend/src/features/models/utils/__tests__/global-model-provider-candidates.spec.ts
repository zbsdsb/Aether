import { describe, expect, it } from 'vitest'

import type { GlobalModelProviderCandidate } from '@/api/endpoints/types/model'
import {
  buildProviderCandidateSearchText,
  filterProviderCandidates,
  getVisibleCandidateModelNames,
  getSelectableCandidateIds,
} from '@/features/models/utils/global-model-provider-candidates'

function candidate(
  overrides: Partial<GlobalModelProviderCandidate> = {},
): GlobalModelProviderCandidate {
  return {
    provider_id: 'provider-1',
    provider_name: 'Provider One',
    provider_website: 'https://provider.one',
    provider_active: true,
    already_linked: false,
    match_status: 'unknown',
    cached_models: [],
    cached_model_count: 0,
    ...overrides,
  }
}

describe('global-model-provider-candidates', () => {
  it('buildProviderCandidateSearchText includes provider name, url and cached models', () => {
    const text = buildProviderCandidateSearchText(candidate({
      cached_models: [{ id: 'gpt-5.4' }],
      cached_model_count: 1,
    }))

    expect(text).toContain('provider one')
    expect(text).toContain('provider.one')
    expect(text).toContain('gpt-5.4')
  })

  it('filterProviderCandidates matches plain text against cached model names', () => {
    const result = filterProviderCandidates([
      candidate({ provider_id: 'p1', cached_models: [{ id: 'gpt-5.4' }], cached_model_count: 1 }),
      candidate({ provider_id: 'p2', provider_name: 'Claude Hub', cached_models: [{ id: 'claude-sonnet-4.5' }], cached_model_count: 1 }),
    ], {
      modelQuery: 'gpt-5.4',
    })

    expect(result.items.map((item) => item.provider_id)).toEqual(['p1'])
  })

  it('filterProviderCandidates supports fuzzy model variants', () => {
    const result = filterProviderCandidates([
      candidate({ provider_id: 'p1', cached_models: [{ id: 'gpt-5.4(xhigh)' }], cached_model_count: 1 }),
      candidate({ provider_id: 'p2', cached_models: [{ id: 'gpt-5.4-2026-03-05' }], cached_model_count: 1 }),
      candidate({ provider_id: 'p3', cached_models: [{ id: 'gpt-4.1' }], cached_model_count: 1 }),
    ], {
      modelQuery: 'gpt-5.4',
    })

    expect(result.items.map((item) => item.provider_id)).toEqual(['p1', 'p2'])
  })

  it('filterProviderCandidates combines provider search and model search', () => {
    const result = filterProviderCandidates([
      candidate({
        provider_id: 'p1',
        provider_name: 'OpenAI Hub',
        provider_website: 'https://openai.example.com',
        cached_models: [{ id: 'gpt-5.4-2026-03-05' }],
        cached_model_count: 1,
      }),
      candidate({
        provider_id: 'p2',
        provider_name: 'Claude Gateway',
        provider_website: 'https://claude.example.com',
        cached_models: [{ id: 'gpt-5.4' }],
        cached_model_count: 1,
      }),
    ], {
      providerQuery: 'openai',
      modelQuery: 'gpt-5.4',
    })

    expect(result.items.map((item) => item.provider_id)).toEqual(['p1'])
  })

  it('filterProviderCandidates hides inactive providers by default', () => {
    const result = filterProviderCandidates([
      candidate({
        provider_id: 'p1',
        provider_name: 'Active Hub',
        provider_active: true,
        cached_models: [{ id: 'gpt-5.4' }],
        cached_model_count: 1,
      }),
      candidate({
        provider_id: 'p2',
        provider_name: 'Inactive Hub',
        provider_active: false,
        cached_models: [{ id: 'gpt-5.4' }],
        cached_model_count: 1,
      }),
    ], {
      modelQuery: 'gpt-5.4',
    })

    expect(result.items.map((item) => item.provider_id)).toEqual(['p1'])
  })

  it('filterProviderCandidates matches provider text only against provider fields', () => {
    const result = filterProviderCandidates([candidate()], {
      providerQuery: 'provider',
    })

    expect(result.items).toHaveLength(1)
  })

  it('filterProviderCandidates providerQuery ignores model names', () => {
    const result = filterProviderCandidates([
      candidate({ provider_id: 'p1', provider_name: 'Alpha Hub', cached_models: [{ id: 'gpt-5.4' }], cached_model_count: 1 }),
      candidate({ provider_id: 'p2', provider_name: 'Beta Hub', cached_models: [{ id: 'claude-sonnet-4.5' }], cached_model_count: 1 }),
    ], {
      providerQuery: 'gpt-5.4',
    })

    expect(result.items).toHaveLength(0)
  })

  it('getVisibleCandidateModelNames returns fuzzy matched model variants', () => {
    const names = getVisibleCandidateModelNames(candidate({
      provider_id: 'p1',
      provider_name: 'Mixed Hub',
      cached_models: [{ id: 'gpt-5.4' }, { id: 'gpt-5.4(xhigh)' }, { id: 'gpt-4.1' }],
      cached_model_count: 3,
    }), {
      modelQuery: 'gpt-5.4',
    })

    expect(names).toEqual(['gpt-5.4', 'gpt-5.4(xhigh)'])
  })

  it('getVisibleCandidateModelNames keeps all models when modelQuery is empty', () => {
    const names = getVisibleCandidateModelNames(candidate({
      provider_id: 'p1',
      provider_name: 'Gateway Hub',
      cached_models: [{ id: 'gpt-5.4' }, { id: 'gpt-5.4-mini' }, { id: 'gpt-4.1' }],
      cached_model_count: 3,
    }), {
      providerQuery: 'gateway',
    })

    expect(names).toEqual(['gpt-5.4', 'gpt-5.4-mini', 'gpt-4.1'])
  })

  it('getSelectableCandidateIds returns unique ids for current result set', () => {
    const ids = getSelectableCandidateIds([
      candidate({ provider_id: 'p1' }),
      candidate({ provider_id: 'p2' }),
      candidate({ provider_id: 'p1' }),
    ])

    expect(ids).toEqual(['p1', 'p2'])
  })
})
