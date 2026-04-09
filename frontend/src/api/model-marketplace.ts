import client from './client'

export interface UserModelMarketplaceProviderItem {
  provider_id: string
  provider_name: string
  provider_website: string | null
  is_active: boolean
  endpoint_count: number
  active_endpoint_count: number
  supported_api_formats: string[]
}

export interface UserModelMarketplaceItem {
  id: string
  name: string
  display_name: string | null
  description: string | null
  brand: string
  icon_url: string | null
  is_active: boolean
  supported_capabilities: string[] | null
  tags: string[]
  usage_count: number
  provider_count: number
  active_provider_count: number
  endpoint_count: number
  active_endpoint_count: number
  supported_api_formats: string[]
  success_rate: number | null
  avg_latency_ms: number | null
  is_recommended: boolean
  recommendation_reason?: string | null
  is_most_stable: boolean
  stability_reason?: string | null
  default_price_per_request: number | null
  default_tiered_pricing: Record<string, unknown> | null
  providers: UserModelMarketplaceProviderItem[]
}

export interface UserModelMarketplaceSummary {
  total_models: number
  total_provider_count: number
  active_provider_count: number
  overall_success_rate: number | null
}

export interface UserModelMarketplaceResponse {
  summary: UserModelMarketplaceSummary
  models: UserModelMarketplaceItem[]
  total: number
  generated_at: string
}

export interface UserModelMarketplaceQuery {
  search?: string
  brand?: string
  tag?: string
  capability?: string
  only_available?: boolean
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
}

export async function getUserModelMarketplace(params?: UserModelMarketplaceQuery): Promise<UserModelMarketplaceResponse> {
  const response = await client.get('/api/users/me/model-marketplace', { params })
  return response.data
}
