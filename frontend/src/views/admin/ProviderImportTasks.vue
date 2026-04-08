<template>
  <div class="space-y-6 pb-8">
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Card class="p-4">
        <p class="text-xs text-muted-foreground">最近导入任务</p>
        <p class="mt-2 text-2xl font-bold">{{ jobs.length }}</p>
      </Card>
      <Card class="p-4">
        <p class="text-xs text-muted-foreground">进行中</p>
        <p class="mt-2 text-2xl font-bold">{{ runningJobsCount }}</p>
      </Card>
      <Card class="p-4">
        <p class="text-xs text-muted-foreground">待处理/复核</p>
        <p class="mt-2 text-2xl font-bold">{{ manualItemsCount }}</p>
      </Card>
      <Card class="p-4">
        <p class="text-xs text-muted-foreground">代理检测异常</p>
        <p class="mt-2 text-2xl font-bold">{{ providerIssuesCount }}</p>
      </Card>
    </div>

    <Card class="overflow-hidden">
      <div class="flex items-center justify-between border-b border-border/60 px-4 py-3.5">
        <div>
          <h3 class="text-base font-semibold">导入任务</h3>
          <p class="mt-1 text-xs text-muted-foreground">查看 All-in-Hub 导入、抓上游模型和代理检测的完整后台状态。</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          class="h-8 w-8"
          :disabled="loading"
          @click="refreshJobs"
        >
          <RefreshCw
            class="w-3.5 h-3.5"
            :class="{ 'animate-spin': loading }"
          />
        </Button>
      </div>

      <div
        v-if="loading && jobs.length === 0"
        class="p-8 text-center"
      >
        <Loader2 class="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
        <p class="mt-2 text-sm text-muted-foreground">加载中...</p>
      </div>

      <div
        v-else-if="jobs.length === 0"
        class="p-8 text-center"
      >
        <FileUp class="mx-auto h-10 w-10 text-muted-foreground/40" />
        <p class="mt-2 text-sm text-muted-foreground">暂无导入任务</p>
      </div>

      <Table
        v-else
        class="hidden lg:table"
      >
        <TableHeader>
          <TableRow>
            <TableHead class="w-[24%]">任务</TableHead>
            <TableHead class="w-[20%]">阶段</TableHead>
            <TableHead class="w-[18%]">导入结果</TableHead>
            <TableHead class="w-[18%]">后台子任务</TableHead>
            <TableHead class="w-[12%]">时间</TableHead>
            <TableHead class="w-[8%] text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="job in jobs"
            :key="job.task_id"
            class="cursor-pointer hover:bg-muted/40"
            :class="selectedTaskId === job.task_id ? 'bg-muted/30' : ''"
            @click="selectJob(job.task_id)"
          >
            <TableCell>
              <div class="space-y-1">
                <p class="font-medium">{{ job.task_id }}</p>
                <p class="text-xs text-muted-foreground">{{ job.message || '后台处理中' }}</p>
              </div>
            </TableCell>
            <TableCell>
              <div class="space-y-1">
                <Badge :variant="statusVariant(job.status)">{{ statusLabel(job.status) }}</Badge>
                <p class="text-xs text-muted-foreground">{{ stageLabel(job.stage) }}</p>
              </div>
            </TableCell>
            <TableCell>
              <div class="space-y-1 text-xs text-muted-foreground">
                <p>Provider {{ job.import_result?.stats.providers_created ?? 0 }}</p>
                <p>Endpoint {{ job.import_result?.stats.endpoints_created ?? 0 }}</p>
                <p>Key {{ job.import_result?.stats.keys_created ?? 0 }}</p>
              </div>
            </TableCell>
            <TableCell>
              <div class="space-y-1 text-xs text-muted-foreground">
                <p>{{ summarizeBackgroundTask(job, 'fetch_models') }}</p>
                <p>{{ summarizeBackgroundTask(job, 'proxy_probe') }}</p>
              </div>
            </TableCell>
            <TableCell>
              <div class="space-y-1 text-xs text-muted-foreground">
                <p>{{ formatDateTime(job.created_at) }}</p>
                <p>{{ formatDateTime(job.updated_at) }}</p>
              </div>
            </TableCell>
            <TableCell class="text-right">
              <Button
                variant="ghost"
                size="sm"
                class="h-7 text-xs"
                @click.stop="selectJob(job.task_id)"
              >
                查看
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <div
        v-if="jobs.length > 0"
        class="divide-y divide-border/50 lg:hidden"
      >
        <div
          v-for="job in jobs"
          :key="`mobile-${job.task_id}`"
          class="space-y-2 p-4"
          @click="selectJob(job.task_id)"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="truncate font-medium">{{ job.task_id }}</p>
              <p class="mt-1 text-xs text-muted-foreground">{{ stageLabel(job.stage) }}</p>
            </div>
            <Badge :variant="statusVariant(job.status)">{{ statusLabel(job.status) }}</Badge>
          </div>
          <p class="text-xs text-muted-foreground">{{ job.message || '后台处理中' }}</p>
        </div>
      </div>
    </Card>

    <Card
      v-if="selectedJob"
      class="overflow-hidden"
    >
      <div class="border-b border-border/60 px-4 py-3.5">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="text-base font-semibold">任务详情</h3>
            <p class="mt-1 text-xs text-muted-foreground">{{ selectedJob.task_id }}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            class="text-xs"
            @click="refreshSelectedJob"
          >
            刷新当前任务
          </Button>
        </div>
      </div>

      <div class="space-y-6 px-4 py-4">
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div
            v-for="task in selectedJob.background_tasks"
            :key="task.key"
            class="rounded-lg border border-border/60 p-3"
          >
            <p class="text-sm font-medium">{{ task.label }}</p>
            <p class="mt-1 text-xs text-muted-foreground">{{ task.message || '无详情' }}</p>
            <p class="mt-2 text-xs text-muted-foreground">{{ statusLabel(task.status) }} · {{ task.completed }}/{{ task.total }} · 失败 {{ task.failed }}</p>
          </div>
        </div>

        <div class="grid gap-3 md:grid-cols-4">
          <div class="rounded-lg border border-border/60 p-3">
            <p class="text-xs text-muted-foreground">新增 Provider</p>
            <p class="mt-1 text-lg font-semibold">{{ selectedJob.import_result?.stats.providers_created ?? 0 }}</p>
          </div>
          <div class="rounded-lg border border-border/60 p-3">
            <p class="text-xs text-muted-foreground">新增 Endpoint</p>
            <p class="mt-1 text-lg font-semibold">{{ selectedJob.import_result?.stats.endpoints_created ?? 0 }}</p>
          </div>
          <div class="rounded-lg border border-border/60 p-3">
            <p class="text-xs text-muted-foreground">新增 Key</p>
            <p class="mt-1 text-lg font-semibold">{{ selectedJob.import_result?.stats.keys_created ?? 0 }}</p>
          </div>
          <div class="rounded-lg border border-border/60 p-3">
            <p class="text-xs text-muted-foreground">自动执行任务</p>
            <p class="mt-1 text-lg font-semibold">{{ selectedJob.execution_result?.total_selected ?? 0 }}</p>
          </div>
        </div>

        <div class="grid gap-6 xl:grid-cols-2">
          <div class="rounded-lg border border-border/60">
            <div class="border-b border-border/60 px-4 py-3">
              <p class="text-sm font-medium">待人工处理 / 复核</p>
            </div>
            <div
              v-if="(selectedJob.import_result?.manual_items.length || 0) === 0"
              class="px-4 py-6 text-sm text-muted-foreground"
            >
              当前没有待人工处理项。
            </div>
            <div
              v-else
              class="divide-y divide-border/50"
            >
              <div
                v-for="item in selectedJob.import_result?.manual_items || []"
                :key="`${item.item_type}-${item.provider_website}-${item.source_id}`"
                class="px-4 py-3"
              >
                <p class="text-sm font-medium">{{ item.provider_name }}</p>
                <p class="mt-1 text-xs text-muted-foreground">{{ item.reason || item.status }}</p>
                <p class="mt-1 text-xs text-muted-foreground">{{ item.provider_website }}</p>
              </div>
            </div>
          </div>

          <div class="rounded-lg border border-border/60">
            <div class="border-b border-border/60 px-4 py-3">
              <p class="text-sm font-medium">Provider 异常列表</p>
            </div>
            <div
              v-if="selectedJob.provider_issues.length === 0"
              class="px-4 py-6 text-sm text-muted-foreground"
            >
              当前没有 Provider 级异常。
            </div>
            <div
              v-else
              class="divide-y divide-border/50"
            >
              <div
                v-for="issue in selectedJob.provider_issues"
                :key="`${issue.provider_id || issue.provider_name}-${issue.status}-${issue.mode}`"
                class="flex items-start justify-between gap-3 px-4 py-3"
              >
                <div class="min-w-0">
                  <p class="text-sm font-medium">{{ issue.provider_name }}</p>
                  <p class="mt-1 text-xs text-muted-foreground">{{ issue.mode || issue.status }} · {{ issue.message || '无详情' }}</p>
                </div>
                <Button
                  v-if="issue.provider_id"
                  variant="outline"
                  size="sm"
                  class="h-7 text-xs"
                  @click="openProvider(issue.provider_id)"
                >
                  查看 Provider
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>

    <ProviderDetailDrawer
      :open="providerDrawerOpen"
      :provider-id="selectedProviderId"
      @update:open="providerDrawerOpen = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FileUp, Loader2, RefreshCw } from 'lucide-vue-next'

import Button from '@/components/ui/button.vue'
import Card from '@/components/ui/card.vue'
import Table from '@/components/ui/table.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableCell from '@/components/ui/table-cell.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableRow from '@/components/ui/table-row.vue'
import Badge from '@/components/ui/badge.vue'
import ProviderDetailDrawer from '@/features/providers/components/ProviderDetailDrawer.vue'
import {
  getAllInHubImportJob,
  listAllInHubImportJobs,
  type AllInHubImportBackgroundTaskStatus,
  type AllInHubImportJobStatusResponse,
} from '@/api/endpoints'
import { useToast } from '@/composables/useToast'
import { parseApiError } from '@/utils/errorParser'

const { error: showError } = useToast()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const jobs = ref<AllInHubImportJobStatusResponse[]>([])
const selectedTaskId = ref<string>('')
const providerDrawerOpen = ref(false)
const selectedProviderId = ref<string | null>(null)

let refreshTimer: ReturnType<typeof setTimeout> | null = null

const selectedJob = computed(() =>
  jobs.value.find((job) => job.task_id === selectedTaskId.value) || null,
)

const runningJobsCount = computed(() =>
  jobs.value.filter((job) => ['pending', 'running'].includes(job.status)).length,
)

const manualItemsCount = computed(() =>
  jobs.value.reduce((sum, job) => sum + (job.import_result?.manual_items.length || 0), 0),
)

const providerIssuesCount = computed(() =>
  jobs.value.reduce((sum, job) => sum + job.provider_issues.length, 0),
)

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function statusLabel(status: string): string {
  if (status === 'running') return '进行中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'cancelled') return '已取消'
  if (status === 'pending') return '等待中'
  return status
}

function statusVariant(status: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (status === 'completed') return 'default'
  if (status === 'failed') return 'destructive'
  if (status === 'running') return 'outline'
  return 'secondary'
}

function stageLabel(stage: string): string {
  const mapping: Record<string, string> = {
    queued: '已排队',
    importing: '导入 Provider/Endpoint/Key',
    executing_tasks: '执行导入后任务',
    fetching_models: '抓取上游模型',
    probing_proxies: '代理检测',
    completed: '已完成',
    failed: '失败',
  }
  return mapping[stage] || stage
}

function summarizeBackgroundTask(
  job: AllInHubImportJobStatusResponse,
  key: string,
): string {
  const task = job.background_tasks.find((item) => item.key === key)
  if (!task) return '-'
  return `${task.label}: ${task.completed}/${task.total}，失败 ${task.failed}`
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearTimeout(refreshTimer)
    refreshTimer = null
  }
}

function scheduleAutoRefresh() {
  stopAutoRefresh()
  if (!jobs.value.some((job) => ['pending', 'running'].includes(job.status))) return
  refreshTimer = setTimeout(() => {
    void refreshJobs()
  }, 5000)
}

async function refreshJobs() {
  loading.value = true
  try {
    const response = await listAllInHubImportJobs(30)
    jobs.value = response.items

    const routeTask = typeof route.query.task === 'string' ? route.query.task : ''
    if (routeTask && jobs.value.some((job) => job.task_id === routeTask)) {
      selectedTaskId.value = routeTask
    } else if (!selectedTaskId.value && jobs.value.length > 0) {
      selectedTaskId.value = jobs.value[0].task_id
    } else if (selectedTaskId.value && !jobs.value.some((job) => job.task_id === selectedTaskId.value)) {
      selectedTaskId.value = jobs.value[0]?.task_id || ''
    }

    if (selectedTaskId.value) {
      await refreshSelectedJob(false)
    }
  } catch (err: unknown) {
    showError(parseApiError(err, '加载导入任务失败'), '错误')
  } finally {
    loading.value = false
    scheduleAutoRefresh()
  }
}

async function refreshSelectedJob(showLoading = true) {
  if (!selectedTaskId.value) return
  if (showLoading) {
    loading.value = true
  }
  try {
    const detail = await getAllInHubImportJob(selectedTaskId.value)
    const nextJobs = jobs.value.slice()
    const index = nextJobs.findIndex((job) => job.task_id === detail.task_id)
    if (index >= 0) {
      nextJobs[index] = detail
    } else {
      nextJobs.unshift(detail)
    }
    jobs.value = nextJobs
  } catch (err: unknown) {
    showError(parseApiError(err, '加载任务详情失败'), '错误')
  } finally {
    if (showLoading) {
      loading.value = false
    }
  }
}

function selectJob(taskId: string) {
  selectedTaskId.value = taskId
  void router.replace({ query: { ...route.query, task: taskId } })
  void refreshSelectedJob()
}

function openProvider(providerId: string) {
  selectedProviderId.value = providerId
  providerDrawerOpen.value = true
}

watch(
  () => route.query.task,
  (value) => {
    if (typeof value === 'string' && value && value !== selectedTaskId.value) {
      selectedTaskId.value = value
      void refreshSelectedJob()
    }
  },
  { immediate: true },
)

onMounted(() => {
  void refreshJobs()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>
