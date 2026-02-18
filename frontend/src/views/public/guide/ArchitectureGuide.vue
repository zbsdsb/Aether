<script setup lang="ts">
import { RouterLink } from 'vue-router'
import {
  ArrowRight,
  ChevronRight,
  Monitor,
  Shield,
  Zap,
  Database,
  Info,
  Shuffle
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

// 系统分层
const layers = [
  {
    name: 'API 层',
    path: 'api/ + middleware/',
    description: '协议路由、格式适配、认证鉴权、请求管道'
  },
  {
    name: '编排层',
    path: 'services/orchestration/',
    description: '候选排序、请求分发、错误分类、故障转移'
  },
  {
    name: '调度层',
    path: 'services/scheduling/',
    description: '候选构建、优先级排序、缓存亲和性、并发检查'
  },
  {
    name: '供应商适配层',
    path: 'services/provider/',
    description: '上游 HTTP 调用、认证管理、流式传输'
  }
]

// 请求处理流程
const requestFlow = [
  { step: '请求进入', detail: 'ASGI 中间件处理限流、监控、DB Session 管理' },
  { step: '路由匹配', detail: '根据请求路径选择对应的格式适配器（Claude/OpenAI/Gemini）' },
  { step: '认证鉴权', detail: 'API Key / JWT / Management Token 认证，配额与权限检查' },
  { step: '候选构建', detail: '查询可用的 Provider + Endpoint + Key 组合，构建候选列表' },
  { step: '候选排序', detail: '按调度模式排序（优先级/全局Key），结合缓存亲和性调整顺序' },
  { step: '故障转移执行', detail: '按序尝试候选，失败时根据错误分类决定重试或放弃' },
  { step: '上游调用', detail: '构建上游请求，处理流式/非流式响应' },
  { step: '响应后处理', detail: '用量统计、计费、缓存亲和性更新、审计记录' }
]

// 数据存储
const dataStores = [
  {
    name: 'PostgreSQL',
    role: '主存储',
    items: ['用户与认证', '供应商/端点/密钥', '模型与路由', '用量与配额', '统计聚合', '审计日志']
  },
  {
    name: 'Redis',
    role: '缓存与协调',
    items: ['缓存亲和性 (affinity)', 'RPM 限流计数', '任务协调锁', 'Usage 队列 (Streams)', '通用缓存 (Provider/Model/User)']
  }
]
</script>

<template>
  <div class="space-y-8">
    <!-- 标题 -->
    <div class="space-y-3">
      <h1 class="text-3xl font-bold text-[#262624] dark:text-[#f1ead8]">
        架构说明
      </h1>
      <p class="text-base text-[#666663] dark:text-[#a3a094]">
        {{ siteName }} 的系统架构、请求处理流程和数据流向。
      </p>
    </div>

    <!-- 系统概览 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        系统概览
      </h2>

      <div
        class="p-5"
        :class="[panelClasses.section]"
      >
        <div class="flex items-center justify-center gap-3 sm:gap-6 flex-wrap text-sm">
          <div class="text-center">
            <Monitor class="h-4 w-4 text-[#cc785c] mx-auto mb-1.5" />
            <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
              客户端
            </div>
            <div class="text-xs text-[#666663] dark:text-[#a3a094]">
              SDK / CLI / Web
            </div>
          </div>

          <ChevronRight class="h-4 w-4 text-[#999]" />

          <div class="text-center">
            <Shield class="h-4 w-4 text-[#cc785c] mx-auto mb-1.5" />
            <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
              {{ siteName }}
            </div>
            <div class="text-xs text-[#666663] dark:text-[#a3a094]">
              认证 / 路由 / 编排
            </div>
          </div>

          <ChevronRight class="h-4 w-4 text-[#999]" />

          <div class="text-center">
            <Zap class="h-4 w-4 text-[#cc785c] mx-auto mb-1.5" />
            <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
              上游供应商
            </div>
            <div class="text-xs text-[#666663] dark:text-[#a3a094]">
              Claude / OpenAI / Gemini
            </div>
          </div>
        </div>

        <div class="mt-3 flex items-center justify-center gap-6 text-xs text-[#666663] dark:text-[#a3a094]">
          <div class="flex items-center gap-1.5">
            <Database class="h-3 w-3" />
            <span>PostgreSQL</span>
          </div>
          <div class="flex items-center gap-1.5">
            <Zap class="h-3 w-3" />
            <span>Redis</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 分层架构 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        分层架构
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        系统采用严格的分层架构，依赖方向从上到下，禁止反向依赖：
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
                  路径
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  职责
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(layer, index) in layers"
                :key="layer.name"
                class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] last:border-0"
              >
                <td class="px-4 py-2.5 text-[#cc785c] font-bold">
                  {{ index + 1 }}
                </td>
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  {{ layer.name }}
                </td>
                <td class="px-4 py-2.5 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  {{ layer.path }}
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
              依赖规则
            </p>
            <ul class="mt-1 space-y-1">
              <li><code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">api/</code> 可以依赖 <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">services/</code> 和 <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">core/</code></li>
              <li><code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">services/</code> 可以依赖 <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">core/</code>、<code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">models/</code>、<code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">clients/</code>，禁止反向依赖 <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">api/</code></li>
              <li><code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1 py-0.5 rounded">core/</code> 保持纯工具与协议，尽量无副作用</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- 请求处理流程 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        请求处理流程
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        一个 API 请求从进入到响应的完整处理链路：
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
              <tr
                v-for="(item, index) in requestFlow"
                :key="item.step"
                class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] last:border-0"
              >
                <td class="px-4 py-2.5 text-[#cc785c] font-bold">
                  {{ index + 1 }}
                </td>
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  {{ item.step }}
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  {{ item.detail }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 格式转换流程 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        格式转换原理
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        当客户端使用的 API 格式与上游端点不同时，系统会自动执行格式转换：
      </p>

      <div
        class="p-5"
        :class="[panelClasses.section]"
      >
        <div class="flex items-center justify-center gap-3 sm:gap-6 flex-wrap text-sm">
          <div class="text-center">
            <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
              入站格式
            </div>
            <div class="text-xs text-[#666663] dark:text-[#a3a094]">
              OpenAI / Claude / Gemini
            </div>
          </div>

          <ChevronRight class="h-4 w-4 text-[#999]" />

          <div class="text-center">
            <Shuffle class="h-4 w-4 text-[#cc785c] mx-auto mb-1" />
            <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
              归一化
            </div>
            <div class="text-xs text-[#666663] dark:text-[#a3a094]">
              统一内部格式
            </div>
          </div>

          <ChevronRight class="h-4 w-4 text-[#999]" />

          <div class="text-center">
            <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
              目标格式
            </div>
            <div class="text-xs text-[#666663] dark:text-[#a3a094]">
              匹配上游端点
            </div>
          </div>
        </div>
        <p class="text-center text-xs text-[#666663] dark:text-[#a3a094] mt-3">
          例如：用 OpenAI SDK 发送请求 -> 归一化为内部格式 -> 转换为 Claude API 格式发送给上游
        </p>
      </div>
    </section>

    <!-- 数据存储 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        数据存储
      </h2>

      <div class="grid gap-3 md:grid-cols-2">
        <div
          v-for="store in dataStores"
          :key="store.name"
          class="p-4"
          :class="[panelClasses.section]"
        >
          <div class="flex items-center gap-2.5 mb-2.5">
            <Database class="h-4 w-4 text-[#cc785c]" />
            <div>
              <h3 class="font-semibold text-sm text-[#262624] dark:text-[#f1ead8]">
                {{ store.name }}
              </h3>
              <span class="text-xs text-[#666663] dark:text-[#a3a094]">{{ store.role }}</span>
            </div>
          </div>
          <ul class="space-y-1">
            <li
              v-for="item in store.items"
              :key="item"
              class="flex items-start gap-2 text-sm text-[#666663] dark:text-[#a3a094]"
            >
              <span class="text-[#cc785c] mt-1.5 flex-shrink-0 text-[6px]">&#9679;</span>
              <span>{{ item }}</span>
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
              Redis 降级
            </p>
            <p class="mt-1">
              Redis 客户端内置熔断机制：连续 3 次失败触发熔断，60 秒后尝试恢复。开发模式下可完全降级为内存模式运行。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 适配器体系 -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        适配器体系
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        {{ siteName }} 通过适配器模式支持多种 API 格式，每种格式有独立的请求构建和响应解析逻辑：
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
                  基类
                </th>
                <th class="px-4 py-2.5 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  实现
                </th>
              </tr>
            </thead>
            <tbody>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)]">
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8]">
                  聊天 API
                </td>
                <td class="px-4 py-2.5 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  ChatAdapterBase
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  Claude / OpenAI / Gemini
                </td>
              </tr>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)]">
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8]">
                  CLI 透传
                </td>
                <td class="px-4 py-2.5 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  CliAdapterBase
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  Claude CLI / OpenAI CLI (Codex) / Gemini CLI
                </td>
              </tr>
              <tr class="last:border-0">
                <td class="px-4 py-2.5 font-medium text-[#262624] dark:text-[#f1ead8]">
                  视频/图片
                </td>
                <td class="px-4 py-2.5 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  VideoAdapterBase
                </td>
                <td class="px-4 py-2.5 text-[#666663] dark:text-[#a3a094]">
                  OpenAI Video / Gemini Video / Gemini Image
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 下一步 -->
    <section class="pt-2">
      <RouterLink
        to="/guide/concepts"
        class="p-4 flex items-center gap-3 group"
        :class="[panelClasses.section, panelClasses.cardHover]"
      >
        <div class="flex-1">
          <div class="font-medium text-sm text-[#262624] dark:text-[#f1ead8]">
            下一步：相关概念
          </div>
          <div class="text-xs text-[#666663] dark:text-[#a3a094]">
            深入了解供应商、端点、模型等核心概念
          </div>
        </div>
        <ArrowRight class="h-4 w-4 text-[#999] group-hover:text-[#cc785c] transition-colors" />
      </RouterLink>
    </section>
  </div>
</template>
