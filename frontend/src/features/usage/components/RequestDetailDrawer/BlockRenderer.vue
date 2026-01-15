<template>
  <div class="block-renderer">
    <template
      v-for="(block, index) in blocks"
      :key="index"
    >
      <!-- 文本块 -->
      <pre
        v-if="block.type === 'text'"
        class="render-block text-block"
        :class="[block.className, { 'pre-wrap': block.preWrap !== false }]"
      >{{ block.content }}</pre>

      <!-- 可折叠块 -->
      <details
        v-else-if="block.type === 'collapsible'"
        class="render-block collapsible-block"
        :class="block.className"
        :open="block.defaultOpen"
      >
        <summary class="collapsible-summary">
          <ChevronRight class="w-4 h-4 chevron" />
          <span class="text-muted-foreground">{{ block.title }}</span>
        </summary>
        <div class="collapsible-content">
          <BlockRenderer :blocks="block.content" />
        </div>
      </details>

      <!-- 代码块 -->
      <div
        v-else-if="block.type === 'code'"
        class="render-block code-block"
      >
        <div
          v-if="block.language"
          class="code-language"
        >
          {{ block.language }}
        </div>
        <pre
          class="code-content"
          :style="block.maxHeight ? { maxHeight: `${block.maxHeight}px` } : {}"
        >{{ block.code }}</pre>
      </div>

      <!-- 徽章块 -->
      <Badge
        v-else-if="block.type === 'badge'"
        :variant="block.variant || 'secondary'"
        class="render-block badge-block"
      >
        {{ block.label }}
      </Badge>

      <!-- 图片块 -->
      <div
        v-else-if="block.type === 'image'"
        class="render-block image-block"
      >
        <img
          v-if="block.src"
          :src="block.src"
          :alt="block.alt || '图片'"
          class="rendered-image"
        >
        <div
          v-else
          class="image-placeholder"
        >
          <ImageIcon class="w-6 h-6" />
          <span>{{ block.mimeType || block.alt || '图片' }}</span>
        </div>
      </div>

      <!-- 错误块 -->
      <div
        v-else-if="block.type === 'error'"
        class="render-block error-block"
      >
        <AlertCircle class="w-4 h-4" />
        <span>{{ block.message }}</span>
        <span
          v-if="block.code"
          class="error-code"
        >{{ block.code }}</span>
      </div>

      <!-- 容器块 -->
      <div
        v-else-if="block.type === 'container'"
        class="render-block container-block"
        :class="block.className"
      >
        <div
          v-if="block.header"
          class="container-header"
        >
          <BlockRenderer :blocks="block.header" />
        </div>
        <div class="container-content">
          <BlockRenderer :blocks="block.children" />
        </div>
      </div>

      <!-- 消息块 -->
      <div
        v-else-if="block.type === 'message'"
        class="render-block message-block"
        :class="block.role"
      >
        <div class="message-header">
          <component
            :is="getRoleIcon(block.role)"
            class="w-3.5 h-3.5"
          />
          <span>{{ block.roleLabel || getRoleLabel(block.role) }}</span>
          <template v-if="block.badges">
            <Badge
              v-for="(badge, badgeIndex) in block.badges"
              :key="badgeIndex"
              :variant="badge.variant || 'secondary'"
              class="ml-2 text-xs"
            >
              {{ badge.label }}
            </Badge>
          </template>
        </div>
        <div class="message-content">
          <BlockRenderer :blocks="block.content" />
        </div>
      </div>

      <!-- 工具调用块 -->
      <div
        v-else-if="block.type === 'tool_use'"
        class="render-block tool-block"
      >
        <div class="tool-header">
          <Wrench class="w-3 h-3" />
          <span>{{ block.toolName }}</span>
          <span
            v-if="block.toolId"
            class="tool-id"
          >{{ block.toolId }}</span>
        </div>
        <pre class="tool-content">{{ block.input }}</pre>
      </div>

      <!-- 工具结果块 -->
      <div
        v-else-if="block.type === 'tool_result'"
        class="render-block tool-result-block"
        :class="{ 'is-error': block.isError }"
      >
        <div class="tool-header">
          <FileText class="w-3 h-3" />
          <span>工具结果</span>
          <Badge
            v-if="block.isError"
            variant="destructive"
            class="ml-2 text-xs"
          >
            错误
          </Badge>
        </div>
        <pre class="tool-content">{{ block.content }}</pre>
      </div>

      <!-- 分隔符块 -->
      <hr
        v-else-if="block.type === 'divider'"
        class="render-block divider-block"
      >

      <!-- 标签块 -->
      <div
        v-else-if="block.type === 'label'"
        class="render-block label-block"
      >
        <span class="label-key">{{ block.label }}:</span>
        <span
          class="label-value"
          :class="{ mono: block.mono }"
        >{{ block.value }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { User, Bot, Settings, Wrench, AlertCircle, ChevronRight, FileText, Image as ImageIcon } from 'lucide-vue-next'
import Badge from '@/components/ui/badge.vue'
import type { RenderBlock } from '../../conversation'

defineProps<{
  blocks: RenderBlock[]
}>()

const getRoleIcon = (role: string) => {
  switch (role) {
    case 'user':
      return User
    case 'assistant':
      return Bot
    case 'system':
      return Settings
    case 'tool':
      return Wrench
    default:
      return User
  }
}

const getRoleLabel = (role: string) => {
  switch (role) {
    case 'user':
      return 'User'
    case 'assistant':
      return 'Assistant'
    case 'system':
      return 'System'
    case 'tool':
      return 'Tool'
    default:
      return role
  }
}
</script>

<style scoped>
.block-renderer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 通用渲染块样式 */
.render-block {
  border-radius: 6px;
}

/* 文本块 */
.text-block {
  margin: 0;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
}

.text-block.pre-wrap {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 可折叠块 */
.collapsible-block {
  cursor: pointer;
  background: hsl(var(--muted) / 0.3);
  padding: 8px 12px;
}

.collapsible-summary {
  display: flex;
  align-items: center;
  gap: 4px;
  list-style: none;
  user-select: none;
}

.collapsible-summary::-webkit-details-marker {
  display: none;
}

.collapsible-summary .chevron {
  transition: transform 0.2s;
}

.collapsible-block[open] .chevron {
  transform: rotate(90deg);
}

.collapsible-content {
  margin-top: 8px;
  padding: 12px;
  background: hsl(var(--muted) / 0.5);
  border-radius: 6px;
}

/* 代码块 */
.code-block {
  background: hsl(var(--muted) / 0.5);
  overflow: hidden;
}

.code-language {
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 500;
  background: hsl(var(--muted) / 0.5);
  color: hsl(var(--muted-foreground));
  border-bottom: 1px solid hsl(var(--border));
}

.code-content {
  margin: 0;
  padding: 12px;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 徽章块 */
.badge-block {
  display: inline-flex;
}

/* 图片块 */
.image-block {
  background: hsl(var(--muted) / 0.3);
  padding: 12px;
}

.rendered-image {
  max-width: 100%;
  max-height: 400px;
  border-radius: 4px;
}

.image-placeholder {
  display: flex;
  align-items: center;
  gap: 8px;
  color: hsl(var(--muted-foreground));
  font-size: 12px;
}

/* 错误块 */
.error-block {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: hsl(var(--destructive) / 0.1);
  border: 1px solid hsl(var(--destructive) / 0.2);
  color: hsl(var(--destructive));
  font-size: 13px;
}

.error-code {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 11px;
  opacity: 0.8;
}

/* 容器块 */
.container-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.container-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 消息块 */
.message-block {
  border-radius: 8px;
  overflow: hidden;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
}

.message-content {
  padding: 0 12px 12px;
  font-size: 13px;
  line-height: 1.6;
}

/* User 消息样式 */
.message-block.user {
  background: hsl(var(--primary) / 0.08);
  border: 1px solid hsl(var(--primary) / 0.2);
}

.message-block.user .message-header {
  color: hsl(var(--primary));
}

/* Assistant 消息样式 */
.message-block.assistant {
  background: hsl(var(--muted) / 0.5);
  border: 1px solid hsl(var(--border));
}

.message-block.assistant .message-header {
  color: hsl(var(--foreground));
}

/* System 消息样式 */
.message-block.system {
  background: hsl(var(--muted) / 0.3);
  border: 1px dashed hsl(var(--border));
}

.message-block.system .message-header {
  color: hsl(var(--muted-foreground));
}

/* Tool 消息样式 */
.message-block.tool {
  background: hsl(var(--muted) / 0.3);
  border: 1px solid hsl(var(--border));
}

/* 工具调用块 */
.tool-block,
.tool-result-block {
  background: hsl(var(--muted) / 0.3);
  padding: 8px 12px;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 8px;
  color: hsl(var(--muted-foreground));
}

.tool-id {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 10px;
  opacity: 0.6;
}

.tool-content {
  margin: 0;
  padding: 12px;
  background: hsl(var(--muted) / 0.5);
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.tool-result-block.is-error {
  background: hsl(var(--destructive) / 0.1);
  border: 1px solid hsl(var(--destructive) / 0.2);
}

/* 分隔符块 */
.divider-block {
  border: none;
  border-top: 1px solid hsl(var(--border));
  margin: 8px 0;
}

/* 标签块 */
.label-block {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.label-key {
  color: hsl(var(--muted-foreground));
}

.label-value.mono {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
