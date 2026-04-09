<template>
  <div class="space-y-6 pb-8">
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Card class="p-4">
        <p class="text-xs text-muted-foreground">总任务数</p>
        <p class="mt-2 text-2xl font-bold">{{ stats?.total ?? '-' }}</p>
      </Card>
      <Card class="p-4">
        <p class="text-xs text-muted-foreground">处理中</p>
        <p class="mt-2 text-2xl font-bold">{{ stats?.processing_count ?? '-' }}</p>
      </Card>
      <Card class="p-4">
        <p class="text-xs text-muted-foreground">导入任务</p>
        <p class="mt-2 text-2xl font-bold">{{ stats?.by_task_type?.provider_import ?? 0 }}</p>
      </Card>
      <Card class="p-4">
        <p class="text-xs text-muted-foreground">刷新并适配</p>
        <p class="mt-2 text-2xl font-bold">{{ stats?.by_task_type?.provider_refresh_sync ?? 0 }}</p>
      </Card>
    </div>

    <Card class="overflow-hidden">
      <div class="border-b border-border/60 px-4 py-3.5">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 class="text-base font-semibold">异步任务中心</h3>
            <p class="mt-1 text-xs text-muted-foreground">统一查看视频任务、导入任务与 Provider 刷新并适配任务。</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <Select v-model="filterTaskType">
              <SelectTrigger class="h-8 w-36 text-xs border-border/60">
                <SelectValue placeholder="任务类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部类型</SelectItem>
                <SelectItem value="video">视频任务</SelectItem>
                <SelectItem value="provider_import">导入任务</SelectItem>
                <SelectItem value="provider_refresh_sync">刷新并适配</SelectItem>
              </SelectContent>
            </Select>

            <Select v-model="filterStatus">
              <SelectTrigger class="h-8 w-28 text-xs border-border/60">
                <SelectValue placeholder="状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="pending">等待中</SelectItem>
                <SelectItem value="running">进行中</SelectItem>
                <SelectItem value="processing">处理中</SelectItem>
                <SelectItem value="completed">已完成</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
                <SelectItem value="cancelled">已取消</SelectItem>
              </SelectContent>
            </Select>

            <Input
              v-model="filterKeyword"
              placeholder="搜索任务/模型..."
              class="h-8 w-40 text-xs"
            />

            <Button
              variant="ghost"
              size="icon"
              class="h-8 w-8"
              :disabled="loading"
              @click="refreshOverview"
            >
              <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': loading }" />
            </Button>
          </div>
        </div>
      </div>

      <div
        v-if="loading && tasks.length === 0"
        class="p-8 text-center"
      >
        <Loader2 class="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
        <p class="mt-2 text-sm text-muted-foreground">加载中...</p>
      </div>

      <div
        v-else-if="tasks.length === 0"
        class="p-8 text-center"
      >
        <Zap class="mx-auto h-10 w-10 text-muted-foreground/40" />
        <p class="mt-2 text-sm text-muted-foreground">暂无异步任务</p>
      </div>

      <Table
        v-else
        class="hidden lg:table"
      >
        <TableHeader>
          <TableRow>
            <TableHead class="w-[22%]">任务</TableHead>
            <TableHead class="w-[12%]">类型</TableHead>
            <TableHead class="w-[12%]">状态</TableHead>
            <TableHead class="w-[18%]">渠道商</TableHead>
            <TableHead class="w-[24%]">摘要</TableHead>
            <TableHead class="w-[12%]">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="task in tasks"
            :key="task.id"
            class="cursor-pointer hover:bg-muted/40"
            @click="openTaskDetail(task)"
          >
            <TableCell>
              <div class="space-y-1">
                <p class="font-medium">{{ getAsyncTaskDisplayTitle(task) }}</p>
                <p class="text-xs text-muted-foreground">{{ task.source_task_id }}</p>
              </div>
            </TableCell>
            <TableCell>
              <Badge variant="secondary">{{ getTaskTypeLabel(task.task_type) }}</Badge>
            </TableCell>
            <TableCell>
              <div class="space-y-1">
                <Badge :variant="getStatusVariant(task.status)">{{ getStatusLabel(task.status) }}</Badge>
                <p class="text-xs text-muted-foreground">{{ getStageLabel(task.stage) }}</p>
              </div>
            </TableCell>
            <TableCell>
              <div class="space-y-1 text-sm">
                <p>{{ task.provider_name || '-' }}</p>
                <p class="text-xs text-muted-foreground">{{ formatDate(task.updated_at || task.created_at) }}</p>
              </div>
            </TableCell>
            <TableCell>
              <p class="line-clamp-2 text-sm text-muted-foreground">{{ task.summary || '-' }}</p>
            </TableCell>
            <TableCell>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="h-7 text-xs" @click.stop="openTaskDetail(task)">查看</Button>
                <Button
                  v-if="isVideoTask(task)"
                  variant="ghost"
                  size="sm"
                  class="h-7 text-xs"
                  @click.stop="openUsageRecord(task)"
                >
                  使用记录
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <div
        v-if="tasks.length > 0"
        class="divide-y divide-border/50 lg:hidden"
      >
        <div
          v-for="task in tasks"
          :key="`mobile-${task.id}`"
          class="space-y-3 p-4"
          @click="openTaskDetail(task)"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="truncate font-medium">{{ getAsyncTaskDisplayTitle(task) }}</p>
              <p class="mt-1 text-xs text-muted-foreground">{{ getTaskTypeLabel(task.task_type) }} · {{ getStageLabel(task.stage) }}</p>
            </div>
            <Badge :variant="getStatusVariant(task.status)">{{ getStatusLabel(task.status) }}</Badge>
          </div>
          <p class="text-sm text-muted-foreground">{{ task.summary || '-' }}</p>
          <p class="text-xs text-muted-foreground">{{ task.provider_name || '无渠道商上下文' }}</p>
        </div>
      </div>

      <Pagination
        v-if="total > 0"
        :current="currentPage"
        :total="total"
        :page-size="pageSize"
        cache-key="async-tasks-page-size"
        @update:current="goToPage"
        @update:page-size="handlePageSizeChange"
      />
    </Card>

    <Teleport to="body">
      <Transition name="drawer">
        <div
          v-if="showDetail && selectedTask"
          class="fixed inset-0 z-50 flex justify-end"
          @click.self="closeDetail"
        >
          <div class="absolute inset-0 bg-black/30 backdrop-blur-sm" @click="closeDetail" />
          <Card class="relative flex h-full w-full flex-col rounded-none shadow-2xl sm:w-[720px] sm:max-w-[90vw]">
            <div class="sticky top-0 z-10 border-b bg-background px-4 py-4">
              <div class="flex items-start justify-between gap-4">
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <h3 class="text-lg font-semibold">{{ getAsyncTaskDisplayTitle(selectedTask) }}</h3>
                    <Badge :variant="getStatusVariant(selectedTask.status)">{{ getStatusLabel(selectedTask.status) }}</Badge>
                  </div>
                  <p class="text-xs text-muted-foreground">{{ getTaskTypeLabel(selectedTask.task_type) }} · {{ getStageLabel(selectedTask.stage) }}</p>
                  <p class="text-xs text-muted-foreground">{{ selectedTask.source_task_id }}</p>
                </div>
                <div class="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-8 w-8"
                    :class="{ 'text-primary': detailAutoRefresh }"
                    @click="toggleDetailAutoRefresh"
                  >
                    <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': detailAutoRefresh }" />
                  </Button>
                  <Button variant="ghost" size="icon" class="h-8 w-8" @click="closeDetail">
                    <X class="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>

            <div class="flex-1 overflow-y-auto px-4 py-4 space-y-4">
              <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div class="rounded-lg border border-border/60 p-3">
                  <p class="text-xs text-muted-foreground">类型</p>
                  <p class="mt-1 text-sm font-medium">{{ getTaskTypeLabel(selectedTask.task_type) }}</p>
                </div>
                <div class="rounded-lg border border-border/60 p-3">
                  <p class="text-xs text-muted-foreground">状态</p>
                  <p class="mt-1 text-sm font-medium">{{ getStatusLabel(selectedTask.status) }}</p>
                </div>
                <div class="rounded-lg border border-border/60 p-3">
                  <p class="text-xs text-muted-foreground">渠道商</p>
                  <p class="mt-1 text-sm font-medium">{{ selectedTask.provider_name || '-' }}</p>
                </div>
                <div class="rounded-lg border border-border/60 p-3">
                  <p class="text-xs text-muted-foreground">最后更新</p>
                  <p class="mt-1 text-sm font-medium">{{ formatDate(selectedTask.updated_at || selectedTask.created_at) }}</p>
                </div>
              </div>

              <div class="rounded-lg border border-border/60 p-4">
                <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">摘要</p>
                <p class="mt-2 text-sm leading-6 text-foreground/90">{{ selectedTask.summary || '无摘要' }}</p>
              </div>

              <div
                v-if="selectedTask.detail"
                class="rounded-lg border border-border/60 p-4"
              >
                <div class="flex items-center justify-between gap-3">
                  <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">详情</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-7 text-xs"
                    @click="copyToClipboard(JSON.stringify(selectedTask.detail, null, 2))"
                  >
                    <Copy class="mr-1 h-3.5 w-3.5" />
                    复制 JSON
                  </Button>
                </div>
                <pre class="mt-3 max-h-[380px] overflow-auto rounded-lg bg-muted/40 p-3 text-xs leading-5 text-foreground/80">{{ formatJson(selectedTask.detail) }}</pre>
              </div>

              <div
                v-if="failedProviders.length > 0"
                class="rounded-lg border border-destructive/20 bg-destructive/5 p-4"
              >
                <p class="text-xs font-medium uppercase tracking-wide text-destructive">同步失败渠道商</p>
                <div class="mt-3 space-y-2">
                  <div
                    v-for="item in failedProviders"
                    :key="`${item.provider_name}-${item.error}`"
                    class="rounded-lg border border-destructive/15 bg-background/80 px-3 py-2"
                  >
                    <p class="text-sm font-medium">{{ item.provider_name }}</p>
                    <p class="mt-1 text-xs text-muted-foreground">{{ item.error }}</p>
                  </div>
                </div>
              </div>

              <div
                v-if="isVideoTask(selectedTask)"
                class="flex gap-2 pt-2"
              >
                <Button variant="outline" class="flex-1" @click="openUsageRecord(selectedTask)">
                  <ExternalLink class="mr-2 h-4 w-4" />
                  查看使用记录
                </Button>
                <Button
                  v-if="canCancel(selectedTask.status)"
                  variant="destructive"
                  class="flex-1"
                  @click="cancelTask(selectedTask)"
                >
                  <XCircle class="mr-2 h-4 w-4" />
                  取消任务
                </Button>
              </div>

              <div
                v-else
                class="flex gap-2 pt-2"
              >
                <RouterLink
                  :to="buildAsyncTaskHref(selectedTask)"
                  class="w-full"
                >
                  <Button variant="outline" class="w-full">打开任务来源页</Button>
                </RouterLink>
              </div>
            </div>
          </Card>
        </div>
      </Transition>
    </Teleport>

    <RequestDetailDrawer
      :is-open="usageDetailOpen"
      :request-id="usageRequestId"
      @close="usageDetailOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Copy,
  ExternalLink,
  Loader2,
  RefreshCw,
  X,
  XCircle,
  Zap,
} from 'lucide-vue-next'

import { asyncTasksApi, type AsyncTaskDetail, type AsyncTaskItem, type AsyncTaskStatsResponse, type AsyncTaskStatus, type AsyncTaskType } from '@/api/async-tasks'
import Badge from '@/components/ui/badge.vue'
import Button from '@/components/ui/button.vue'
import Card from '@/components/ui/card.vue'
import Input from '@/components/ui/input.vue'
import Pagination from '@/components/ui/pagination.vue'
import Select from '@/components/ui/select.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectValue from '@/components/ui/select-value.vue'
import Table from '@/components/ui/table.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableCell from '@/components/ui/table-cell.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableRow from '@/components/ui/table-row.vue'
import { useClipboard } from '@/composables/useClipboard'
import { useToast } from '@/composables/useToast'
import { RequestDetailDrawer } from '@/features/usage/components'
import { buildAsyncTaskHref, getAsyncTaskDisplayTitle } from './async-task-center'

const { toast } = useToast()
const { copyToClipboard } = useClipboard()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const tasks = ref<AsyncTaskItem[]>([])
const stats = ref<AsyncTaskStatsResponse | null>(null)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const filterStatus = ref<'all' | AsyncTaskStatus>('all')
const filterTaskType = ref<'all' | AsyncTaskType>('all')
const filterKeyword = ref('')
const selectedTask = ref<AsyncTaskDetail | null>(null)
const showDetail = ref(false)
const detailAutoRefresh = ref(false)
const usageDetailOpen = ref(false)
const usageRequestId = ref<string | null>(null)

let detailRefreshTimer: ReturnType<typeof setInterval> | null = null
let pageRefreshTimer: ReturnType<typeof setInterval> | null = null

function isVideoTask(task: AsyncTaskItem | AsyncTaskDetail): boolean {
  return task.task_type === 'video'
}

const failedProviders = computed(() => {
  const detail = selectedTask.value?.detail as
    | {
        result?: {
          failed_providers?: Array<{ provider_name: string; error: string }>
        }
      }
    | null
    | undefined

  return detail?.result?.failed_providers || []
})

function getTaskTypeLabel(taskType: AsyncTaskType): string {
  if (taskType === 'provider_import') return '导入任务'
  if (taskType === 'provider_refresh_sync') return '刷新并适配'
  if (taskType === 'provider_proxy_probe') return '代理检测'
  return '视频任务'
}

function getStatusLabel(status: string): string {
  const mapping: Record<string, string> = {
    pending: '等待中',
    submitted: '已提交',
    queued: '已排队',
    processing: '处理中',
    running: '进行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return mapping[status] || status
}

function getStageLabel(stage: string): string {
  const mapping: Record<string, string> = {
    queued: '已排队',
    processing: '处理中',
    refreshing: '刷新中',
    importing: '导入中',
    completed: '已完成',
    failed: '失败',
  }
  return mapping[stage] || stage
}

function getStatusVariant(status: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (status === 'completed') return 'default'
  if (status === 'failed') return 'destructive'
  if (status === 'running' || status === 'processing') return 'outline'
  return 'secondary'
}

function canCancel(status: string): boolean {
  return ['pending', 'submitted', 'queued', 'processing', 'running'].includes(status)
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value ?? '')
  }
}

async function fetchTasks() {
  loading.value = true
  try {
    const response = await asyncTasksApi.list({
      status: filterStatus.value === 'all' ? undefined : filterStatus.value,
      task_type: filterTaskType.value === 'all' ? undefined : filterTaskType.value,
      model: filterKeyword.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    tasks.value = response.items
    total.value = response.total
  } catch (error: unknown) {
    toast({
      title: '加载异步任务失败',
      description: error instanceof Error ? error.message : String(error),
      variant: 'destructive',
    })
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  stats.value = await asyncTasksApi.getStats()
}

async function refreshOverview() {
  await Promise.all([fetchTasks(), fetchStats()])
}

async function openTaskDetail(task: AsyncTaskItem) {
  try {
    selectedTask.value = await asyncTasksApi.getDetail(task.id)
    showDetail.value = true
    await router.replace({
      query: {
        ...route.query,
        task: task.id,
        taskType: task.task_type,
      },
    })
  } catch (error: unknown) {
    toast({
      title: '加载任务详情失败',
      description: error instanceof Error ? error.message : String(error),
      variant: 'destructive',
    })
  }
}

function closeDetail() {
  showDetail.value = false
  selectedTask.value = null
  detailAutoRefresh.value = false
  stopDetailAutoRefresh()
  const nextQuery = { ...route.query }
  delete nextQuery.task
  void router.replace({ query: nextQuery })
}

function stopDetailAutoRefresh() {
  if (detailRefreshTimer) {
    clearInterval(detailRefreshTimer)
    detailRefreshTimer = null
  }
}

function toggleDetailAutoRefresh() {
  detailAutoRefresh.value = !detailAutoRefresh.value
  stopDetailAutoRefresh()
  if (!detailAutoRefresh.value || !selectedTask.value) return
  detailRefreshTimer = setInterval(async () => {
    if (!selectedTask.value) return
    selectedTask.value = await asyncTasksApi.getDetail(selectedTask.value.id)
  }, 5000)
}

function schedulePageRefresh() {
  if (pageRefreshTimer) {
    clearInterval(pageRefreshTimer)
    pageRefreshTimer = null
  }
  pageRefreshTimer = setInterval(() => {
    void refreshOverview()
  }, 15000)
}

function goToPage(page: number) {
  currentPage.value = page
}

function handlePageSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
}

async function openUsageRecord(task: AsyncTaskItem | AsyncTaskDetail) {
  if (!isVideoTask(task)) return
  usageRequestId.value = task.source_task_id
  usageDetailOpen.value = true
}

async function cancelTask(task: AsyncTaskItem | AsyncTaskDetail) {
  if (!isVideoTask(task)) return
  try {
    await asyncTasksApi.cancel(task.id)
    toast({
      title: '任务已取消',
      description: '视频任务已提交取消请求',
    })
    await refreshOverview()
    if (selectedTask.value?.id === task.id) {
      selectedTask.value = await asyncTasksApi.getDetail(task.id)
    }
  } catch (error: unknown) {
    toast({
      title: '取消任务失败',
      description: error instanceof Error ? error.message : String(error),
      variant: 'destructive',
    })
  }
}

watch([filterStatus, filterTaskType], () => {
  currentPage.value = 1
  void refreshOverview()
})

watch(filterKeyword, () => {
  currentPage.value = 1
  void refreshOverview()
})

watch([currentPage, pageSize], () => {
  void refreshOverview()
})

watch(
  () => route.query.taskType,
  (value) => {
    if (typeof value === 'string' && value && value !== filterTaskType.value) {
      filterTaskType.value = value as AsyncTaskType
    }
  },
  { immediate: true },
)

watch(
  () => route.query.task,
  async (value) => {
    if (typeof value !== 'string' || !value.trim()) return
    try {
      selectedTask.value = await asyncTasksApi.getDetail(value)
      showDetail.value = true
    } catch {
      // ignore invalid task id from query
    }
  },
  { immediate: true },
)

onMounted(() => {
  void refreshOverview()
  schedulePageRefresh()
})

onUnmounted(() => {
  stopDetailAutoRefresh()
  if (pageRefreshTimer) {
    clearInterval(pageRefreshTimer)
  }
})
</script>
