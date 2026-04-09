import { describe, expect, it } from 'vitest'

import { coerceTypewriterText } from '@/views/public/home-typewriter'

describe('home-typewriter', () => {
  it('returns an empty string for non-string values', () => {
    expect(coerceTypewriterText(undefined)).toBe('')
    expect(coerceTypewriterText(null)).toBe('')
    expect(coerceTypewriterText(123)).toBe('')
    expect(coerceTypewriterText({})).toBe('')
  })

  it('keeps valid strings unchanged', () => {
    expect(coerceTypewriterText('Aether')).toBe('Aether')
  })
})
