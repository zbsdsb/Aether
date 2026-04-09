<template>
  <Card class="flex h-full min-h-[720px] flex-col overflow-hidden">
    <div class="flex items-center justify-between border-b border-border/60 px-4 py-3.5">
      <div>
        <h3 class="text-base font-semibold">对话</h3>
        <p class="mt-1 text-xs text-muted-foreground">{{ statusText }}</p>
      </div>
      <Badge :variant="statusVariant">
        {{ statusBadge }}
      </Badge>
    </div>

    <div class="flex-1 space-y-3 overflow-y-auto bg-muted/10 p-4">
      <div
        v-if="messages.length === 0"
        class="flex h-full min-h-[320px] items-center justify-center rounded-2xl border border-dashed border-border/60 bg-background/60 text-center"
      >
        <div class="space-y-2 px-6">
          <p class="text-sm font-medium text-foreground">还没有发送测试消息</p>
          <p class="text-xs text-muted-foreground">选择模型和协议后，在底部输入框里发送第一条消息。</p>
        </div>
      </div>

      <div
        v-for="(message, index) in messages"
        :key="`${message.role}-${index}`"
        class="flex"
        :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <div
          class="max-w-[88%] rounded-3xl border px-4 py-3 shadow-sm"
          :class="message.role === 'user'
            ? 'border-primary/20 bg-primary/10 text-primary'
            : 'border-border/60 bg-background text-foreground'"
        >
          <div class="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] opacity-70">
            {{ message.role === 'user' ? 'User' : 'Assistant' }}
          </div>
          <p class="whitespace-pre-wrap text-sm leading-6">{{ message.content }}</p>
        </div>
      </div>

      <div
        v-if="lastError"
        class="rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
      >
        <p class="font-medium">本轮测试失败</p>
        <p class="mt-1 whitespace-pre-wrap text-xs leading-5">{{ lastError }}</p>
      </div>
    </div>

    <div class="border-t border-border/60 bg-background px-4 py-4">
      <div class="space-y-3">
        <Textarea
          :model-value="draftInput"
          class="min-h-[120px]"
          placeholder="输入测试问题，发送到当前模型操练场..."
          @update:model-value="$emit('update:draftInput', String($event ?? ''))"
        />

        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="text-xs text-muted-foreground">
            {{ helperText }}
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              :disabled="sending"
              @click="$emit('retry')"
            >
              重试上次
            </Button>
            <Button
              variant="outline"
              :disabled="!sending"
              @click="$emit('stop')"
            >
              停止
            </Button>
            <Button
              variant="ghost"
              :disabled="sending && messages.length === 0"
              @click="$emit('clear')"
            >
              清空
            </Button>
            <Button
              :disabled="!canSend || sending"
              @click="$emit('send')"
            >
              {{ sending ? '发送中...' : '发送' }}
            </Button>
          </div>
        </div>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import type { PlaygroundMessage } from '../types'

import { Badge, Button, Card, Textarea } from '@/components/ui'

interface Props {
  messages: PlaygroundMessage[]
  draftInput: string
  canSend: boolean
  sending: boolean
  statusBadge: string
  statusText: string
  statusVariant: 'default' | 'secondary' | 'destructive' | 'outline' | 'success'
  helperText: string
  lastError: string
}

defineProps<Props>()

defineEmits<{
  'update:draftInput': [string]
  send: []
  stop: []
  retry: []
  clear: []
}>()
</script>
