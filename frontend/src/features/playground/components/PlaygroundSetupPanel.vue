<template>
  <Card class="overflow-hidden">
    <div class="border-b border-border/60 px-4 py-3.5">
      <h3 class="text-base font-semibold">设置</h3>
      <p class="mt-1 text-xs text-muted-foreground">选择测试来源、目标模型、协议和生成参数。</p>
    </div>

    <div class="space-y-5 p-4">
      <div class="space-y-2">
        <Label>测试来源</Label>
        <div class="grid grid-cols-2 gap-2">
          <button
            type="button"
            class="rounded-xl border px-3 py-2 text-sm font-medium transition-colors"
            :class="sourceMode === 'global' ? activeButtonClass : inactiveButtonClass"
            @click="$emit('update:sourceMode', 'global')"
          >
            全局模型
          </button>
          <button
            type="button"
            class="rounded-xl border px-3 py-2 text-sm font-medium transition-colors"
            :class="sourceMode === 'provider' ? activeButtonClass : inactiveButtonClass"
            @click="$emit('update:sourceMode', 'provider')"
          >
            渠道模型
          </button>
        </div>
      </div>

      <div
        v-if="sourceMode === 'global'"
        class="space-y-4"
      >
        <div class="space-y-2">
          <Label>搜索全局模型</Label>
          <Input
            :model-value="globalModelSearch"
            placeholder="搜索模型名称..."
            @update:model-value="$emit('update:globalModelSearch', String($event ?? ''))"
          />
        </div>

        <div class="space-y-2">
          <Label>全局模型</Label>
          <Select
            :model-value="selectedGlobalModelId"
            @update:model-value="$emit('update:selectedGlobalModelId', String($event ?? ''))"
          >
            <SelectTrigger>
              <SelectValue placeholder="选择全局模型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="model in filteredGlobalModels"
                :key="model.id"
                :value="model.id"
              >
                {{ model.display_name || model.name }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p class="text-xs text-muted-foreground">共 {{ filteredGlobalModels.length }} 个活跃模型</p>
        </div>
      </div>

      <div
        v-else
        class="space-y-4"
      >
        <div class="space-y-2">
          <Label>搜索渠道商</Label>
          <Input
            :model-value="providerSearch"
            placeholder="搜索渠道商或站点..."
            @update:model-value="$emit('update:providerSearch', String($event ?? ''))"
          />
        </div>

        <div class="space-y-2">
          <Label>渠道商</Label>
          <Select
            :model-value="selectedProviderId"
            @update:model-value="$emit('update:selectedProviderId', String($event ?? ''))"
          >
            <SelectTrigger>
              <SelectValue placeholder="选择渠道商" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="provider in filteredProviders"
                :key="provider.id"
                :value="provider.id"
              >
                {{ provider.name }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p class="text-xs text-muted-foreground">共 {{ filteredProviders.length }} 个可选渠道</p>
        </div>

        <div class="space-y-2">
          <Label>搜索渠道模型</Label>
          <Input
            :model-value="providerModelSearch"
            placeholder="搜索模型名称..."
            :disabled="!selectedProviderId"
            @update:model-value="$emit('update:providerModelSearch', String($event ?? ''))"
          />
        </div>

        <div class="space-y-2">
          <Label>渠道模型</Label>
          <Select
            :model-value="selectedProviderModelName"
            @update:model-value="$emit('update:selectedProviderModelName', String($event ?? ''))"
          >
            <SelectTrigger>
              <SelectValue placeholder="选择渠道模型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="model in filteredProviderModels"
                :key="`${model.source}:${model.name}`"
                :value="model.name"
              >
                {{ model.name }} · {{ model.source === 'configured' ? '已配置' : '上游发现' }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p class="text-xs text-muted-foreground">共 {{ filteredProviderModels.length }} 个模型</p>
        </div>
      </div>

      <div class="space-y-2">
        <Label>协议 / 输出格式</Label>
        <div class="grid gap-2 sm:grid-cols-2">
          <button
            v-for="option in protocolOptions"
            :key="option.key"
            type="button"
            class="rounded-2xl border px-3 py-3 text-left transition-colors"
            :class="protocol === option.key ? activeButtonClass : inactiveButtonClass"
            @click="$emit('update:protocol', option.key)"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-semibold">{{ option.label }}</span>
              <Badge
                v-if="option.badge"
                :variant="option.badge === '已配置' ? 'success' : option.badge === '高风险' ? 'destructive' : 'secondary'"
              >
                {{ option.badge }}
              </Badge>
            </div>
            <p class="mt-1 text-xs text-muted-foreground">{{ option.description }}</p>
          </button>
        </div>
        <p
          v-if="protocolWarning"
          class="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300"
        >
          {{ protocolWarning }}
        </p>
      </div>

      <div class="space-y-2">
        <Label>System Prompt</Label>
        <Textarea
          :model-value="systemPrompt"
          class="min-h-[120px]"
          placeholder="可选的系统提示词。"
          @update:model-value="$emit('update:systemPrompt', String($event ?? ''))"
        />
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <Label>流式输出</Label>
            <Switch
              :model-value="stream"
              @update:model-value="$emit('update:stream', Boolean($event))"
            />
          </div>
          <p class="text-xs text-muted-foreground">默认开启，便于观察真实响应过程。</p>
        </div>

        <div class="space-y-2">
          <Label>思考深度</Label>
          <Select
            :model-value="reasoningEffort"
            @update:model-value="$emit('update:reasoningEffort', String($event ?? ''))"
          >
            <SelectTrigger>
              <SelectValue placeholder="选择思考深度" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">low</SelectItem>
              <SelectItem value="medium">medium</SelectItem>
              <SelectItem value="high">high</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div class="grid gap-4 sm:grid-cols-3">
        <div class="space-y-2">
          <Label>temperature</Label>
          <Input
            :model-value="temperature"
            placeholder="0.7"
            @update:model-value="$emit('update:temperature', String($event ?? ''))"
          />
        </div>
        <div class="space-y-2">
          <Label>max output tokens</Label>
          <Input
            :model-value="maxOutputTokens"
            placeholder="2048"
            @update:model-value="$emit('update:maxOutputTokens', String($event ?? ''))"
          />
        </div>
        <div class="space-y-2">
          <Label>top_p</Label>
          <Input
            :model-value="topP"
            placeholder="1.0"
            @update:model-value="$emit('update:topP', String($event ?? ''))"
          />
        </div>
      </div>

      <details class="rounded-2xl border border-border/60 bg-muted/20 p-3">
        <summary class="cursor-pointer text-sm font-medium text-foreground">高级请求覆盖</summary>
        <div class="mt-3 space-y-3">
          <div class="space-y-2">
            <Label>附加请求头 JSON</Label>
            <Textarea
              :model-value="requestHeadersText"
              class="min-h-[100px] font-mono text-xs"
              placeholder='{"x-playground":"true"}'
              @update:model-value="$emit('update:requestHeadersText', String($event ?? ''))"
            />
          </div>

          <div class="space-y-2">
            <Label>请求体覆盖 JSON</Label>
            <Textarea
              :model-value="requestBodyText"
              class="min-h-[140px] font-mono text-xs"
              placeholder='{"metadata":{"source":"playground"}}'
              @update:model-value="$emit('update:requestBodyText', String($event ?? ''))"
            />
          </div>
        </div>
      </details>
    </div>
  </Card>
</template>

<script setup lang="ts">
import type { GlobalModelResponse, ProviderType, ProviderWithEndpointsSummary } from '@/api/endpoints/types'
import type { PlaygroundProtocolKey, PlaygroundProtocolOptionState } from '../types'

import { Badge, Card, Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Switch, Textarea } from '@/components/ui'

interface ProviderModelOption {
  name: string
  source: 'configured' | 'upstream'
}

interface Props {
  sourceMode: 'global' | 'provider'
  globalModelSearch: string
  selectedGlobalModelId: string
  filteredGlobalModels: GlobalModelResponse[]
  providerSearch: string
  selectedProviderId: string
  filteredProviders: ProviderWithEndpointsSummary[]
  providerModelSearch: string
  selectedProviderModelName: string
  filteredProviderModels: ProviderModelOption[]
  protocol: PlaygroundProtocolKey
  protocolOptions: PlaygroundProtocolOptionState[]
  protocolWarning: string
  systemPrompt: string
  stream: boolean
  reasoningEffort: string
  temperature: string
  maxOutputTokens: string
  topP: string
  requestHeadersText: string
  requestBodyText: string
  providerType?: ProviderType | null
}

defineProps<Props>()

defineEmits<{
  'update:sourceMode': ['global' | 'provider']
  'update:globalModelSearch': [string]
  'update:selectedGlobalModelId': [string]
  'update:providerSearch': [string]
  'update:selectedProviderId': [string]
  'update:providerModelSearch': [string]
  'update:selectedProviderModelName': [string]
  'update:protocol': [PlaygroundProtocolKey]
  'update:systemPrompt': [string]
  'update:stream': [boolean]
  'update:reasoningEffort': [string]
  'update:temperature': [string]
  'update:maxOutputTokens': [string]
  'update:topP': [string]
  'update:requestHeadersText': [string]
  'update:requestBodyText': [string]
}>()

const activeButtonClass = 'border-primary/50 bg-primary/10 text-primary shadow-sm'
const inactiveButtonClass = 'border-border/60 bg-background text-foreground hover:bg-muted/50'
</script>
