<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import {
  Server,
  Layers,
  Key,
  Copy,
  Check,
  Plus,
  ChevronDown,
  ChevronRight,
  Info,
  Shield,
  Globe,
  Trash2,
  Lock,
  Search,
  GitMerge,
  Settings,
  Zap,
  Container,
  Code,
  Monitor,
  Power,
  Shuffle,
  Radio,
  Filter,
  ExternalLink
} from 'lucide-vue-next'
import {
  Input,
  Label,
  Button,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Switch,
  Badge,
  Textarea,
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent
} from '@/components/ui'
import { apiFormats, panelClasses } from './guide-config'
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

const recommendedPosts = [
  { title: 'Aether 使用经验1', url: 'https://linux.do/t/topic/1537222' },
  { title: 'Aether 使用经验2', url: 'https://linux.do/t/topic/1587573' },
  { title: 'Aether 模型映射', url: 'https://linux.do/t/topic/1539470' }
]

// 当前展开的步骤
const activeStep = ref(0)

// ========== Step 1: 全局模型表单 ==========
const step1 = reactive({
  display_name: '',
  name: '',
  description: '',
  capabilities: [] as string[],
  // 阶梯定价
  input_price: '0',
  output_price: '0',
  cache_creation: '',
  cache_read: '',
  // 按次计费
  price_per_request: '',
  // 左侧搜索和展开
  searchQuery: '',
  expandedProvider: null as string | null,
  selectedModel: null as { providerId: string; modelId: string } | null
})

const allCapabilities = [
  { name: '1_hour_cache', display: '1 小时缓存' },
  { name: 'cli_1m_context', display: 'CLI 1M 上下文' },
  { name: 'gemini_file_api', display: 'Gemini 文件 API' }
]

const step1ProviderModels = [
  { providerId: 'alibaba', providerName: 'Alibaba', logo: 'alibaba', count: 39, models: [
    { modelId: 'qwen-turbo', modelName: 'Qwen Turbo' },
    { modelId: 'qwen-plus', modelName: 'Qwen Plus' }
  ] },
  { providerId: 'anthropic', providerName: 'Anthropic', logo: 'anthropic', count: 22, models: [
    { modelId: 'claude-sonnet-4-20250514', modelName: 'Claude Sonnet 4' },
    { modelId: 'claude-opus-4-20250514', modelName: 'Claude Opus 4' }
  ] },
  { providerId: 'google', providerName: 'Google', logo: 'google', count: 26, models: [
    { modelId: 'gemini-2.5-pro', modelName: 'Gemini 2.5 Pro' },
    { modelId: 'gemini-2.5-flash', modelName: 'Gemini 2.5 Flash' }
  ] },
  { providerId: 'openai', providerName: 'OpenAI', logo: 'openai', count: 42, models: [
    { modelId: 'gpt-4o', modelName: 'GPT-4o' },
    { modelId: 'o3', modelName: 'o3' }
  ] },
  { providerId: 'deepseek', providerName: 'DeepSeek', logo: 'deepseek', count: 2, models: [
    { modelId: 'deepseek-chat', modelName: 'DeepSeek Chat' },
    { modelId: 'deepseek-reasoner', modelName: 'DeepSeek Reasoner' }
  ] }
]

function toggleCapability(cap: string) {
  const idx = step1.capabilities.indexOf(cap)
  if (idx === -1) step1.capabilities.push(cap)
  else step1.capabilities.splice(idx, 1)
}

function selectStep1Model(providerId: string, modelId: string, modelName: string) {
  step1.selectedModel = { providerId, modelId }
  step1.name = modelId
  step1.display_name = modelName
}

// ========== Step 2: 提供商表单 ==========
const step2 = reactive({
  name: '',
  provider_type: 'custom',
  website: '',
  billing_type: 'pay_as_you_go',
  max_retries: '',
  stream_first_byte_timeout: '',
  request_timeout: '',
  keep_priority_on_conversion: false,
  proxy_enabled: false
})

// ========== Step 3: 端点表单 ==========
interface HeaderRule {
  action: 'set' | 'drop' | 'rename'
  key: string
  value: string
  from: string
  to: string
}

interface BodyRule {
  action: 'set' | 'drop' | 'rename' | 'insert' | 'regex_replace'
  path: string
  value: string
  from: string
  to: string
  conditionEnabled: boolean
  conditionPath: string
  conditionOp: string
  conditionValue: string
}

const step3Endpoints = ref([
  {
    id: '1',
    api_format: 'openai_chat',
    label: 'OpenAI Chat',
    base_url: 'https://api.openai.com',
    custom_path: '',
    enabled: true,
    format_conversion: false,
    upstream_stream_policy: 'auto' as 'auto' | 'force_stream' | 'force_non_stream',
    header_rules: [] as HeaderRule[],
    body_rules: [] as BodyRule[]
  },
  {
    id: '2',
    api_format: 'claude_chat',
    label: 'Claude Chat',
    base_url: 'https://api.anthropic.com',
    custom_path: '',
    enabled: true,
    format_conversion: true,
    upstream_stream_policy: 'auto' as 'auto' | 'force_stream' | 'force_non_stream',
    header_rules: [
      { action: 'set' as const, key: 'anthropic-version', value: '2023-06-01', from: '', to: '' }
    ] as HeaderRule[],
    body_rules: [] as BodyRule[]
  }
])

const endpointRulesExpanded = reactive<Record<string, boolean>>({
  '2': true
})

function addHeaderRule(endpointId: string) {
  const ep = step3Endpoints.value.find(e => e.id === endpointId)
  if (ep) {
    ep.header_rules.push({ action: 'set', key: '', value: '', from: '', to: '' })
    endpointRulesExpanded[endpointId] = true
  }
}

function addBodyRule(endpointId: string) {
  const ep = step3Endpoints.value.find(e => e.id === endpointId)
  if (ep) {
    ep.body_rules.push({ action: 'set', path: '', value: '', from: '', to: '', conditionEnabled: false, conditionPath: '', conditionOp: 'eq', conditionValue: '' })
    endpointRulesExpanded[endpointId] = true
  }
}

function removeHeaderRule(endpointId: string, index: number) {
  const ep = step3Endpoints.value.find(e => e.id === endpointId)
  if (ep) ep.header_rules.splice(index, 1)
}

function removeBodyRule(endpointId: string, index: number) {
  const ep = step3Endpoints.value.find(e => e.id === endpointId)
  if (ep) ep.body_rules.splice(index, 1)
}

function getTotalRulesCount(endpoint: typeof step3Endpoints.value[0]) {
  return endpoint.header_rules.length + endpoint.body_rules.length
}

const step3New = reactive({
  api_format: 'gemini_chat',
  base_url: '',
  custom_path: ''
})

const apiFormatOptions = [
  { value: 'openai_chat', label: 'OpenAI Chat' },
  { value: 'openai_cli', label: 'OpenAI CLI (Responses)' },
  { value: 'claude_chat', label: 'Claude Chat' },
  { value: 'claude_cli', label: 'Claude CLI' },
  { value: 'gemini_chat', label: 'Gemini Chat' },
  { value: 'gemini_cli', label: 'Gemini CLI' }
]

const apiFormatDefaultPaths: Record<string, string> = {
  openai_chat: '/v1/chat/completions',
  openai_cli: '/v1/responses',
  claude_chat: '/v1/messages',
  claude_cli: '/v1/messages',
  gemini_chat: '/v1beta/models/{model}:generateContent',
  gemini_cli: '/v1beta/models/{model}:generateContent'
}

const step3AvailableFormats = computed(() => {
  const usedFormats = step3Endpoints.value.map(e => e.api_format)
  return apiFormatOptions.filter(f => !usedFormats.includes(f.value))
})

function toggleEndpointStreamPolicy(endpoint: typeof step3Endpoints.value[0]) {
  const policies = ['auto', 'force_stream', 'force_non_stream'] as const
  const idx = policies.indexOf(endpoint.upstream_stream_policy)
  endpoint.upstream_stream_policy = policies[(idx + 1) % 3]
}

function getEndpointStreamClass(endpoint: typeof step3Endpoints.value[0]): string {
  const base = 'h-7 w-7'
  if (endpoint.upstream_stream_policy === 'force_stream') return `${base} text-primary`
  if (endpoint.upstream_stream_policy === 'force_non_stream') return `${base} text-destructive`
  return `${base} text-muted-foreground`
}

const streamPolicyLabels: Record<string, string> = {
  auto: '自动',
  force_stream: '强制流式',
  force_non_stream: '强制非流式'
}

// ========== Step 4: 密钥表单 ==========
const step4 = reactive({
  name: '',
  auth_type: 'api_key',
  api_key: '',
  note: '',
  api_formats: ['openai_chat'] as string[],
  rate_multipliers: {} as Record<string, number>,
  internal_priority: 10,
  rpm_limit: '',
  cache_ttl_minutes: '5',
  max_probe_interval_minutes: '',
  auto_fetch_models: false
})

const keyApiFormats = [
  { value: 'openai_chat', label: 'OpenAI Chat' },
  { value: 'openai_cli', label: 'OpenAI CLI' },
  { value: 'claude_chat', label: 'Claude Chat' },
  { value: 'claude_cli', label: 'Claude CLI' },
  { value: 'gemini_chat', label: 'Gemini Chat' },
  { value: 'gemini_cli', label: 'Gemini CLI' }
]

function toggleKeyApiFormat(format: string) {
  const idx = step4.api_formats.indexOf(format)
  if (idx === -1) step4.api_formats.push(format)
  else step4.api_formats.splice(idx, 1)
}

// ========== Step 5: 关联模型 ==========
const step5 = reactive({
  searchQuery: '',
  globalExpanded: true
})

const step5GlobalModels = [
  { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4' },
  { id: 'claude-opus-4-20250514', name: 'Claude Opus 4' },
  { id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku' },
  { id: 'gpt-4o', name: 'GPT-4o' },
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini' },
  { id: 'o3', name: 'o3' },
  { id: 'o4-mini', name: 'o4 Mini' },
  { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
  { id: 'deepseek-chat', name: 'DeepSeek Chat' },
  { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner' },
  { id: 'qwen-plus', name: 'Qwen Plus' },
  { id: 'qwen-turbo', name: 'Qwen Turbo' }
]

const step5SelectedModels = ref([
  'claude-sonnet-4-20250514',
  'claude-opus-4-20250514',
  'claude-3-5-haiku-20241022'
])

const step5FilteredModels = computed(() => {
  if (!step5.searchQuery) return step5GlobalModels
  const q = step5.searchQuery.toLowerCase()
  return step5GlobalModels.filter(m => m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q))
})

function toggleStep5Model(modelId: string) {
  const idx = step5SelectedModels.value.indexOf(modelId)
  if (idx === -1) step5SelectedModels.value.push(modelId)
  else step5SelectedModels.value.splice(idx, 1)
}

function toggleStep5All() {
  const filtered = step5FilteredModels.value
  const allSelected = filtered.every(m => step5SelectedModels.value.includes(m.id))
  if (allSelected) {
    step5SelectedModels.value = step5SelectedModels.value.filter(id => !filtered.some(m => m.id === id))
  } else {
    const toAdd = filtered.filter(m => !step5SelectedModels.value.includes(m.id)).map(m => m.id)
    step5SelectedModels.value.push(...toAdd)
  }
}

// ========== Step 6: 模型权限 ==========
const step6 = reactive({
  searchQuery: '',
  selectedModels: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514'] as string[],
  lockedModels: [] as string[]
})

const step6AllModels = [
  { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4', group: 'global' },
  { id: 'claude-opus-4-20250514', name: 'Claude Opus 4', group: 'global' },
  { id: 'gpt-4o', name: 'GPT-4o', group: 'global' },
  { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', group: 'upstream' },
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', group: 'upstream' }
]

function toggleModel(modelId: string) {
  const idx = step6.selectedModels.indexOf(modelId)
  if (idx === -1) step6.selectedModels.push(modelId)
  else step6.selectedModels.splice(idx, 1)
}

function toggleModelLock(modelId: string) {
  const idx = step6.lockedModels.indexOf(modelId)
  if (idx === -1) step6.lockedModels.push(modelId)
  else step6.lockedModels.splice(idx, 1)
}

// 部署步骤数据
const activeDeployTab = ref(0)
const copiedStep = ref<string | null>(null)

const productionSteps = [
  {
    title: '克隆代码',
    code: 'git clone https://github.com/fawney19/Aether.git\ncd Aether',
    icon: Code
  },
  {
    title: '配置环境变量',
    note: '生成密钥并填入 .env',
    code: 'cp .env.example .env\npython generate_keys.py',
    icon: Key
  },
  {
    title: '部署 / 更新',
    note: '自动执行数据库迁移',
    code: 'docker compose pull && docker compose up -d',
    icon: Container
  },
  {
    title: '升级前备份',
    note: '可选',
    code: 'docker compose exec postgres pg_dump -U postgres aether | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz',
    icon: Shield,
    optional: true
  }
]

const developmentSteps = [
  {
    title: '启动依赖',
    note: 'PostgreSQL + Redis',
    code: 'docker compose -f docker-compose.build.yml up -d postgres redis',
    icon: Container
  },
  {
    title: '后端',
    note: '热重载开发服务器',
    code: 'uv sync\n./dev.sh',
    icon: Server
  },
  {
    title: '前端',
    note: '自动代理到 8084',
    code: 'cd frontend && npm install && npm run dev',
    icon: Monitor
  }
]

function copyStep(stepId: string, code: string) {
  navigator.clipboard.writeText(code)
  copiedStep.value = stepId
  setTimeout(() => {
    copiedStep.value = null
  }, 2000)
}

// 配置流程步骤元数据
const configStepsMeta = [
  { icon: Layers, title: '全局模型', short: '模型', optional: false },
  { icon: Server, title: '添加提供商', short: '提供商', optional: false },
  { icon: Globe, title: '添加端点', short: '端点', optional: false },
  { icon: Key, title: '添加密钥', short: '密钥', optional: false },
  { icon: GitMerge, title: '关联模型', short: '关联', optional: false },
  { icon: Shield, title: '模型权限', short: '权限', optional: true }
]
</script>

<template>
  <div class="space-y-8">
    <!-- Hero 区域 -->
    <div class="space-y-4">
      <div class="inline-flex items-center gap-1.5 rounded-full bg-[#cc785c]/10 dark:bg-[#cc785c]/20 border border-[#cc785c]/20 dark:border-[#cc785c]/40 px-3 py-1 text-xs font-medium text-[#cc785c] dark:text-[#d4a27f]">
        <Zap class="h-3 w-3" />
        AI API Gateway
      </div>
      <h1 class="text-3xl font-bold text-[#262624] dark:text-[#f1ead8]">
        快速开始
      </h1>
      <p class="text-base text-[#666663] dark:text-[#a3a094] max-w-2xl">
        部署 {{ siteName }}，统一管理 Claude、OpenAI、Gemini 等多个 AI 服务供应商。
      </p>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="feature in ['多供应商聚合', '智能负载均衡', '自动故障转移', '用量统计']"
          :key="feature"
          class="inline-flex items-center gap-1 rounded-full bg-[#f5f5f0] dark:bg-[#262624]/80 border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] px-2.5 py-1 text-xs text-[#666663] dark:text-[#a3a094]"
        >
          <Check class="h-3 w-3 text-[#cc785c]" />
          {{ feature }}
        </span>
      </div>
    </div>

    <!-- 部署 -->
    <section
      id="production"
      class="scroll-mt-24 lg:scroll-mt-20"
    >
      <div :class="[panelClasses.card]">
        <!-- Header -->
        <div class="px-5 pt-5 pb-0">
          <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
            部署
          </h2>
          <p class="text-sm text-[#666663] dark:text-[#a3a094] mt-1">
            选择适合你的部署方式开始
          </p>
        </div>

        <!-- Tab 切换 -->
        <div class="flex border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] px-5 mt-3">
          <button
            v-for="(tab, idx) in [
              { icon: Container, label: '生产环境', desc: 'Docker Compose 预构建镜像' },
              { icon: Code, label: '开发环境', desc: '本地开发' }
            ]"
            :key="idx"
            class="flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px"
            :class="activeDeployTab === idx
              ? 'border-[#cc785c] text-[#cc785c] dark:text-[#d4a27f]'
              : 'border-transparent text-[#666663] dark:text-[#a3a094] hover:text-[#262624] dark:hover:text-[#f1ead8]'"
            @click="activeDeployTab = idx"
          >
            <component
              :is="tab.icon"
              class="h-4 w-4"
            />
            {{ tab.label }}
          </button>
        </div>

        <!-- 生产环境步骤 -->
        <div
          v-show="activeDeployTab === 0"
          id="deploy-production"
          class="p-5 space-y-3"
        >
          <div
            v-for="(step, idx) in productionSteps"
            :key="idx"
            class="group rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] overflow-hidden transition-colors"
            :class="step.optional ? 'border-dashed opacity-80' : ''"
          >
            <div class="flex items-center gap-3 px-4 py-3">
              <span
                class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 bg-[#cc785c] text-white"
              >
                {{ idx + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-[#262624] dark:text-[#f1ead8]">{{ step.title }}</span>
                  <span
                    v-if="step.optional"
                    class="text-[10px] px-1.5 py-0.5 rounded-full bg-[#e5e4df] dark:bg-[rgba(227,224,211,0.12)] text-[#666663] dark:text-[#a3a094]"
                  >
                    可选
                  </span>
                </div>
                <span
                  v-if="step.note"
                  class="text-xs text-[#91918d] dark:text-[#a3a094]/80"
                >{{ step.note }}</span>
              </div>
              <button
                class="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-[#666663] dark:text-[#a3a094] hover:bg-[#f0f0eb] dark:hover:bg-[#3a3731] transition-colors shrink-0"
                @click="copyStep(`prod-${idx}`, step.code)"
              >
                <Check
                  v-if="copiedStep === `prod-${idx}`"
                  class="h-3.5 w-3.5 text-green-500"
                />
                <Copy
                  v-else
                  class="h-3.5 w-3.5"
                />
                {{ copiedStep === `prod-${idx}` ? '已复制' : '复制' }}
              </button>
            </div>
            <pre class="px-4 pb-3 text-[13px] font-mono text-[#262624] dark:text-[#f1ead8] overflow-x-auto leading-relaxed border-t border-[#e5e4df]/50 dark:border-[rgba(227,224,211,0.06)] pt-3 mx-4 mb-1"><code>{{ step.code }}</code></pre>
          </div>
        </div>

        <!-- 开发环境步骤 -->
        <div
          v-show="activeDeployTab === 1"
          id="deploy-development"
          class="p-5 space-y-3"
        >
          <div
            v-for="(step, idx) in developmentSteps"
            :key="idx"
            class="group rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] overflow-hidden transition-colors"
          >
            <div class="flex items-center gap-3 px-4 py-3">
              <span
                class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 bg-[#cc785c] text-white"
              >
                {{ idx + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-[#262624] dark:text-[#f1ead8]">{{ step.title }}</span>
                </div>
                <span
                  v-if="step.note"
                  class="text-xs text-[#91918d] dark:text-[#a3a094]/80"
                >{{ step.note }}</span>
              </div>
              <button
                class="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-[#666663] dark:text-[#a3a094] hover:bg-[#f0f0eb] dark:hover:bg-[#3a3731] transition-colors shrink-0"
                @click="copyStep(`dev-${idx}`, step.code)"
              >
                <Check
                  v-if="copiedStep === `dev-${idx}`"
                  class="h-3.5 w-3.5 text-green-500"
                />
                <Copy
                  v-else
                  class="h-3.5 w-3.5"
                />
                {{ copiedStep === `dev-${idx}` ? '已复制' : '复制' }}
              </button>
            </div>
            <pre class="px-4 pb-3 text-[13px] font-mono text-[#262624] dark:text-[#f1ead8] overflow-x-auto leading-relaxed border-t border-[#e5e4df]/50 dark:border-[rgba(227,224,211,0.06)] pt-3 mx-4 mb-1"><code>{{ step.code }}</code></pre>
          </div>
        </div>
      </div>
    </section>

    <!-- 配置流程 -->
    <section
      id="config-steps"
      class="space-y-4 scroll-mt-24 lg:scroll-mt-20"
    >
      <div>
        <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
          配置流程
        </h2>
        <p class="text-sm text-[#666663] dark:text-[#a3a094] mt-1">
          部署完成后，按以下步骤完成初始配置即可开始使用
        </p>
      </div>

      <!-- 流程概览节点图 -->
      <div
        class="p-4"
        :class="[panelClasses.section]"
      >
        <!-- 图标行：图标 + 连接线严格水平对齐 -->
        <div class="flex items-center justify-between gap-0">
          <template
            v-for="(step, index) in configStepsMeta"
            :key="index"
          >
            <button
              class="shrink-0 cursor-pointer group"
              @click="activeStep = index"
            >
              <div
                class="w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-200"
                :class="activeStep === index
                  ? 'bg-[#cc785c] text-white shadow-md shadow-[#cc785c]/30 scale-110'
                  : activeStep > index
                    ? 'bg-[#cc785c]/15 dark:bg-[#cc785c]/25 text-[#cc785c] dark:text-[#d4a27f]'
                    : 'bg-[#f5f5f0] dark:bg-[#262624]/80 text-[#91918d] dark:text-[#a3a094]/70 group-hover:bg-[#cc785c]/10 group-hover:text-[#cc785c]'"
              >
                <component
                  :is="step.icon"
                  class="h-4 w-4"
                />
              </div>
            </button>
            <div
              v-if="index < configStepsMeta.length - 1"
              class="flex-1 h-px mx-1 transition-colors"
              :class="activeStep > index
                ? 'bg-[#cc785c]/40'
                : 'bg-[#e5e4df] dark:bg-[rgba(227,224,211,0.12)]'"
            />
          </template>
        </div>
        <!-- 文字行：与图标逐一对齐 -->
        <div class="flex items-start justify-between gap-0 mt-1.5">
          <template
            v-for="(step, index) in configStepsMeta"
            :key="`label-${index}`"
          >
            <button
              class="w-9 shrink-0 flex flex-col items-center cursor-pointer"
              @click="activeStep = index"
            >
              <span
                class="text-[11px] font-medium transition-colors"
                :class="activeStep === index
                  ? 'text-[#cc785c] dark:text-[#d4a27f]'
                  : 'text-[#91918d] dark:text-[#a3a094]/70'"
              >
                {{ step.short }}
              </span>
              <span
                v-if="step.optional"
                class="text-[9px] text-[#91918d] dark:text-[#a3a094]/50"
              >
                可选
              </span>
            </button>
            <div
              v-if="index < configStepsMeta.length - 1"
              class="flex-1 mx-1"
            />
          </template>
        </div>
      </div>

      <!-- 步骤选择器（移动端可见，桌面端隐藏） -->
      <div class="flex flex-wrap gap-1.5 pb-1 lg:hidden">
        <button
          v-for="(step, index) in configStepsMeta"
          :key="index"
          class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all"
          :class="activeStep === index
            ? 'bg-[#cc785c]/10 dark:bg-[#cc785c]/20 text-[#cc785c] dark:text-[#d4a27f] border border-[#cc785c]/30 dark:border-[#cc785c]/40'
            : 'text-[#666663] dark:text-[#a3a094] border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] hover:border-[#cc785c]/20 dark:hover:border-[#cc785c]/20'"
          @click="activeStep = index"
        >
          <span
            class="w-4.5 h-4.5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0"
            :class="activeStep === index
              ? 'bg-[#cc785c] text-white'
              : 'bg-[#e5e4df] dark:bg-[rgba(227,224,211,0.12)] text-[#666663] dark:text-[#a3a094]'"
          >
            {{ index + 1 }}
          </span>
          <component
            :is="step.icon"
            class="h-3 w-3"
          />
          {{ step.title }}
        </button>
      </div>

      <!-- ==================== Step 1: 添加全局模型 ==================== -->
      <div
        v-show="activeStep === 0"
        class="grid grid-cols-1 lg:grid-cols-[1fr,280px] gap-4"
      >
        <!-- 左侧: 表单 -->
        <div class="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
          <div class="border-b border-border px-6 py-4">
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                <Layers class="h-5 w-5 text-primary" />
              </div>
              <div class="flex-1 min-w-0">
                <h3 class="text-lg font-semibold text-foreground leading-tight">
                  创建统一模型
                </h3>
              </div>
            </div>
          </div>
          <div class="flex gap-4 px-6 py-4">
            <!-- 左列：模型选择面板 -->
            <div class="w-[220px] shrink-0 flex flex-col">
              <div class="relative mb-3">
                <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  v-model="step1.searchQuery"
                  placeholder="搜索模型、提供商..."
                  class="pl-8 h-8 text-sm"
                />
              </div>
              <div class="flex-1 overflow-y-auto border rounded-lg max-h-[420px] scrollbar-thin">
                <div
                  v-for="group in step1ProviderModels.filter(g => !step1.searchQuery || g.providerName.toLowerCase().includes(step1.searchQuery.toLowerCase()) || g.models.some(m => m.modelId.includes(step1.searchQuery) || m.modelName.toLowerCase().includes(step1.searchQuery.toLowerCase())))"
                  :key="group.providerId"
                  class="border-b last:border-b-0"
                >
                  <div
                    class="flex items-center gap-2 px-2.5 py-2 cursor-pointer hover:bg-muted text-sm"
                    @click="step1.expandedProvider = step1.expandedProvider === group.providerId ? null : group.providerId"
                  >
                    <ChevronRight
                      class="w-3.5 h-3.5 text-muted-foreground transition-transform shrink-0"
                      :class="step1.expandedProvider === group.providerId ? 'rotate-90' : ''"
                    />
                    <span class="truncate font-medium text-xs flex-1">{{ group.providerName }}</span>
                    <span class="text-[10px] text-muted-foreground shrink-0">{{ group.count }}</span>
                  </div>
                  <div
                    v-if="step1.expandedProvider === group.providerId"
                    class="bg-muted/30"
                  >
                    <div
                      v-for="model in group.models.filter(m => !step1.searchQuery || m.modelId.includes(step1.searchQuery) || m.modelName.toLowerCase().includes(step1.searchQuery.toLowerCase()))"
                      :key="model.modelId"
                      class="flex flex-col gap-0.5 pl-7 pr-2.5 py-1.5 cursor-pointer text-xs border-t"
                      :class="step1.selectedModel?.modelId === model.modelId && step1.selectedModel?.providerId === group.providerId
                        ? 'bg-primary text-primary-foreground'
                        : 'hover:bg-muted'"
                      @click="selectStep1Model(group.providerId, model.modelId, model.modelName)"
                    >
                      <span class="truncate font-medium">{{ model.modelName }}</span>
                      <span
                        class="truncate text-[10px]"
                        :class="step1.selectedModel?.modelId === model.modelId && step1.selectedModel?.providerId === group.providerId
                          ? 'text-primary-foreground/70'
                          : 'text-muted-foreground'"
                      >{{ model.modelId }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <!-- 右列：表单 -->
            <div class="flex-1 overflow-y-auto max-h-[420px] scrollbar-thin">
              <form
                class="space-y-5"
                @submit.prevent
              >
                <section class="space-y-3">
                  <h4 class="font-medium text-sm">
                    基本信息
                  </h4>
                  <div class="grid grid-cols-2 gap-3">
                    <div class="space-y-1.5">
                      <Label class="text-xs">名称 *</Label>
                      <Input
                        v-model="step1.display_name"
                        placeholder="Claude 3.5 Sonnet"
                      />
                    </div>
                    <div class="space-y-1.5">
                      <Label class="text-xs">模型ID *</Label>
                      <Input
                        v-model="step1.name"
                        placeholder="claude-3-5-sonnet-20241022"
                      />
                    </div>
                  </div>
                  <div class="space-y-1.5">
                    <Label class="text-xs">描述</Label>
                    <Input
                      v-model="step1.description"
                      placeholder="简短描述此模型的特点"
                    />
                  </div>
                </section>
                <section class="space-y-2">
                  <h4 class="font-medium text-sm">
                    模型偏好
                  </h4>
                  <div class="flex flex-wrap gap-2">
                    <label
                      v-for="cap in allCapabilities"
                      :key="cap.name"
                      class="flex items-center gap-2 px-2.5 py-1 rounded-md border bg-muted/30 cursor-pointer text-sm"
                    >
                      <input
                        type="checkbox"
                        :checked="step1.capabilities.includes(cap.name)"
                        class="rounded"
                        @change="toggleCapability(cap.name)"
                      >
                      <span>{{ cap.display }}</span>
                    </label>
                  </div>
                </section>
                <section class="space-y-3">
                  <h4 class="font-medium text-sm">
                    价格配置
                  </h4>
                  <!-- 阶梯定价 -->
                  <div class="p-3 border rounded-lg bg-muted/20 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="text-sm text-muted-foreground">0 - <strong class="text-foreground">无上限</strong></span>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <div class="space-y-1">
                        <Label class="text-xs">输入 ($/M)</Label>
                        <Input
                          v-model="step1.input_price"
                          type="number"
                          step="0.01"
                          min="0"
                          class="h-8"
                          placeholder="0"
                        />
                      </div>
                      <div class="space-y-1">
                        <Label class="text-xs">输出 ($/M)</Label>
                        <Input
                          v-model="step1.output_price"
                          type="number"
                          step="0.01"
                          min="0"
                          class="h-8"
                          placeholder="0"
                        />
                      </div>
                      <div class="space-y-1">
                        <Label class="text-xs text-muted-foreground">缓存创建 ($/M)</Label>
                        <Input
                          v-model="step1.cache_creation"
                          type="number"
                          step="0.01"
                          min="0"
                          class="h-8"
                          placeholder="自动"
                        />
                      </div>
                      <div class="space-y-1">
                        <Label class="text-xs text-muted-foreground">缓存读取 ($/M)</Label>
                        <Input
                          v-model="step1.cache_read"
                          type="number"
                          step="0.01"
                          min="0"
                          class="h-8"
                          placeholder="自动"
                        />
                      </div>
                    </div>
                  </div>
                  <!-- 添加价格阶梯 -->
                  <button
                    type="button"
                    class="w-full py-2 text-sm text-muted-foreground border border-dashed rounded-lg hover:bg-muted/20 transition-colors flex items-center justify-center gap-1"
                  >
                    <Plus class="w-3.5 h-3.5" />
                    添加价格阶梯
                  </button>
                  <!-- 按次计费 -->
                  <div class="flex items-center gap-3 pt-2 border-t">
                    <Label class="text-xs whitespace-nowrap">按次计费</Label>
                    <Input
                      v-model="step1.price_per_request"
                      type="number"
                      step="0.001"
                      min="0"
                      class="w-24"
                      placeholder="$/次"
                    />
                    <span class="text-xs text-muted-foreground">可与 Token 计费叠加</span>
                  </div>
                  <!-- 视频计费 -->
                  <div class="pt-3 border-t space-y-2">
                    <div class="text-sm font-medium">
                      视频计费（分辨率 x 时长）
                    </div>
                    <div class="flex items-center gap-1.5 flex-wrap">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        class="h-7 text-xs"
                        disabled
                      >
                        通用
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        class="h-7 text-xs"
                        disabled
                      >
                        Sora
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        class="h-7 text-xs"
                        disabled
                      >
                        Veo
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        class="h-7 text-xs"
                        disabled
                      >
                        <Plus class="w-3.5 h-3.5 mr-0.5" />
                        自定义
                      </Button>
                    </div>
                  </div>
                </section>
              </form>
            </div>
          </div>
          <div class="border-t border-border px-6 py-4 bg-muted/10 flex flex-row-reverse gap-3">
            <Button disabled>
              创建
            </Button>
            <Button variant="outline">
              取消
            </Button>
          </div>
        </div>
        <!-- 右侧: 说明 -->
        <div class="space-y-3">
          <div class="rounded-lg border border-border bg-muted/20 p-4 space-y-2.5">
            <div class="flex items-center gap-2 text-sm font-medium text-foreground">
              <Info class="h-4 w-4 text-primary" />
              说明
            </div>
            <div class="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>统一模型是用户请求时使用的模型名称。左侧列表展示了所有提供商已有的模型，点击可快速填充。</p>
              <p><strong>模型ID</strong> 是用户在 API 请求中使用的标识符，如 <code class="px-1 py-0.5 rounded bg-muted text-foreground">claude-sonnet-4-20250514</code>。</p>
              <p><strong>模型偏好</strong> 用于标记模型的能力特征。</p>
              <p><strong>价格配置</strong> 总费用 = Token 费用 + 按次费用 + 视频费用。Token 费用支持阶梯定价，用于成本统计和配额计算。</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== Step 2: 添加提供商 ==================== -->
      <div
        v-show="activeStep === 1"
        class="grid grid-cols-1 lg:grid-cols-[1fr,280px] gap-4"
      >
        <!-- 左侧: 表单 -->
        <div class="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
          <div class="border-b border-border px-6 py-4">
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                <Server class="h-5 w-5 text-primary" />
              </div>
              <div class="flex-1 min-w-0">
                <h3 class="text-lg font-semibold text-foreground leading-tight">
                  添加提供商
                </h3>
                <p class="text-xs text-muted-foreground">
                  创建新的提供商配置。创建后可以为其添加 API 端点和密钥
                </p>
              </div>
            </div>
          </div>
          <div class="px-6 py-3 space-y-3">
            <div class="space-y-1.5">
              <Label class="text-xs">名称 *</Label>
              <Input
                v-model="step2.name"
                placeholder="例如: OpenAI 主账号"
              />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <Label class="text-xs">提供商类型</Label>
                <Select v-model="step2.provider_type">
                  <SelectTrigger>
                    <SelectValue placeholder="请选择" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="custom">
                      自定义
                    </SelectItem>
                    <SelectItem value="claude_code">
                      Claude Code
                    </SelectItem>
                    <SelectItem value="codex">
                      Codex
                    </SelectItem>
                    <SelectItem value="gemini_cli">
                      Gemini CLI
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div class="space-y-1.5">
                <Label class="text-xs">主站链接</Label>
                <Input
                  v-model="step2.website"
                  placeholder="https://example.com（可选）"
                />
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <Label class="text-xs">计费类型</Label>
                <Select v-model="step2.billing_type">
                  <SelectTrigger>
                    <SelectValue placeholder="选择计费类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pay_as_you_go">
                      按量付费
                    </SelectItem>
                    <SelectItem value="monthly_quota">
                      包月额度
                    </SelectItem>
                    <SelectItem value="free_tier">
                      免费额度
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div class="space-y-1.5">
                <Label class="text-xs">最大重试次数</Label>
                <Input
                  v-model="step2.max_retries"
                  placeholder="默认 2"
                  type="number"
                  min="0"
                  max="10"
                />
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <Label class="text-xs">流式首字节超时 (秒)</Label>
                <Input
                  v-model="step2.stream_first_byte_timeout"
                  placeholder="30"
                  type="number"
                  min="1"
                  max="300"
                />
              </div>
              <div class="space-y-1.5">
                <Label class="text-xs">非流式请求超时 (秒)</Label>
                <Input
                  v-model="step2.request_timeout"
                  placeholder="300"
                  type="number"
                  min="1"
                  max="600"
                />
              </div>
            </div>
            <!-- 格式转换 -->
            <div class="space-y-3 py-2 px-3 rounded-md border border-border/60 bg-muted/30">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <Label class="text-sm font-medium">保持优先级</Label>
                  <p class="text-xs text-muted-foreground">
                    当请求由格式转换后, 跨格式发出请求时, 保持原优先级排名，不降级到格式匹配的提供商之后
                  </p>
                </div>
                <Switch v-model="step2.keep_priority_on_conversion" />
              </div>
            </div>
            <!-- 代理配置 -->
            <div class="space-y-3 py-2 px-3 rounded-md border border-border/60 bg-muted/30">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <Label class="text-sm font-medium">启用代理</Label>
                  <p class="text-xs text-muted-foreground">
                    通过代理节点转发请求到上游 API
                  </p>
                </div>
                <Switch v-model="step2.proxy_enabled" />
              </div>
            </div>
          </div>
          <div class="border-t border-border px-6 py-4 bg-muted/10 flex flex-row-reverse gap-3">
            <Button disabled>
              创建
            </Button>
            <Button variant="outline">
              取消
            </Button>
          </div>
        </div>
        <!-- 右侧: 说明 -->
        <div class="space-y-3">
          <div class="rounded-lg border border-border bg-muted/20 p-4 space-y-2.5">
            <div class="flex items-center gap-2 text-sm font-medium text-foreground">
              <Info class="h-4 w-4 text-primary" />
              说明
            </div>
            <div class="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>提供商是上游 API 服务的逻辑分组。一个提供商可以包含多个端点和密钥。</p>
              <p><strong>提供商类型</strong> 自定义或反代，若不知何为反代请默认选择自定义</p>
              <p><strong>计费类型</strong> 影响配额管理方式：按量付费按实际用量扣费，包月额度按周期重置。</p>
              <p><strong>最大重试次数</strong> 缓存亲和调度模式下，请求失败时的重试次数。</p>
              <p><strong>流式首字节超时</strong> 流式请求收到首字节的超时时间，超时则触发故障转移。</p>
              <p><strong>非流式请求超时</strong> 非流式请求的总请求超时时间，超时则触发故障转移。</p>
              <p><strong>保持优先级</strong> 当请求由格式转换后, 跨格式发出请求时, 保持原优先级排名，不降级到格式匹配的提供商之后。</p>
              <p><strong>启用代理</strong> 通过代理节点转发请求到上游 API，适用于需要网络代理的场景。</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== Step 3: 添加端点 ==================== -->
      <div
        v-show="activeStep === 2"
        class="grid grid-cols-1 lg:grid-cols-[1fr,280px] gap-4"
      >
        <!-- 左侧: 端点管理 -->
        <div class="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
          <div class="border-b border-border px-6 py-4">
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                <Settings class="h-5 w-5 text-primary" />
              </div>
              <div class="flex-1 min-w-0">
                <h3 class="text-lg font-semibold text-foreground leading-tight">
                  端点管理
                </h3>
                <p class="text-xs text-muted-foreground">
                  在供应商详情中，为其配置 API 端点
                </p>
              </div>
            </div>
          </div>

          <div class="p-4 space-y-3">
            <!-- 已配置的端点 标签 -->
            <Label class="text-muted-foreground">已配置的端点</Label>

            <!-- 端点列表 -->
            <div class="space-y-3">
              <div
                v-for="endpoint in step3Endpoints"
                :key="endpoint.id"
                class="rounded-lg border bg-card"
                :class="{ 'opacity-60': !endpoint.enabled }"
              >
                <!-- 端点卡片头部 -->
                <div class="flex items-center justify-between px-4 py-2.5 bg-muted/30 border-b">
                  <div class="flex items-center gap-3">
                    <span class="font-medium">{{ endpoint.label }}</span>
                    <Badge
                      v-if="!endpoint.enabled"
                      variant="secondary"
                      class="text-xs"
                    >
                      已停用
                    </Badge>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <!-- 格式转换 -->
                    <span
                      class="mr-1"
                      :title="endpoint.format_conversion ? '已启用格式转换（点击关闭）' : '启用格式转换'"
                    >
                      <Button
                        variant="ghost"
                        size="icon"
                        :class="`h-7 w-7 ${endpoint.format_conversion ? 'text-primary' : ''}`"
                        @click="endpoint.format_conversion = !endpoint.format_conversion"
                      >
                        <Shuffle class="w-3.5 h-3.5" />
                      </Button>
                    </span>
                    <!-- 上游流式策略 -->
                    <Button
                      variant="ghost"
                      size="icon"
                      :class="getEndpointStreamClass(endpoint)"
                      :title="`上游流式: ${streamPolicyLabels[endpoint.upstream_stream_policy]}`"
                      @click="toggleEndpointStreamPolicy(endpoint)"
                    >
                      <Radio class="w-3.5 h-3.5" />
                    </Button>
                    <!-- 启用/停用 -->
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-7 w-7"
                      :title="endpoint.enabled ? '停用' : '启用'"
                      @click="endpoint.enabled = !endpoint.enabled"
                    >
                      <Power class="w-3.5 h-3.5" />
                    </Button>
                    <!-- 删除 -->
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-7 w-7 hover:text-destructive"
                      title="删除"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
                <!-- 端点内容 -->
                <div class="p-4 space-y-4">
                  <!-- URL 配置 -->
                  <div class="flex items-end gap-3">
                    <div class="flex-1 min-w-0 grid grid-cols-3 gap-3">
                      <div class="col-span-2 space-y-1.5">
                        <Label class="text-xs text-muted-foreground">Base URL</Label>
                        <Input
                          :model-value="endpoint.base_url"
                          placeholder="https://api.example.com"
                        />
                      </div>
                      <div class="space-y-1.5">
                        <Label class="text-xs text-muted-foreground">自定义路径</Label>
                        <Input
                          :model-value="endpoint.custom_path"
                          :placeholder="apiFormatDefaultPaths[endpoint.api_format] || '留空使用默认'"
                        />
                      </div>
                    </div>
                  </div>
                  <!-- 请求规则 -->
                  <Collapsible v-model:open="endpointRulesExpanded[endpoint.id]">
                    <div class="flex items-center gap-2">
                      <CollapsibleTrigger
                        v-if="getTotalRulesCount(endpoint) > 0"
                        as-child
                      >
                        <button
                          type="button"
                          class="flex items-center gap-2 py-1.5 px-2 -mx-2 rounded-md hover:bg-muted/50 transition-colors"
                        >
                          <ChevronRight
                            class="w-4 h-4 transition-transform text-muted-foreground"
                            :class="{ 'rotate-90': endpointRulesExpanded[endpoint.id] }"
                          />
                          <span class="text-sm font-medium">请求规则</span>
                          <Badge
                            variant="secondary"
                            class="text-xs"
                          >
                            {{ getTotalRulesCount(endpoint) }} 条
                          </Badge>
                        </button>
                      </CollapsibleTrigger>
                      <span
                        v-else
                        class="text-sm text-muted-foreground py-1.5"
                      >
                        请求规则
                      </span>
                      <div class="flex-1" />
                      <div class="flex items-center gap-1 shrink-0">
                        <Button
                          variant="ghost"
                          size="sm"
                          class="h-7 text-xs px-2"
                          title="添加请求头规则"
                          @click="addHeaderRule(endpoint.id)"
                        >
                          <Plus class="w-3 h-3 mr-1" />
                          请求头
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          class="h-7 text-xs px-2"
                          title="添加请求体规则"
                          @click="addBodyRule(endpoint.id)"
                        >
                          <Plus class="w-3 h-3 mr-1" />
                          请求体
                        </Button>
                      </div>
                    </div>
                    <CollapsibleContent class="pt-3">
                      <div class="space-y-2">
                        <!-- 请求头规则 -->
                        <div
                          v-for="(rule, index) in endpoint.header_rules"
                          :key="`header-${index}`"
                          class="flex items-center gap-1.5 px-2 py-1.5 rounded-md border-l-4 border-primary/60 bg-muted/30"
                        >
                          <span
                            class="text-[10px] font-semibold text-primary shrink-0"
                            title="请求头"
                          >H</span>
                          <Select v-model="rule.action">
                            <SelectTrigger class="w-[88px] h-7 text-xs shrink-0">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="set">
                                覆写
                              </SelectItem>
                              <SelectItem value="drop">
                                删除
                              </SelectItem>
                              <SelectItem value="rename">
                                重命名
                              </SelectItem>
                            </SelectContent>
                          </Select>
                          <template v-if="rule.action === 'set'">
                            <Input
                              v-model="rule.key"
                              placeholder="名称"
                              class="flex-1 min-w-0 h-7 text-xs"
                            />
                            <span class="text-muted-foreground text-xs">=</span>
                            <Input
                              v-model="rule.value"
                              placeholder="值"
                              class="flex-1 min-w-0 h-7 text-xs"
                            />
                          </template>
                          <template v-else-if="rule.action === 'drop'">
                            <Input
                              v-model="rule.key"
                              placeholder="要删除的名称"
                              class="flex-1 min-w-0 h-7 text-xs"
                            />
                          </template>
                          <template v-else-if="rule.action === 'rename'">
                            <Input
                              v-model="rule.from"
                              placeholder="原名"
                              class="flex-1 min-w-0 h-7 text-xs"
                            />
                            <span class="text-muted-foreground text-xs">→</span>
                            <Input
                              v-model="rule.to"
                              placeholder="新名"
                              class="flex-1 min-w-0 h-7 text-xs"
                            />
                          </template>
                          <Button
                            variant="ghost"
                            size="icon"
                            class="h-7 w-7 shrink-0"
                            @click="removeHeaderRule(endpoint.id, index)"
                          >
                            <Trash2 class="w-3 h-3" />
                          </Button>
                        </div>
                        <!-- 请求体规则 -->
                        <template
                          v-for="(rule, index) in endpoint.body_rules"
                          :key="`body-${index}`"
                        >
                          <div
                            class="flex items-center gap-1.5 px-2 py-1.5 rounded-md border-l-4 border-muted-foreground/40 bg-muted/30"
                          >
                            <span
                              class="text-[10px] font-semibold text-muted-foreground shrink-0"
                              title="请求体"
                            >B</span>
                            <Select v-model="rule.action">
                              <SelectTrigger class="w-[96px] h-7 text-xs shrink-0">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="set">
                                  覆写
                                </SelectItem>
                                <SelectItem value="drop">
                                  删除
                                </SelectItem>
                                <SelectItem value="rename">
                                  重命名
                                </SelectItem>
                                <SelectItem value="insert">
                                  插入
                                </SelectItem>
                                <SelectItem value="regex_replace">
                                  正则替换
                                </SelectItem>
                              </SelectContent>
                            </Select>
                            <Button
                              variant="ghost"
                              size="icon"
                              class="h-7 w-7 shrink-0"
                              :class="rule.conditionEnabled ? 'text-primary' : ''"
                              title="条件触发"
                              @click="rule.conditionEnabled = !rule.conditionEnabled"
                            >
                              <Filter class="w-3 h-3" />
                            </Button>
                            <template v-if="rule.action === 'set'">
                              <Input
                                v-model="rule.path"
                                placeholder="字段路径"
                                class="flex-1 min-w-0 h-7 text-xs"
                              />
                              <span class="text-muted-foreground text-xs">=</span>
                              <Input
                                v-model="rule.value"
                                placeholder="值"
                                class="flex-1 min-w-0 h-7 text-xs"
                              />
                            </template>
                            <template v-else-if="rule.action === 'drop'">
                              <Input
                                v-model="rule.path"
                                placeholder="要删除的字段路径"
                                class="flex-1 min-w-0 h-7 text-xs"
                              />
                            </template>
                            <template v-else-if="rule.action === 'rename'">
                              <Input
                                v-model="rule.from"
                                placeholder="原路径"
                                class="flex-1 min-w-0 h-7 text-xs"
                              />
                              <span class="text-muted-foreground text-xs">→</span>
                              <Input
                                v-model="rule.to"
                                placeholder="新路径"
                                class="flex-1 min-w-0 h-7 text-xs"
                              />
                            </template>
                            <template v-else>
                              <Input
                                v-model="rule.path"
                                placeholder="字段路径"
                                class="flex-1 min-w-0 h-7 text-xs"
                              />
                              <Input
                                v-model="rule.value"
                                placeholder="值"
                                class="flex-1 min-w-0 h-7 text-xs"
                              />
                            </template>
                            <Button
                              variant="ghost"
                              size="icon"
                              class="h-7 w-7 shrink-0"
                              @click="removeBodyRule(endpoint.id, index)"
                            >
                              <Trash2 class="w-3 h-3" />
                            </Button>
                          </div>
                          <!-- 条件编辑行 -->
                          <div
                            v-if="rule.conditionEnabled"
                            class="flex items-center gap-1.5 px-2 py-1 ml-6 rounded-md bg-muted/20"
                          >
                            <span class="text-[10px] font-semibold text-muted-foreground shrink-0">IF</span>
                            <Input
                              v-model="rule.conditionPath"
                              placeholder="字段路径"
                              class="flex-1 min-w-0 h-7 text-xs"
                            />
                            <Select v-model="rule.conditionOp">
                              <SelectTrigger class="w-[100px] h-7 text-xs shrink-0">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="eq">
                                  等于
                                </SelectItem>
                                <SelectItem value="neq">
                                  不等于
                                </SelectItem>
                                <SelectItem value="gt">
                                  大于
                                </SelectItem>
                                <SelectItem value="lt">
                                  小于
                                </SelectItem>
                                <SelectItem value="contains">
                                  包含
                                </SelectItem>
                                <SelectItem value="matches">
                                  正则匹配
                                </SelectItem>
                                <SelectItem value="exists">
                                  存在
                                </SelectItem>
                                <SelectItem value="not_exists">
                                  不存在
                                </SelectItem>
                              </SelectContent>
                            </Select>
                            <Input
                              v-if="rule.conditionOp !== 'exists' && rule.conditionOp !== 'not_exists'"
                              v-model="rule.conditionValue"
                              placeholder="值"
                              class="flex-1 min-w-0 h-7 text-xs"
                            />
                          </div>
                        </template>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                </div>
              </div>
            </div>

            <!-- 新增端点区域 -->
            <div
              v-if="step3AvailableFormats.length > 0"
              class="rounded-lg border border-dashed p-3"
            >
              <div class="flex items-center justify-between px-4 py-2.5 bg-muted/30 border-b border-dashed">
                <Select v-model="step3New.api_format">
                  <SelectTrigger class="h-auto w-auto gap-1.5 !border-0 bg-transparent !shadow-none p-0 font-medium rounded-none flex-row-reverse !ring-0 !ring-offset-0 !outline-none [&>svg]:h-4 [&>svg]:w-4 [&>svg]:opacity-70">
                    <SelectValue placeholder="选择格式..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem
                      v-for="fmt in step3AvailableFormats"
                      :key="fmt.value"
                      :value="fmt.value"
                    >
                      {{ fmt.label }}
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 px-3"
                  disabled
                >
                  添加
                </Button>
              </div>
              <div class="p-4">
                <div class="flex items-end gap-3">
                  <div class="flex-1 min-w-0 grid grid-cols-3 gap-3">
                    <div class="col-span-2 space-y-1.5">
                      <Label class="text-xs text-muted-foreground">Base URL</Label>
                      <Input
                        v-model="step3New.base_url"
                        placeholder="https://api.example.com"
                      />
                    </div>
                    <div class="space-y-1.5">
                      <Label class="text-xs text-muted-foreground">自定义路径</Label>
                      <Input
                        v-model="step3New.custom_path"
                        :placeholder="apiFormatDefaultPaths[step3New.api_format] || '留空使用默认'"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 底部关闭按钮 -->
          <div class="border-t border-border px-6 py-4 bg-muted/10 flex flex-row-reverse">
            <Button variant="outline">
              关闭
            </Button>
          </div>
        </div>
        <!-- 右侧: 说明 -->
        <div class="space-y-3">
          <div class="rounded-lg border border-border bg-muted/20 p-4 space-y-2.5">
            <div class="flex items-center gap-2 text-sm font-medium text-foreground">
              <Info class="h-4 w-4 text-primary" />
              说明
            </div>
            <div class="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>端点是实际调用上游 API 的配置单元。端点是看上游支持什么, 而不是你需要调用什么。</p>
              <p><strong>API 格式</strong> 决定了请求和响应的协议格式。添加上游支持的端点。</p>
              <p><strong>请求规则</strong> 可在转发请求时添加、修改或删除 HTTP 请求头和请求体字段。更多请前往高级功能了解。</p>
              <p class="pl-2 border-l-2 border-primary/40">
                <strong class="text-primary">H</strong> 请求头规则：覆写（设置/替换）、删除、重命名。
              </p>
              <p class="pl-2 border-l-2 border-muted-foreground/30">
                <strong>B</strong> 请求体规则：覆写、删除、重命名、插入、正则替换。
              </p>
              <p class="pl-2 border-l-2 border-muted-foreground/30">
                <strong><Filter class="inline h-3 w-3" /> 条件触发</strong> 请求体规则支持条件触发，仅在匹配指定条件时才执行该规则。
              </p>
              <p><strong><Shuffle class="inline h-3 w-3" /> 格式转换</strong> 启用后允许跨格式调用，如用 OpenAI Chat 请求 Claude Chat 端点。</p>
              <p><strong><Radio class="inline h-3 w-3" /> 上游流式策略</strong> 控制转发到上游的流式行为：自动（跟随客户端）、强制流式、强制非流式。</p>
              <p><strong><Power class="inline h-3 w-3" /> 启用/停用</strong> 停用后该端点不参与请求调度。</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== Step 4: 添加密钥 ==================== -->
      <div
        v-show="activeStep === 3"
        class="grid grid-cols-1 lg:grid-cols-[1fr,280px] gap-4"
      >
        <!-- 左侧: 表单 -->
        <div class="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
          <div class="border-b border-border px-6 py-4">
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                <Key class="h-5 w-5 text-primary" />
              </div>
              <div class="flex-1 min-w-0">
                <h3 class="text-lg font-semibold text-foreground leading-tight">
                  添加密钥
                </h3>
                <p class="text-xs text-muted-foreground">
                  为提供商添加新的 API 密钥
                </p>
              </div>
            </div>
          </div>
          <form
            class="px-6 py-3 space-y-3"
            @submit.prevent
          >
            <div class="grid grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <Label class="text-xs">密钥名称 *</Label>
                <Input
                  v-model="step4.name"
                  placeholder="例如：主 Key、备用 Key 1"
                  maxlength="100"
                />
              </div>
              <div class="space-y-1.5">
                <Label class="text-xs">认证类型</Label>
                <Select v-model="step4.auth_type">
                  <SelectTrigger>
                    <SelectValue placeholder="选择认证类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="api_key">
                      API Key
                    </SelectItem>
                    <SelectItem value="vertex_ai">
                      Vertex AI
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div class="space-y-1.5">
              <Label class="text-xs">
                {{ step4.auth_type === 'vertex_ai' ? 'Service Account JSON' : 'API 密钥' }} *
              </Label>
              <Textarea
                v-if="step4.auth_type === 'vertex_ai'"
                v-model="step4.api_key"
                placeholder="粘贴完整的 Service Account JSON"
                class="min-h-[120px] font-mono text-xs"
              />
              <Input
                v-else
                v-model="step4.api_key"
                placeholder="sk-..."
              />
            </div>
            <div class="space-y-1.5">
              <Label class="text-xs">备注</Label>
              <Input
                v-model="step4.note"
                placeholder="可选的备注信息"
              />
            </div>
            <div>
              <Label class="mb-1.5 block text-xs">支持的 API 格式 *</Label>
              <div class="grid grid-cols-2 gap-2">
                <div
                  v-for="fmt in keyApiFormats"
                  :key="fmt.value"
                  class="flex items-center justify-between rounded-md border px-2 py-1.5 transition-colors cursor-pointer"
                  :class="step4.api_formats.includes(fmt.value)
                    ? 'bg-primary/5 border-primary/30'
                    : 'bg-muted/30 border-border hover:border-muted-foreground/30'"
                  @click="toggleKeyApiFormat(fmt.value)"
                >
                  <div class="flex items-center gap-1.5 min-w-0">
                    <span
                      class="w-4 h-4 rounded border flex items-center justify-center text-xs shrink-0"
                      :class="step4.api_formats.includes(fmt.value)
                        ? 'bg-primary border-primary text-primary-foreground'
                        : 'border-muted-foreground/30'"
                    >
                      <span v-if="step4.api_formats.includes(fmt.value)">&#10003;</span>
                    </span>
                    <span
                      class="text-sm whitespace-nowrap"
                      :class="step4.api_formats.includes(fmt.value) ? 'text-primary' : 'text-muted-foreground'"
                    >{{ fmt.label }}</span>
                  </div>
                  <div
                    class="flex items-center shrink-0 ml-2 text-xs text-muted-foreground gap-1"
                    @click.stop
                  >
                    <span>&times;</span>
                    <input
                      :value="step4.rate_multipliers[fmt.value] ?? ''"
                      type="number"
                      step="0.01"
                      min="0.01"
                      placeholder="1"
                      class="w-9 bg-transparent text-right outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                      :class="step4.api_formats.includes(fmt.value) ? 'text-primary' : 'text-muted-foreground'"
                      title="成本倍率"
                      @input="(e: Event) => { const v = parseFloat((e.target as HTMLInputElement).value); if (!isNaN(v) && v >= 0.01 && v <= 100) step4.rate_multipliers[fmt.value] = v; else if ((e.target as HTMLInputElement).value === '') delete step4.rate_multipliers[fmt.value] }"
                    >
                  </div>
                </div>
              </div>
            </div>
            <div class="grid grid-cols-4 gap-3">
              <div class="space-y-1.5">
                <Label class="text-xs">优先级</Label>
                <Input
                  v-model.number="step4.internal_priority"
                  type="number"
                  min="0"
                  class="h-8"
                />
                <p class="text-xs text-muted-foreground mt-0.5">
                  越小越优先
                </p>
              </div>
              <div class="space-y-1.5">
                <Label class="text-xs">RPM 限制</Label>
                <Input
                  v-model="step4.rpm_limit"
                  placeholder="自适应"
                  type="number"
                  min="1"
                  max="10000"
                  class="h-8"
                />
                <p class="text-xs text-muted-foreground mt-0.5">
                  留空自适应
                </p>
              </div>
              <div class="space-y-1.5">
                <Label class="text-xs">缓存 TTL</Label>
                <Input
                  v-model="step4.cache_ttl_minutes"
                  type="number"
                  min="0"
                  max="60"
                  class="h-8"
                />
                <p class="text-xs text-muted-foreground mt-0.5">
                  分钟，0禁用
                </p>
              </div>
              <div class="space-y-1.5">
                <Label class="text-xs">熔断探测</Label>
                <Input
                  v-model="step4.max_probe_interval_minutes"
                  placeholder="32"
                  type="number"
                  min="2"
                  max="32"
                  class="h-8"
                />
                <p class="text-xs text-muted-foreground mt-0.5">
                  分钟，2-32
                </p>
              </div>
            </div>
            <!-- 自动获取模型 -->
            <div class="space-y-3 py-2 px-3 rounded-md border border-border/60 bg-muted/30">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <Label class="text-sm font-medium">自动获取上游可用模型</Label>
                  <p class="text-xs text-muted-foreground">
                    定时更新上游模型, 配合关联模型使用
                  </p>
                </div>
                <Switch v-model="step4.auto_fetch_models" />
              </div>
            </div>
          </form>
          <div class="border-t border-border px-6 py-4 bg-muted/10 flex flex-row-reverse gap-3">
            <Button disabled>
              添加
            </Button>
            <Button variant="outline">
              取消
            </Button>
          </div>
        </div>
        <!-- 右侧: 说明 -->
        <div class="space-y-3">
          <div class="rounded-lg border border-border bg-muted/20 p-4 space-y-2.5">
            <div class="flex items-center gap-2 text-sm font-medium text-foreground">
              <Info class="h-4 w-4 text-primary" />
              说明
            </div>
            <div class="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>密钥是端点的鉴权凭据，每个端点可以有多个密钥用于负载均衡。</p>
              <p><strong>API 格式</strong> 标记该密钥支持的格式，系统据此选择合适的密钥进行请求。</p>
              <p><strong>优先级</strong> 数值越小越优先。当多个密钥可用时，优先使用高优先级的。</p>
              <p><strong>RPM 限制</strong> 留空则自动根据上游返回的 429 错误动态调整。</p>
              <p><strong>缓存 TTL</strong> 控制 Prompt Caching 的亲和性时间，设为 0 禁用。</p>
              <p><strong>自动获取模型</strong> 开启后会定期从上游获取可用模型列表，自动更新密钥的模型白名单。</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== Step 5: 关联模型 ==================== -->
      <div
        v-show="activeStep === 4"
        class="grid grid-cols-1 lg:grid-cols-[1fr,280px] gap-4"
      >
        <!-- 左侧: 批量管理模型 -->
        <div class="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
          <!-- Header -->
          <div class="border-b border-border px-6 py-4">
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                <Layers class="h-5 w-5 text-primary" />
              </div>
              <div class="flex-1 min-w-0">
                <h3 class="text-base font-semibold leading-tight">
                  批量管理模型 - NekoCode
                </h3>
                <p class="text-sm text-muted-foreground mt-0.5">
                  选中的模型将被关联到提供商，取消选中将移除关联
                </p>
              </div>
            </div>
          </div>

          <div class="p-4 space-y-4">
            <!-- 搜索栏 -->
            <div class="flex items-center gap-2">
              <div class="flex-1 relative">
                <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  v-model="step5.searchQuery"
                  placeholder="搜索模型..."
                  class="pl-8 h-9"
                />
              </div>
              <button
                class="p-2 hover:bg-muted rounded-md transition-colors shrink-0"
                title="从提供商获取模型"
              >
                <Zap class="w-4 h-4" />
              </button>
            </div>

            <!-- 全局模型分组 -->
            <div class="border rounded-lg overflow-hidden">
              <div class="max-h-96 overflow-y-auto">
                <div>
                  <div
                    class="flex items-center justify-between px-3 py-2 bg-muted sticky top-0 z-10 cursor-pointer hover:bg-muted/80 transition-colors"
                    @click="step5.globalExpanded = !step5.globalExpanded"
                  >
                    <div class="flex items-center gap-2">
                      <ChevronDown
                        class="w-4 h-4 transition-transform shrink-0"
                        :class="{ '-rotate-90': !step5.globalExpanded }"
                      />
                      <span class="text-xs font-medium">全局模型</span>
                      <span class="text-xs text-muted-foreground">({{ step5FilteredModels.length }})</span>
                    </div>
                    <button
                      type="button"
                      class="text-xs text-primary hover:underline shrink-0"
                      @click.stop="toggleStep5All"
                    >
                      {{ step5FilteredModels.every(m => step5SelectedModels.includes(m.id)) ? '取消全选' : '全选' }}
                    </button>
                  </div>
                  <div
                    v-show="step5.globalExpanded"
                    class="space-y-1 p-2"
                  >
                    <div
                      v-for="model in step5FilteredModels"
                      :key="model.id"
                      class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer"
                      @click="toggleStep5Model(model.id)"
                    >
                      <div
                        class="w-4 h-4 border rounded flex items-center justify-center shrink-0"
                        :class="step5SelectedModels.includes(model.id) ? 'bg-primary border-primary' : ''"
                      >
                        <Check
                          v-if="step5SelectedModels.includes(model.id)"
                          class="w-3 h-3 text-primary-foreground"
                        />
                      </div>
                      <div class="flex-1 min-w-0">
                        <p class="text-sm font-medium truncate">
                          {{ model.name }}
                        </p>
                        <p class="text-xs text-muted-foreground truncate font-mono">
                          {{ model.id }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="border-t border-border px-4 py-3 flex items-center justify-between">
            <p class="text-xs text-muted-foreground">
              3 项更改待保存
            </p>
            <div class="flex items-center gap-2">
              <Button disabled>
                保存
              </Button>
              <Button
                variant="outline"
                disabled
              >
                关闭
              </Button>
            </div>
          </div>
        </div>

        <!-- 右侧: 说明 -->
        <div class="space-y-3">
          <div class="rounded-lg border border-border bg-muted/20 p-4 space-y-2.5">
            <div class="flex items-center gap-2 text-sm font-medium text-foreground">
              <Info class="h-4 w-4 text-primary" />
              说明
            </div>
            <div class="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>在提供商详情中点击「批量管理模型」，将全局模型关联到该提供商。</p>
              <p><strong>关联</strong>：勾选模型即可将其关联到当前提供商，系统会自动创建同名的提供商模型。</p>
              <p><strong>取消关联</strong>：取消勾选将移除该模型与提供商的关联。</p>
              <p><strong>多提供商</strong>：同一个全局模型可以关联到多个提供商，系统在请求时自动进行负载均衡和故障转移。</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== Step 6: 模型权限 ==================== -->
      <div
        v-show="activeStep === 5"
        class="grid grid-cols-1 lg:grid-cols-[1fr,280px] gap-4"
      >
        <!-- 左侧: KeyAllowedModelsEditDialog -->
        <div class="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
          <div class="border-b border-border px-6 py-4">
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                <Shield class="h-5 w-5 text-primary" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <h3 class="text-lg font-semibold text-foreground leading-tight">
                    模型权限
                  </h3>
                  <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-[#e5e4df] dark:bg-[rgba(227,224,211,0.12)] text-[#666663] dark:text-[#a3a094]">可选</span>
                </div>
                <p class="text-xs text-muted-foreground">
                  管理密钥可以访问的模型列表，不设置则允许所有模型
                </p>
              </div>
              <Badge
                variant="secondary"
                class="text-xs"
              >
                已选 {{ step6.selectedModels.length }} 个
              </Badge>
            </div>
          </div>
          <!-- 搜索栏 -->
          <div class="px-4 py-2 border-b border-border/60">
            <div class="relative">
              <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                v-model="step6.searchQuery"
                placeholder="搜索模型..."
                class="pl-8 h-8"
              />
            </div>
          </div>
          <!-- 模型列表 -->
          <div class="max-h-[360px] overflow-y-auto">
            <!-- 全局模型 -->
            <div class="px-3 py-1.5 bg-muted/30 border-b border-border/40 flex items-center justify-between">
              <span class="text-xs font-medium text-muted-foreground">全局模型</span>
              <button
                class="text-xs text-primary hover:underline"
                type="button"
                @click="step6AllModels.filter(m => m.group === 'global').forEach(m => { if (!step6.selectedModels.includes(m.id)) step6.selectedModels.push(m.id) })"
              >
                全选
              </button>
            </div>
            <div class="divide-y divide-border/30">
              <div
                v-for="model in step6AllModels.filter(m => m.group === 'global' && (m.id.includes(step6.searchQuery) || m.name.includes(step6.searchQuery)))"
                :key="model.id"
                class="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/20 transition-colors cursor-pointer"
                @click="toggleModel(model.id)"
              >
                <span
                  class="w-4 h-4 rounded border flex items-center justify-center text-xs shrink-0"
                  :class="step6.selectedModels.includes(model.id)
                    ? 'bg-primary border-primary text-primary-foreground'
                    : 'border-muted-foreground/30'"
                >
                  <span v-if="step6.selectedModels.includes(model.id)">&#10003;</span>
                </span>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium truncate">
                    {{ model.id }}
                  </div>
                  <div class="text-xs text-muted-foreground">
                    {{ model.name }}
                  </div>
                </div>
                <button
                  type="button"
                  class="p-1 rounded hover:bg-muted/50 transition-colors"
                  :class="step6.lockedModels.includes(model.id) ? 'text-primary' : 'text-muted-foreground/30'"
                  title="锁定模型（自动刷新时不删除）"
                  @click.stop="toggleModelLock(model.id)"
                >
                  <Lock class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            <!-- 上游模型 -->
            <div class="px-3 py-1.5 bg-muted/30 border-y border-border/40 flex items-center justify-between">
              <span class="text-xs font-medium text-muted-foreground">上游模型</span>
              <button
                class="text-xs text-primary hover:underline"
                type="button"
                @click="step6AllModels.filter(m => m.group === 'upstream').forEach(m => { if (!step6.selectedModels.includes(m.id)) step6.selectedModels.push(m.id) })"
              >
                全选
              </button>
            </div>
            <div class="divide-y divide-border/30">
              <div
                v-for="model in step6AllModels.filter(m => m.group === 'upstream' && (m.id.includes(step6.searchQuery) || m.name.includes(step6.searchQuery)))"
                :key="model.id"
                class="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/20 transition-colors cursor-pointer"
                @click="toggleModel(model.id)"
              >
                <span
                  class="w-4 h-4 rounded border flex items-center justify-center text-xs shrink-0"
                  :class="step6.selectedModels.includes(model.id)
                    ? 'bg-primary border-primary text-primary-foreground'
                    : 'border-muted-foreground/30'"
                >
                  <span v-if="step6.selectedModels.includes(model.id)">&#10003;</span>
                </span>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium truncate">
                    {{ model.id }}
                  </div>
                  <div class="text-xs text-muted-foreground">
                    {{ model.name }}
                  </div>
                </div>
                <button
                  type="button"
                  class="p-1 rounded hover:bg-muted/50 transition-colors"
                  :class="step6.lockedModels.includes(model.id) ? 'text-primary' : 'text-muted-foreground/30'"
                  title="锁定模型（自动刷新时不删除）"
                  @click.stop="toggleModelLock(model.id)"
                >
                  <Lock class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
          <div class="border-t border-border px-6 py-4 bg-muted/10 flex flex-row-reverse gap-3">
            <Button disabled>
              保存
            </Button>
            <Button variant="outline">
              取消
            </Button>
          </div>
        </div>
        <!-- 右侧: 说明 -->
        <div class="space-y-3">
          <div class="rounded-lg border border-border bg-muted/20 p-4 space-y-2.5">
            <div class="flex items-center gap-2 text-sm font-medium text-foreground">
              <Info class="h-4 w-4 text-primary" />
              说明
            </div>
            <div class="text-xs text-muted-foreground space-y-2 leading-relaxed">
              <p>模型权限控制该密钥可以访问哪些上游模型。不设置则允许访问所有模型。</p>
              <p><strong>全局模型</strong>：系统中注册的标准模型，与全局模型管理中的配置对应。</p>
              <p><strong>上游模型</strong>：通过自动获取从上游 API 发现的模型。</p>
              <p><strong>锁定</strong>：锁定的模型在自动刷新时不会被删除，适用于手动添加但上游未列出的模型。</p>
              <p>此功能位于提供商详情 > 密钥管理 > 编辑模型权限。</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 支持的 API 格式 -->
    <section
      id="api-formats"
      class="space-y-3"
    >
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        支持的 API 格式
      </h2>
      <p class="text-sm text-[#666663] dark:text-[#a3a094]">
        {{ siteName }} 原生支持以下 API 格式，可以作为不同客户端的统一入口：
      </p>

      <!-- 可视化概览 -->
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
              认证 / 路由 / 格式转换
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
      </div>

      <div
        class="overflow-hidden"
        :class="[panelClasses.section]"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50">
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  格式
                </th>
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  端点
                </th>
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  认证方式
                </th>
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">
                  常用客户端
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="format in apiFormats"
                :key="format.name"
                class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] last:border-0"
              >
                <td class="px-4 py-3 font-medium text-[#262624] dark:text-[#f1ead8] whitespace-nowrap">
                  {{ format.name }}
                </td>
                <td class="px-4 py-3 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  {{ format.endpoint }}
                </td>
                <td class="px-4 py-3 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  {{ format.auth }}
                </td>
                <td class="px-4 py-3 text-[#666663] dark:text-[#a3a094]">
                  {{ format.clients.join(', ') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 推荐帖子 -->
    <section
      id="recommended-posts"
      class="space-y-3"
    >
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        推荐帖子
      </h2>
      <div class="grid gap-3 sm:grid-cols-3">
        <a
          v-for="(post, idx) in recommendedPosts"
          :key="idx"
          :href="post.url"
          target="_blank"
          rel="noopener noreferrer"
          class="p-4 flex items-center gap-3 group transition-all duration-200 hover:-translate-y-0.5"
          :class="[panelClasses.section, panelClasses.cardHover]"
        >
          <span
            class="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 bg-[#cc785c]/10 dark:bg-[#cc785c]/20 text-[#cc785c] dark:text-[#d4a27f]"
          >
            {{ idx + 1 }}
          </span>
          <div class="flex-1 min-w-0">
            <div class="font-medium text-[#262624] dark:text-[#f1ead8] truncate">
              {{ post.title }}
            </div>
            <div class="text-xs text-[#666663] dark:text-[#a3a094]">
              LINUX DO
            </div>
          </div>
          <ExternalLink class="h-4 w-4 text-[#999] group-hover:text-[#cc785c] transition-colors flex-shrink-0" />
        </a>
      </div>
    </section>
  </div>
</template>
