import type {
  PlaygroundMessage,
  PlaygroundRequestPreview,
  PlaygroundRequestPreviewParams,
} from '../types'

function normalizeText(value: string): string {
  return value.trim()
}

function withSystemPrompt(
  systemPrompt: string,
  messages: PlaygroundMessage[],
): Array<{ role: string; content: string }> {
  const normalizedPrompt = normalizeText(systemPrompt)
  const result = messages.map(message => ({
    role: message.role,
    content: message.content,
  }))

  if (!normalizedPrompt) return result
  return [{ role: 'system', content: normalizedPrompt }, ...result]
}

function mergeObjects<T extends Record<string, unknown>>(
  base: T,
  overrides: Record<string, unknown> | null | undefined,
): T {
  if (!overrides) return base

  const output: Record<string, unknown> = { ...base }
  for (const [key, value] of Object.entries(overrides)) {
    const current = output[key]
    if (
      value
      && typeof value === 'object'
      && !Array.isArray(value)
      && current
      && typeof current === 'object'
      && !Array.isArray(current)
    ) {
      output[key] = mergeObjects(
        current as Record<string, unknown>,
        value as Record<string, unknown>,
      )
    } else {
      output[key] = value
    }
  }
  return output as T
}

function addOptional(
  target: Record<string, unknown>,
  key: string,
  value: unknown,
): void {
  if (value == null || value === '') return
  target[key] = value
}

function buildResponsesInput(
  systemPrompt: string,
  messages: PlaygroundMessage[],
): Array<Record<string, unknown>> {
  const normalizedPrompt = normalizeText(systemPrompt)
  const result: Array<Record<string, unknown>> = []

  if (normalizedPrompt) {
    result.push({
      role: 'system',
      content: [{ type: 'input_text', text: normalizedPrompt }],
    })
  }

  for (const message of messages) {
    result.push({
      role: message.role,
      content: [{ type: 'input_text', text: message.content }],
    })
  }

  return result
}

function buildGeminiContents(messages: PlaygroundMessage[]): Array<Record<string, unknown>> {
  return messages.map(message => ({
    role: message.role,
    parts: [{ text: message.content }],
  }))
}

export function buildPlaygroundRequestPreview(
  params: PlaygroundRequestPreviewParams,
): PlaygroundRequestPreview {
  const normalizedSystemPrompt = normalizeText(params.systemPrompt)
  const protocol = params.protocol

  if (protocol === 'openai-chat') {
    const body: Record<string, unknown> = {
      model: params.model,
      messages: withSystemPrompt(normalizedSystemPrompt, params.messages),
      stream: params.stream,
    }
    addOptional(body, 'temperature', params.temperature)
    addOptional(body, 'top_p', params.topP)
    addOptional(body, 'max_completion_tokens', params.maxOutputTokens)
    if (params.reasoningEffort) {
      body.reasoning = { effort: params.reasoningEffort }
    }
    return {
      protocol,
      transportLabel: 'OpenAI Chat',
      apiFormat: 'openai:chat',
      body: mergeObjects(body, params.requestBodyOverrides),
    }
  }

  if (protocol === 'openai-responses') {
    const body: Record<string, unknown> = {
      model: params.model,
      input: buildResponsesInput(normalizedSystemPrompt, params.messages),
      stream: params.stream,
    }
    addOptional(body, 'temperature', params.temperature)
    addOptional(body, 'top_p', params.topP)
    addOptional(body, 'max_output_tokens', params.maxOutputTokens)
    if (params.reasoningEffort) {
      body.reasoning = { effort: params.reasoningEffort }
    }
    return {
      protocol,
      transportLabel: 'OpenAI Responses',
      apiFormat: 'openai:cli',
      body: mergeObjects(body, params.requestBodyOverrides),
    }
  }

  if (protocol === 'claude') {
    const body: Record<string, unknown> = {
      model: params.model,
      messages: params.messages.map(message => ({
        role: message.role,
        content: message.content,
      })),
      stream: params.stream,
      max_tokens: params.maxOutputTokens ?? 2048,
    }
    addOptional(body, 'system', normalizedSystemPrompt)
    addOptional(body, 'temperature', params.temperature)
    addOptional(body, 'top_p', params.topP)
    return {
      protocol,
      transportLabel: 'Claude',
      apiFormat: 'claude:chat',
      body: mergeObjects(body, params.requestBodyOverrides),
    }
  }

  const generationConfig: Record<string, unknown> = {}
  addOptional(generationConfig, 'temperature', params.temperature)
  addOptional(generationConfig, 'topP', params.topP)
  addOptional(generationConfig, 'maxOutputTokens', params.maxOutputTokens)

  const body: Record<string, unknown> = {
    model: params.model,
    contents: buildGeminiContents(params.messages),
  }
  if (normalizedSystemPrompt) {
    body.systemInstruction = { parts: [{ text: normalizedSystemPrompt }] }
  }
  if (Object.keys(generationConfig).length > 0) {
    body.generationConfig = generationConfig
  }

  return {
    protocol,
    transportLabel: 'Gemini Native',
    apiFormat: 'gemini:chat',
    body: mergeObjects(body, params.requestBodyOverrides),
  }
}
