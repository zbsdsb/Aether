<template>
  <Dialog
    :open="open"
    title="导入 All-in-Hub"
    description="解析导出文件，创建 Provider 与 openai:chat Endpoint，并导入可直接使用的明文 API Key。缺少明文 Key 的来源会保留在报告里。"
    @update:open="$emit('update:open', $event)"
  >
    <div class="space-y-4">
      <JsonImportInput
        :model-value="content"
        :disabled="loading"
        :multiple="false"
        accept=".json,application/json,text/plain"
        drop-title="拖入 all-in-hub 导出文件或点击选择"
        drop-hint="支持 .json，单文件导入"
        manual-label="导出内容"
        manual-placeholder="粘贴 all-in-hub 导出 JSON"
        manual-description="预览不会落库；确认导入后只创建可确定的 Provider / Endpoint / 明文 Key。"
        @update:model-value="$emit('update:content', $event)"
        @error="$emit('error', $event.message)"
      />

      <div
        v-if="jobStatus"
        class="space-y-3 rounded-xl border border-primary/20 bg-primary/5 p-4"
      >
        <div class="flex items-start justify-between gap-3 text-sm">
          <div class="min-w-0">
            <p class="font-medium">后台导入任务</p>
            <p class="mt-1 text-xs text-muted-foreground">
              {{ jobStatus.stage }} · {{ jobStatus.message || '后台处理中' }}
            </p>
          </div>
          <div class="shrink-0 text-right text-xs text-muted-foreground">
            <p>{{ jobStatus.status }}</p>
            <p class="mt-1 font-mono">{{ jobStatus.task_id }}</p>
          </div>
        </div>
        <div
          v-if="jobStatus.background_tasks.length > 0"
          class="grid gap-2 sm:grid-cols-2"
        >
          <div
            v-for="task in jobStatus.background_tasks"
            :key="task.key"
            class="rounded-lg border border-border/50 bg-background/70 p-3"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-sm font-medium">{{ task.label }}</p>
                <p class="mt-1 text-xs text-muted-foreground">
                  {{ task.message || getBackgroundTaskDefaultMessage(task) }}
                </p>
              </div>
              <p
                class="shrink-0 text-xs font-medium"
                :class="getBackgroundTaskStatusClass(task.status)"
              >
                {{ getBackgroundTaskStatusLabel(task.status) }}
              </p>
            </div>
            <p class="mt-2 text-xs text-muted-foreground">
              {{ task.completed }}/{{ task.total }}，失败 {{ task.failed }}
            </p>
          </div>
        </div>
      </div>

      <div
        v-if="preview"
        class="space-y-4"
      >
        <div class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
          <div class="rounded-xl border border-border/60 bg-muted/20 p-3">
            <p class="text-xs text-muted-foreground">站点</p>
            <p class="mt-1 text-lg font-semibold">{{ preview.stats.providers_total }}</p>
          </div>
          <div class="rounded-xl border border-border/60 bg-muted/20 p-3">
            <p class="text-xs text-muted-foreground">待建 Provider</p>
            <p class="mt-1 text-lg font-semibold">{{ preview.stats.providers_to_create || preview.stats.providers_created }}</p>
          </div>
          <div class="rounded-xl border border-border/60 bg-muted/20 p-3">
            <p class="text-xs text-muted-foreground">待建 Endpoint</p>
            <p class="mt-1 text-lg font-semibold">{{ preview.stats.endpoints_to_create || preview.stats.endpoints_created }}</p>
          </div>
          <div class="rounded-xl border border-border/60 bg-muted/20 p-3">
            <p class="text-xs text-muted-foreground">可直导 Key</p>
            <p class="mt-1 text-lg font-semibold">{{ preview.stats.direct_keys_ready }}</p>
          </div>
          <div class="rounded-xl border border-border/60 bg-muted/20 p-3">
            <p class="text-xs text-muted-foreground">待补钥来源</p>
            <p class="mt-1 text-lg font-semibold">{{ preview.stats.pending_sources }}</p>
          </div>
          <div class="rounded-xl border border-border/60 bg-muted/20 p-3">
            <p class="text-xs text-muted-foreground">{{ preview.dry_run ? '预估新建 Key' : '已创建 Key' }}</p>
            <p class="mt-1 text-lg font-semibold">{{ preview.dry_run ? preview.stats.direct_keys_ready : preview.stats.keys_created }}</p>
          </div>
        </div>

        <div
          v-if="preview.warnings.length > 0"
          class="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm"
        >
          <p class="font-medium text-amber-700 dark:text-amber-300">导入提示</p>
          <ul class="mt-2 space-y-1 text-amber-700/90 dark:text-amber-200/90">
            <li
              v-for="warning in preview.warnings"
              :key="warning"
            >
              {{ warning }}
            </li>
          </ul>
        </div>

        <div class="rounded-xl border border-border/60">
          <div class="border-b border-border/60 px-4 py-3">
            <p class="text-sm font-medium">站点预览</p>
          </div>
          <div class="divide-y divide-border/40">
            <div
              v-for="provider in preview.providers"
              :key="`${provider.provider_website}-${provider.endpoint_base_url}`"
              class="px-4 py-3 text-sm"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="font-medium">{{ provider.provider_name }}</p>
                  <p class="mt-0.5 truncate text-xs text-muted-foreground">{{ provider.provider_website }}</p>
                  <p class="mt-1 truncate font-mono text-[11px] text-muted-foreground">{{ provider.endpoint_base_url }}</p>
                </div>
                <div class="shrink-0 text-right text-xs text-muted-foreground">
                  <p>直导 Key: {{ provider.direct_key_count }}</p>
                  <p class="mt-1">待补钥: {{ provider.pending_source_count }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="preview.manual_items.length > 0"
          class="rounded-xl border border-amber-500/20 bg-amber-500/5"
        >
          <div class="border-b border-amber-500/20 px-4 py-3">
            <p class="text-sm font-medium">待人工处理</p>
            <p class="mt-1 text-xs text-muted-foreground">缺明文或需要人工复核的站点会保留在这里，导入后可继续人工处理。</p>
          </div>
          <div class="divide-y divide-border/40">
            <div
              v-for="item in preview.manual_items"
              :key="`${item.item_type}-${item.provider_website}-${item.source_id}`"
              class="px-4 py-3 text-sm"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="font-medium">{{ item.provider_name }}</p>
                  <p class="mt-0.5 truncate text-xs text-muted-foreground">{{ item.provider_website }}</p>
                  <p class="mt-1 truncate font-mono text-[11px] text-muted-foreground">{{ item.endpoint_base_url }}</p>
                  <p
                    v-if="item.reason"
                    class="mt-2 text-xs text-amber-700 dark:text-amber-300"
                  >
                    {{ item.reason }}
                  </p>
                </div>
                <div class="shrink-0 text-right text-xs text-muted-foreground">
                  <p>{{ item.status }}</p>
                  <p class="mt-1">{{ item.task_type || item.item_type }}</p>
                  <p
                    v-if="item.site_type"
                    class="mt-1"
                  >
                    {{ item.site_type }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="executionResult"
        class="space-y-4 rounded-xl border border-border/60 bg-muted/10 p-4"
      >
        <div class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div class="rounded-xl border border-border/60 bg-background/80 p-3">
            <p class="text-xs text-muted-foreground">本次执行</p>
            <p class="mt-1 text-lg font-semibold">{{ executionResult.total_selected }}</p>
          </div>
          <div class="rounded-xl border border-border/60 bg-background/80 p-3">
            <p class="text-xs text-muted-foreground">成功补钥</p>
            <p class="mt-1 text-lg font-semibold">{{ executionResult.completed }}</p>
          </div>
          <div class="rounded-xl border border-border/60 bg-background/80 p-3">
            <p class="text-xs text-muted-foreground">新建 Key</p>
            <p class="mt-1 text-lg font-semibold">{{ executionResult.keys_created }}</p>
          </div>
          <div class="rounded-xl border border-border/60 bg-background/80 p-3">
            <p class="text-xs text-muted-foreground">失败</p>
            <p class="mt-1 text-lg font-semibold">{{ executionResult.failed }}</p>
          </div>
        </div>

        <div
          v-if="executionResult.results.length > 0"
          class="rounded-xl border border-border/60"
        >
          <div class="border-b border-border/60 px-4 py-3">
            <p class="text-sm font-medium">补钥结果</p>
          </div>
          <div class="divide-y divide-border/40">
            <div
              v-for="item in executionResult.results"
              :key="item.task_id"
              class="px-4 py-3 text-sm"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="font-medium">{{ item.task_id }}</p>
                  <p
                    v-if="item.last_error"
                    class="mt-1 text-xs text-destructive"
                  >
                    {{ item.last_error }}
                  </p>
                </div>
                <div class="shrink-0 text-right text-xs text-muted-foreground">
                  <p>{{ item.status }}</p>
                  <p
                    v-if="item.result_key_id"
                    class="mt-1 font-mono text-[11px]"
                  >
                    {{ item.result_key_id }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <Button
        variant="outline"
        @click="$emit('update:open', false)"
      >
        关闭
      </Button>
      <Button
        variant="outline"
        :disabled="loading || !content.trim()"
        @click="$emit('preview')"
      >
        {{ loading ? '处理中...' : '预览导入' }}
      </Button>
      <Button
        :disabled="loading || !preview || !content.trim() || importInFlight"
        @click="$emit('confirm')"
      >
        {{ importInFlight ? '任务执行中' : loading ? '处理中...' : '确认导入' }}
      </Button>
      <Button
        v-if="jobStatus"
        variant="outline"
        @click="$emit('view-task', jobStatus.task_id)"
      >
        查看导入任务
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import JsonImportInput from '@/components/common/JsonImportInput.vue'
import Button from '@/components/ui/button.vue'
import { Dialog } from '@/components/ui'
import type {
  AllInHubImportBackgroundTaskStatus,
  AllInHubImportJobStatusResponse,
  AllInHubImportResponse,
  AllInHubTaskExecutionResponse,
} from '@/api/endpoints'

function getBackgroundTaskStatusLabel(status: string): string {
  if (status === 'running') return '进行中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'skipped') return '已跳过'
  return '等待中'
}

function getBackgroundTaskStatusClass(status: string): string {
  if (status === 'running') return 'text-primary'
  if (status === 'completed') return 'text-green-600 dark:text-green-400'
  if (status === 'failed') return 'text-destructive'
  return 'text-muted-foreground'
}

function getBackgroundTaskDefaultMessage(task: AllInHubImportBackgroundTaskStatus): string {
  if (task.status === 'pending') return '等待执行'
  if (task.status === 'completed') return '后台处理已完成'
  if (task.status === 'failed') return '后台处理失败'
  return '后台处理中'
}

const props = defineProps<{
  open: boolean
  content: string
  jobStatus: AllInHubImportJobStatusResponse | null
  preview: AllInHubImportResponse | null
  executionResult: AllInHubTaskExecutionResponse | null
  loading: boolean
}>()

const importInFlight = computed(() =>
  !!props.jobStatus && ['pending', 'running'].includes(props.jobStatus.status),
)

defineEmits<{
  preview: []
  confirm: []
  'view-task': [taskId: string]
  error: [message: string]
  'update:open': [value: boolean]
  'update:content': [value: string]
}>()
</script>
