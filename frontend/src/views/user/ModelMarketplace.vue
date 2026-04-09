<template>
  <div class="space-y-6 pb-8">
    <section class="relative overflow-hidden rounded-[2rem] border border-border/60 bg-card/80 p-5 shadow-sm sm:p-7">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.12),transparent_35%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.12),transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent)]" />
      <div class="relative">
        <div class="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div class="max-w-3xl space-y-3">
            <div class="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              Model Marketplace
            </div>
            <div>
              <h2 class="text-2xl font-semibold tracking-tight sm:text-3xl">
                模型广场
              </h2>
              <p class="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
                从“能不能用”升级到“值不值得用”。这里按真实来源覆盖、最近成功率、延迟和模型能力组织你当前可访问的模型池。
              </p>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <div class="relative min-w-[240px] flex-1 lg:min-w-[300px] lg:flex-none">
              <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="searchQuery"
                type="text"
                placeholder="搜索模型名称、展示名或描述..."
                class="h-11 rounded-2xl border-border/70 bg-background/80 pl-10"
              />
            </div>
            <RefreshButton
              :loading="loading"
              @click="loadMarketplace"
            />
          </div>
        </div>

        <div class="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div
            v-for="card in summaryCards"
            :key="card.label"
            class="rounded-[1.5rem] border border-border/60 bg-background/70 p-4 shadow-sm backdrop-blur"
          >
            <p class="text-xs uppercase tracking-[0.14em] text-muted-foreground">
              {{ card.label }}
            </p>
            <p class="mt-3 text-2xl font-semibold tracking-tight">
              {{ card.value }}
            </p>
            <p class="mt-1 text-xs text-muted-foreground">
              {{ card.hint }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <Card class="overflow-hidden border-border/60">
      <div class="border-b border-border/60 px-4 py-4 sm:px-6">
        <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h3 class="text-sm font-semibold sm:text-base">
              发现与筛选
            </h3>
            <p class="mt-1 text-xs text-muted-foreground">
              当前结果 {{ filteredModels.length }} / {{ marketplace.total }} 个模型
            </p>
          </div>

          <div class="grid gap-2 sm:grid-cols-2 xl:flex xl:flex-wrap xl:items-center">
            <Select v-model="selectedBrand">
              <SelectTrigger class="h-10 min-w-[140px] rounded-xl border-border/70">
                <SelectValue placeholder="全部品牌" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  全部品牌
                </SelectItem>
                <SelectItem
                  v-for="brand in brandOptions"
                  :key="brand.value"
                  :value="brand.value"
                >
                  {{ brand.label }}
                </SelectItem>
              </SelectContent>
            </Select>

            <Select v-model="selectedTag">
              <SelectTrigger class="h-10 min-w-[140px] rounded-xl border-border/70">
                <SelectValue placeholder="全部标签" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  全部标签
                </SelectItem>
                <SelectItem
                  v-for="tag in tagOptions"
                  :key="tag"
                  :value="tag"
                >
                  {{ tag }}
                </SelectItem>
              </SelectContent>
            </Select>

            <Select v-model="selectedCapability">
              <SelectTrigger class="h-10 min-w-[160px] rounded-xl border-border/70">
                <SelectValue placeholder="全部能力" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  全部能力
                </SelectItem>
                <SelectItem
                  v-for="capability in capabilityOptions"
                  :key="capability"
                  :value="capability"
                >
                  {{ capability }}
                </SelectItem>
              </SelectContent>
            </Select>

            <Select v-model="selectedSort">
              <SelectTrigger class="h-10 min-w-[170px] rounded-xl border-border/70">
                <SelectValue placeholder="排序方式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="provider_count">
                  按来源覆盖
                </SelectItem>
                <SelectItem value="active_provider_count">
                  按活跃来源
                </SelectItem>
                <SelectItem value="success_rate">
                  按成功率
                </SelectItem>
                <SelectItem value="avg_latency_ms">
                  按平均延迟
                </SelectItem>
                <SelectItem value="usage_count">
                  按调用次数
                </SelectItem>
                <SelectItem value="name">
                  按名称
                </SelectItem>
              </SelectContent>
            </Select>

            <label class="flex items-center gap-3 rounded-xl border border-border/70 px-3 py-2 text-sm text-muted-foreground">
              <Switch v-model="onlyAvailable" />
              <span>只看有活跃来源</span>
            </label>
          </div>
        </div>
      </div>

      <div
        v-if="error"
        class="px-4 py-16 text-center sm:px-6"
      >
        <p class="text-sm font-medium text-foreground">
          模型广场加载失败
        </p>
        <p class="mt-2 text-sm text-muted-foreground">
          {{ error }}
        </p>
      </div>

      <div
        v-else-if="loading"
        class="grid gap-4 p-4 sm:grid-cols-2 sm:p-6 xl:grid-cols-3"
      >
        <div
          v-for="index in 6"
          :key="index"
          class="rounded-[1.75rem] border border-border/60 bg-card/70 p-5"
        >
          <Skeleton class="h-5 w-28 rounded-full" />
          <Skeleton class="mt-4 h-8 w-40 rounded-xl" />
          <Skeleton class="mt-3 h-4 w-full rounded-lg" />
          <Skeleton class="mt-2 h-4 w-3/4 rounded-lg" />
          <div class="mt-6 grid grid-cols-2 gap-3">
            <Skeleton class="h-16 rounded-2xl" />
            <Skeleton class="h-16 rounded-2xl" />
          </div>
        </div>
      </div>

      <div
        v-else-if="filteredModels.length === 0"
        class="px-4 py-16 text-center sm:px-6"
      >
        <p class="text-sm font-medium text-foreground">
          没有找到匹配的模型
        </p>
        <p class="mt-2 text-sm text-muted-foreground">
          可以尝试切换品牌、标签，或者关闭“只看有活跃来源”再看看。
        </p>
      </div>

      <div
        v-else
        class="grid gap-4 p-4 sm:grid-cols-2 sm:p-6 2xl:grid-cols-3"
      >
        <article
          v-for="model in filteredModels"
          :key="model.id"
          class="group cursor-pointer overflow-hidden rounded-[1.75rem] border border-border/60 bg-card/70 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-primary/25 hover:shadow-xl"
          @click="openDetail(model)"
        >
          <div class="border-b border-border/50 px-5 py-5">
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0">
                <div class="flex items-center gap-3">
                  <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-sm font-bold uppercase text-primary ring-1 ring-primary/15">
                    {{ getBrandMonogram(model) }}
                  </div>
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-2">
                      <h4 class="truncate text-base font-semibold tracking-tight">
                        {{ model.display_name || model.name }}
                      </h4>
                      <Badge
                        v-for="badge in resolveMarketplaceBadges(model)"
                        :key="badge"
                        :variant="badge === '推荐' ? 'success' : 'warning'"
                      >
                        {{ badge }}
                      </Badge>
                    </div>
                    <p class="truncate text-xs font-mono text-muted-foreground">
                      {{ model.name }}
                    </p>
                  </div>
                </div>
                <p class="mt-3 line-clamp-2 min-h-[2.5rem] text-sm leading-6 text-muted-foreground">
                  {{ model.description || '当前未提供描述信息，但已聚合可访问来源、能力和最近表现。' }}
                </p>
              </div>
              <Badge variant="outline">
                {{ brandLabelMap[resolveMarketplaceBrand(model)] || 'Other' }}
              </Badge>
            </div>

            <div class="mt-4 flex flex-wrap gap-2">
              <Badge
                v-for="tag in model.tags"
                :key="tag"
                variant="outline"
                class="uppercase"
              >
                {{ tag }}
              </Badge>
            </div>
          </div>

          <div class="space-y-4 px-5 py-5">
            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-2xl border border-border/60 bg-background/70 p-3">
                <p class="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                  覆盖来源
                </p>
                <p class="mt-2 text-xl font-semibold">
                  {{ model.provider_count }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  活跃 {{ model.active_provider_count }}
                </p>
              </div>
              <div class="rounded-2xl border border-border/60 bg-background/70 p-3">
                <p class="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                  最近成功率
                </p>
                <p class="mt-2 text-xl font-semibold">
                  {{ formatPercent(model.success_rate) }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  近 24 小时
                </p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-2xl border border-border/60 bg-background/70 p-3">
                <p class="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                  平均延迟
                </p>
                <p class="mt-2 text-lg font-semibold">
                  {{ formatLatency(model.avg_latency_ms) }}
                </p>
              </div>
              <div class="rounded-2xl border border-border/60 bg-background/70 p-3">
                <p class="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                  调用次数
                </p>
                <p class="mt-2 text-lg font-semibold">
                  {{ formatUsageCount(model.usage_count) }}
                </p>
              </div>
            </div>

            <div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
              <span>{{ model.supported_api_formats.length }} 种 API 格式</span>
              <span>{{ formatPrice(model.default_tiered_pricing, model.default_price_per_request) }}</span>
            </div>
          </div>
        </article>
      </div>
    </Card>

    <ModelMarketplaceDetailDrawer
      v-model:open="drawerOpen"
      :model="selectedModel"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Search } from 'lucide-vue-next'

import {
  getUserModelMarketplace,
  type UserModelMarketplaceItem,
  type UserModelMarketplaceQuery,
  type UserModelMarketplaceResponse,
} from '@/api/model-marketplace'
import { useToast } from '@/composables/useToast'
import { parseApiError } from '@/utils/errorParser'
import { log } from '@/utils/logger'
import { formatUsageCount } from '@/utils/format'
import {
  Badge,
  Card,
  Input,
  RefreshButton,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Switch,
} from '@/components/ui'
import ModelMarketplaceDetailDrawer from './components/ModelMarketplaceDetailDrawer.vue'
import {
  filterMarketplaceModels,
  resolveMarketplaceBadges,
  resolveMarketplaceBrand,
  sortMarketplaceModels,
  type MarketplaceSortKey,
} from './utils/model-marketplace'

const { error: showError } = useToast()

const loading = ref(false)
const error = ref('')
const marketplace = ref<UserModelMarketplaceResponse>({
  summary: {
    total_models: 0,
    total_provider_count: 0,
    active_provider_count: 0,
    overall_success_rate: null,
  },
  models: [],
  total: 0,
  generated_at: '',
})

const searchQuery = ref('')
const selectedBrand = ref('all')
const selectedTag = ref('all')
const selectedCapability = ref('all')
const selectedSort = ref<MarketplaceSortKey>('provider_count')
const onlyAvailable = ref(false)
const drawerOpen = ref(false)
const selectedModel = ref<UserModelMarketplaceItem | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const brandLabelMap: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
  deepseek: 'DeepSeek',
  other: 'Other',
}

const brandOptions = computed(() =>
  [...new Set(marketplace.value.models.map(model => resolveMarketplaceBrand(model)))]
    .filter(Boolean)
    .sort()
    .map(value => ({ value, label: brandLabelMap[value] || value }))
)

const tagOptions = computed(() =>
  [...new Set(marketplace.value.models.flatMap(model => model.tags))]
    .filter(Boolean)
    .sort()
)

const capabilityOptions = computed(() =>
  [...new Set(marketplace.value.models.flatMap(model => model.supported_capabilities || []))]
    .filter(Boolean)
    .sort()
)

const filteredModels = computed(() =>
  sortMarketplaceModels(
    filterMarketplaceModels(marketplace.value.models, {
      search: searchQuery.value,
      brand: selectedBrand.value,
      tag: selectedTag.value,
      capability: selectedCapability.value,
      onlyAvailable: onlyAvailable.value,
    }),
    selectedSort.value,
  )
)

const summaryCards = computed(() => [
  {
    label: '模型总数',
    value: String(marketplace.value.summary.total_models),
    hint: '当前账号可访问的统一模型数量',
  },
  {
    label: '来源总数',
    value: String(marketplace.value.summary.total_provider_count),
    hint: '按模型聚合后的来源覆盖总和',
  },
  {
    label: '活跃来源',
    value: String(marketplace.value.summary.active_provider_count),
    hint: '当前仍具备可用性的活跃来源总和',
  },
  {
    label: '总体成功率',
    value: formatPercent(marketplace.value.summary.overall_success_rate),
    hint: '按来源覆盖加权后的最近窗口表现',
  },
])

onMounted(() => {
  void loadMarketplace()
})

async function loadMarketplace() {
  loading.value = true
  error.value = ''
  try {
    const response = await getUserModelMarketplace(buildMarketplaceQuery())
    marketplace.value = normalizeMarketplaceResponse(response)
  } catch (err: unknown) {
    log.error('加载模型广场失败:', err)
    const parsed = parseApiError(err, '')
    error.value = parsed
    showError(parsed, '加载模型广场失败')
  } finally {
    loading.value = false
  }
}

watch([selectedBrand, selectedTag, selectedCapability, onlyAvailable, selectedSort], () => {
  void loadMarketplace()
})

watch(searchQuery, () => {
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    void loadMarketplace()
  }, 250)
})

function openDetail(model: UserModelMarketplaceItem) {
  selectedModel.value = model
  drawerOpen.value = true
}

function formatPercent(value: number | null) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '暂无样本'
}

function formatLatency(value: number | null) {
  return typeof value === 'number' ? `${value} ms` : '暂无样本'
}

function formatPrice(
  pricing: Record<string, unknown> | null,
  perRequestPrice: number | null,
) {
  const tiers = Array.isArray(pricing?.tiers) ? pricing?.tiers as Array<Record<string, unknown>> : []
  const firstTier = tiers[0]
  const input = firstTier?.input_price_per_1m
  const output = firstTier?.output_price_per_1m
  if (typeof input === 'number' || typeof output === 'number') {
    return `In ${typeof input === 'number' ? `$${input.toFixed(2)}` : '-'} / Out ${typeof output === 'number' ? `$${output.toFixed(2)}` : '-'}`
  }
  if (typeof perRequestPrice === 'number') {
    return `$${perRequestPrice.toFixed(3)}/次`
  }
  return '价格未配置'
}

function getBrandMonogram(model: UserModelMarketplaceItem) {
  const brand = brandLabelMap[resolveMarketplaceBrand(model)] || 'Other'
  return brand.slice(0, 2).toUpperCase()
}

function buildMarketplaceQuery(): UserModelMarketplaceQuery {
  return {
    search: searchQuery.value.trim() || undefined,
    brand: selectedBrand.value !== 'all' ? selectedBrand.value : undefined,
    tag: selectedTag.value !== 'all' ? selectedTag.value : undefined,
    capability: selectedCapability.value !== 'all' ? selectedCapability.value : undefined,
    only_available: onlyAvailable.value || undefined,
    sort_by: selectedSort.value,
    sort_dir: 'desc',
  }
}

function normalizeMarketplaceResponse(raw: unknown): UserModelMarketplaceResponse {
  const fallback: UserModelMarketplaceResponse = {
    summary: {
      total_models: 0,
      total_provider_count: 0,
      active_provider_count: 0,
      overall_success_rate: null,
    },
    models: [],
    total: 0,
    generated_at: '',
  }

  if (!raw || typeof raw !== 'object') {
    return fallback
  }

  const response = raw as Partial<UserModelMarketplaceResponse>
  return {
    summary: {
      total_models: response.summary?.total_models ?? 0,
      total_provider_count: response.summary?.total_provider_count ?? 0,
      active_provider_count: response.summary?.active_provider_count ?? 0,
      overall_success_rate: response.summary?.overall_success_rate ?? null,
    },
    models: Array.isArray(response.models) ? response.models : [],
    total: response.total ?? (Array.isArray(response.models) ? response.models.length : 0),
    generated_at: response.generated_at ?? '',
  }
}
</script>
