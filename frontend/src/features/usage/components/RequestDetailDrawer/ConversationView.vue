<template>
  <div class="conversation-view-wrapper">
    <div class="conversation-view-content">
      <!-- 渲染错误提示 -->
      <div
        v-if="renderResult.error"
        class="render-error"
      >
        <AlertCircle class="w-4 h-4" />
        <span>{{ renderResult.error }}</span>
      </div>

      <!-- 空内容提示 -->
      <div
        v-else-if="renderResult.blocks.length === 0"
        class="text-sm text-muted-foreground"
      >
        {{ emptyMessage }}
      </div>

      <!-- 渲染内容块 -->
      <template v-else>
        <BlockRenderer :blocks="renderResult.blocks" />

        <!-- 流式响应标记 -->
        <div
          v-if="renderResult.isStream"
          class="stream-indicator"
        >
          <Zap class="w-3 h-3" />
          <span>流式响应</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { AlertCircle, Zap } from 'lucide-vue-next'
import BlockRenderer from './BlockRenderer.vue'
import type { RenderResult } from '../../conversation'

defineProps<{
  renderResult: RenderResult
  emptyMessage: string
}>()
</script>

<style scoped>
.conversation-view-wrapper {
  max-height: 500px;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.conversation-view-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px;
}

.render-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: hsl(var(--destructive) / 0.1);
  border: 1px solid hsl(var(--destructive) / 0.3);
  border-radius: 8px;
  color: hsl(var(--destructive));
  font-size: 13px;
}

/* 流式响应标记 */
.stream-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  font-size: 11px;
  color: hsl(var(--muted-foreground));
  background: hsl(var(--muted) / 0.3);
  border-radius: 4px;
  width: fit-content;
}
</style>
