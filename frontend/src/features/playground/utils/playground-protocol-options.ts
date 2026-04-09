import type { ProviderType } from '@/api/endpoints/types'

import type {
  PlaygroundProtocolBadge,
  PlaygroundProtocolKey,
  PlaygroundProtocolOptionContext,
  PlaygroundProtocolOptionState,
  PlaygroundSourceMode,
} from '../types'

const PROTOCOL_OPTIONS: Array<{
  key: PlaygroundProtocolKey
  label: string
  description: string
  apiFormat: string
}> = [
  {
    key: 'openai-chat',
    label: 'OpenAI Chat',
    description: 'Chat Completions 风格请求',
    apiFormat: 'openai:chat',
  },
  {
    key: 'openai-responses',
    label: 'OpenAI Responses',
    description: 'Responses 风格请求',
    apiFormat: 'openai:cli',
  },
  {
    key: 'claude',
    label: 'Claude',
    description: 'Anthropic Messages 风格请求',
    apiFormat: 'claude:chat',
  },
  {
    key: 'gemini-native',
    label: 'Gemini Native',
    description: 'Gemini 原生内容请求',
    apiFormat: 'gemini:chat',
  },
]

function buildBadge(
  option: { apiFormat: string; key: PlaygroundProtocolKey },
  configuredFormats: Set<string>,
  providerType: ProviderType | null,
): PlaygroundProtocolBadge {
  if (configuredFormats.has(option.apiFormat)) return '已配置'

  if (providerType === 'vertex_ai') {
    if (option.key === 'gemini-native' || option.key === 'claude') return '未配置，可试测'
    return '高风险'
  }

  return '未配置，可试测'
}

export function buildProtocolOptionState(
  context: PlaygroundProtocolOptionContext,
): PlaygroundProtocolOptionState[] {
  if (context.sourceMode === 'global') {
    return PROTOCOL_OPTIONS.map(option => ({ ...option, badge: null }))
  }

  const configuredFormats = new Set(context.configuredFormats)
  return PROTOCOL_OPTIONS.map(option => ({
    ...option,
    badge: buildBadge(option, configuredFormats, context.providerType),
  }))
}

export function resolvePlaygroundSourceLabel(sourceMode: PlaygroundSourceMode): string {
  return sourceMode === 'global' ? '全局模型' : '渠道模型'
}
