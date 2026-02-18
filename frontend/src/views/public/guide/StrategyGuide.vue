<script setup lang="ts">
import { RouterLink } from 'vue-router'
import {
  ArrowRight,
  TrendingUp,
  Hash,
  Info,
  Activity
} from 'lucide-vue-next'
import { panelClasses } from './guide-config'
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

// 调度模式
const schedulingModes = [
  {
    name: '提供商优先',
    description: '按 Provider 优先级排序，同优先级内按 Key 优先级排序，相同优先级哈希分散。适合优先使用特定供应商。',
    icon: TrendingUp,
    badge: '默认'
  },
  {
    name: '全局 Key 优先',
    description: '忽略 Provider 层级，所有 Key 按全局优先级统一排序，相同优先级哈希分散。适合跨 Provider 统一调度，最大化利用所有 Key。',
    icon: Hash,
    badge: ''
  }
]

// 错误分类
const errorCategories = [
  {
    type: 'RETRYABLE',
    name: '可重试',
    description: '超时、限流 (429)、5xx 服务端错误',
    action: 'FailoverEngine 尝试下一个候选'
  },
  {
    type: 'FATAL',
    name: '致命',
    description: '认证失败、模型不存在',
    action: '立即返回错误，不再重试'
  },
  {
    type: 'CLIENT',
    name: '客户端',
    description: '400 系列客户端错误',
    action: '透传原始错误给调用方'
  }
]

// 错误处理副作用
const errorSideEffects = [
  { name: '缓存失效', description: '通过 CacheAwareScheduler 失效亲和性缓存' },
  { name: '健康记录', description: '通过 health_monitor 记录失败事件' },
  { name: 'RPM 调整', description: '429 错误时自适应调整 RPM 限制' },
  { name: 'OAuth 标记', description: '403 VALIDATION_REQUIRED 时标记 Key 为账号封禁' }
]

// 格式转换三层开关
const conversionLayers = [
  {
    level: '全局',
    setting: 'enable_format_conversion',
    description: '系统设置中的全局开关。开启后允许所有跨格式路由。'
  },
  {
    level: 'Provider',
    setting: 'Provider.enable_format_conversion',
    description: '全局关闭时，可在 Provider 级别单独开启格式转换。'
  },
  {
    level: 'Endpoint',
    setting: 'format_acceptance_config',
    description: '以上两级都关闭时，通过端点的 accept/reject 规则精细控制接受哪些入站格式。'
  }
]

// 配额类型
const quotaTypes = [
  {
    name: '请求次数配额',
    description: '限制每日/每月的 API 调用次数，超过后请求会被拒绝',
    scope: '用户级 / Key 级'
  },
  {
    name: 'Token 用量配额',
    description: '限制每日/每月的 Token 消耗量，适合控制成本',
    scope: '用户级 / Key 级'
  }
]
</script>

<template>
  <div class="space-y-8">
    <!-- 标题 -->
    <div class="space-y-3">
      <h1 class="text-3xl font-bold text-[#262624] dark:text-[#f1ead8]">
        关键策略
      </h1>
      <p class="text-base text-[#666663] dark:text-[#a3a094]">
        {{ siteName }} 的调度、缓存亲和性、故障转移、并发控制等核心策略机制。
      </p>
    </div>

    <!-- 调度策略 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        调度策略
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        当一个模型关联了多个端点和密钥时，系统需要决定使用哪个 Provider + Endpoint + Key 组合。调度模式决定了候选的排序方式：
      </p>

      <div class="grid gap-3 md:grid-cols-2">
        <div
          v-for="mode in schedulingModes"
          :key="mode.name"
          class="p-4"
          :class="[panelClasses.section]"
        >
          <div class="flex items-center gap-2.5 mb-2">
            <component
              :is="mode.icon"
              class="h-4 w-4 text-[#cc785c]"
            />
            <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8]">
              {{ mode.name }}
            </h3>
            <span
              v-if="mode.badge"
              :class="panelClasses.badge"
            >{{ mode.badge }}</span>
          </div>
          <p class="text-sm text-[#666663] dark:text-[#a3a094]">
            {{ mode.description }}
          </p>
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
              哈希分散
            </p>
            <p class="mt-1">
              当多个候选具有相同优先级时，系统使用哈希算法将请求均匀分散到各个候选上，避免所有请求集中到同一个 Key。
              哈希因子结合了 affinity_key（通常为用户 API Key ID），使得同一用户的请求倾向于命中相同的候选。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 缓存亲和性 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        缓存亲和性
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        缓存亲和性是 {{ siteName }} 的核心优化策略，用于最大化利用上游供应商的 Prompt Caching 机制。
      </p>

      <div
        class="overflow-hidden"
        :class="[panelClasses.section]"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50">
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094] w-10">
                  #
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  步骤
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  说明
                </th>
              </tr>
            </thead>
            <tbody>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)]">
                <td class="px-4 py-2.5 text-[#cc785c] font-bold">
                  1
                </td>
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  提取亲和性键
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  用户发起请求时，系统提取 <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">affinity_key</code>（通常为用户 API Key ID）
                </td>
              </tr>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)]">
                <td class="px-4 py-2.5 text-[#cc785c] font-bold">
                  2
                </td>
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  查询缓存
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  查找该 affinity_key 上次成功使用的 ProviderAPIKey（从 Redis 缓存读取）
                </td>
              </tr>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)]">
                <td class="px-4 py-2.5 text-[#cc785c] font-bold">
                  3
                </td>
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  候选置顶
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  如果找到且该 Key 仍可用，将其置顶到候选列表最前面
                </td>
              </tr>
              <tr class="last:border-0">
                <td class="px-4 py-2.5 text-[#cc785c] font-bold">
                  4
                </td>
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  更新记录
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  请求成功后，更新缓存记录。请求失败时，失效该缓存条目
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="grid gap-3 md:grid-cols-2">
        <div
          class="p-4"
          :class="[panelClasses.section]"
        >
          <h4 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8] mb-2">
            为什么重要？
          </h4>
          <ul class="space-y-1 text-sm text-[#666663] dark:text-[#a3a094]">
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>Claude/OpenAI 等供应商支持 Prompt Caching，重复前缀可免费/降价</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>同一用户的连续请求通常有大量重复上下文</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>稳定路由到同一个 Key 可以最大化缓存命中率</span>
            </li>
          </ul>
        </div>

        <div
          class="p-4"
          :class="[panelClasses.section]"
        >
          <h4 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8] mb-2">
            缓存层级
          </h4>
          <ul class="space-y-1 text-sm text-[#666663] dark:text-[#a3a094]">
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span><strong>L1 内存缓存</strong>：3 秒 TTL，减少 Redis 访问</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span><strong>L2 Redis 缓存</strong>：持久化亲和性映射</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span><strong>降级</strong>：Redis 不可用时禁用亲和性，使用普通排序</span>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 故障转移 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        故障转移
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        当某个候选失败时，系统会根据错误类型决定是否尝试下一个候选。错误分类由 ErrorClassifier 负责：
      </p>

      <div
        class="overflow-hidden"
        :class="[panelClasses.section]"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50">
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  类型
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  触发条件
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  处理方式
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="error in errorCategories"
                :key="error.type"
                class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] last:border-0"
              >
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1.5 py-0.5 rounded">{{ error.type }}</code>
                  <span class="ml-1.5 text-[#666663] dark:text-[#a3a094] font-normal text-xs">{{ error.name }}</span>
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  {{ error.description }}
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  {{ error.action }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 错误处理副作用 -->
      <div
        class="p-4"
        :class="[panelClasses.section]"
      >
        <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8] mb-2">
          错误处理副作用
        </h3>
        <p class="text-sm text-[#666663] dark:text-[#a3a094] mb-2.5">
          错误分类后，ErrorHandlerService 负责执行副作用操作：
        </p>
        <div class="grid gap-2 sm:grid-cols-2">
          <div
            v-for="effect in errorSideEffects"
            :key="effect.name"
            class="p-3 rounded-lg bg-[#f5f5f0]/50 dark:bg-[#1f1d1a]/50"
          >
            <h4 class="font-medium text-xs text-[#262624] dark:text-[#f1ead8]">
              {{ effect.name }}
            </h4>
            <p class="text-xs text-[#666663] dark:text-[#a3a094] mt-0.5">
              {{ effect.description }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 并发控制 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        并发控制
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        系统通过多层并发控制保护上游服务不被过载：
      </p>

      <div class="grid gap-3 md:grid-cols-2">
        <div
          class="p-4"
          :class="[panelClasses.section]"
        >
          <div class="flex items-center gap-2.5 mb-2">
            <Activity class="h-4 w-4 text-[#cc785c]" />
            <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8]">
              RPM 限流
            </h3>
          </div>
          <ul class="space-y-1 text-sm text-[#666663] dark:text-[#a3a094]">
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>按 ProviderAPIKey 维度限制每分钟请求数</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>超过 RPM 限制的候选在构建阶段被跳过</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>429 错误时自适应降低 RPM 限制</span>
            </li>
          </ul>
        </div>

        <div
          class="p-4"
          :class="[panelClasses.section]"
        >
          <div class="flex items-center gap-2.5 mb-2">
            <Activity class="h-4 w-4 text-[#cc785c]" />
            <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8]">
              动态预留
            </h3>
          </div>
          <ul class="space-y-1 text-sm text-[#666663] dark:text-[#a3a094]">
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>为缓存亲和性用户预留一定的 RPM 额度</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>避免非缓存用户占满配额导致缓存用户无法命中</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>预留比例根据负载情况自适应调整</span>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 格式转换开关 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        格式转换控制
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        格式转换（跨格式路由）由三层开关从高到低控制：
      </p>

      <div
        class="overflow-hidden"
        :class="[panelClasses.section]"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50">
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094] w-10">
                  #
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  层级
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  配置项
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  说明
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(layer, index) in conversionLayers"
                :key="layer.level"
                class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] last:border-0"
              >
                <td class="px-4 py-2.5 text-[#cc785c] font-bold">
                  {{ index + 1 }}
                </td>
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  {{ layer.level }}
                </td>
                <td class="px-4 py-2.5 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  {{ layer.setting }}
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  {{ layer.description }}
                </td>
              </tr>
            </tbody>
          </table>
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
              优先级降级
            </p>
            <p class="mt-1">
              需要格式转换的候选默认会被排到列表后面（降级排序）。通过全局 <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">keep_priority_on_conversion</code>
              或 Provider 级别的同名配置，可以保持原有优先级不降级。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 配额管理 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        配额管理
      </h2>

      <div class="grid gap-3 md:grid-cols-2">
        <div
          v-for="quota in quotaTypes"
          :key="quota.name"
          class="p-4"
          :class="[panelClasses.section]"
        >
          <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8] mb-1.5">
            {{ quota.name }}
          </h3>
          <p class="text-sm text-[#666663] dark:text-[#a3a094]">
            {{ quota.description }}
          </p>
          <div class="mt-2">
            <span :class="panelClasses.badgeBlue">{{ quota.scope }}</span>
          </div>
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
              配额继承
            </p>
            <p class="mt-1">
              可以在用户级别设置默认配额，新创建的 API Key 会自动继承。也可以在创建 Key 时覆盖默认配额。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 健康监控 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        健康监控
      </h2>

      <div
        class="p-4"
        :class="[panelClasses.section]"
      >
        <ul class="space-y-1.5 text-sm text-[#666663] dark:text-[#a3a094]">
          <li class="flex items-start gap-2">
            <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
            <span>系统持续记录每个端点的成功/失败请求</span>
          </li>
          <li class="flex items-start gap-2">
            <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
            <span>连续失败超过阈值的端点会被标记为不健康</span>
          </li>
          <li class="flex items-start gap-2">
            <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
            <span>不健康的端点在候选构建时被跳过，请求自动路由到其他端点</span>
          </li>
          <li class="flex items-start gap-2">
            <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
            <span>定期对不健康端点进行探测恢复</span>
          </li>
          <li class="flex items-start gap-2">
            <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
            <span>可以在管理后台的「健康监控」页面查看实时状态并手动触发检查</span>
          </li>
        </ul>
      </div>
    </section>

    <!-- 下一步 -->
    <section class="pt-2">
      <RouterLink
        to="/guide/advanced"
        class="p-4 flex items-center gap-3 group"
        :class="[panelClasses.section, panelClasses.cardHover]"
      >
        <div class="flex-1">
          <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
            下一步：高级功能
          </div>
          <div class="text-xs text-[#666663] dark:text-[#a3a094]">
            格式转换操作、请求头/请求体规则、系统设置
          </div>
        </div>
        <ArrowRight class="h-4 w-4 text-[#999] group-hover:text-[#cc785c] transition-colors" />
      </RouterLink>
    </section>
  </div>
</template>
