<template>
  <div class="px-4 sm:px-6 py-3 sm:py-3.5 border-b border-border/50">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
      <!-- 左侧：标题 -->
      <h3 class="text-sm sm:text-base font-semibold text-foreground shrink-0">
        提供商管理
      </h3>

      <!-- 右侧：操作区 -->
      <div class="flex flex-wrap items-center gap-2">
        <!-- 搜索框 -->
        <div class="relative">
          <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/70 z-10 pointer-events-none" />
          <Input
            id="provider-search"
            :model-value="searchQuery"
            type="text"
            placeholder="搜索提供商..."
            class="w-32 sm:w-44 pl-8 pr-3 h-8 text-sm bg-muted/30 border-border/50 focus:border-primary/50 transition-colors"
            @update:model-value="$emit('update:searchQuery', $event)"
          />
        </div>

        <!-- 状态筛选 -->
        <Select
          v-if="visibleFilterKeys.includes('status')"
          :model-value="filterStatus"
          @update:model-value="$emit('update:filterStatus', $event)"
        >
          <SelectTrigger class="w-20 sm:w-28 h-8 text-xs border-border/60">
            <SelectValue placeholder="全部状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="status in statusFilters"
              :key="status.value"
              :value="status.value"
            >
              {{ status.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <!-- API 格式筛选 -->
        <Select
          v-if="visibleFilterKeys.includes('apiFormat')"
          :model-value="filterApiFormat"
          @update:model-value="$emit('update:filterApiFormat', $event)"
        >
          <SelectTrigger class="w-20 sm:w-28 h-8 text-xs border-border/60">
            <SelectValue placeholder="全部格式" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="fmt in apiFormatFilters"
              :key="fmt.value"
              :value="fmt.value"
            >
              {{ fmt.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <!-- 模型筛选 -->
        <Select
          v-if="visibleFilterKeys.includes('model')"
          :model-value="filterModel"
          @update:model-value="$emit('update:filterModel', $event)"
        >
          <SelectTrigger class="w-20 sm:w-36 h-8 text-xs border-border/60">
            <SelectValue placeholder="全部模型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="model in modelFilters"
              :key="model.value"
              :value="model.value"
            >
              {{ model.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select
          v-if="visibleFilterKeys.includes('importTaskStatus')"
          :model-value="filterImportTaskStatus"
          @update:model-value="$emit('update:filterImportTaskStatus', $event)"
        >
          <SelectTrigger class="w-24 sm:w-32 h-8 text-xs border-border/60">
            <SelectValue placeholder="导入状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="item in importTaskFilters"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select
          v-if="visibleFilterKeys.includes('proxyEnabled')"
          :model-value="filterProxyEnabled"
          @update:model-value="$emit('update:filterProxyEnabled', $event)"
        >
          <SelectTrigger class="w-24 sm:w-32 h-8 text-xs border-border/60">
            <SelectValue placeholder="代理状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="item in proxyFilters"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <TooltipProvider :delay-duration="120">
          <Tooltip>
            <TooltipTrigger as-child>
              <DropdownMenu :modal="false">
                <DropdownMenuTrigger as-child>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-8 w-8"
                  >
                    <SlidersHorizontal class="w-3.5 h-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent class="w-56 p-3" align="end">
                  <div class="space-y-2">
                    <div class="text-xs font-medium text-foreground">
                      显示筛选项
                    </div>
                    <label
                      v-for="item in filterVisibilityOptions"
                      :key="item.key"
                      class="flex items-center gap-2 text-xs text-foreground"
                    >
                      <Checkbox
                        :model-value="visibleFilterKeys.includes(item.key)"
                        @update:model-value="$emit('setFilterVisible', item.key, $event)"
                      />
                      <span>{{ item.label }}</span>
                    </label>
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            </TooltipTrigger>
            <TooltipContent>配置筛选项</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <!-- 重置筛选 -->
        <TooltipProvider
          v-if="hasActiveFilters"
          :delay-duration="120"
        >
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                class="h-8 w-8"
                @click="$emit('resetFilters')"
              >
                <FilterX class="w-3.5 h-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>重置筛选</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <div class="hidden sm:block h-4 w-px bg-border" />

        <!-- 调度策略 -->
        <button
          class="group inline-flex items-center gap-1.5 px-2.5 h-8 rounded-md border border-border/50 bg-muted/20 hover:bg-muted/40 hover:border-primary/40 transition-all duration-200 text-xs"
          title="点击调整调度策略"
          @click="$emit('openPriorityDialog')"
        >
          <span class="text-muted-foreground/80 hidden sm:inline">调度:</span>
          <span class="font-medium text-foreground/90">{{ priorityModeLabel }}</span>
          <ChevronDown class="w-3 h-3 text-muted-foreground/70 group-hover:text-foreground transition-colors" />
        </button>

        <div class="hidden sm:block h-4 w-px bg-border" />

        <!-- 操作按钮 -->
        <TooltipProvider :delay-duration="120">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                class="h-8 w-8"
                @click="$emit('openAllInHubImport')"
              >
                <Upload class="w-3.5 h-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>导入 All-in-Hub</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider :delay-duration="120">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                class="h-8 w-8"
                :disabled="refreshingCapabilities"
                @click="$emit('refreshAllCapabilities')"
              >
                <Layers class="w-3.5 h-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>刷新全部上游模型并适配</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider :delay-duration="120">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                class="h-8 w-8"
                :disabled="refreshingProxyProbe"
                @click="$emit('runProxyProbeAll')"
              >
                <Radar class="w-3.5 h-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>全局代理检测</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider :delay-duration="120">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                class="h-8 w-8"
                @click="$emit('addProvider')"
              >
                <Plus class="w-3.5 h-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>新增提供商</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <RefreshButton
          :loading="loading"
          @click="$emit('refresh')"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search, Plus, ChevronDown, FilterX, Upload, SlidersHorizontal, Layers, Radar } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import Checkbox from '@/components/ui/checkbox.vue'
import Input from '@/components/ui/input.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectValue from '@/components/ui/select-value.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import RefreshButton from '@/components/ui/refresh-button.vue'
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent } from '@/components/ui'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import type { FilterOption, ProviderFilterKey } from '@/features/providers/composables/useProviderFilters'

defineProps<{
  searchQuery: string
  filterStatus: string
  filterApiFormat: string
  filterModel: string
  filterImportTaskStatus: string
  filterProxyEnabled: string
  visibleFilterKeys: ProviderFilterKey[]
  statusFilters: FilterOption[]
  apiFormatFilters: FilterOption[]
  modelFilters: FilterOption[]
  importTaskFilters: FilterOption[]
  proxyFilters: FilterOption[]
  hasActiveFilters: boolean
  priorityModeLabel: string
  loading: boolean
  refreshingCapabilities?: boolean
  refreshingProxyProbe?: boolean
}>()

const filterVisibilityOptions: Array<{ key: ProviderFilterKey; label: string }> = [
  { key: 'status', label: '状态' },
  { key: 'apiFormat', label: 'API 格式' },
  { key: 'model', label: '模型' },
  { key: 'importTaskStatus', label: '导入状态' },
  { key: 'proxyEnabled', label: '代理状态' },
]

defineEmits<{
  'update:searchQuery': [value: string]
  'update:filterStatus': [value: string]
  'update:filterApiFormat': [value: string]
  'update:filterModel': [value: string]
  'update:filterImportTaskStatus': [value: string]
  'update:filterProxyEnabled': [value: string]
  'setFilterVisible': [key: ProviderFilterKey, visible: boolean]
  'resetFilters': []
  'openPriorityDialog': []
  'openAllInHubImport': []
  'refreshAllCapabilities': []
  'runProxyProbeAll': []
  'addProvider': []
  'refresh': []
}>()
</script>
