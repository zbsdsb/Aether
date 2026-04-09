<template>
  <div class="space-y-6 pb-8">
    <PageHeader
      title="模型操练场"
      description="像 metapi / New API Playground 一样调参数、切协议、看真实请求和响应。"
    />

    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card class="overflow-hidden border-0 bg-gradient-to-br from-violet-500 to-fuchsia-400 p-4 text-white shadow-lg">
        <p class="text-xs uppercase tracking-[0.16em] text-white/70">可测模型数</p>
        <p class="mt-3 text-3xl font-semibold">{{ state.availableModelCount }}</p>
      </Card>
      <Card class="overflow-hidden border-0 bg-gradient-to-br from-sky-500 to-indigo-400 p-4 text-white shadow-lg">
        <p class="text-xs uppercase tracking-[0.16em] text-white/70">当前目标</p>
        <p class="mt-3 line-clamp-2 text-lg font-semibold">{{ state.currentTargetLabel }}</p>
      </Card>
      <Card class="overflow-hidden border-0 bg-gradient-to-br from-emerald-500 to-teal-400 p-4 text-white shadow-lg">
        <p class="text-xs uppercase tracking-[0.16em] text-white/70">当前协议</p>
        <p class="mt-3 text-lg font-semibold">{{ currentProtocolLabel }}</p>
      </Card>
      <Card class="overflow-hidden border-0 bg-gradient-to-br from-orange-500 to-amber-400 p-4 text-white shadow-lg">
        <p class="text-xs uppercase tracking-[0.16em] text-white/70">当前会话轮次</p>
        <p class="mt-3 text-3xl font-semibold">{{ state.conversationRounds }}</p>
      </Card>
    </div>

    <div
      v-if="state.loading"
      class="rounded-3xl border border-border/60 bg-background/80 px-6 py-12 text-center text-sm text-muted-foreground"
    >
      正在加载模型操练场数据...
    </div>

    <div
      v-else
      class="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)_380px]"
    >
      <PlaygroundSetupPanel
        :source-mode="state.sourceMode"
        :global-model-search="state.globalModelSearch"
        :selected-global-model-id="state.selectedGlobalModelId"
        :filtered-global-models="state.filteredGlobalModels"
        :provider-search="state.providerSearch"
        :selected-provider-id="state.selectedProviderId"
        :filtered-providers="state.filteredProviders"
        :provider-model-search="state.providerModelSearch"
        :selected-provider-model-name="state.selectedProviderModelName"
        :filtered-provider-models="state.filteredProviderModels"
        :protocol="state.protocol"
        :protocol-options="state.protocolOptions"
        :protocol-warning="state.protocolWarning"
        :system-prompt="state.systemPrompt"
        :stream="state.stream"
        :reasoning-effort="state.reasoningEffort"
        :temperature="state.temperature"
        :max-output-tokens="state.maxOutputTokens"
        :top-p="state.topP"
        :request-headers-text="state.requestHeadersText"
        :request-body-text="state.requestBodyText"
        :provider-type="state.selectedProvider?.provider_type ?? null"
        @update:source-mode="state.sourceMode = $event"
        @update:global-model-search="state.globalModelSearch = $event"
        @update:selected-global-model-id="state.selectedGlobalModelId = $event"
        @update:provider-search="state.providerSearch = $event"
        @update:selected-provider-id="state.selectedProviderId = $event"
        @update:provider-model-search="state.providerModelSearch = $event"
        @update:selected-provider-model-name="state.selectedProviderModelName = $event"
        @update:protocol="state.protocol = $event"
        @update:system-prompt="state.systemPrompt = $event"
        @update:stream="state.stream = $event"
        @update:reasoning-effort="state.reasoningEffort = $event"
        @update:temperature="state.temperature = $event"
        @update:max-output-tokens="state.maxOutputTokens = $event"
        @update:top-p="state.topP = $event"
        @update:request-headers-text="state.requestHeadersText = $event"
        @update:request-body-text="state.requestBodyText = $event"
      />

      <PlaygroundConversationPanel
        :messages="state.messages"
        :draft-input="state.draftInput"
        :can-send="state.canSend"
        :sending="state.sending"
        :status-badge="state.statusBadge"
        :status-text="state.statusText"
        :status-variant="state.statusVariant"
        :helper-text="state.helperText"
        :last-error="state.lastError"
        @update:draft-input="state.draftInput = $event"
        @send="state.sendCurrent"
        @stop="state.stopCurrent"
        @retry="state.retryLast"
        @clear="state.clearConversation"
      />

      <PlaygroundDebugPanel
        :active-tab="state.debugTab"
        :mode-label="state.runModeLabel"
        :preview="state.lastRequestPreview?.body ?? state.requestPreview?.body ?? null"
        :request="state.lastRawRequest"
        :response="state.lastRawResponse"
        :request-meta="state.requestMeta"
        :last-error="state.lastError"
        @update:active-tab="state.debugTab = $event"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { Card } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import PlaygroundConversationPanel from '@/features/playground/components/PlaygroundConversationPanel.vue'
import PlaygroundDebugPanel from '@/features/playground/components/PlaygroundDebugPanel.vue'
import PlaygroundSetupPanel from '@/features/playground/components/PlaygroundSetupPanel.vue'
import { useModelPlaygroundState } from '@/features/playground/composables/useModelPlaygroundState'

const state = useModelPlaygroundState()

const currentProtocolLabel = computed(() =>
  state.protocolOptions.value.find(option => option.key === state.protocol.value)?.label || '未选择',
)
</script>
