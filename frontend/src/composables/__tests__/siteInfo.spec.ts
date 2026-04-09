import { describe, expect, it } from 'vitest'

import { normalizeSiteInfoPayload } from '@/composables/useSiteInfo'

describe('useSiteInfo normalizeSiteInfoPayload', () => {
  it('keeps fallback values when payload fields are missing or invalid', () => {
    expect(normalizeSiteInfoPayload({}, { siteName: 'Aether', siteSubtitle: 'AI Gateway' })).toEqual({
      siteName: 'Aether',
      siteSubtitle: 'AI Gateway',
    })

    expect(normalizeSiteInfoPayload({ site_name: null, site_subtitle: 123 }, { siteName: 'Aether', siteSubtitle: 'AI Gateway' })).toEqual({
      siteName: 'Aether',
      siteSubtitle: 'AI Gateway',
    })
  })

  it('accepts string values from a valid payload', () => {
    expect(normalizeSiteInfoPayload({ site_name: 'My Site', site_subtitle: 'Subtitle' }, { siteName: 'Aether', siteSubtitle: 'AI Gateway' })).toEqual({
      siteName: 'My Site',
      siteSubtitle: 'Subtitle',
    })
  })
})
