import type { UserModelMarketplaceItem } from '@/api/model-marketplace'

export type MarketplaceSortKey =
  | 'provider_count'
  | 'active_provider_count'
  | 'success_rate'
  | 'avg_latency_ms'
  | 'usage_count'
  | 'name'

export interface MarketplaceFilterState {
  search: string
  brand: string
  tag: string
  capability: string
  onlyAvailable: boolean
}

export function resolveMarketplaceBrand(model: UserModelMarketplaceItem): string {
  if (model.brand && model.brand !== 'other') {
    return model.brand
  }

  const text = `${model.name} ${model.display_name || ''} ${model.description || ''}`.toLowerCase()
  if (text.includes('gemini') || text.includes('google') || text.includes('vertex')) {
    return 'google'
  }
  if (text.includes('claude') || text.includes('anthropic')) {
    return 'anthropic'
  }
  if (text.includes('gpt') || text.includes('openai')) {
    return 'openai'
  }
  if (text.includes('deepseek')) {
    return 'deepseek'
  }
  return 'other'
}

export function resolveMarketplaceBadges(model: UserModelMarketplaceItem): string[] {
  const badges: string[] = []
  if (model.is_recommended) {
    badges.push('推荐')
  }
  if (model.is_most_stable) {
    badges.push('最稳')
  }
  return badges
}

export function filterMarketplaceModels(
  models: UserModelMarketplaceItem[],
  filters: MarketplaceFilterState,
): UserModelMarketplaceItem[] {
  const query = filters.search.trim().toLowerCase()

  return models.filter((model) => {
    if (filters.onlyAvailable && model.active_provider_count <= 0) {
      return false
    }

    if (filters.brand !== 'all' && resolveMarketplaceBrand(model) !== filters.brand) {
      return false
    }

    if (filters.tag !== 'all' && !model.tags.includes(filters.tag)) {
      return false
    }

    if (
      filters.capability !== 'all'
      && !(model.supported_capabilities || []).includes(filters.capability)
    ) {
      return false
    }

    if (!query) {
      return true
    }

    const searchText = `${model.name} ${model.display_name || ''} ${model.description || ''}`.toLowerCase()
    return searchText.includes(query)
  })
}

export function sortMarketplaceModels(
  models: UserModelMarketplaceItem[],
  sortKey: MarketplaceSortKey,
): UserModelMarketplaceItem[] {
  const sorted = [...models]
  sorted.sort((left, right) => {
    if (sortKey === 'name') {
      return left.name.localeCompare(right.name)
    }

    const leftValue = left[sortKey] ?? -1
    const rightValue = right[sortKey] ?? -1
    if (leftValue === rightValue) {
      return left.name.localeCompare(right.name)
    }
    return Number(rightValue) - Number(leftValue)
  })
  return sorted
}
