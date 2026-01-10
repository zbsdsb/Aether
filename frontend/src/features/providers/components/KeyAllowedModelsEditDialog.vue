<template>
  <Dialog
    :model-value="isOpen"
    title="模型权限"
    :description="`管理密钥 ${props.apiKey?.name || ''} 可访问的模型，清空右侧列表表示允许全部`"
    :icon="Shield"
    size="4xl"
    @update:model-value="handleDialogUpdate"
  >
    <template #default>
      <div class="space-y-4">
        <!-- 字典模式警告 -->
        <div
          v-if="isDictMode"
          class="rounded-lg border border-amber-500/50 bg-amber-50 dark:bg-amber-950/30 p-3"
        >
          <p class="text-sm text-amber-700 dark:text-amber-400">
            <strong>注意：</strong>此密钥使用按 API 格式区分的模型权限配置。
            编辑后将转换为统一列表模式，原有的格式区分信息将丢失。
          </p>
        </div>

        <!-- 密钥信息头部 -->
        <div class="rounded-lg border bg-muted/30 p-4">
          <div class="flex items-start justify-between">
            <div>
              <p class="font-semibold text-lg">{{ apiKey?.name }}</p>
              <p class="text-sm text-muted-foreground font-mono">
                {{ apiKey?.api_key_masked }}
              </p>
            </div>
            <Badge
              :variant="allowedModels.length === 0 ? 'default' : 'outline'"
              class="text-xs"
            >
              {{ allowedModels.length === 0 ? '允许全部' : `限制 ${allowedModels.length} 个模型` }}
            </Badge>
          </div>
        </div>

        <!-- 左右对比布局 -->
        <div class="flex gap-2 items-stretch">
          <!-- 左侧：可添加的模型 -->
          <div class="flex-1 space-y-2">
            <div class="flex items-center justify-between gap-2">
              <p class="text-sm font-medium shrink-0">可添加</p>
              <div class="flex-1 relative">
                <Search class="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <Input
                  v-model="searchQuery"
                  placeholder="搜索模型..."
                  class="pl-7 h-7 text-xs"
                />
              </div>
              <button
                v-if="upstreamModelsLoaded"
                type="button"
                class="p-1.5 hover:bg-muted rounded-md transition-colors shrink-0"
                title="刷新上游模型"
                :disabled="fetchingUpstreamModels"
                @click="fetchUpstreamModels()"
              >
                <RefreshCw
                  class="w-3.5 h-3.5"
                  :class="{ 'animate-spin': fetchingUpstreamModels }"
                />
              </button>
              <button
                v-else-if="!fetchingUpstreamModels"
                type="button"
                class="p-1.5 hover:bg-muted rounded-md transition-colors shrink-0"
                title="从提供商获取模型"
                @click="fetchUpstreamModels()"
              >
                <Zap class="w-3.5 h-3.5" />
              </button>
              <Loader2
                v-else
                class="w-3.5 h-3.5 animate-spin text-muted-foreground shrink-0"
              />
            </div>
            <div class="border rounded-lg h-80 overflow-y-auto">
              <div
                v-if="loadingGlobalModels"
                class="flex items-center justify-center h-full"
              >
                <Loader2 class="w-6 h-6 animate-spin text-primary" />
              </div>
              <div
                v-else-if="totalAvailableCount === 0 && !upstreamModelsLoaded"
                class="flex flex-col items-center justify-center h-full text-muted-foreground"
              >
                <Shield class="w-10 h-10 mb-2 opacity-30" />
                <p class="text-sm">{{ searchQuery ? '无匹配结果' : '暂无可添加模型' }}</p>
              </div>
              <div v-else class="p-2 space-y-2">
                <!-- 全局模型折叠组 -->
                <div
                  v-if="availableGlobalModels.length > 0 || !upstreamModelsLoaded"
                  class="border rounded-lg overflow-hidden"
                >
                  <div class="flex items-center gap-2 px-3 py-2 bg-muted/30">
                    <button
                      type="button"
                      class="flex items-center gap-2 flex-1 hover:bg-muted/50 -mx-1 px-1 rounded transition-colors"
                      @click="toggleGroupCollapse('global')"
                    >
                      <ChevronDown
                        class="w-4 h-4 transition-transform shrink-0"
                        :class="collapsedGroups.has('global') ? '-rotate-90' : ''"
                      />
                      <span class="text-xs font-medium">全局模型</span>
                      <span class="text-xs text-muted-foreground">
                        ({{ availableGlobalModels.length }})
                      </span>
                    </button>
                    <button
                      v-if="availableGlobalModels.length > 0"
                      type="button"
                      class="text-xs text-primary hover:underline shrink-0"
                      @click.stop="selectAllGlobalModels"
                    >
                      {{ isAllGlobalModelsSelected ? '取消' : '全选' }}
                    </button>
                  </div>
                  <div
                    v-show="!collapsedGroups.has('global')"
                    class="p-2 space-y-1 border-t"
                  >
                    <div
                      v-if="availableGlobalModels.length === 0"
                      class="py-4 text-center text-xs text-muted-foreground"
                    >
                      所有全局模型均已添加
                    </div>
                    <div
                      v-for="model in availableGlobalModels"
                      v-else
                      :key="model.name"
                      class="flex items-center gap-2 p-2 rounded-lg border transition-colors cursor-pointer"
                      :class="selectedLeftIds.includes(model.name)
                        ? 'border-primary bg-primary/10'
                        : 'hover:bg-muted/50'"
                      @click="toggleLeftSelection(model.name)"
                    >
                      <Checkbox
                        :checked="selectedLeftIds.includes(model.name)"
                        @update:checked="toggleLeftSelection(model.name)"
                        @click.stop
                      />
                      <div class="flex-1 min-w-0">
                        <p class="font-medium text-sm truncate">{{ model.display_name }}</p>
                        <p class="text-xs text-muted-foreground truncate font-mono">{{ model.name }}</p>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 从提供商获取的模型折叠组 -->
                <div
                  v-for="group in upstreamModelGroups"
                  :key="group.api_format"
                  class="border rounded-lg overflow-hidden"
                >
                  <div class="flex items-center gap-2 px-3 py-2 bg-muted/30">
                    <button
                      type="button"
                      class="flex items-center gap-2 flex-1 hover:bg-muted/50 -mx-1 px-1 rounded transition-colors"
                      @click="toggleGroupCollapse(group.api_format)"
                    >
                      <ChevronDown
                        class="w-4 h-4 transition-transform shrink-0"
                        :class="collapsedGroups.has(group.api_format) ? '-rotate-90' : ''"
                      />
                      <span class="text-xs font-medium">
                        {{ API_FORMAT_LABELS[group.api_format] || group.api_format }}
                      </span>
                      <span class="text-xs text-muted-foreground">
                        ({{ group.models.length }})
                      </span>
                    </button>
                    <button
                      type="button"
                      class="text-xs text-primary hover:underline shrink-0"
                      @click.stop="selectAllUpstreamModels(group.api_format)"
                    >
                      {{ isUpstreamGroupAllSelected(group.api_format) ? '取消' : '全选' }}
                    </button>
                  </div>
                  <div
                    v-show="!collapsedGroups.has(group.api_format)"
                    class="p-2 space-y-1 border-t"
                  >
                    <div
                      v-for="model in group.models"
                      :key="model.id"
                      class="flex items-center gap-2 p-2 rounded-lg border transition-colors cursor-pointer"
                      :class="selectedLeftIds.includes(model.id)
                        ? 'border-primary bg-primary/10'
                        : 'hover:bg-muted/50'"
                      @click="toggleLeftSelection(model.id)"
                    >
                      <Checkbox
                        :checked="selectedLeftIds.includes(model.id)"
                        @update:checked="toggleLeftSelection(model.id)"
                        @click.stop
                      />
                      <div class="flex-1 min-w-0">
                        <p class="font-medium text-sm truncate">{{ model.id }}</p>
                        <p class="text-xs text-muted-foreground truncate font-mono">
                          {{ model.owned_by || model.id }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 中间：操作按钮 -->
          <div class="flex flex-col items-center justify-center w-12 shrink-0 gap-2">
            <Button
              variant="outline"
              size="sm"
              class="w-9 h-8"
              :class="selectedLeftIds.length > 0 ? 'border-primary' : ''"
              :disabled="selectedLeftIds.length === 0"
              title="添加选中"
              @click="addSelected"
            >
              <ChevronRight
                class="w-6 h-6 stroke-[3]"
                :class="selectedLeftIds.length > 0 ? 'text-primary' : ''"
              />
            </Button>
            <Button
              variant="outline"
              size="sm"
              class="w-9 h-8"
              :class="selectedRightIds.length > 0 ? 'border-primary' : ''"
              :disabled="selectedRightIds.length === 0"
              title="移除选中"
              @click="removeSelected"
            >
              <ChevronLeft
                class="w-6 h-6 stroke-[3]"
                :class="selectedRightIds.length > 0 ? 'text-primary' : ''"
              />
            </Button>
          </div>

          <!-- 右侧：已添加的允许模型 -->
          <div class="flex-1 space-y-2">
            <div class="flex items-center justify-between">
              <p class="text-sm font-medium">已添加</p>
              <Button
                v-if="allowedModels.length > 0"
                variant="ghost"
                size="sm"
                class="h-6 px-2 text-xs"
                @click="toggleSelectAllRight"
              >
                {{ isAllRightSelected ? '取消' : '全选' }}
              </Button>
            </div>
            <div class="border rounded-lg h-80 overflow-y-auto">
              <div
                v-if="allowedModels.length === 0"
                class="flex flex-col items-center justify-center h-full text-muted-foreground"
              >
                <Shield class="w-10 h-10 mb-2 opacity-30" />
                <p class="text-sm">允许访问全部模型</p>
                <p class="text-xs mt-1">添加模型以限制访问范围</p>
              </div>
              <div v-else class="p-2 space-y-1">
                <div
                  v-for="modelName in allowedModels"
                  :key="'allowed-' + modelName"
                  class="flex items-center gap-2 p-2 rounded-lg border transition-colors cursor-pointer"
                  :class="selectedRightIds.includes(modelName)
                    ? 'border-primary bg-primary/10'
                    : 'hover:bg-muted/50'"
                  @click="toggleRightSelection(modelName)"
                >
                  <Checkbox
                    :checked="selectedRightIds.includes(modelName)"
                    @update:checked="toggleRightSelection(modelName)"
                    @click.stop
                  />
                  <div class="flex-1 min-w-0">
                    <p class="font-medium text-sm truncate">
                      {{ getModelDisplayName(modelName) }}
                    </p>
                    <p class="text-xs text-muted-foreground truncate font-mono">
                      {{ modelName }}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex items-center justify-between w-full">
        <p class="text-xs text-muted-foreground">
          {{ hasChanges ? '有未保存的更改' : '' }}
        </p>
        <div class="flex items-center gap-2">
          <Button variant="outline" @click="handleCancel">取消</Button>
          <Button :disabled="saving || !hasChanges" @click="handleSave">
            {{ saving ? '保存中...' : '保存' }}
          </Button>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import {
  Shield,
  Search,
  RefreshCw,
  Loader2,
  Zap,
  ChevronRight,
  ChevronLeft,
  ChevronDown
} from 'lucide-vue-next'
import { Dialog, Button, Input, Checkbox, Badge } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { parseApiError } from '@/utils/errorParser'
import {
  updateProviderKey,
  API_FORMAT_LABELS,
  type EndpointAPIKey,
  type AllowedModels,
} from '@/api/endpoints'
import { getGlobalModels, type GlobalModelResponse } from '@/api/global-models'
import { adminApi } from '@/api/admin'
import type { UpstreamModel } from '@/api/endpoints/types'

interface AvailableModel {
  name: string
  display_name: string
}

const props = defineProps<{
  open: boolean
  apiKey: EndpointAPIKey | null
  providerId: string
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const { success, error: showError } = useToast()

const isOpen = computed(() => props.open)
const saving = ref(false)
const loadingGlobalModels = ref(false)
const fetchingUpstreamModels = ref(false)
const upstreamModelsLoaded = ref(false)

// 用于取消异步操作的标志
let loadingCancelled = false

// 搜索
const searchQuery = ref('')

// 折叠状态
const collapsedGroups = ref<Set<string>>(new Set())

// 可用模型列表（全局模型）
const allGlobalModels = ref<AvailableModel[]>([])
// 上游模型列表
const upstreamModels = ref<UpstreamModel[]>([])

// 已添加的允许模型（右侧）
const allowedModels = ref<string[]>([])
const initialAllowedModels = ref<string[]>([])

// 选中状态
const selectedLeftIds = ref<string[]>([])
const selectedRightIds = ref<string[]>([])

// 是否有更改
const hasChanges = computed(() => {
  if (allowedModels.value.length !== initialAllowedModels.value.length) return true
  const sorted1 = [...allowedModels.value].sort()
  const sorted2 = [...initialAllowedModels.value].sort()
  return sorted1.some((v, i) => v !== sorted2[i])
})

// 计算可添加的全局模型（排除已添加的）
const availableGlobalModelsBase = computed(() => {
  const allowedSet = new Set(allowedModels.value)
  return allGlobalModels.value.filter(m => !allowedSet.has(m.name))
})

// 搜索过滤后的全局模型
const availableGlobalModels = computed(() => {
  if (!searchQuery.value.trim()) return availableGlobalModelsBase.value
  const query = searchQuery.value.toLowerCase()
  return availableGlobalModelsBase.value.filter(m =>
    m.name.toLowerCase().includes(query) ||
    m.display_name.toLowerCase().includes(query)
  )
})

// 计算可添加的上游模型（排除已添加的）
const availableUpstreamModelsBase = computed(() => {
  const allowedSet = new Set(allowedModels.value)
  return upstreamModels.value.filter(m => !allowedSet.has(m.id))
})

// 搜索过滤后的上游模型
const availableUpstreamModels = computed(() => {
  if (!searchQuery.value.trim()) return availableUpstreamModelsBase.value
  const query = searchQuery.value.toLowerCase()
  return availableUpstreamModelsBase.value.filter(m =>
    m.id.toLowerCase().includes(query) ||
    (m.owned_by && m.owned_by.toLowerCase().includes(query))
  )
})

// 按 API 格式分组的上游模型
const upstreamModelGroups = computed(() => {
  const groups: Record<string, UpstreamModel[]> = {}
  for (const model of availableUpstreamModels.value) {
    const format = model.api_format || 'unknown'
    if (!groups[format]) groups[format] = []
    groups[format].push(model)
  }
  const order = Object.keys(API_FORMAT_LABELS)
  return Object.entries(groups)
    .map(([api_format, models]) => ({ api_format, models }))
    .sort((a, b) => {
      const aIndex = order.indexOf(a.api_format)
      const bIndex = order.indexOf(b.api_format)
      if (aIndex === -1 && bIndex === -1) return a.api_format.localeCompare(b.api_format)
      if (aIndex === -1) return 1
      if (bIndex === -1) return -1
      return aIndex - bIndex
    })
})

// 总可添加数量
const totalAvailableCount = computed(() => {
  return availableGlobalModels.value.length + availableUpstreamModels.value.length
})

// 右侧全选状态
const isAllRightSelected = computed(() =>
  allowedModels.value.length > 0 &&
  selectedRightIds.value.length === allowedModels.value.length
)

// 全局模型是否全选
const isAllGlobalModelsSelected = computed(() => {
  if (availableGlobalModels.value.length === 0) return false
  return availableGlobalModels.value.every(m => selectedLeftIds.value.includes(m.name))
})

// 检查某个上游组是否全选
function isUpstreamGroupAllSelected(apiFormat: string): boolean {
  const group = upstreamModelGroups.value.find(g => g.api_format === apiFormat)
  if (!group || group.models.length === 0) return false
  return group.models.every(m => selectedLeftIds.value.includes(m.id))
}

// 获取模型显示名称
function getModelDisplayName(name: string): string {
  const globalModel = allGlobalModels.value.find(m => m.name === name)
  if (globalModel) return globalModel.display_name
  const upstreamModel = upstreamModels.value.find(m => m.id === name)
  if (upstreamModel) return upstreamModel.id
  return name
}

// 加载全局模型
async function loadGlobalModels() {
  loadingGlobalModels.value = true
  try {
    const response = await getGlobalModels({ limit: 1000 })
    // 检查是否已取消（dialog 已关闭）
    if (loadingCancelled) return
    allGlobalModels.value = response.models.map((m: GlobalModelResponse) => ({
      name: m.name,
      display_name: m.display_name
    }))
  } catch (err) {
    if (loadingCancelled) return
    showError('加载全局模型失败', '错误')
  } finally {
    loadingGlobalModels.value = false
  }
}

// 从提供商获取模型（使用当前 key）
async function fetchUpstreamModels() {
  if (!props.providerId || !props.apiKey) return
  try {
    fetchingUpstreamModels.value = true
    // 使用当前 key 的 ID 来查询上游模型
    const response = await adminApi.queryProviderModels(props.providerId, props.apiKey.id)
    // 检查是否已取消
    if (loadingCancelled) return
    if (response.success && response.data?.models) {
      upstreamModels.value = response.data.models
      upstreamModelsLoaded.value = true
      const allGroups = new Set(['global'])
      for (const model of response.data.models) {
        if (model.api_format) allGroups.add(model.api_format)
      }
      collapsedGroups.value = allGroups
    } else {
      showError(response.data?.error || '获取上游模型失败', '错误')
    }
  } catch (err: any) {
    if (loadingCancelled) return
    showError(err.response?.data?.detail || '获取上游模型失败', '错误')
  } finally {
    fetchingUpstreamModels.value = false
  }
}

// 切换折叠状态
function toggleGroupCollapse(group: string) {
  if (collapsedGroups.value.has(group)) {
    collapsedGroups.value.delete(group)
  } else {
    collapsedGroups.value.add(group)
  }
  collapsedGroups.value = new Set(collapsedGroups.value)
}

// 是否为字典模式（按 API 格式区分）
const isDictMode = ref(false)

// 解析 allowed_models
function parseAllowedModels(allowed: AllowedModels): string[] {
  if (allowed === null || allowed === undefined) {
    isDictMode.value = false
    return []
  }
  if (Array.isArray(allowed)) {
    isDictMode.value = false
    return [...allowed]
  }
  // 字典模式：合并所有格式的模型，并设置警告标志
  isDictMode.value = true
  const all = new Set<string>()
  for (const models of Object.values(allowed)) {
    models.forEach(m => all.add(m))
  }
  return Array.from(all)
}

// 左侧选择
function toggleLeftSelection(name: string) {
  const idx = selectedLeftIds.value.indexOf(name)
  if (idx === -1) {
    selectedLeftIds.value.push(name)
  } else {
    selectedLeftIds.value.splice(idx, 1)
  }
}

// 右侧选择
function toggleRightSelection(name: string) {
  const idx = selectedRightIds.value.indexOf(name)
  if (idx === -1) {
    selectedRightIds.value.push(name)
  } else {
    selectedRightIds.value.splice(idx, 1)
  }
}

// 右侧全选切换
function toggleSelectAllRight() {
  if (isAllRightSelected.value) {
    selectedRightIds.value = []
  } else {
    selectedRightIds.value = [...allowedModels.value]
  }
}

// 全选全局模型
function selectAllGlobalModels() {
  const allNames = availableGlobalModels.value.map(m => m.name)
  const allSelected = allNames.every(name => selectedLeftIds.value.includes(name))
  if (allSelected) {
    selectedLeftIds.value = selectedLeftIds.value.filter(id => !allNames.includes(id))
  } else {
    const newNames = allNames.filter(name => !selectedLeftIds.value.includes(name))
    selectedLeftIds.value.push(...newNames)
  }
}

// 全选某个 API 格式的上游模型
function selectAllUpstreamModels(apiFormat: string) {
  const group = upstreamModelGroups.value.find(g => g.api_format === apiFormat)
  if (!group) return
  const allIds = group.models.map(m => m.id)
  const allSelected = allIds.every(id => selectedLeftIds.value.includes(id))
  if (allSelected) {
    selectedLeftIds.value = selectedLeftIds.value.filter(id => !allIds.includes(id))
  } else {
    const newIds = allIds.filter(id => !selectedLeftIds.value.includes(id))
    selectedLeftIds.value.push(...newIds)
  }
}

// 添加选中的模型到右侧
function addSelected() {
  for (const name of selectedLeftIds.value) {
    if (!allowedModels.value.includes(name)) {
      allowedModels.value.push(name)
    }
  }
  selectedLeftIds.value = []
}

// 从右侧移除选中的模型
function removeSelected() {
  allowedModels.value = allowedModels.value.filter(
    name => !selectedRightIds.value.includes(name)
  )
  selectedRightIds.value = []
}

// 监听对话框打开
watch(() => props.open, async (open) => {
  if (open && props.apiKey) {
    // 重置取消标志
    loadingCancelled = false

    const parsed = parseAllowedModels(props.apiKey.allowed_models ?? null)
    allowedModels.value = [...parsed]
    initialAllowedModels.value = [...parsed]
    selectedLeftIds.value = []
    selectedRightIds.value = []
    searchQuery.value = ''
    upstreamModels.value = []
    upstreamModelsLoaded.value = false
    collapsedGroups.value = new Set()

    await loadGlobalModels()
  } else {
    // dialog 关闭时设置取消标志
    loadingCancelled = true
  }
})

// 组件卸载时取消所有异步操作
onUnmounted(() => {
  loadingCancelled = true
})

function handleDialogUpdate(value: boolean) {
  if (!value) emit('close')
}

function handleCancel() {
  emit('close')
}

async function handleSave() {
  if (!props.apiKey) return

  saving.value = true
  try {
    // 空列表 = null（允许全部）
    const newAllowed: AllowedModels = allowedModels.value.length > 0
      ? [...allowedModels.value]
      : null

    await updateProviderKey(props.apiKey.id, { allowed_models: newAllowed })
    success('模型权限已更新', '成功')
    emit('saved')
    emit('close')
  } catch (err: any) {
    showError(parseApiError(err, '保存失败'), '错误')
  } finally {
    saving.value = false
  }
}
</script>
