import type { Component } from 'vue'
import {
  Rocket,
  Network,
  BookOpen,
  Target,
  Settings,
  HelpCircle
} from 'lucide-vue-next'

// 导航配置
export interface GuideNavItem {
  id: string
  name: string
  path: string
  icon: Component
  description?: string
}

export const guideNavItems: GuideNavItem[] = [
  {
    id: 'overview',
    name: '快速开始',
    path: '/guide',
    icon: Rocket,
    description: '部署后的配置指南'
  },
  {
    id: 'architecture',
    name: '架构说明',
    path: '/guide/architecture',
    icon: Network,
    description: '系统架构与请求流程'
  },
  {
    id: 'concepts',
    name: '相关概念',
    path: '/guide/concepts',
    icon: BookOpen,
    description: '核心概念深入解释'
  },
  {
    id: 'strategy',
    name: '关键策略',
    path: '/guide/strategy',
    icon: Target,
    description: '调度、缓存与故障转移'
  },
  {
    id: 'advanced',
    name: '高级功能',
    path: '/guide/advanced',
    icon: Settings,
    description: '格式转换、请求规则等'
  },
  {
    id: 'faq',
    name: '常见问题',
    path: '/guide/faq',
    icon: HelpCircle,
    description: '使用中的常见问题'
  }
]

// 样式类常量
export const panelClasses = {
  card: 'bg-white/70 dark:bg-[#262624]/80 backdrop-blur-sm rounded-2xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.16)]',
  cardHover: 'hover:border-[#cc785c]/30 dark:hover:border-[#d4a27f]/30 transition-colors',
  section: 'bg-white/50 dark:bg-[#262624]/60 backdrop-blur-sm rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)]',
  commandPanel: 'rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-white/50 dark:bg-[#1f1d1a]/50',
  configPanel: 'rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] overflow-hidden',
  panelHeader: 'px-4 py-2 border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50',
  codeBody: 'p-0',
  badge: 'inline-flex items-center gap-1.5 rounded-full bg-[#cc785c]/10 dark:bg-[#cc785c]/20 border border-[#cc785c]/20 dark:border-[#cc785c]/40 px-3 py-1.5 text-xs font-medium text-[#cc785c] dark:text-[#d4a27f]',
  badgeBlue: 'inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 dark:bg-blue-500/20 border border-blue-500/20 dark:border-blue-500/40 px-2 py-0.5 text-xs font-medium text-blue-600 dark:text-blue-400',
  badgeGreen: 'inline-flex items-center gap-1.5 rounded-full bg-green-500/10 dark:bg-green-500/20 border border-green-500/20 dark:border-green-500/40 px-2 py-0.5 text-xs font-medium text-green-600 dark:text-green-400',
  badgeYellow: 'inline-flex items-center gap-1.5 rounded-full bg-yellow-500/10 dark:bg-yellow-500/20 border border-yellow-500/20 dark:border-yellow-500/40 px-2 py-0.5 text-xs font-medium text-yellow-600 dark:text-yellow-400',
  badgePurple: 'inline-flex items-center gap-1.5 rounded-full bg-purple-500/10 dark:bg-purple-500/20 border border-purple-500/20 dark:border-purple-500/40 px-2 py-0.5 text-xs font-medium text-purple-600 dark:text-purple-400',
  iconButtonSmall: [
    'flex items-center justify-center rounded-lg border h-7 w-7',
    'border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)]',
    'bg-transparent',
    'text-[#666663] dark:text-[#f1ead8]',
    'transition hover:bg-[#f0f0eb] dark:hover:bg-[#3a3731]'
  ].join(' ')
} as const

// API 格式说明
export const apiFormats = [
  {
    name: 'OpenAI Chat',
    endpoint: '/v1/chat/completions',
    auth: 'Authorization: Bearer xxx',
    clients: ['OpenAI SDK', 'Cursor', 'LangChain', '大部分开源工具']
  },
  {
    name: 'OpenAI CLI',
    endpoint: '/v1/responses',
    auth: 'Authorization: Bearer xxx',
    clients: ['Codex CLI']
  },
  {
    name: 'OpenAI Video',
    endpoint: '/v1/videos',
    auth: 'Authorization: Bearer xxx',
    clients: ['Sora']
  },
  {
    name: 'Claude Chat',
    endpoint: '/v1/messages',
    auth: 'x-api-key: xxx',
    clients: ['Anthropic SDK']
  },
  {
    name: 'Claude CLI',
    endpoint: '/v1/messages',
    auth: 'Authorization: Bearer xxx',
    clients: ['Claude Code']
  },
  {
    name: 'Gemini Chat',
    endpoint: '/v1beta/models/{model}:generateContent',
    auth: 'x-goog-api-key: xxx',
    clients: ['Gemini SDK']
  },
  {
    name: 'Gemini CLI',
    endpoint: '/v1beta/models/{model}:generateContent',
    auth: 'x-goog-api-key: xxx',
    clients: ['Gemini CLI']
  },
  {
    name: 'Gemini Video',
    endpoint: '/v1beta/models/{model}:predictLongRunning',
    auth: 'x-goog-api-key: xxx',
    clients: ['Veo']
  }
]

// 配置流程步骤
export const configSteps = [
  {
    step: 1,
    title: '添加供应商',
    description: '创建供应商并配置端点（URL、API Key、API 格式）',
    path: '/admin/providers'
  },
  {
    step: 2,
    title: '创建模型',
    description: '定义用户可用的模型名，关联到端点',
    path: '/admin/models'
  },
  {
    step: 3,
    title: '发放密钥',
    description: '为用户创建 API Key，设置权限和配额',
    path: '/admin/keys'
  },
  {
    step: 4,
    title: '开始使用',
    description: '配置客户端，开始调用 API',
    path: '/guide'
  }
]

// 客户端配置示例
export const clientExamples = [
  {
    name: 'Claude Code',
    configKey: 'ANTHROPIC_BASE_URL',
    code: (baseUrl: string) => `# 设置环境变量
export ANTHROPIC_BASE_URL="${baseUrl}"
export ANTHROPIC_API_KEY="your-api-key"

# 启动 Claude Code
claude`,
    note: '使用 Claude CLI 格式 (Authorization: Bearer)'
  },
  {
    name: 'Codex CLI',
    configKey: 'OPENAI_BASE_URL',
    code: (baseUrl: string) => `# 设置环境变量
export OPENAI_BASE_URL="${baseUrl}"
export OPENAI_API_KEY="your-api-key"

# 启动 Codex
codex`,
    note: '使用 OpenAI CLI 格式 (Responses API)'
  },
  {
    name: 'Cursor',
    configKey: 'Base URL',
    code: (baseUrl: string) => `# Cursor Settings > Models > OpenAI API Key
Base URL: ${baseUrl}/v1
API Key: your-api-key`,
    note: '使用 OpenAI Chat 格式'
  },
  {
    name: 'OpenAI SDK (Python)',
    configKey: 'base_url',
    code: (baseUrl: string) => `from openai import OpenAI

client = OpenAI(
    base_url="${baseUrl}/v1",
    api_key="your-api-key"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello"}]
)`,
    note: '使用 OpenAI Chat 格式，支持格式转换调用 Claude/Gemini'
  },
  {
    name: 'Gemini CLI',
    configKey: 'GEMINI_API_BASE',
    code: (baseUrl: string) => `# 设置环境变量
export GEMINI_API_BASE="${baseUrl}"
export GEMINI_API_KEY="your-api-key"

# 启动 Gemini CLI
gemini`,
    note: '使用 Gemini Chat 格式'
  }
]

// 常见供应商配置
export const providerExamples = [
  {
    name: 'OpenAI',
    url: 'https://api.openai.com',
    format: 'OpenAI Chat',
    note: '官方 API'
  },
  {
    name: 'Anthropic',
    url: 'https://api.anthropic.com',
    format: 'Claude Chat',
    note: '官方 Claude API'
  },
  {
    name: 'Google AI',
    url: 'https://generativelanguage.googleapis.com',
    format: 'Gemini Chat',
    note: '官方 Gemini API'
  },
  {
    name: 'Azure OpenAI',
    url: 'https://{resource}.openai.azure.com',
    format: 'OpenAI Chat',
    note: '替换 {resource} 为你的资源名'
  },
  {
    name: 'OpenRouter',
    url: 'https://openrouter.ai/api',
    format: 'OpenAI Chat',
    note: '聚合多家供应商的 API 代理'
  },
  {
    name: '自托管/其他',
    url: 'https://your-api.com',
    format: 'OpenAI Chat',
    note: '大多数兼容服务选择 OpenAI Chat 格式'
  }
]

// FAQ 数据
export const faqItems = [
  {
    id: 'concept-provider-endpoint',
    category: '概念理解',
    question: '供应商和端点有什么区别？',
    answer: '供应商是逻辑分组，用于组织管理多个端点。一个供应商可以有多个端点（比如不同区域、不同账号的 API）。端点才是实际调用 API 的配置单元，包含 URL、密钥等信息。'
  },
  {
    id: 'concept-model-mapping',
    category: '概念理解',
    question: '模型映射是什么意思？',
    answer: '模型映射让你可以用自定义的模型名（如 gpt-4）来访问实际的模型（如某端点的 gpt-4-turbo）。一个模型可以映射到多个端点，实现负载均衡和故障转移。'
  },
  {
    id: 'config-format',
    category: '配置问题',
    question: '端点的 API 格式怎么选择？',
    answer: '根据实际服务商的 API 格式选择。比如 OpenAI 官方选 OpenAI，Anthropic 官方选 Claude。如果用的是 OpenAI 兼容的第三方服务，通常选 OpenAI 格式。'
  },
  {
    id: 'config-priority',
    category: '配置问题',
    question: '端点优先级有什么用？',
    answer: '当模型关联多个端点且使用优先级负载均衡模式时，系统会先调用高优先级端点。如果失败（超时、错误等），会自动降级到低优先级端点。适合主备切换场景。'
  },
  {
    id: 'config-quota',
    category: '配置问题',
    question: '如何限制用户的使用量？',
    answer: '在 API Key 配置中设置配额：可以限制每日/每月的请求次数或 Token 用量。也可以在用户层面设置默认配额，新建的 Key 会继承用户配额。'
  },
  {
    id: 'advanced-conversion',
    category: '高级功能',
    question: '什么是格式转换？',
    answer: '格式转换允许用 OpenAI SDK 调用 Claude 模型，或用 Anthropic SDK 调用 OpenAI 模型。系统会自动转换请求和响应格式。需要在系统设置开启，并在端点配置中启用。'
  },
  {
    id: 'advanced-header-rules',
    category: '高级功能',
    question: '请求头规则有什么用？',
    answer: '可以在转发请求时添加、修改或删除 HTTP 头。常用于：添加认证信息、设置特定的 API 版本、添加跟踪标记等。'
  },
  {
    id: 'error-401',
    category: '常见错误',
    question: '返回 401 Unauthorized 错误？',
    answer: '检查：1) API Key 是否正确；2) Key 是否已过期或被禁用；3) 请求头格式是否正确（OpenAI 用 Bearer，Claude 用 x-api-key）。'
  },
  {
    id: 'error-404',
    category: '常见错误',
    question: '返回 404 Not Found 错误？',
    answer: '检查：1) 模型名称是否正确；2) 该模型是否已在系统中配置；3) API Key 是否有权限访问该模型；4) 端点 URL 是否正确。'
  },
  {
    id: 'error-502',
    category: '常见错误',
    question: '返回 502/503 错误？',
    answer: '表示上游服务不可用。检查：1) 端点健康状态；2) 供应商 API 是否正常；3) 网络连接是否正常。可以在健康监控页面查看端点状态。'
  }
]
