import type { GlobalModelProviderCandidate } from '@/api/endpoints/types/model'

export interface CandidateFilterResult {
  items: GlobalModelProviderCandidate[]
}

export interface CandidateFilterOptions {
  providerQuery?: string
  modelQuery?: string
}

function stringifyCachedModelName(model: Record<string, unknown>): string {
  return String(model.id || model.name || '').trim()
}

function normalizeSearchText(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[()_[\]{}]+/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function compactSearchText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '')
    .trim()
}

function splitQueryKeywords(query: string): string[] {
  return query
    .trim()
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function matchesKeyword(value: string, keyword: string): boolean {
  const normalizedValue = normalizeSearchText(value)
  const normalizedKeyword = normalizeSearchText(keyword)
  const compactValue = compactSearchText(value)
  const compactKeyword = compactSearchText(keyword)

  if (!normalizedKeyword && !compactKeyword) {
    return true
  }

  return (
    (normalizedKeyword && normalizedValue.includes(normalizedKeyword)) ||
    (compactKeyword && compactValue.includes(compactKeyword))
  )
}

function matchesFuzzyText(value: string, query: string): boolean {
  const keywords = splitQueryKeywords(query)
  if (keywords.length === 0) {
    return true
  }

  return keywords.every((keyword) => matchesKeyword(value, keyword))
}

function buildCandidateProviderSearchFields(candidate: GlobalModelProviderCandidate): string[] {
  return [
    candidate.provider_name,
    candidate.provider_website || '',
  ].filter(Boolean)
}

function buildCandidateModelNames(candidate: GlobalModelProviderCandidate): string[] {
  return candidate.cached_models
    .map((item) => stringifyCachedModelName(item))
    .filter(Boolean)
}

function matchesProviderQuery(candidate: GlobalModelProviderCandidate, query: string): boolean {
  if (!query.trim()) {
    return true
  }

  return buildCandidateProviderSearchFields(candidate)
    .some((field) => matchesFuzzyText(field, query))
}

function getMatchedModelNames(candidate: GlobalModelProviderCandidate, query: string): string[] {
  const modelNames = buildCandidateModelNames(candidate)
  if (!query.trim()) {
    return modelNames
  }

  return modelNames.filter((modelName) => matchesFuzzyText(modelName, query))
}

export function buildProviderCandidateSearchText(candidate: GlobalModelProviderCandidate): string {
  return [
    ...buildCandidateProviderSearchFields(candidate),
    ...buildCandidateModelNames(candidate),
  ]
    .join(' ')
    .toLowerCase()
}

export function filterProviderCandidates(
  candidates: GlobalModelProviderCandidate[],
  options: CandidateFilterOptions = {},
): CandidateFilterResult {
  const {
    providerQuery = '',
    modelQuery = '',
  } = options

  return {
    items: candidates.filter((candidate) => (
      matchesProviderQuery(candidate, providerQuery) &&
      (!modelQuery.trim() || getMatchedModelNames(candidate, modelQuery).length > 0)
    )),
  }
}

export function getVisibleCandidateModelNames(
  candidate: GlobalModelProviderCandidate,
  options: CandidateFilterOptions = {},
): string[] {
  return getMatchedModelNames(candidate, options.modelQuery || '')
}

export function getSelectableCandidateIds(
  candidates: GlobalModelProviderCandidate[],
): string[] {
  return [...new Set(candidates.map((item) => item.provider_id))]
}
