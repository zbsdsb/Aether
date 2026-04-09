import { describe, expect, it } from 'vitest'

import type { UserModelMarketplaceItem } from '@/api/model-marketplace'
import {
  filterMarketplaceModels,
  resolveMarketplaceBadges,
  resolveMarketplaceBrand,
  sortMarketplaceModels,
} from '../model-marketplace'

function createModel(overrides: Partial<UserModelMarketplaceItem> = {}): UserModelMarketplaceItem {
  return {
    id: 'gm-1',
    name: 'gpt-4o',
    display_name: 'GPT-4o',
    description: 'Fast general model',
    brand: 'openai',
    icon_url: null,
    is_active: true,
    supported_capabilities: ['context_1m'],
    tags: ['coding'],
    usage_count: 20,
    provider_count: 3,
    active_provider_count: 2,
    endpoint_count: 4,
    active_endpoint_count: 3,
    supported_api_formats: ['openai:chat'],
    success_rate: 0.96,
    avg_latency_ms: 520,
    is_recommended: false,
    is_most_stable: false,
    default_price_per_request: null,
    default_tiered_pricing: { tiers: [] },
    providers: [],
    ...overrides,
  }
}

describe('model marketplace utils', () => {
  it('filters by search, tag, brand and onlyAvailable together', () => {
    const models = [
      createModel(),
      createModel({
        id: 'gm-2',
        name: 'text-embedding-3-large',
        display_name: 'Embedding Large',
        description: 'Vector embedding model',
        brand: 'openai',
        tags: ['embedding'],
        active_provider_count: 0,
      }),
      createModel({
        id: 'gm-3',
        name: 'claude-sonnet-4',
        display_name: 'Claude Sonnet 4',
        description: 'Reasoning model',
        brand: 'anthropic',
        tags: ['thinking'],
      }),
    ]

    const filtered = filterMarketplaceModels(models, {
      search: 'claude',
      brand: 'anthropic',
      tag: 'thinking',
      capability: 'all',
      onlyAvailable: true,
    })

    expect(filtered).toHaveLength(1)
    expect(filtered[0]?.name).toBe('claude-sonnet-4')
  })

  it('filters by capability when requested', () => {
    const models = [
      createModel({ name: 'gpt-4o', supported_capabilities: ['context_1m'] }),
      createModel({
        id: 'gm-2',
        name: 'claude-sonnet-4',
        supported_capabilities: ['cache_1h'],
      }),
    ]

    const filtered = filterMarketplaceModels(models, {
      search: '',
      brand: 'all',
      tag: 'all',
      capability: 'cache_1h',
      onlyAvailable: false,
    })

    expect(filtered.map(model => model.name)).toEqual(['claude-sonnet-4'])
  })

  it('sorts by provider coverage descending', () => {
    const models = [
      createModel({ id: 'gm-1', name: 'gpt-4o', provider_count: 2 }),
      createModel({ id: 'gm-2', name: 'o3', provider_count: 5 }),
      createModel({ id: 'gm-3', name: 'claude-sonnet-4', provider_count: 3 }),
    ]

    const sorted = sortMarketplaceModels(models, 'provider_count')

    expect(sorted.map(model => model.name)).toEqual(['o3', 'claude-sonnet-4', 'gpt-4o'])
  })

  it('resolves badges from recommended and stable flags', () => {
    const badges = resolveMarketplaceBadges(
      createModel({
        is_recommended: true,
        is_most_stable: true,
      }),
    )

    expect(badges).toEqual(['推荐', '最稳'])
  })

  it('derives brand from explicit family or model name hints', () => {
    expect(resolveMarketplaceBrand(createModel({ name: 'gemini-2.5-pro', brand: 'other' }))).toBe('google')
    expect(
      resolveMarketplaceBrand(
        createModel({
          name: 'custom-model',
          display_name: 'Custom',
          brand: 'other',
          description: 'demo',
        }),
      ),
    ).toBe('other')
  })
})
