<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div
        v-if="open && model"
        class="fixed inset-0 z-50 flex justify-end"
        @click.self="handleClose"
      >
        <div
          class="absolute inset-0 bg-slate-950/45 backdrop-blur-sm"
          @click="handleClose"
        />

        <Card class="relative h-full w-full sm:w-[760px] sm:max-w-[92vw] rounded-none overflow-y-auto border-l border-border/70 shadow-2xl">
          <div class="sticky top-0 z-10 border-b border-border/60 bg-background/95 backdrop-blur px-4 py-4 sm:px-6">
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0 flex-1 space-y-2">
                <div class="flex items-center gap-3">
                  <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-sm font-bold uppercase text-primary ring-1 ring-primary/15">
                    {{ brandMonogram }}
                  </div>
                  <div class="min-w-0">
                    <h3 class="truncate text-lg font-semibold sm:text-xl">
                      {{ model.display_name || model.name }}
                    </h3>
                    <div class="mt-1 flex flex-wrap items-center gap-2">
                      <Badge variant="outline">
                        {{ brandLabel }}
                      </Badge>
                      <Badge
                        v-if="model.is_recommended"
                        variant="success"
                      >
                        推荐
                      </Badge>
                      <Badge
                        v-if="model.is_most_stable"
                        variant="warning"
                      >
                        最稳
                      </Badge>
                      <span class="text-xs font-mono text-muted-foreground">
                        {{ model.name }}
                      </span>
                    </div>
                  </div>
                </div>
                <p
                  v-if="model.description"
                  class="max-w-2xl text-sm leading-6 text-muted-foreground"
                >
                  {{ model.description }}
                </p>
              </div>

              <Button
                variant="ghost"
                size="icon"
                title="关闭"
                @click="handleClose"
              >
                <X class="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div class="space-y-6 p-4 sm:p-6">
            <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div class="rounded-2xl border border-border/70 bg-muted/20 p-4">
                <p class="text-xs text-muted-foreground">
                  来源覆盖
                </p>
                <p class="mt-2 text-2xl font-semibold">
                  {{ model.provider_count }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  活跃 {{ model.active_provider_count }} 个
                </p>
              </div>
              <div class="rounded-2xl border border-border/70 bg-muted/20 p-4">
                <p class="text-xs text-muted-foreground">
                  最近成功率
                </p>
                <p class="mt-2 text-2xl font-semibold">
                  {{ formatPercent(model.success_rate) }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  基于最近请求
                </p>
              </div>
              <div class="rounded-2xl border border-border/70 bg-muted/20 p-4">
                <p class="text-xs text-muted-foreground">
                  平均延迟
                </p>
                <p class="mt-2 text-2xl font-semibold">
                  {{ formatLatency(model.avg_latency_ms) }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  优先使用成功样本
                </p>
              </div>
              <div class="rounded-2xl border border-border/70 bg-muted/20 p-4">
                <p class="text-xs text-muted-foreground">
                  用户调用次数
                </p>
                <p class="mt-2 text-2xl font-semibold">
                  {{ formatUsageCount(model.usage_count) }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  当前账号维度
                </p>
              </div>
            </section>

            <section class="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
              <div class="space-y-6">
                <div class="rounded-3xl border border-border/60 bg-card/70 p-5">
                  <div class="mb-3 flex items-center justify-between">
                    <h4 class="text-sm font-semibold">
                      能力与标签
                    </h4>
                    <span class="text-xs text-muted-foreground">
                      {{ model.supported_api_formats.length }} 种 API 格式
                    </span>
                  </div>

                  <div class="flex flex-wrap gap-2">
                    <Badge
                      v-for="tag in model.tags"
                      :key="tag"
                      variant="outline"
                      class="uppercase"
                    >
                      {{ tag }}
                    </Badge>
                    <Badge
                      v-for="capability in model.supported_capabilities || []"
                      :key="capability"
                      variant="secondary"
                    >
                      {{ capability }}
                    </Badge>
                    <Badge
                      v-for="apiFormat in model.supported_api_formats"
                      :key="apiFormat"
                      variant="dark"
                    >
                      {{ apiFormat }}
                    </Badge>
                  </div>
                </div>

                <div class="rounded-3xl border border-border/60 bg-card/70 p-5">
                  <div class="mb-4 flex items-center justify-between">
                    <h4 class="text-sm font-semibold">
                      来源明细
                    </h4>
                    <span class="text-xs text-muted-foreground">
                      {{ model.providers.length }} 个 Provider
                    </span>
                  </div>

                  <div class="space-y-3">
                    <div
                      v-for="provider in model.providers"
                      :key="provider.provider_id"
                      class="rounded-2xl border border-border/60 bg-background/80 p-4"
                    >
                      <div class="flex flex-wrap items-start justify-between gap-3">
                        <div class="min-w-0 space-y-1">
                          <div class="flex flex-wrap items-center gap-2">
                            <h5 class="text-sm font-semibold">
                              {{ provider.provider_name }}
                            </h5>
                            <Badge :variant="provider.is_active ? 'success' : 'secondary'">
                              {{ provider.is_active ? '当前可用' : '当前不可用' }}
                            </Badge>
                          </div>
                          <p
                            v-if="provider.provider_website"
                            class="truncate text-xs text-muted-foreground"
                          >
                            {{ provider.provider_website }}
                          </p>
                        </div>

                        <div class="grid grid-cols-2 gap-2 text-right text-xs text-muted-foreground sm:grid-cols-3">
                          <div>
                            <p>端点</p>
                            <p class="mt-1 text-sm font-semibold text-foreground">
                              {{ provider.endpoint_count }}
                            </p>
                          </div>
                          <div>
                            <p>活跃端点</p>
                            <p class="mt-1 text-sm font-semibold text-foreground">
                              {{ provider.active_endpoint_count }}
                            </p>
                          </div>
                          <div class="col-span-2 sm:col-span-1">
                            <p>协议</p>
                            <p class="mt-1 text-sm font-semibold text-foreground">
                              {{ provider.supported_api_formats.length }}
                            </p>
                          </div>
                        </div>
                      </div>

                      <div class="mt-3 flex flex-wrap gap-2">
                        <Badge
                          v-for="apiFormat in provider.supported_api_formats"
                          :key="apiFormat"
                          variant="outline"
                        >
                          {{ apiFormat }}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="space-y-6">
                <div class="rounded-3xl border border-border/60 bg-card/70 p-5">
                  <h4 class="text-sm font-semibold">
                    价格摘要
                  </h4>
                  <div class="mt-4 grid gap-3">
                    <div class="rounded-2xl border border-border/60 bg-background/70 p-4">
                      <p class="text-xs text-muted-foreground">
                        输入价格
                      </p>
                      <p class="mt-1 text-lg font-semibold">
                        {{ firstTierInputPrice }}
                      </p>
                    </div>
                    <div class="rounded-2xl border border-border/60 bg-background/70 p-4">
                      <p class="text-xs text-muted-foreground">
                        输出价格
                      </p>
                      <p class="mt-1 text-lg font-semibold">
                        {{ firstTierOutputPrice }}
                      </p>
                    </div>
                    <div class="rounded-2xl border border-border/60 bg-background/70 p-4">
                      <p class="text-xs text-muted-foreground">
                        按次计费
                      </p>
                      <p class="mt-1 text-lg font-semibold">
                        {{ requestPriceLabel }}
                      </p>
                    </div>
                  </div>
                </div>

                <div class="rounded-3xl border border-border/60 bg-card/70 p-5">
                  <h4 class="text-sm font-semibold">
                    页面结论
                  </h4>
                  <div class="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                    <p>
                      这个模型当前有 <span class="font-semibold text-foreground">{{ model.active_provider_count }}</span> 个活跃来源，
                      最近成功率为 <span class="font-semibold text-foreground">{{ formatPercent(model.success_rate) }}</span>。
                    </p>
                    <p v-if="model.is_recommended">
                      它被标记为 <span class="font-semibold text-foreground">推荐</span>，意味着在覆盖度和稳定性之间的综合表现更适合作为默认模型候选。
                    </p>
                    <p
                      v-if="model.is_recommended && model.recommendation_reason"
                      class="rounded-2xl border border-border/60 bg-background/70 px-4 py-3"
                    >
                      {{ model.recommendation_reason }}
                    </p>
                    <p v-if="model.is_most_stable">
                      它被标记为 <span class="font-semibold text-foreground">最稳</span>，说明最近窗口里它的成功率和延迟表现更突出。
                    </p>
                    <p
                      v-if="model.is_most_stable && model.stability_reason"
                      class="rounded-2xl border border-border/60 bg-background/70 px-4 py-3"
                    >
                      {{ model.stability_reason }}
                    </p>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </Card>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'

import type { UserModelMarketplaceItem } from '@/api/model-marketplace'
import { Badge, Button, Card } from '@/components/ui'
import { formatUsageCount } from '@/utils/format'

const props = defineProps<{
  open: boolean
  model: UserModelMarketplaceItem | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const brandLabel = computed(() => {
  const brand = props.model?.brand || 'other'
  return {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    google: 'Google',
    deepseek: 'DeepSeek',
    other: 'Other',
  }[brand] || 'Other'
})

const brandMonogram = computed(() => brandLabel.value.slice(0, 2))

const firstTierInputPrice = computed(() => formatTierPrice(props.model?.default_tiered_pricing, 'input_price_per_1m'))
const firstTierOutputPrice = computed(() => formatTierPrice(props.model?.default_tiered_pricing, 'output_price_per_1m'))
const requestPriceLabel = computed(() => {
  const price = props.model?.default_price_per_request
  return typeof price === 'number' ? `$${price.toFixed(3)}/次` : '未配置'
})

function handleClose() {
  emit('update:open', false)
}

function formatPercent(value: number | null) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '暂无样本'
}

function formatLatency(value: number | null) {
  return typeof value === 'number' ? `${value} ms` : '暂无样本'
}

function formatTierPrice(
  pricing: Record<string, unknown> | null | undefined,
  field: 'input_price_per_1m' | 'output_price_per_1m',
) {
  const tiers = Array.isArray(pricing?.tiers) ? pricing?.tiers as Array<Record<string, unknown>> : []
  const firstTier = tiers[0]
  const raw = firstTier?.[field]
  return typeof raw === 'number' ? `$${raw.toFixed(2)} / 1M` : '未配置'
}
</script>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.24s ease;
}

.drawer-enter-active .relative,
.drawer-leave-active .relative {
  transition: transform 0.24s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .relative,
.drawer-leave-to .relative {
  transform: translateX(24px);
}
</style>
