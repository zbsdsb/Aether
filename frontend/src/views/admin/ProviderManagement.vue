<template>
  <div class="space-y-4">
    <Card
      v-if="providerDeleteProgress"
      class="border-primary/30 bg-primary/5"
    >
      <div class="px-5 py-4 space-y-4">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <div class="text-sm font-semibold text-foreground">
              正在删除提供商：{{ providerDeleteProgress.providerName }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{ providerDeleteStageLabel }} · {{ providerDeleteProgress.message || '后台处理中' }}
            </div>
          </div>
          <div class="shrink-0 text-right">
            <div class="text-xs font-medium text-primary">
              {{ providerDeleteOverallPercent }}%
            </div>
            <div class="text-[11px] text-muted-foreground">
              {{ providerDeleteCompletedUnits }}/{{ providerDeleteTotalUnits }}
            </div>
          </div>
        </div>

        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs text-muted-foreground">
            <span>总体进度</span>
            <span>{{ providerDeleteCompletedUnits }}/{{ providerDeleteTotalUnits }}</span>
          </div>
          <div class="h-2 rounded-full bg-primary/10 overflow-hidden">
            <div
              class="h-full bg-primary transition-all duration-300"
              :style="{ width: `${providerDeleteOverallPercent}%` }"
            />
          </div>
        </div>

        <div class="grid gap-3 md:grid-cols-2">
          <div class="space-y-2">
            <div class="flex items-center justify-between text-xs text-muted-foreground">
              <span>账号删除</span>
              <span>{{ providerDeleteProgress.deletedKeys }}/{{ providerDeleteProgress.totalKeys || '...' }}</span>
            </div>
            <div class="h-2 rounded-full bg-primary/10 overflow-hidden">
              <div
                class="h-full bg-primary/80 transition-all duration-300"
                :style="{ width: `${providerDeleteKeysPercent}%` }"
              />
            </div>
          </div>

          <div class="space-y-2">
            <div class="flex items-center justify-between text-xs text-muted-foreground">
              <span>端点删除</span>
              <span>{{ providerDeleteProgress.deletedEndpoints }}/{{ providerDeleteProgress.totalEndpoints || '...' }}</span>
            </div>
            <div class="h-2 rounded-full bg-primary/10 overflow-hidden">
              <div
                class="h-full bg-primary/60 transition-all duration-300"
                :style="{ width: `${providerDeleteEndpointsPercent}%` }"
              />
            </div>
          </div>
        </div>
      </div>
    </Card>

    <ImportTaskOverviewCard
      :overview="importTaskOverview"
      :active-filter="filterImportTaskStatus"
      @select-needs-key="filterImportTaskStatus = 'needs_key'"
      @select-manual-review="filterImportTaskStatus = 'manual_review'"
      @clear-filter="filterImportTaskStatus = 'all'"
    />

    <!-- 提供商表格 -->
    <Card
      variant="default"
    >
      <!-- 标题和操作栏 -->
      <ProviderTableHeader
        :search-query="searchQuery"
        :filter-status="filterStatus"
        :filter-api-format="filterApiFormat"
        :filter-model="filterModel"
        :filter-import-task-status="filterImportTaskStatus"
        :status-filters="statusFilters"
        :api-format-filters="apiFormatFilters"
        :model-filters="modelFilters"
        :import-task-filters="importTaskFilters"
        :has-active-filters="hasActiveFilters"
        :priority-mode-label="priorityModeConfig.label"
        :loading="loading"
        @update:search-query="searchQuery = $event"
        @update:filter-status="filterStatus = $event"
        @update:filter-api-format="filterApiFormat = $event"
        @update:filter-model="filterModel = $event"
        @update:filter-import-task-status="filterImportTaskStatus = $event"
        @reset-filters="resetFilters"
        @open-priority-dialog="openPriorityDialog"
        @open-all-in-hub-import="openAllInHubImportDialog"
        @add-provider="openAddProviderDialog"
        @refresh="loadProviders"
      />

      <!-- 加载状态 -->
      <div
        v-if="loading"
        class="flex items-center justify-center py-12"
      >
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>

      <!-- 空状态 -->
      <div
        v-else-if="providers.length === 0"
        class="flex flex-col items-center justify-center py-16 text-center"
      >
        <div class="text-muted-foreground mb-2">
          <template v-if="hasActiveFilters">
            未找到匹配当前筛选条件的提供商
          </template>
          <template v-else>
            暂无提供商，点击右上角添加
          </template>
        </div>
        <Button
          v-if="hasActiveFilters"
          variant="outline"
          size="sm"
          @click="resetFilters"
        >
          清除筛选
        </Button>
      </div>

      <!-- 桌面端表格 -->
      <div
        v-else
        class="hidden xl:block overflow-x-auto"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead class="w-[18%] min-w-[140px]">
                提供商信息
              </TableHead>
              <TableHead class="w-[20%] min-w-[180px]">
                余额监控
              </TableHead>
              <TableHead class="w-[12%] min-w-[100px] text-center">
                资源统计
              </TableHead>
              <TableHead class="w-[24%] min-w-[260px]">
                端点健康
              </TableHead>
              <TableHead class="w-[8%] min-w-[60px] text-center">
                状态
              </TableHead>
              <TableHead class="w-[18%] min-w-[120px] text-center">
                操作
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <ProviderTableRow
              v-for="provider in displayedProviders"
              :key="provider.id"
              :provider="provider"
              :editing-description-id="editingDescriptionId"
              :is-balance-loading="isBalanceLoading"
              :get-provider-balance="getProviderBalance"
              :get-provider-balance-breakdown="getProviderBalanceBreakdown"
              :get-provider-balance-error="getProviderBalanceError"
              :get-provider-checkin="getProviderCheckin"
              :get-provider-cookie-expired="getProviderCookieExpired"
              :get-provider-balance-extra="getProviderBalanceExtra"
              :format-balance-display="formatBalanceDisplay"
              :format-reset-countdown="formatResetCountdown"
              :get-quota-used-color-class="getQuotaUsedColorClass"
              @mousedown="handleMouseDown"
              @row-click="handleRowClick"
              @view-detail="openProviderDrawer"
              @edit-provider="openEditProviderDialog"
              @open-ops-config="openOpsConfigDialog"
              @toggle-status="toggleProviderStatus"
              @delete-provider="handleDeleteProvider"
              @start-edit-description="startEditDescription"
              @save-description="saveDescription"
              @cancel-edit-description="cancelEditDescription"
            />
          </TableBody>
        </Table>
      </div>

      <!-- 移动端卡片列表 -->
      <div
        v-if="!loading && providers.length > 0"
        class="xl:hidden divide-y divide-border/40"
      >
        <ProviderMobileCard
          v-for="provider in displayedProviders"
          :key="provider.id"
          :provider="provider"
          :editing-description-id="editingDescriptionId"
          :is-balance-loading="isBalanceLoading"
          :get-provider-balance="getProviderBalance"
          :get-provider-balance-error="getProviderBalanceError"
          :get-provider-checkin="getProviderCheckin"
          :get-provider-cookie-expired="getProviderCookieExpired"
          :format-balance-display="formatBalanceDisplay"
          :get-quota-used-color-class="getQuotaUsedColorClass"
          @view-detail="openProviderDrawer"
          @edit-provider="openEditProviderDialog"
          @open-ops-config="openOpsConfigDialog"
          @toggle-status="toggleProviderStatus"
          @delete-provider="handleDeleteProvider"
          @start-edit-description="startEditDescription"
          @save-description="saveDescription"
          @cancel-edit-description="cancelEditDescription"
        />
      </div>

      <!-- 分页 -->
      <Pagination
        v-if="!loading && total > 0"
        :current="currentPage"
        :total="total"
        :page-size="pageSize"
        cache-key="provider-management-page-size"
        @update:current="currentPage = $event"
        @update:page-size="pageSize = $event"
      />
    </Card>
  </div>

  <!-- 对话框 -->
  <ProviderFormDialog
    v-model="providerDialogOpen"
    :provider="providerToEdit"
    :max-priority="maxProviderPriority"
    @provider-created="handleProviderAdded"
    @provider-updated="handleProviderUpdated"
  />

  <PriorityManagementDialog
    v-model="priorityDialogOpen"
    @saved="handlePrioritySaved"
  />

  <ProviderDetailDrawer
    :open="providerDrawerOpen"
    :provider-id="selectedProviderId"
    @update:open="providerDrawerOpen = $event"
    @edit="openEditProviderDialog"
    @open-imported-auth-prefill="openImportedAuthPrefill"
    @toggle-status="toggleProviderStatus"
    @refresh="handleDrawerRefresh"
  />

  <ProviderAuthDialog
    v-model:open="opsConfigDialogOpen"
    :provider-id="opsConfigProviderId"
    :provider-website="opsConfigProviderWebsite"
    :prefill-draft="opsConfigPrefillDraft"
    @saved="handleOpsConfigSaved"
  />

  <AllInHubImportDialog
    :open="allInHubImportDialogOpen"
    :content="allInHubImportContent"
    :job-status="allInHubImportJobStatus"
    :preview="allInHubImportPreview"
    :execution-result="allInHubTaskExecutionResult"
    :can-execute-tasks="canExecuteAllInHubTasks"
    :loading="allInHubImportLoading"
    @update:open="allInHubImportDialogOpen = $event"
    @update:content="allInHubImportContent = $event"
    @error="showError($event, '导入内容错误')"
    @preview="handlePreviewAllInHubImport"
    @confirm="handleConfirmAllInHubImport"
    @execute-tasks="handleExecuteAllInHubTasks"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import Button from '@/components/ui/button.vue'
import Card from '@/components/ui/card.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import Pagination from '@/components/ui/pagination.vue'
import {
  AllInHubImportDialog,
  ImportTaskOverviewCard,
  ProviderFormDialog,
  PriorityManagementDialog,
  ProviderAuthDialog,
} from '@/features/providers/components'
import ProviderDetailDrawer from '@/features/providers/components/ProviderDetailDrawer.vue'
import ProviderTableHeader from '@/features/providers/components/ProviderTableHeader.vue'
import ProviderTableRow from '@/features/providers/components/ProviderTableRow.vue'
import ProviderMobileCard from '@/features/providers/components/ProviderMobileCard.vue'
import { buildImportedAuthPrefillConfig } from '@/features/providers/utils/imported-auth-prefill'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useRowClick } from '@/composables/useRowClick'
import { useProviderFilters } from '@/features/providers/composables/useProviderFilters'
import { useProviderBalance } from '@/features/providers/composables/useProviderBalance'
import {
  getProvidersSummary,
  getProvider,
  getAllInHubImportJob,
  executeAllInHubImportTasks,
  deleteProvider,
  getProviderDeleteTask,
  previewAllInHubImport,
  submitAllInHubImportJob,
  updateProvider,
  getGlobalModels,
  type AllInHubImportJobStatusResponse,
  type AllInHubImportManualItem,
  type AllInHubImportResponse,
  type AllInHubTaskExecutionResponse,
  type ProviderImportTaskOverview,
  type ProviderWithEndpointsSummary,
} from '@/api/endpoints'
import type { ImportedAuthPrefillResponse } from '@/api/providerOps'
import { adminApi } from '@/api/admin'
import { parseApiError } from '@/utils/errorParser'
import { useRouteQuery } from '@/composables/useRouteQuery'

interface ProviderDeleteProgressState {
  providerId: string
  providerName: string
  taskId: string
  status: string
  stage: string
  totalKeys: number
  deletedKeys: number
  totalEndpoints: number
  deletedEndpoints: number
  message: string
}

const { error: showError, success: showSuccess, warning: showWarning, info: showInfo } = useToast()
const { confirmDanger } = useConfirm()
const { getQueryValue, patchQuery } = useRouteQuery()

const EMPTY_IMPORT_TASK_OVERVIEW: ProviderImportTaskOverview = {
  providers_with_import_tasks: 0,
  providers_with_pending_tasks: 0,
  providers_needing_manual_key_input: 0,
  providers_needing_manual_review: 0,
  tasks_pending: 0,
  tasks_waiting_plaintext: 0,
  tasks_failed: 0,
}

// 状态
const loading = ref(false)
const providers = ref<ProviderWithEndpointsSummary[]>([])
const importTaskOverview = ref<ProviderImportTaskOverview>(EMPTY_IMPORT_TASK_OVERVIEW)
let providersRequestId = 0
const providerDialogOpen = ref(false)
const providerToEdit = ref<ProviderWithEndpointsSummary | null>(null)
const priorityDialogOpen = ref(false)
const priorityMode = ref<'provider' | 'global_key'>('provider')
const providerDrawerOpen = ref(false)
const selectedProviderId = ref<string | null>(null)
const providerDeleteProgress = ref<ProviderDeleteProgressState | null>(null)
const allInHubImportDialogOpen = ref(false)
const allInHubImportContent = ref('')
const allInHubImportPreview = ref<AllInHubImportResponse | null>(null)
const allInHubTaskExecutionResult = ref<AllInHubTaskExecutionResponse | null>(null)
const allInHubImportJobStatus = ref<AllInHubImportJobStatusResponse | null>(null)
const canExecuteAllInHubTasks = ref(false)
const allInHubImportLoading = ref(false)
let allInHubImportPollTimer: ReturnType<typeof setTimeout> | null = null
let deletePollAbort: AbortController | null = null

const DELETE_POLL_INTERVAL_MS = 2000
const DELETE_POLL_MAX_MS = 30 * 60 * 1000
const DELETE_POLL_MAX_FAILURES = 3

async function pollProviderDeleteTask(providerId: string, taskId: string) {
  deletePollAbort?.abort()
  const abort = new AbortController()
  deletePollAbort = abort

  const deadline = Date.now() + DELETE_POLL_MAX_MS
  let consecutiveFailures = 0

  while (Date.now() < deadline) {
    if (abort.signal.aborted) return null
    try {
      const task = await getProviderDeleteTask(providerId, taskId)
      consecutiveFailures = 0
      if (providerDeleteProgress.value?.taskId === taskId) {
        providerDeleteProgress.value = {
          ...providerDeleteProgress.value,
          status: task.status,
          stage: task.stage,
          totalKeys: task.total_keys,
          deletedKeys: task.deleted_keys,
          totalEndpoints: task.total_endpoints,
          deletedEndpoints: task.deleted_endpoints,
          message: task.message,
        }
      }
      if (task.status === 'completed' || task.status === 'failed') {
        return task
      }
    } catch {
      consecutiveFailures += 1
      if (consecutiveFailures >= DELETE_POLL_MAX_FAILURES) {
        throw new Error('provider delete task polling failed')
      }
    }
    await new Promise((resolve) => {
      const timer = setTimeout(resolve, DELETE_POLL_INTERVAL_MS)
      abort.signal.addEventListener('abort', () => { clearTimeout(timer); resolve(undefined) }, { once: true })
    })
  }

  throw new Error('provider delete task timeout')
}

const providerDeleteStageLabel = computed(() => {
  switch (providerDeleteProgress.value?.stage) {
    case 'preparing':
      return '准备删除'
    case 'disabling':
      return '停用提供商'
    case 'cleaning_restrictions':
      return '清理访问限制'
    case 'cleaning_provider_refs':
      return '清理历史引用'
    case 'deleting_keys':
      return '删除号池账号'
    case 'deleting_endpoints':
      return '删除端点'
    case 'completed':
      return '删除完成'
    case 'failed':
      return '删除失败'
    default:
      return '等待执行'
  }
})

const providerDeleteTotalUnits = computed(() => {
  const progress = providerDeleteProgress.value
  if (!progress) return 0
  return progress.totalKeys + progress.totalEndpoints
})

const providerDeleteCompletedUnits = computed(() => {
  const progress = providerDeleteProgress.value
  if (!progress) return 0
  return Math.min(progress.deletedKeys + progress.deletedEndpoints, providerDeleteTotalUnits.value)
})

const providerDeleteOverallPercent = computed(() => {
  const progress = providerDeleteProgress.value
  if (!progress) return 0
  if (progress.status === 'completed') return 100
  if (providerDeleteTotalUnits.value <= 0) return 0
  return Math.min(
    100,
    Math.round((providerDeleteCompletedUnits.value / providerDeleteTotalUnits.value) * 100),
  )
})

const providerDeleteKeysPercent = computed(() => {
  const progress = providerDeleteProgress.value
  if (!progress?.totalKeys) return 0
  return Math.min(100, Math.round((progress.deletedKeys / progress.totalKeys) * 100))
})

const providerDeleteEndpointsPercent = computed(() => {
  const progress = providerDeleteProgress.value
  if (!progress?.totalEndpoints) return 0
  return Math.min(100, Math.round((progress.deletedEndpoints / progress.totalEndpoints) * 100))
})

watch(allInHubImportContent, () => {
  allInHubImportPreview.value = null
  allInHubTaskExecutionResult.value = null
  canExecuteAllInHubTasks.value = false
})

function buildManualItemKey(item: Pick<AllInHubImportManualItem, 'item_type' | 'provider_website' | 'source_id' | 'task_type'>): string {
  return [
    item.item_type,
    item.provider_website || '',
    item.source_id || '',
    item.task_type || '',
  ].join('::')
}

function mapExecutionItemToManualItem(
  item: AllInHubTaskExecutionResponse['results'][number],
): AllInHubImportManualItem | null {
  if (item.status === 'completed') {
    return null
  }

  if (item.status === 'waiting_plaintext') {
    const masked = item.masked_key_preview ? `（${item.masked_key_preview}）` : ''
    return {
      item_type: 'pending_task',
      status: item.status,
      provider_name: item.provider_name || '未命名站点',
      provider_website: item.provider_website || '',
      endpoint_base_url: item.endpoint_base_url || '',
      source_id: item.source_id || item.task_id,
      task_type: item.task_type,
      auth_type: item.auth_type,
      site_type: item.site_type,
      reason: `缺少明文 Key${masked}，等待人工补抓或补录`,
    }
  }

  if (item.status === 'failed') {
    return {
      item_type: 'verification_failure',
      status: item.status,
      provider_name: item.provider_name || '未命名站点',
      provider_website: item.provider_website || '',
      endpoint_base_url: item.endpoint_base_url || '',
      source_id: item.source_id || item.task_id,
      task_type: item.task_type,
      auth_type: item.auth_type,
      site_type: item.site_type,
      reason: item.last_error || '补钥或模型校验失败，等待人工复核',
    }
  }

  return null
}

function mergeExecutionManualItems(
  preview: AllInHubImportResponse,
  execution: AllInHubTaskExecutionResponse,
): AllInHubImportResponse {
  const executedSourceKeys = new Set(
    execution.results.map(item => buildManualItemKey({
      item_type: 'pending_task',
      provider_website: item.provider_website || '',
      source_id: item.source_id || item.task_id,
      task_type: item.task_type,
    })),
  )

  const keptItems = preview.manual_items.filter(item => {
    if (item.item_type !== 'pending_task') {
      return true
    }
    return !executedSourceKeys.has(buildManualItemKey(item))
  })

  const appendedItems = execution.results
    .map(mapExecutionItemToManualItem)
    .filter((item): item is AllInHubImportManualItem => item !== null)

  const deduped = new Map<string, AllInHubImportManualItem>()
  for (const item of [...keptItems, ...appendedItems]) {
    deduped.set(buildManualItemKey(item), item)
  }

  return {
    ...preview,
    manual_items: [...deduped.values()],
  }
}

// 全局模型数据（用于模型筛选下拉）
const globalModels = ref<{ id: string; name: string }[]>([])

// Composables
const {
  searchQuery,
  filterStatus,
  filterApiFormat,
  filterModel,
  filterImportTaskStatus,
  statusFilters,
  apiFormatFilters,
  modelFilters,
  importTaskFilters,
  hasActiveFilters,
  currentPage,
  pageSize,
  total,
  queryParams,
  resetFilters,
} = useProviderFilters(
  () => globalModels.value,
)

const {
  loadArchitectureSchemas,
  loadBalances,
  getProviderBalance,
  getProviderBalanceBreakdown,
  getProviderBalanceError,
  isBalanceLoading,
  getProviderCheckin,
  getProviderCookieExpired,
  formatBalanceDisplay,
  formatResetCountdown,
  getProviderBalanceExtra,
  getQuotaUsedColorClass,
  startTick,
  stopTick,
} = useProviderBalance()

watch(
  () => getQueryValue('search') ?? '',
  (value) => {
    if (searchQuery.value === value) return
    searchQuery.value = value
  },
  { immediate: true },
)

watch(searchQuery, (value) => {
  patchQuery({ search: value.trim() || undefined })
})

watch(
  () => getQueryValue('importTaskStatus') ?? 'all',
  (value) => {
    if (filterImportTaskStatus.value === value) return
    filterImportTaskStatus.value = value
  },
  { immediate: true },
)

watch(filterImportTaskStatus, (value) => {
  patchQuery({ importTaskStatus: value !== 'all' ? value : undefined })
})

watch(
  () => getQueryValue('providerId'),
  (value) => {
    if (value) {
      if (selectedProviderId.value === value) {
        if (!providerDrawerOpen.value) providerDrawerOpen.value = true
        return
      }
      openProviderDrawer(value)
      return
    }
    if (selectedProviderId.value) selectedProviderId.value = null
    if (providerDrawerOpen.value) providerDrawerOpen.value = false
  },
  { immediate: true },
)

watch(selectedProviderId, (value) => {
  patchQuery({ providerId: value || undefined })
})

watch(providerDrawerOpen, (open) => {
  if (!open && selectedProviderId.value) {
    selectedProviderId.value = null
  }
})

// 扩展操作配置对话框
const opsConfigDialogOpen = ref(false)
const opsConfigProviderId = ref('')
const opsConfigProviderWebsite = ref('')
const opsConfigPrefillDraft = ref<Record<string, unknown> | null>(null)

// 内联编辑备注
const editingDescriptionId = ref<string | null>(null)

function sortProvidersByActiveAndPriority(items: ProviderWithEndpointsSummary[]) {
  return [...items].sort((a, b) => {
    if (a.is_active !== b.is_active) {
      return a.is_active ? -1 : 1
    }
    if (a.provider_priority !== b.provider_priority) {
      return a.provider_priority - b.provider_priority
    }
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  })
}

const displayedProviders = computed(() => sortProvidersByActiveAndPriority(providers.value))

function startEditDescription(_event: Event, provider: ProviderWithEndpointsSummary) {
  editingDescriptionId.value = provider.id
}

function cancelEditDescription(_event?: Event) {
  editingDescriptionId.value = null
}

async function saveDescription(_event: Event, provider: ProviderWithEndpointsSummary, newValue: string) {
  const trimmed = newValue.trim()
  const oldValue = provider.description || ''
  if (trimmed === oldValue) {
    cancelEditDescription()
    return
  }
  try {
    await updateProvider(provider.id, { description: trimmed || null })
    provider.description = trimmed || undefined
    // 同步更新 providers 数组
    const target = providers.value.find(p => p.id === provider.id)
    if (target) {
      target.description = trimmed || undefined
    }
    cancelEditDescription()
  } catch (err: unknown) {
    showError(parseApiError(err, '更新备注失败'), '错误')
  }
}

// 优先级模式配置
const priorityModeConfig = computed(() => {
  return {
    label: priorityMode.value === 'global_key' ? '全局 Key 优先' : '提供商优先',
  }
})

// 当前已有提供商的最大优先级
const maxProviderPriority = computed(() => {
  if (providers.value.length === 0) return undefined
  const priorities = providers.value
    .map(p => p.provider_priority)
    .filter(v => typeof v === 'number' && Number.isFinite(v))
  return priorities.length > 0 ? Math.max(...priorities) : undefined
})

// 加载优先级模式
async function loadPriorityMode() {
  try {
    const response = await adminApi.getSystemConfig('provider_priority_mode')
    if (response.value) {
      priorityMode.value = response.value as 'provider' | 'global_key'
    }
  } catch {
    priorityMode.value = 'provider'
  }
}

// 加载全局模型列表（用于模型筛选下拉）
async function loadGlobalModelList() {
  try {
    const response = await getGlobalModels({ is_active: true, limit: 1000 })
    globalModels.value = response.models.map(m => ({ id: m.id, name: m.name }))
  } catch {
    globalModels.value = []
  }
}

// 加载提供商列表（服务端分页）
async function loadProviders() {
  const requestId = ++providersRequestId
  loading.value = true
  try {
    const response = await getProvidersSummary(queryParams.value)
    if (requestId !== providersRequestId) return
    providers.value = response.items
    total.value = response.total
    importTaskOverview.value = response.import_task_overview ?? EMPTY_IMPORT_TASK_OVERVIEW
    // 异步加载配置了 ops 的 provider 的余额数据
    loadBalances(providers.value)
  } catch (err: unknown) {
    if (requestId !== providersRequestId) return
    importTaskOverview.value = EMPTY_IMPORT_TASK_OVERVIEW
    showError(parseApiError(err, '加载提供商列表失败'), '错误')
  } finally {
    if (requestId === providersRequestId) {
      loading.value = false
    }
  }
}

// 分页/筛选/搜索变化时重新加载
let debounceTimer: ReturnType<typeof setTimeout> | null = null
watch(queryParams, (newParams, oldParams) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  // 搜索输入 debounce 300ms，其他变化立即执行
  const isSearchOnly = newParams.search !== oldParams?.search &&
    newParams.page === oldParams?.page &&
    newParams.page_size === oldParams?.page_size &&
    newParams.status === oldParams?.status &&
    newParams.api_format === oldParams?.api_format &&
    newParams.model_id === oldParams?.model_id &&
    newParams.import_task_status === oldParams?.import_task_status
  if (isSearchOnly) {
    debounceTimer = setTimeout(loadProviders, 300)
  } else {
    loadProviders()
  }
}, { deep: true })

// 使用复用的行点击逻辑
const { handleMouseDown, shouldTriggerRowClick } = useRowClick()

// 处理行点击 - 只在非选中文本时打开抽屉
function handleRowClick(event: MouseEvent, providerId: string) {
  if (!shouldTriggerRowClick(event)) return
  openProviderDrawer(providerId)
}

// 打开添加提供商对话框
function openAddProviderDialog() {
  providerToEdit.value = null
  providerDialogOpen.value = true
}

// 打开优先级管理对话框
function openPriorityDialog() {
  priorityDialogOpen.value = true
}

// 打开提供商详情抽屉
function openProviderDrawer(providerId: string) {
  selectedProviderId.value = providerId
  providerDrawerOpen.value = true
}

function openAllInHubImportDialog() {
  allInHubImportDialogOpen.value = true
  allInHubImportContent.value = ''
  allInHubImportPreview.value = null
  allInHubTaskExecutionResult.value = null
  allInHubImportJobStatus.value = null
  canExecuteAllInHubTasks.value = false
}

async function handlePreviewAllInHubImport() {
  if (!allInHubImportContent.value.trim()) {
    showInfo('请先提供 all-in-hub 导出内容')
    return
  }
  allInHubImportLoading.value = true
  try {
    allInHubImportPreview.value = await previewAllInHubImport(allInHubImportContent.value)
    allInHubTaskExecutionResult.value = null
    canExecuteAllInHubTasks.value = false
    if (allInHubImportPreview.value.stats.providers_total === 0) {
      showInfo('未识别到可导入的站点记录')
    }
  } catch (err: unknown) {
    showError(parseApiError(err, '预览导入失败'), '导入失败')
  } finally {
    allInHubImportLoading.value = false
  }
}

async function handleConfirmAllInHubImport() {
  if (!allInHubImportContent.value.trim()) {
    showInfo('请先提供 all-in-hub 导出内容')
    return
  }
  allInHubImportLoading.value = true
  try {
    const submission = await submitAllInHubImportJob(allInHubImportContent.value)
    allInHubImportJobStatus.value = {
      task_id: submission.task_id,
      status: submission.status,
      stage: submission.stage,
      message: submission.message,
      import_result: null,
      execution_result: null,
    }
    allInHubTaskExecutionResult.value = null
    canExecuteAllInHubTasks.value = false
    showInfo(`后台导入任务已提交：${submission.task_id}`)
    startAllInHubImportPolling(submission.task_id)
  } catch (err: unknown) {
    showError(parseApiError(err, '执行导入失败'), '导入失败')
  } finally {
    allInHubImportLoading.value = false
  }
}

function stopAllInHubImportPolling() {
  if (allInHubImportPollTimer) {
    clearTimeout(allInHubImportPollTimer)
    allInHubImportPollTimer = null
  }
}

function scheduleAllInHubImportPolling(taskId: string, delay = 1500) {
  stopAllInHubImportPolling()
  allInHubImportPollTimer = setTimeout(() => {
    void pollAllInHubImportJob(taskId)
  }, delay)
}

async function pollAllInHubImportJob(taskId: string) {
  try {
    const status = await getAllInHubImportJob(taskId)
    allInHubImportJobStatus.value = status
    allInHubImportPreview.value = status.import_result
    allInHubTaskExecutionResult.value = status.execution_result
    canExecuteAllInHubTasks.value = !!status.execution_result && status.execution_result.total_selected >= 20

    if (status.status === 'completed') {
      stopAllInHubImportPolling()
      if (status.import_result && status.execution_result) {
        allInHubImportPreview.value = mergeExecutionManualItems(status.import_result, status.execution_result)
      }
      await loadProviders()
      const importStats = status.import_result?.stats
      const executionStats = status.execution_result
      let successMessage = '后台导入已完成'
      if (importStats) {
        successMessage = `导入完成：新增 ${importStats.providers_created} 个 Provider，${importStats.endpoints_created} 个 Endpoint，${importStats.keys_created} 个 Key`
      }
      if (executionStats && executionStats.total_selected > 0) {
        successMessage += `；自动执行 ${executionStats.total_selected} 条任务，成功 ${executionStats.completed}，失败 ${executionStats.failed}`
      }
      const pendingReviewCount = allInHubImportPreview.value?.manual_items.length || 0
      if (pendingReviewCount > 0) {
        showWarning(`仍有 ${pendingReviewCount} 条待人工处理或复核`, '导入结果已更新')
      }
      showSuccess(successMessage)
      return
    }

    if (status.status === 'failed') {
      stopAllInHubImportPolling()
      showError(status.message || '后台导入失败', '导入失败')
      return
    }

    scheduleAllInHubImportPolling(taskId)
  } catch (err: unknown) {
    stopAllInHubImportPolling()
    showError(parseApiError(err, '获取导入任务状态失败'), '导入失败')
  }
}

function startAllInHubImportPolling(taskId: string) {
  scheduleAllInHubImportPolling(taskId, 500)
}

async function handleExecuteAllInHubTasks() {
  allInHubImportLoading.value = true
  try {
    const result = await executeAllInHubImportTasks(20)
    allInHubTaskExecutionResult.value = result
    if (allInHubImportPreview.value) {
      allInHubImportPreview.value = mergeExecutionManualItems(allInHubImportPreview.value, result)
    }
    canExecuteAllInHubTasks.value = result.total_selected === 20
    await loadProviders()
    const pendingReviewCount = allInHubImportPreview.value?.manual_items.length || 0
    if (pendingReviewCount > 0) {
      showWarning(`剩余 ${pendingReviewCount} 条待人工处理或复核`, '补钥执行完成')
    }
    showSuccess(`补钥完成：成功 ${result.completed}，失败 ${result.failed}，新建 Key ${result.keys_created}`)
  } catch (err: unknown) {
    showError(parseApiError(err, '执行补钥任务失败'), '补钥失败')
  } finally {
    allInHubImportLoading.value = false
  }
}

// 打开编辑提供商对话框
function openEditProviderDialog(provider: ProviderWithEndpointsSummary) {
  providerToEdit.value = provider
  providerDialogOpen.value = true
}

// 打开扩展操作配置对话框
function openOpsConfigDialog(provider: ProviderWithEndpointsSummary) {
  opsConfigProviderId.value = provider.id
  opsConfigProviderWebsite.value = provider.website || ''
  opsConfigPrefillDraft.value = null
  opsConfigDialogOpen.value = true
}

function openImportedAuthPrefill(payload: {
  provider: ProviderWithEndpointsSummary
  prefill: ImportedAuthPrefillResponse
}) {
  opsConfigProviderId.value = payload.provider.id
  opsConfigProviderWebsite.value = payload.provider.website || ''
  opsConfigPrefillDraft.value = buildImportedAuthPrefillConfig(payload.prefill)
  opsConfigDialogOpen.value = true
}

// 扩展操作配置保存回调
function handleOpsConfigSaved() {
  opsConfigDialogOpen.value = false
  opsConfigPrefillDraft.value = null
  loadProviders()
}

// 处理提供商编辑完成
function handleProviderUpdated(updated: ProviderWithEndpointsSummary) {
  const index = providers.value.findIndex(p => p.id === updated.id)
  if (index !== -1) {
    providers.value[index] = updated
    // 刷新该提供商的余额数据
    loadBalances([updated], false)
  }
}

// 处理详情抽屉内的刷新：只刷新当前查看的那一条提供商
async function handleDrawerRefresh() {
  if (!selectedProviderId.value) return
  try {
    const updated = await getProvider(selectedProviderId.value)
    const index = providers.value.findIndex(p => p.id === updated.id)
    if (index !== -1) {
      providers.value[index] = updated
      loadBalances([updated], false)
    }
  } catch (err) {
    showError(parseApiError(err, '刷新提供商数据失败'), '错误')
  }
}

// 优先级保存成功回调
async function handlePrioritySaved() {
  await loadProviders()
  await loadPriorityMode()
}

// 处理提供商添加
function handleProviderAdded() {
  loadProviders()
}

// 删除提供商
async function handleDeleteProvider(provider: ProviderWithEndpointsSummary) {
  const confirmed = await confirmDanger(
    '删除提供商',
    `确定要删除提供商 "${provider.name}" 吗？\n\n这将同时删除其所有端点、密钥和配置。此操作不可恢复！`,
  )

  if (!confirmed) return

  try {
    const result = await deleteProvider(provider.id)
    providerDeleteProgress.value = {
      providerId: provider.id,
      providerName: provider.name,
      taskId: result.task_id,
      status: result.status,
      stage: 'queued',
      totalKeys: provider.total_keys || 0,
      deletedKeys: 0,
      totalEndpoints: provider.total_endpoints || 0,
      deletedEndpoints: 0,
      message: result.message || '删除任务已提交，后台处理中',
    }
    showInfo(result.message || '删除任务已提交，后台处理中')

    const task = await pollProviderDeleteTask(provider.id, result.task_id)
    if (!task) return // aborted
    if (task.status === 'failed') {
      throw new Error(task.message || 'provider delete task failed')
    }

    showSuccess('提供商已删除')
    providerDeleteProgress.value = null
    loadProviders()
  } catch (err: unknown) {
    providerDeleteProgress.value = null
    showError(parseApiError(err, '删除提供商失败'), '错误')
  }
}

// 切换提供商状态
async function toggleProviderStatus(provider: ProviderWithEndpointsSummary) {
  try {
    const newStatus = !provider.is_active
    await updateProvider(provider.id, { is_active: newStatus })

    // 更新抽屉内部的 provider 对象
    provider.is_active = newStatus

    // 同时更新主页面 providers 数组中的对象，实现无感更新
    const targetProvider = providers.value.find(p => p.id === provider.id)
    if (targetProvider) {
      targetProvider.is_active = newStatus
    }

    showSuccess(newStatus ? '提供商已启用' : '提供商已停用')
  } catch (err: unknown) {
    showError(parseApiError(err, '操作失败'), '错误')
  }
}

// 点击外部自动取消编辑备注
function handleGlobalClick(event: MouseEvent) {
  if (!editingDescriptionId.value) return
  const target = event.target as HTMLElement
  if (target.closest('[data-desc-editor]')) return
  cancelEditDescription()
}

onMounted(() => {
  loadProviders()
  loadPriorityMode()
  loadGlobalModelList()
  loadArchitectureSchemas()
  document.addEventListener('click', handleGlobalClick, true)
  // 每秒更新一次倒计时
  startTick()
})

onUnmounted(() => {
  deletePollAbort?.abort()
  stopAllInHubImportPolling()
  if (debounceTimer) clearTimeout(debounceTimer)
  document.removeEventListener('click', handleGlobalClick, true)
  stopTick()
})
</script>
