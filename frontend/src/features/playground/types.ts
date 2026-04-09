import type { ProviderType } from '@/api/endpoints/types'

export type PlaygroundSourceMode = 'global' | 'provider'

export type PlaygroundProtocolKey =
  | 'openai-chat'
  | 'openai-responses'
  | 'claude'
  | 'gemini-native'

export type PlaygroundProtocolBadge =
  | '已配置'
  | '未配置，可试测'
  | '高风险'

export type PlaygroundReasoningEffort = 'low' | 'medium' | 'high'

export interface PlaygroundProtocolOptionState {
  key: PlaygroundProtocolKey
  label: string
  description: string
  apiFormat: string
  badge: PlaygroundProtocolBadge | null
}

export interface PlaygroundProtocolOptionContext {
  sourceMode: PlaygroundSourceMode
  configuredFormats: string[]
  providerType: ProviderType | null
}

export interface PlaygroundMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface PlaygroundRequestPreviewParams {
  protocol: PlaygroundProtocolKey
  model: string
  systemPrompt: string
  messages: PlaygroundMessage[]
  stream: boolean
  reasoningEffort?: PlaygroundReasoningEffort | null
  temperature?: number | null
  maxOutputTokens?: number | null
  topP?: number | null
  requestBodyOverrides?: Record<string, unknown> | null
}

export interface PlaygroundRequestPreview {
  protocol: PlaygroundProtocolKey
  transportLabel: string
  apiFormat: string
  body: Record<string, unknown>
}
