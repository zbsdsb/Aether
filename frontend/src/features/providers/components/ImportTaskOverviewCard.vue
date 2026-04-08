<template>
  <Card
    v-if="visible"
    class="border-amber-500/30 bg-amber-500/5"
  >
    <div class="px-5 py-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="text-sm font-semibold text-foreground">
            导入待处理提醒
          </div>
        </div>
        <Button
          size="icon"
          variant="ghost"
          class="h-8 w-8 shrink-0"
          title="关闭提醒"
          @click="dismissed = true"
        >
          <X class="h-4 w-4" />
        </Button>
      </div>
      <div class="mt-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div class="min-w-0">
          <div class="mt-1 text-xs text-muted-foreground">
            待补钥 Provider {{ overview.providers_needing_manual_key_input }} 个，待复核 Provider {{ overview.providers_needing_manual_review }} 个。
          </div>
          <div class="mt-2 text-xs text-muted-foreground">
            等待人工补明文 {{ overview.tasks_waiting_plaintext }} 条，自动补钥失败 {{ overview.tasks_failed }} 条。
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            @click="$emit('viewImportTasks')"
          >
            导入任务页
          </Button>
          <Button
            size="sm"
            variant="outline"
            @click="$emit('selectNeedsKey')"
          >
            查看待补钥
          </Button>
          <Button
            size="sm"
            variant="outline"
            @click="$emit('selectManualReview')"
          >
            查看待复核
          </Button>
          <Button
            v-if="activeFilter !== 'all'"
            size="sm"
            variant="ghost"
            @click="$emit('clearFilter')"
          >
            清除导入筛选
          </Button>
        </div>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'

import Button from '@/components/ui/button.vue'
import Card from '@/components/ui/card.vue'
import type { ProviderImportTaskOverview } from '@/api/endpoints'
import {
  hasActionableImportTasks,
  shouldResetImportTaskOverviewDismissed,
} from '@/features/providers/utils/import-task-overview'

const props = defineProps<{
  overview: ProviderImportTaskOverview
  activeFilter: string
}>()

const dismissed = ref(false)

watch(
  () => props.overview,
  (nextOverview, previousOverview) => {
    if (previousOverview && shouldResetImportTaskOverviewDismissed(previousOverview, nextOverview)) {
      dismissed.value = false
    }
    if (!hasActionableImportTasks(nextOverview)) {
      dismissed.value = false
    }
  },
  { deep: true },
)

const visible = computed(() => hasActionableImportTasks(props.overview) && !dismissed.value)

defineEmits<{
  viewImportTasks: []
  selectNeedsKey: []
  selectManualReview: []
  clearFilter: []
}>()
</script>
