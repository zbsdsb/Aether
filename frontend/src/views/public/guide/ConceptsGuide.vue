<script setup lang="ts">
import { RouterLink } from 'vue-router'
import {
  ArrowRight,
  Server,
  Box,
  Key,
  Link,
  Layers,
  Users,
  Info,
  Tag
} from 'lucide-vue-next'
import { providerExamples, panelClasses } from './guide-config'
import { useSiteInfo } from '@/composables/useSiteInfo'

withDefaults(
  defineProps<{
    baseUrl?: string
  }>(),
  {
    baseUrl: typeof window !== 'undefined' ? window.location.origin : 'https://your-aether.com'
  }
)

const { siteName } = useSiteInfo()

// 核心概念列表
const concepts = [
  {
    name: '供应商 (Provider)',
    icon: Server,
    description: '上游 AI 服务商的逻辑抽象，用于组织和管理多个端点。',
    details: [
      '一个供应商代表一个 AI 服务提供商（如 OpenAI、Anthropic）',
      '供应商下可以有多个端点（不同区域、不同账号）',
      '供应商级别可以配置格式转换开关',
      '供应商的优先级影响候选排序'
    ]
  },
  {
    name: '端点 (ProviderEndpoint)',
    icon: Box,
    description: '实际的 API 配置单元，包含调用上游所需的全部信息。',
    details: [
      '包含 URL、API 格式（api_family:endpoint_kind 签名）',
      '可配置代理、超时、请求头/请求体规则',
      '端点下挂载一个或多个 API Key（ProviderAPIKey）',
      '端点是系统实际发起调用的最小单元'
    ]
  },
  {
    name: '供应商密钥 (ProviderAPIKey)',
    icon: Key,
    description: '端点的鉴权凭据，是调度系统操作的核心对象。',
    details: [
      '包含 internal_priority（内部优先级），影响候选排序',
      '可设置能力标签（如 1M 上下文、1H 缓存支持）',
      '可限定模型白名单，只允许特定模型使用此 Key',
      '包含上游配额元信息（RPM 等）'
    ]
  },
  {
    name: '候选 (ProviderCandidate)',
    icon: Link,
    description: 'Provider + Endpoint + Key 的组合，是调度和故障转移的基本单位。',
    details: [
      '每次请求会构建一组候选列表',
      '候选按调度策略排序后依次尝试',
      '失败时自动切换到下一个候选（故障转移）',
      '候选上附带并发检查、缓存亲和性等元数据'
    ]
  }
]

// 模型相关概念
const modelConcepts = [
  {
    name: '全局模型 (GlobalModel)',
    description: '用户请求中使用的模型名定义。用户在 API 调用中指定的 model 参数值必须是已注册的 GlobalModel。',
    example: 'claude-sonnet-4-20250514、gpt-4o、gemini-2.5-pro'
  },
  {
    name: '模型 (Model)',
    description: '供应商侧的模型实现。一个 GlobalModel 可以关联到多个 Provider 的 Model，每个 Model 可以映射不同的上游模型名。',
    example: '用户请求 gpt-4 -> 端点 A 发送 gpt-4-turbo，端点 B 发送 gpt-4o'
  },
  {
    name: '模型别名',
    description: '一个 GlobalModel 可以设置多个别名，用户可以用任意别名调用。适合版本迁移时保持向后兼容。',
    example: 'claude-3-5-sonnet -> claude-3.5-sonnet (别名)'
  }
]

// 用户与密钥
const userConcepts = [
  {
    name: 'API Key（用户密钥）',
    description: '用户访问系统的凭证，与上游 ProviderAPIKey 不同。每个 API Key 归属一个用户，可以设置：',
    features: ['允许访问的模型列表', '请求/Token 配额（日/月）', 'IP 白名单', '有效期', '1H 缓存策略']
  },
  {
    name: '亲和性键 (affinity_key)',
    description: '缓存亲和性的维度标识，通常取值为用户 API Key ID。系统会尝试为同一个 affinity_key 稳定选择相同的 ProviderAPIKey，以最大化利用上游的 Prompt Caching。',
    features: []
  }
]
</script>

<template>
  <div class="space-y-8">
    <!-- 标题 -->
    <div class="space-y-3">
      <h1 class="text-3xl font-bold text-[#262624] dark:text-[#f1ead8]">
        相关概念
      </h1>
      <p class="text-base text-[#666663] dark:text-[#a3a094]">
        深入理解 {{ siteName }} 中的核心概念及其关系。
      </p>
    </div>

    <!-- 概念关系 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        概念关系
      </h2>

      <div
        class="overflow-hidden"
        :class="[panelClasses.section]"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50">
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  关系
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  说明
                </th>
              </tr>
            </thead>
            <tbody>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)]">
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  供应商 → 端点 <span class="text-[#999] font-normal text-xs ml-1">1:N</span>
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  一个供应商包含多个端点（不同区域、不同账号等）
                </td>
              </tr>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)]">
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  端点 → 供应商密钥 <span class="text-[#999] font-normal text-xs ml-1">1:N</span>
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  一个端点下挂载多个 API Key
                </td>
              </tr>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)]">
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  全局模型 → 端点 <span class="text-[#999] font-normal text-xs ml-1">N:M</span>
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  全局模型与端点是多对多关系，通过 Model 关联
                </td>
              </tr>
              <tr class="last:border-0">
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  用户 API Key → 全局模型 <span class="text-[#999] font-normal text-xs ml-1">N:M</span>
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  用户 API Key 可限制可访问的模型列表
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 供应商侧核心概念 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        供应商侧概念
      </h2>

      <div class="space-y-3">
        <div
          v-for="concept in concepts"
          :key="concept.name"
          class="p-4"
          :class="[panelClasses.section]"
        >
          <div class="flex items-center gap-2.5 mb-2">
            <component
              :is="concept.icon"
              class="h-4 w-4 text-[#cc785c]"
            />
            <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8]">
              {{ concept.name }}
            </h3>
          </div>
          <p class="text-sm text-[#666663] dark:text-[#a3a094] mb-2.5">
            {{ concept.description }}
          </p>
          <ul class="space-y-1">
            <li
              v-for="detail in concept.details"
              :key="detail"
              class="flex items-start gap-2 text-sm text-[#666663] dark:text-[#a3a094]"
            >
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>{{ detail }}</span>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 常见供应商配置 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        常见供应商配置
      </h2>

      <div
        class="overflow-hidden"
        :class="[panelClasses.section]"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50">
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  供应商
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  URL
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  格式
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  备注
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="example in providerExamples"
                :key="example.name"
                class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] last:border-0"
              >
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  {{ example.name }}
                </td>
                <td class="px-4 py-2.5 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  {{ example.url }}
                </td>
                <td class="px-4 py-2.5 whitespace-nowrap">
                  <span :class="panelClasses.badgeBlue">{{ example.format }}</span>
                </td>
                <td class="px-4 py-2.5 text-xs text-[#999]">
                  {{ example.note }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 模型概念 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        模型体系
      </h2>

      <div class="space-y-3">
        <div
          v-for="model in modelConcepts"
          :key="model.name"
          class="p-4"
          :class="[panelClasses.section]"
        >
          <div class="flex items-center gap-2.5 mb-2">
            <Layers class="h-4 w-4 text-[#cc785c]" />
            <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8]">
              {{ model.name }}
            </h3>
          </div>
          <p class="text-sm text-[#666663] dark:text-[#a3a094]">
            {{ model.description }}
          </p>
          <div class="mt-2 flex items-center gap-2 text-xs text-[#666663] dark:text-[#a3a094]">
            <Tag class="h-3 w-3 text-[#999]" />
            <span>示例: </span>
            <code class="text-[#262624] dark:text-[#f1ead8] bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1.5 py-0.5 rounded">{{ model.example }}</code>
          </div>
        </div>
      </div>

      <!-- 模型名映射示例 -->
      <div
        class="p-4"
        :class="[panelClasses.section]"
      >
        <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8] mb-3">
          模型名映射示例
        </h3>
        <div class="space-y-2">
          <div class="flex items-center gap-3 text-sm flex-wrap">
            <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-2 py-1 rounded text-[#262624] dark:text-[#f1ead8]">用户请求 gpt-4</code>
            <ArrowRight class="h-3.5 w-3.5 text-[#999]" />
            <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-2 py-1 rounded text-[#262624] dark:text-[#f1ead8]">端点 A: gpt-4-turbo</code>
          </div>
          <div class="flex items-center gap-3 text-sm flex-wrap">
            <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-2 py-1 rounded text-[#262624] dark:text-[#f1ead8]">用户请求 gpt-4</code>
            <ArrowRight class="h-3.5 w-3.5 text-[#999]" />
            <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-2 py-1 rounded text-[#262624] dark:text-[#f1ead8]">端点 B: gpt-4o</code>
          </div>
        </div>
        <p class="text-sm text-[#666663] dark:text-[#a3a094] mt-2.5">
          同一个模型名可以映射到不同端点的不同上游模型名，系统根据调度策略选择端点后使用对应的映射。
        </p>
      </div>
    </section>

    <!-- 用户与密钥 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        用户与 API Key
      </h2>

      <div class="space-y-3">
        <div
          v-for="concept in userConcepts"
          :key="concept.name"
          class="p-4"
          :class="[panelClasses.section]"
        >
          <div class="flex items-center gap-2.5 mb-2">
            <Users class="h-4 w-4 text-[#cc785c]" />
            <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8]">
              {{ concept.name }}
            </h3>
          </div>
          <p class="text-sm text-[#666663] dark:text-[#a3a094]">
            {{ concept.description }}
          </p>
          <ul
            v-if="concept.features.length > 0"
            class="mt-2 space-y-1"
          >
            <li
              v-for="feature in concept.features"
              :key="feature"
              class="flex items-start gap-2 text-sm text-[#666663] dark:text-[#a3a094]"
            >
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>{{ feature }}</span>
            </li>
          </ul>
        </div>
      </div>

      <div
        class="p-4"
        :class="[panelClasses.section]"
      >
        <div class="flex items-start gap-3">
          <Info class="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
          <div class="text-sm text-[#666663] dark:text-[#a3a094]">
            <p class="font-medium text-[#262624] dark:text-[#f1ead8]">
              两种 Key 的区别
            </p>
            <p class="mt-1">
              <strong>用户 API Key</strong>：用户用来访问 {{ siteName }} 的凭证（外部面向用户）。<br>
              <strong>ProviderAPIKey</strong>：{{ siteName }} 用来调用上游服务的凭证（内部面向供应商）。
              两者是独立的概念，用户 API Key 的请求会被路由到合适的 ProviderAPIKey。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 下一步 -->
    <section class="pt-2">
      <RouterLink
        to="/guide/strategy"
        class="p-4 flex items-center gap-3 group"
        :class="[panelClasses.section, panelClasses.cardHover]"
      >
        <div class="flex-1">
          <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
            下一步：关键策略
          </div>
          <div class="text-xs text-[#666663] dark:text-[#a3a094]">
            了解调度、缓存亲和性、故障转移等核心策略
          </div>
        </div>
        <ArrowRight class="h-4 w-4 text-[#999] group-hover:text-[#cc785c] transition-colors" />
      </RouterLink>
    </section>
  </div>
</template>
