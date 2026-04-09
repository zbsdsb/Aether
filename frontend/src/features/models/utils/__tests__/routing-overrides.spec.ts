import { describe, expect, it } from 'vitest'

import type { ModelRoutingPreviewResponse } from '@/api/endpoints/types/routing'
import {
  buildGlobalModelConfigWithRoutingOverrides,
  extractRoutingOverrideDraft,
} from '@/features/models/utils/routing-overrides'

function createRoutingData(): ModelRoutingPreviewResponse {
  return {
    global_model_id: 'gm-1',
    global_model_name: 'gpt-5.4',
    display_name: 'GPT-5.4',
    is_active: true,
    global_model_mappings: [],
    total_providers: 1,
    active_providers: 1,
    scheduling_mode: 'fixed_order',
    priority_mode: 'provider',
    all_keys_whitelist: [],
    providers: [
      {
        id: 'provider-1',
        name: 'Provider One',
        model_id: 'model-1',
        provider_priority: 9,
        override_provider_priority: 2,
        effective_provider_priority: 2,
        billing_type: null,
        monthly_quota_usd: null,
        monthly_used_usd: null,
        is_active: true,
        provider_model_name: 'gpt-5.4',
        model_mappings: [],
        model_is_active: true,
        total_endpoints: 1,
        active_endpoints: 1,
        endpoints: [
          {
            id: 'endpoint-1',
            api_format: 'openai:chat',
            base_url: 'https://example.com',
            custom_path: null,
            is_active: true,
            total_keys: 1,
            active_keys: 1,
            keys: [
              {
                id: 'key-1',
                name: 'Key One',
                masked_key: 'sk-***',
                internal_priority: 8,
                override_internal_priority: 3,
                effective_internal_priority: 3,
                global_priority_by_format: { 'openai:chat': 7 },
                default_global_priority: 7,
                override_global_priority: 1,
                effective_global_priority: 1,
                rpm_limit: null,
                is_adaptive: true,
                effective_rpm: null,
                cache_ttl_minutes: 0,
                health_score: 1,
                is_active: true,
                api_formats: ['openai:chat'],
                allowed_models: null,
                circuit_breaker_open: false,
                circuit_breaker_formats: [],
                next_probe_at: null,
              },
            ],
          },
        ],
      },
    ],
  }
}

describe('routing-overrides utils', () => {
  it('extractRoutingOverrideDraft keeps only explicit model-level overrides from routing preview', () => {
    const draft = extractRoutingOverrideDraft(createRoutingData())

    expect(draft).toEqual({
      provider_priorities: { 'provider-1': 2 },
      key_internal_priorities: { 'key-1': 3 },
      key_priorities_by_format: { 'key-1': { 'openai:chat': 1 } },
    })
  })

  it('buildGlobalModelConfigWithRoutingOverrides merges and prunes empty override sections', () => {
    const updated = buildGlobalModelConfigWithRoutingOverrides(
      {
        description: 'existing',
        routing_overrides: {
          provider_priorities: { old: 9 },
        },
      },
      {
        provider_priorities: { 'provider-1': 2 },
        key_internal_priorities: {},
        key_priorities_by_format: {},
      },
    )

    expect(updated).toEqual({
      description: 'existing',
      routing_overrides: {
        provider_priorities: { 'provider-1': 2 },
      },
    })
  })
})
