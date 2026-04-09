import { describe, expect, it } from 'vitest'

import { buildPlaygroundRequestPreview } from '../playground-request-preview'

const baseMessages = [
  { role: 'user' as const, content: 'hello playground' },
]

describe('playground-request-preview', () => {
  it('builds OpenAI Chat preview from shared conversation state', () => {
    const preview = buildPlaygroundRequestPreview({
      protocol: 'openai-chat',
      model: 'gpt-4.1-mini',
      systemPrompt: 'You are precise.',
      messages: baseMessages,
      stream: true,
      reasoningEffort: 'high',
      temperature: 0.2,
    })

    expect(preview.transportLabel).toBe('OpenAI Chat')
    expect(preview.body.model).toBe('gpt-4.1-mini')
    expect(preview.body.stream).toBe(true)
    expect(preview.body.messages).toEqual([
      { role: 'system', content: 'You are precise.' },
      { role: 'user', content: 'hello playground' },
    ])
  })

  it('builds OpenAI Responses preview with input array and reasoning config', () => {
    const preview = buildPlaygroundRequestPreview({
      protocol: 'openai-responses',
      model: 'gpt-5.4',
      systemPrompt: 'Stay focused.',
      messages: baseMessages,
      stream: false,
      reasoningEffort: 'medium',
      maxOutputTokens: 4096,
    })

    expect(preview.transportLabel).toBe('OpenAI Responses')
    expect(preview.body.model).toBe('gpt-5.4')
    expect(preview.body.input).toHaveLength(2)
    expect(preview.body.reasoning).toEqual({ effort: 'medium' })
    expect(preview.body.max_output_tokens).toBe(4096)
  })

  it('builds Claude preview with top-level system string and messages', () => {
    const preview = buildPlaygroundRequestPreview({
      protocol: 'claude',
      model: 'claude-sonnet-4-5',
      systemPrompt: 'Be concise.',
      messages: baseMessages,
      stream: true,
      maxOutputTokens: 2048,
    })

    expect(preview.transportLabel).toBe('Claude')
    expect(preview.body.system).toBe('Be concise.')
    expect(preview.body.messages).toEqual(baseMessages)
    expect(preview.body.max_tokens).toBe(2048)
  })

  it('builds Gemini Native preview with systemInstruction and contents', () => {
    const preview = buildPlaygroundRequestPreview({
      protocol: 'gemini-native',
      model: 'gemini-2.5-pro',
      systemPrompt: 'Stay concise.',
      messages: baseMessages,
      stream: false,
      topP: 0.8,
    })

    expect(preview.transportLabel).toBe('Gemini Native')
    expect(preview.body.systemInstruction).toEqual({
      parts: [{ text: 'Stay concise.' }],
    })
    expect(preview.body.contents).toEqual([
      { role: 'user', parts: [{ text: 'hello playground' }] },
    ])
    expect(preview.body.generationConfig).toEqual({ topP: 0.8 })
  })

  it('merges request overrides into the generated preview body', () => {
    const preview = buildPlaygroundRequestPreview({
      protocol: 'openai-chat',
      model: 'gpt-4.1-mini',
      systemPrompt: '',
      messages: baseMessages,
      stream: true,
      requestBodyOverrides: {
        metadata: { source: 'playground' },
      },
    })

    expect(preview.body.metadata).toEqual({ source: 'playground' })
  })
})
