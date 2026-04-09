<template>
  <Card class="flex h-full min-h-[720px] flex-col overflow-hidden">
    <div class="border-b border-border/60 px-4 py-3.5">
      <h3 class="text-base font-semibold">调试</h3>
      <p class="mt-1 text-xs text-muted-foreground">{{ modeLabel }}</p>
    </div>

    <div class="flex-1 p-4">
      <Tabs v-model="activeTab">
        <TabsList class="grid w-full grid-cols-3">
          <TabsTrigger value="preview">预览</TabsTrigger>
          <TabsTrigger value="request">请求</TabsTrigger>
          <TabsTrigger value="response">响应</TabsTrigger>
        </TabsList>

        <TabsContent value="preview" class="mt-4">
          <div class="space-y-3">
            <div class="rounded-2xl border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
              协议预览基于当前左栏参数和输入框实时生成，不代表最终路由一定会命中相同 Provider。
            </div>
            <pre class="min-h-[520px] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ previewText }}</pre>
          </div>
        </TabsContent>

        <TabsContent value="request" class="mt-4">
          <div class="space-y-3">
            <div v-if="requestMeta.length > 0" class="flex flex-wrap gap-2">
              <Badge
                v-for="item in requestMeta"
                :key="item"
                variant="secondary"
              >
                {{ item }}
              </Badge>
            </div>
            <pre class="min-h-[520px] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ requestText }}</pre>
          </div>
        </TabsContent>

        <TabsContent value="response" class="mt-4">
          <div class="space-y-3">
            <div
              v-if="lastError"
              class="rounded-2xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
            >
              {{ lastError }}
            </div>
            <pre class="min-h-[520px] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ responseText }}</pre>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { Badge, Card, Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui'

interface Props {
  activeTab: string
  modeLabel: string
  preview: Record<string, unknown> | null
  request: Record<string, unknown> | null
  response: unknown
  requestMeta: string[]
  lastError: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:activeTab': [string]
}>()

const activeTab = computed({
  get: () => props.activeTab,
  set: (value: string) => emit('update:activeTab', value),
})

function prettyPrint(value: unknown, emptyLabel: string): string {
  if (value == null) return emptyLabel
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const previewText = computed(() => prettyPrint(props.preview, '// 暂无预览数据'))
const requestText = computed(() => prettyPrint(props.request, '// 暂无请求数据'))
const responseText = computed(() => prettyPrint(props.response, '// 暂无响应数据'))
</script>
