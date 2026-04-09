import { describe, expect, it } from 'vitest'

import {
  buildProtocolOptionState,
  resolvePlaygroundSourceLabel,
} from '../playground-protocol-options'

describe('playground-protocol-options', () => {
  it('exposes all protocol choices in global mode without probe badges', () => {
    const result = buildProtocolOptionState({
      sourceMode: 'global',
      configuredFormats: ['openai:chat'],
      providerType: null,
    })

    expect(result.map(item => item.key)).toEqual([
      'openai-chat',
      'openai-responses',
      'claude',
      'gemini-native',
    ])
    expect(result.every(item => item.badge == null)).toBe(true)
  })

  it('marks configured and probe-capable protocols separately in provider mode', () => {
    const result = buildProtocolOptionState({
      sourceMode: 'provider',
      configuredFormats: ['openai:chat'],
      providerType: 'custom',
    })

    expect(result.find(item => item.key === 'openai-chat')?.badge).toBe('已配置')
    expect(result.find(item => item.key === 'openai-responses')?.badge).toBe('未配置，可试测')
    expect(result.find(item => item.key === 'claude')?.badge).toBe('未配置，可试测')
    expect(result.find(item => item.key === 'gemini-native')?.badge).toBe('未配置，可试测')
  })

  it('marks clearly unsupported provider protocol combinations as high risk', () => {
    const result = buildProtocolOptionState({
      sourceMode: 'provider',
      configuredFormats: ['gemini:chat'],
      providerType: 'vertex_ai',
    })

    expect(result.find(item => item.key === 'gemini-native')?.badge).toBe('已配置')
    expect(result.find(item => item.key === 'openai-chat')?.badge).toBe('高风险')
  })

  it('returns user-facing source labels', () => {
    expect(resolvePlaygroundSourceLabel('global')).toBe('全局模型')
    expect(resolvePlaygroundSourceLabel('provider')).toBe('渠道模型')
  })
})
