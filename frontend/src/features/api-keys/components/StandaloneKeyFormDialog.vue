<template>
  <Dialog
    :model-value="isOpen"
    size="2xl"
    @update:model-value="handleDialogUpdate"
  >
    <template #header>
      <div class="border-b border-border px-6 py-4">
        <div class="flex items-center gap-3">
          <div
            class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0"
          >
            <Plus
              v-if="!isEditMode"
              class="h-5 w-5 text-primary"
            />
            <SquarePen
              v-else
              class="h-5 w-5 text-primary"
            />
          </div>
          <div class="flex-1 min-w-0">
            <h3 class="text-lg font-semibold text-foreground leading-tight">
              {{ isEditMode ? '编辑独立余额 API Key' : '创建独立余额 API Key' }}
            </h3>
            <p class="text-xs text-muted-foreground">
              {{ isEditMode ? '修改密钥名称、有效期和访问限制' : '用于非注册用户调用接口，可设置初始余额或无限制额度' }}
            </p>
          </div>
        </div>
      </div>
    </template>

    <form @submit.prevent="handleSubmit">
      <div class="space-y-5">
        <section class="space-y-4">
          <div class="flex items-center gap-2 border-b border-border/60 pb-2">
            <span class="text-sm font-medium">基础设置</span>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <div class="space-y-2 md:col-span-2">
              <Label
                for="form-name"
                class="text-sm font-medium"
              >密钥名称</Label>
              <Input
                id="form-name"
                v-model="form.name"
                type="text"
                placeholder="例如: 用户A专用"
                class="h-10"
              />
            </div>

            <div class="space-y-2">
              <Label class="text-sm font-medium">额度</Label>
              <div class="flex items-center gap-3">
                <div class="min-w-0 flex-1">
                  <Input
                    v-if="!isEditMode && !form.unlimited_balance"
                    id="form-balance"
                    :model-value="form.initial_balance_usd ?? ''"
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="初始额度 (USD)"
                    class="h-10"
                    @update:model-value="(v) => form.initial_balance_usd = parseNumberInput(v, { allowFloat: true, min: 0.01 })"
                  />
                  <span
                    v-else
                    class="flex h-10 w-full items-center rounded-lg border bg-background px-3 text-sm text-muted-foreground opacity-60"
                  >{{ balanceDisplayText }}</span>
                </div>
                <Switch
                  :model-value="form.unlimited_balance ?? false"
                  class="shrink-0"
                  @update:model-value="(v) => form.unlimited_balance = v"
                />
              </div>
              <p
                v-if="isEditMode"
                class="text-xs text-muted-foreground"
              >
                {{ form.unlimited_balance ? '该 Key 当前使用独立无限额度。' : '该 Key 当前按独立钱包余额限制；增减金额请在列表页使用“资金”操作。' }}
              </p>
            </div>

            <div class="space-y-2">
              <Label
                for="form-expires-at"
                class="text-sm font-medium"
              >有效期</Label>
              <div class="flex items-center gap-2">
                <div class="relative min-w-0 flex-1">
                  <Input
                    id="form-expires-at"
                    :model-value="form.expires_at || ''"
                    type="date"
                    :min="minExpiryDate"
                    class="h-10 pr-8"
                    :placeholder="form.expires_at ? '' : '永不过期'"
                    @update:model-value="(v) => form.expires_at = v || undefined"
                  />
                  <button
                    v-if="form.expires_at"
                    type="button"
                    class="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    title="清空（永不过期）"
                    @click="clearExpiryDate"
                  >
                    <X class="h-4 w-4" />
                  </button>
                </div>
                <label
                  class="flex h-10 items-center gap-1.5 whitespace-nowrap rounded-md border bg-muted/50 px-2 text-xs cursor-pointer"
                  :class="!form.expires_at ? 'opacity-50 cursor-not-allowed' : ''"
                >
                  <input
                    v-model="form.auto_delete_on_expiry"
                    type="checkbox"
                    class="h-3.5 w-3.5 rounded border-gray-300 cursor-pointer"
                    :disabled="!form.expires_at"
                  >
                  到期删除
                </label>
              </div>
              <p class="text-xs text-muted-foreground">
                {{ form.expires_at ? '到期后' + (form.auto_delete_on_expiry ? '自动删除' : '仅禁用') + '（当天 23:59 失效）' : '留空表示永不过期' }}
              </p>
            </div>
          </div>
        </section>

        <section class="space-y-3">
          <div class="flex items-center gap-2 border-b border-border/60 pb-2">
            <span class="text-sm font-medium">调度策略</span>
          </div>

          <div class="space-y-2">
            <Label class="text-sm font-medium">专用调度策略</Label>
            <Select
              v-model="routingGroupSelectValue"
              :disabled="routingLoading || !routingStateReady"
            >
              <SelectTrigger
                class="h-10 w-full"
                data-testid="routing-group-select"
              >
                <SelectValue placeholder="选择调度策略" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem :value="FOLLOW_SYSTEM_ROUTING_GROUP_VALUE">
                  跟随系统默认（不单独绑定）
                </SelectItem>
                <SelectItem
                  v-if="unavailableCurrentRoutingGroup"
                  :value="unavailableCurrentRoutingGroup.groupId"
                  disabled
                >
                  {{ unavailableCurrentRoutingGroup.label }}
                </SelectItem>
                <SelectItem
                  v-for="group in enabledRoutingGroups"
                  :key="group.id"
                  :value="group.id"
                >
                  {{ group.name }}
                </SelectItem>
              </SelectContent>
            </Select>

            <p
              v-if="routingLoading"
              class="text-xs text-muted-foreground"
              data-testid="routing-binding-loading"
            >
              正在加载调度策略与当前绑定…若现在保存，本次不会修改绑定。
            </p>
            <div
              v-else-if="routingLoadError"
              class="flex items-start justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
              data-testid="routing-binding-load-error"
            >
              <span>{{ routingLoadError }}。API Key 仍可保存，但本次不会修改调度策略绑定。</span>
              <button
                type="button"
                class="shrink-0 font-medium underline underline-offset-2"
                @click="emit('retry-routing-load')"
              >
                重试
              </button>
            </div>
            <p
              v-else-if="unavailableCurrentRoutingGroup"
              class="rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300"
              data-testid="routing-binding-unavailable"
            >
              {{ unavailableCurrentRoutingGroup.label }}。可选择可用策略替换，或改为跟随系统默认以移除此绑定。
            </p>
            <p
              v-else
              class="text-xs text-muted-foreground"
            >
              仅设置该 API Key 的默认调度策略；跟随系统默认时不创建专用绑定。
            </p>

            <p
              v-if="routingSaveError"
              class="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
              data-testid="routing-binding-save-error"
            >
              {{ routingSaveError }}
            </p>
          </div>
        </section>

        <section>
          <div class="rounded-lg border border-border bg-muted/30 px-4 py-3">
            <div class="flex items-center justify-between gap-3">
              <Label class="text-sm font-medium">敏感信息保护</Label>
              <Switch v-model="form.chat_pii_redaction_enabled" />
            </div>
            <div
              v-if="form.chat_pii_redaction_enabled"
              class="mt-3 flex items-center justify-between gap-3 border-t border-border/60 pt-3"
            >
              <Label class="text-sm font-medium">占位符说明</Label>
              <Switch v-model="form.chat_pii_redaction_placeholder_notice" />
            </div>
          </div>
        </section>

        <Collapsible
          v-model:open="accessRestrictionsExpanded"
          class="rounded-lg border border-border"
        >
          <CollapsibleTrigger as-child>
            <button
              type="button"
              class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50"
            >
              <span class="text-sm font-medium">访问限制</span>
              <span class="flex items-center gap-1.5 text-xs text-muted-foreground">
                {{ accessRestrictionsExpanded ? '收起' : '展开' }}
                <ChevronDown
                  class="h-4 w-4 transition-transform"
                  :class="accessRestrictionsExpanded ? 'rotate-180' : ''"
                />
              </span>
            </button>
          </CollapsibleTrigger>

          <CollapsibleContent>
            <div class="grid gap-y-4 border-t border-border px-4 py-4">
              <!-- 提供商 -->
              <div class="space-y-2">
                <Label class="text-sm font-medium">允许的提供商</Label>
                <div class="flex items-center gap-3">
                  <div class="flex-1 min-w-0">
                    <MultiSelect
                      v-model="form.allowed_providers"
                      :options="providerOptions"
                      :search-threshold="0"
                      teleport
                      :disabled="form.provider_unrestricted"
                      :placeholder="form.provider_unrestricted ? '不限制' : '未选择（全部禁用）'"
                      empty-text="暂无可用提供商"
                      no-results-text="未找到匹配的提供商"
                      search-placeholder="搜索提供商名称..."
                    />
                  </div>
                  <Switch
                    v-model="form.provider_unrestricted"
                    class="shrink-0"
                  />
                </div>
              </div>

              <!-- 端点 -->
              <div class="space-y-2">
                <Label class="text-sm font-medium">允许的端点</Label>
                <div class="flex items-center gap-3">
                  <div class="flex-1 min-w-0">
                    <MultiSelect
                      v-model="form.allowed_api_formats"
                      :options="apiFormatOptions"
                      :search-threshold="0"
                      teleport
                      :disabled="form.api_format_unrestricted"
                      :placeholder="form.api_format_unrestricted ? '不限制' : '未选择（全部禁用）'"
                      empty-text="暂无可用端点"
                      no-results-text="未找到匹配的端点"
                      search-placeholder="搜索端点..."
                    />
                  </div>
                  <Switch
                    v-model="form.api_format_unrestricted"
                    class="shrink-0"
                  />
                </div>
              </div>

              <!-- 模型 -->
              <div class="space-y-2">
                <Label class="text-sm font-medium">允许的模型</Label>
                <div class="flex items-center gap-3">
                  <div class="flex-1 min-w-0">
                    <MultiSelect
                      v-model="form.allowed_models"
                      :options="modelOptions"
                      :search-threshold="0"
                      teleport
                      :disabled="form.model_unrestricted"
                      :placeholder="form.model_unrestricted ? '不限制' : '未选择（全部禁用）'"
                      empty-text="暂无可用模型"
                      no-results-text="未找到匹配的模型"
                      search-placeholder="输入模型名搜索..."
                    />
                  </div>
                  <Switch
                    v-model="form.model_unrestricted"
                    class="shrink-0"
                  />
                </div>
              </div>

              <div class="space-y-2">
                <Label
                  for="form-rate-limit"
                  class="text-sm font-medium"
                >速率限制 (请求/分钟)</Label>
                <div class="flex items-center gap-3">
                  <div class="flex-1 min-w-0">
                    <Input
                      v-if="!form.rate_limit_inherited"
                      id="form-rate-limit"
                      :model-value="form.rate_limit ?? ''"
                      type="number"
                      min="0"
                      max="10000"
                      placeholder="0 = 不限速"
                      class="h-10"
                      @update:model-value="(v) => form.rate_limit = parseNumberInput(v, { min: 0, max: 10000 })"
                    />
                    <span
                      v-else
                      class="flex h-10 w-full items-center rounded-lg border bg-background px-3 text-sm text-muted-foreground opacity-60"
                    >跟随系统</span>
                  </div>
                  <Switch
                    v-model="form.rate_limit_inherited"
                    class="shrink-0"
                  />
                </div>
              </div>

              <div class="space-y-2">
                <Label
                  for="form-concurrent-limit"
                  class="text-sm font-medium"
                >并发限制</Label>
                <div class="flex items-center gap-3">
                  <div class="flex-1 min-w-0">
                    <Input
                      v-if="!form.concurrent_limit_inherited"
                      id="form-concurrent-limit"
                      :model-value="form.concurrent_limit ?? ''"
                      type="number"
                      min="0"
                      max="10000"
                      placeholder="0 = 不限制"
                      class="h-10"
                      @update:model-value="(v) => form.concurrent_limit = parseNumberInput(v, { min: 0, max: 10000 })"
                    />
                    <span
                      v-else
                      class="flex h-10 w-full items-center rounded-lg border bg-background px-3 text-sm text-muted-foreground opacity-60"
                    >不限制</span>
                  </div>
                  <Switch
                    v-model="form.concurrent_limit_inherited"
                    class="shrink-0"
                  />
                </div>
                <p class="text-xs text-muted-foreground">
                  留空表示不限制，填 0 也表示不限制并发
                </p>
              </div>

              <div class="space-y-2">
                <Label
                  for="form-ip-rules"
                  class="text-sm font-medium"
                >IP 限制</Label>
                <Input
                  id="form-ip-rules"
                  v-model="form.ip_rules_text"
                  class="h-10"
                  placeholder="例如：203.0.113.10, 10.0.0.0/24"
                />
                <p class="text-xs text-muted-foreground">
                  留空表示不限制；支持 IP、CIDR、IPv4 通配符、*，用 ! 前缀拒绝
                </p>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>
    </form>

    <template #footer>
      <Button
        variant="outline"
        type="button"
        class="h-10 px-5"
        @click="handleCancel"
      >
        取消
      </Button>
      <Button
        :disabled="saving"
        class="h-10 px-5"
        @click="handleSubmit"
      >
        {{ saving ? (isEditMode ? '更新中...' : '创建中...') : (isEditMode ? '更新' : '创建') }}
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Dialog,
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
  Button,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
} from '@/components/ui'
import { ChevronDown, Plus, SquarePen, X } from 'lucide-vue-next'
import { useFormDialog } from '@/composables/useFormDialog'
import { MultiSelect } from '@/components/common'
import { getProvidersSummary } from '@/api/endpoints/providers'
import { getGlobalModels } from '@/api/global-models'
import { adminApi } from '@/api/admin'
import { log } from '@/utils/logger'
import { parseNumberInput } from '@/utils/form'
import {
  mergeChatPiiRedactionFeatureSettings,
  readChatPiiRedactionFeatureSettings,
} from '@/utils/featureSettings'
import type { ProviderWithEndpointsSummary, GlobalModelResponse } from '@/api/endpoints/types'
import type { RoutingGroupBindingRecord, RoutingGroupRecord } from '@/api/routing-profiles'
import {
  FOLLOW_SYSTEM_ROUTING_GROUP_VALUE,
  describeCurrentRoutingGroup,
  enabledRoutingGroupsByName,
} from '@/features/api-keys/utils/apiKeyRoutingBinding'

export interface StandaloneKeyFormData {
  id?: string
  name: string
  initial_balance_usd?: number
  current_balance_usd?: number | null
  unlimited_balance?: boolean
  expires_at?: string  // ISO 日期字符串，如 "2025-12-31"，undefined = 永不过期
  rate_limit?: number | null
  concurrent_limit?: number | null
  auto_delete_on_expiry: boolean
  allowed_providers?: string[] | null
  allowed_api_formats?: string[] | null
  allowed_models?: string[] | null
  ip_rules?: string[] | null
  feature_settings?: Record<string, unknown> | null
  /** undefined 表示绑定状态未成功读取，本次提交不得修改绑定。 */
  routing_group_id?: string | null
}

interface StandaloneKeyFormState {
  id?: string
  name: string
  initial_balance_usd?: number
  current_balance_usd?: number | null
  unlimited_balance?: boolean
  expires_at?: string
  rate_limit_inherited: boolean
  rate_limit?: number
  concurrent_limit_inherited: boolean
  concurrent_limit?: number
  auto_delete_on_expiry: boolean
  provider_unrestricted: boolean
  api_format_unrestricted: boolean
  model_unrestricted: boolean
  allowed_providers: string[]
  allowed_api_formats: string[]
  allowed_models: string[]
  ip_rules_text: string
  chat_pii_redaction_enabled: boolean
  chat_pii_redaction_placeholder_notice: boolean
  routing_group_id?: string | null
}

const props = defineProps<{
  open: boolean
  apiKey: StandaloneKeyFormData | null
  routingGroups?: RoutingGroupRecord[]
  routingBinding?: RoutingGroupBindingRecord | null
  routingLoading?: boolean
  routingStateReady?: boolean
  routingLoadError?: string | null
  routingSaveError?: string | null
}>()

const emit = defineEmits<{
  close: []
  submit: [data: StandaloneKeyFormData]
  'retry-routing-load': []
}>()

const isOpen = computed(() => props.open)
const saving = ref(false)
const accessRestrictionsExpanded = ref(false)
const routingSelectionInitialized = ref(false)

// 选项数据
const providers = ref<ProviderWithEndpointsSummary[]>([])
const globalModels = ref<GlobalModelResponse[]>([])
const allApiFormats = ref<string[]>([])

const providerOptions = computed(() =>
  providers.value.map((provider) => ({
    value: provider.id,
    label: provider.name,
  }))
)
const apiFormatOptions = computed(() =>
  allApiFormats.value.map((format) => ({
    value: format,
    label: format,
  }))
)
const modelOptions = computed(() =>
  globalModels.value.map((model) => ({
    value: model.name,
    label: model.name,
  }))
)
const enabledRoutingGroups = computed(() => enabledRoutingGroupsByName(props.routingGroups ?? []))
const currentRoutingGroupState = computed(() => {
  if (!props.routingBinding) return null
  return describeCurrentRoutingGroup(props.routingBinding, props.routingGroups ?? [])
})
const unavailableCurrentRoutingGroup = computed(() => {
  const current = currentRoutingGroupState.value
  if (!props.routingBinding || !current || current.kind === 'active') return null
  return {
    groupId: props.routingBinding.group_id,
    label: current.label,
  }
})
const routingGroupSelectValue = computed({
  get: () => form.value.routing_group_id == null
    ? FOLLOW_SYSTEM_ROUTING_GROUP_VALUE
    : form.value.routing_group_id,
  set: (value: string) => {
    form.value.routing_group_id = value === FOLLOW_SYSTEM_ROUTING_GROUP_VALUE ? null : value
  },
})
// 表单数据
const form = ref<StandaloneKeyFormState>({
  name: '',
  initial_balance_usd: 10,
  current_balance_usd: undefined,
  unlimited_balance: false,
  expires_at: undefined,
  rate_limit_inherited: true,
  rate_limit: undefined,
  concurrent_limit_inherited: true,
  concurrent_limit: undefined,
  auto_delete_on_expiry: false,
  provider_unrestricted: true,
  api_format_unrestricted: true,
  model_unrestricted: true,
  allowed_providers: [],
  allowed_api_formats: [],
  allowed_models: [],
  ip_rules_text: '',
  chat_pii_redaction_enabled: false,
  chat_pii_redaction_placeholder_notice: true,
  routing_group_id: undefined,
})

function formatDateInputValue(date: Date): string {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

// 计算最小可选日期（明天）
const minExpiryDate = computed(() => {
  const tomorrow = new Date()
  tomorrow.setHours(0, 0, 0, 0)
  tomorrow.setDate(tomorrow.getDate() + 1)
  return formatDateInputValue(tomorrow)
})

const balanceDisplayText = computed(() => {
  if (form.value.unlimited_balance) {
    return '独立无限额度'
  }
  if (isEditMode.value) {
    const currentBalance = form.value.current_balance_usd ?? form.value.initial_balance_usd ?? 0
    return `当前独立钱包余额 $${currentBalance.toFixed(2)}`
  }
  return '按独立钱包余额限制'
})

function resetForm() {
  routingSelectionInitialized.value = false
  form.value = {
    name: '',
    initial_balance_usd: 10,
    current_balance_usd: undefined,
    unlimited_balance: false,
    expires_at: undefined,
    rate_limit_inherited: true,
    rate_limit: undefined,
    concurrent_limit_inherited: true,
    concurrent_limit: undefined,
    auto_delete_on_expiry: false,
    provider_unrestricted: true,
    api_format_unrestricted: true,
    model_unrestricted: true,
    allowed_providers: [],
    allowed_api_formats: [],
    allowed_models: [],
    ip_rules_text: '',
    chat_pii_redaction_enabled: false,
    chat_pii_redaction_placeholder_notice: true,
    routing_group_id: undefined,
  } as typeof form.value
  initializeRoutingSelection()
}

function initializeRoutingSelection() {
  if (!props.routingStateReady || routingSelectionInitialized.value) return
  form.value.routing_group_id = props.apiKey?.routing_group_id !== undefined
    ? props.apiKey.routing_group_id
    : (props.routingBinding?.group_id ?? null)
  routingSelectionInitialized.value = true
}

function loadKeyData() {
  if (!props.apiKey) return
  routingSelectionInitialized.value = false
  const redactionFeature = readChatPiiRedactionFeatureSettings(props.apiKey.feature_settings)
  form.value = {
    id: props.apiKey.id,
    name: props.apiKey.name || '',
    initial_balance_usd: props.apiKey.initial_balance_usd,
    current_balance_usd: props.apiKey.current_balance_usd ?? props.apiKey.initial_balance_usd ?? null,
    unlimited_balance: props.apiKey.initial_balance_usd == null,
    expires_at: props.apiKey.expires_at,
    rate_limit_inherited: props.apiKey.rate_limit == null,
    rate_limit: props.apiKey.rate_limit ?? undefined,
    concurrent_limit_inherited: props.apiKey.concurrent_limit == null,
    concurrent_limit: props.apiKey.concurrent_limit ?? undefined,
    auto_delete_on_expiry: props.apiKey.auto_delete_on_expiry,
    provider_unrestricted: props.apiKey.allowed_providers == null,
    api_format_unrestricted: props.apiKey.allowed_api_formats == null,
    model_unrestricted: props.apiKey.allowed_models == null,
    allowed_providers: props.apiKey.allowed_providers ? [...props.apiKey.allowed_providers] : [],
    allowed_api_formats: props.apiKey.allowed_api_formats ? [...props.apiKey.allowed_api_formats] : [],
    allowed_models: props.apiKey.allowed_models ? [...props.apiKey.allowed_models] : [],
    ip_rules_text: props.apiKey.ip_rules?.join(', ') ?? '',
    chat_pii_redaction_enabled: redactionFeature.enabled,
    chat_pii_redaction_placeholder_notice: redactionFeature.inject_model_instruction,
    routing_group_id: undefined,
  } as typeof form.value
  initializeRoutingSelection()
}

const { isEditMode, handleDialogUpdate, handleCancel } = useFormDialog({
  isOpen: () => props.open,
  entity: () => props.apiKey,
  isLoading: saving,
  onClose: () => emit('close'),
  loadData: loadKeyData,
  resetForm,
})

// 加载选项数据
async function loadAccessRestrictionOptions() {
  try {
    const [providersResponse, modelsData, formatsData] = await Promise.all([
      getProvidersSummary({ page_size: 9999 }),
      getGlobalModels({ limit: 1000, is_active: true }),
      adminApi.getApiFormats()
    ])
    providers.value = providersResponse.items
    globalModels.value = modelsData.models || []
    allApiFormats.value = formatsData.formats?.map((f: { value: string }) => f.value) || []
  } catch (err) {
    log.error('加载访问限制选项失败:', err)
  }
}

// 清空过期日期（同时清空到期删除选项）
function clearExpiryDate() {
  form.value.expires_at = undefined
  form.value.auto_delete_on_expiry = false
}

// 提交表单
function handleSubmit() {
  if (saving.value) return
  const routingGroupId = form.value.routing_group_id === undefined && props.routingStateReady
    ? null
    : form.value.routing_group_id
  emit('submit', {
    id: form.value.id,
    name: form.value.name,
    initial_balance_usd: form.value.initial_balance_usd,
    unlimited_balance: form.value.unlimited_balance,
    expires_at: form.value.expires_at,
    rate_limit: form.value.rate_limit_inherited ? null : (form.value.rate_limit ?? 0),
    concurrent_limit: form.value.concurrent_limit_inherited ? null : (form.value.concurrent_limit ?? 0),
    auto_delete_on_expiry: form.value.auto_delete_on_expiry,
    allowed_providers: form.value.provider_unrestricted ? null : [...form.value.allowed_providers],
    allowed_api_formats: form.value.api_format_unrestricted ? null : [...form.value.allowed_api_formats],
    allowed_models: form.value.model_unrestricted ? null : [...form.value.allowed_models],
    ip_rules: parseIpRulesInput(form.value.ip_rules_text),
    feature_settings: mergeChatPiiRedactionFeatureSettings(props.apiKey?.feature_settings, {
      enabled: form.value.chat_pii_redaction_enabled,
      inject_model_instruction: form.value.chat_pii_redaction_placeholder_notice,
    }),
    routing_group_id: routingGroupId,
  })
}

function parseIpRulesInput(value: string): string[] | null {
  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  return items.length > 0 ? items : null
}

// 设置保存状态
function setSaving(value: boolean) {
  saving.value = value
}

// 监听打开状态，加载选项数据
watch(isOpen, (val) => {
  if (val) {
    accessRestrictionsExpanded.value = false
    loadAccessRestrictionOptions()
  }
})

watch(
  () => [props.routingStateReady, props.routingBinding] as const,
  () => initializeRoutingSelection(),
)

watch(
  () => form.value.unlimited_balance,
  (unlimited) => {
    if (unlimited) {
      form.value.initial_balance_usd = undefined
    } else if (form.value.initial_balance_usd == null) {
      form.value.initial_balance_usd = 10
    }
  }
)

watch(
  () => form.value.concurrent_limit_inherited,
  (inherited) => {
    if (!inherited && form.value.concurrent_limit == null) {
      form.value.concurrent_limit = 0
    }
  }
)

defineExpose({
  setSaving
})
</script>
