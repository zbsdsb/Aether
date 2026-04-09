import { computed, onMounted, ref, watch } from 'vue'

import { useToast } from '@/composables/useToast'
import { adminApi } from '@/api/admin'
import { getGlobalModels } from '@/api/endpoints/global-models'
import { getProviderModels } from '@/api/endpoints/models'
import {
  getProvidersSummary,
  runProviderPlaygroundProbe,
  testGlobalModelPlayground,
  testModelFailover,
  type TestModelFailoverResponse,
} from '@/api/endpoints/providers'
import type { GlobalModelResponse, ProviderWithEndpointsSummary } from '@/api/endpoints/types'
import { parseApiError } from '@/utils/errorParser'

import type {
  PlaygroundMessage,
  PlaygroundProtocolKey,
  PlaygroundRequestPreview,
  PlaygroundSourceMode,
} from '../types'
import { buildProtocolOptionState } from '../utils/playground-protocol-options'
import { buildPlaygroundRequestPreview } from '../utils/playground-request-preview'

interface ProviderModelOption {
  name: string
  source: 'configured' | 'upstream'
}

function parseOptionalNumber(value: string): number | null {
  const normalized = value.trim()
  if (!normalized) return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

function parseJsonObject(value: string, label: string): Record<string, unknown> | null {
  const normalized = value.trim()
  if (!normalized) return null
  const parsed = JSON.parse(normalized)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${label} 必须是 JSON 对象`)
  }
  return parsed as Record<string, unknown>
}

function createRequestId(): string {
  const randomUUID = globalThis.crypto?.randomUUID?.bind(globalThis.crypto)
  if (randomUUID) return `playground-${randomUUID().replace(/-/g, '').slice(0, 20)}`
  return `playground-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
}

function extractAssistantText(result: TestModelFailoverResponse): string {
  const response = result.data?.response as Record<string, unknown> | undefined
  const choices = Array.isArray(response?.choices) ? response?.choices as Array<Record<string, unknown>> : []
  const firstChoice = choices[0]
  const firstMessage = firstChoice?.message
  if (firstMessage && typeof firstMessage === 'object') {
    const content = (firstMessage as Record<string, unknown>).content
    if (typeof content === 'string' && content.trim()) return content.trim()
  }

  const outputText = response?.output_text
  if (typeof outputText === 'string' && outputText.trim()) return outputText.trim()

  const content = response?.content
  if (typeof content === 'string' && content.trim()) return content.trim()

  const successAttempt = result.attempts.find(attempt => attempt.status === 'success')
  if (successAttempt?.response_body && typeof successAttempt.response_body === 'object') {
    const responseBody = successAttempt.response_body as Record<string, unknown>
    const bodyChoices = Array.isArray(responseBody.choices) ? responseBody.choices as Array<Record<string, unknown>> : []
    const bodyMessage = bodyChoices[0]?.message
    if (bodyMessage && typeof bodyMessage === 'object') {
      const bodyContent = (bodyMessage as Record<string, unknown>).content
      if (typeof bodyContent === 'string' && bodyContent.trim()) return bodyContent.trim()
    }
  }

  return result.success ? '请求成功，详细结果见右侧调试面板。' : ''
}

export function useModelPlaygroundState() {
  const { error: showError, success: showSuccess } = useToast()

  const loading = ref(false)
  const providerModelsLoading = ref(false)
  const sending = ref(false)

  const sourceMode = ref<PlaygroundSourceMode>('global')
  const protocol = ref<PlaygroundProtocolKey>('openai-chat')
  const debugTab = ref('preview')

  const globalModelSearch = ref('')
  const selectedGlobalModelId = ref('')
  const providerSearch = ref('')
  const selectedProviderId = ref('')
  const providerModelSearch = ref('')
  const selectedProviderModelName = ref('')

  const systemPrompt = ref('')
  const stream = ref(true)
  const reasoningEffort = ref('medium')
  const temperature = ref('')
  const maxOutputTokens = ref('')
  const topP = ref('')
  const requestHeadersText = ref('')
  const requestBodyText = ref('')

  const draftInput = ref('')
  const messages = ref<PlaygroundMessage[]>([])
  const lastSubmittedInput = ref('')
  const runStatus = ref<'idle' | 'running' | 'success' | 'error'>('idle')
  const lastError = ref('')

  const globalModels = ref<GlobalModelResponse[]>([])
  const providers = ref<ProviderWithEndpointsSummary[]>([])
  const providerModels = ref<ProviderModelOption[]>([])

  const lastResult = ref<TestModelFailoverResponse | null>(null)
  const lastRequestPreview = ref<PlaygroundRequestPreview | null>(null)
  const lastRawRequest = ref<Record<string, unknown> | null>(null)
  const lastRawResponse = ref<unknown>(null)
  const requestMeta = ref<string[]>([])

  let activeAbortController: AbortController | null = null

  const filteredGlobalModels = computed(() => {
    const query = globalModelSearch.value.trim().toLowerCase()
    if (!query) return globalModels.value
    return globalModels.value.filter(model =>
      model.name.toLowerCase().includes(query)
      || model.display_name.toLowerCase().includes(query),
    )
  })

  const filteredProviders = computed(() => {
    const query = providerSearch.value.trim().toLowerCase()
    if (!query) return providers.value
    return providers.value.filter(provider =>
      provider.name.toLowerCase().includes(query)
      || (provider.website || '').toLowerCase().includes(query),
    )
  })

  const filteredProviderModels = computed(() => {
    const query = providerModelSearch.value.trim().toLowerCase()
    if (!query) return providerModels.value
    return providerModels.value.filter(model => model.name.toLowerCase().includes(query))
  })

  const selectedGlobalModel = computed(() =>
    globalModels.value.find(model => model.id === selectedGlobalModelId.value) ?? null,
  )

  const selectedProvider = computed(() =>
    providers.value.find(provider => provider.id === selectedProviderId.value) ?? null,
  )

  const protocolOptions = computed(() => buildProtocolOptionState({
    sourceMode: sourceMode.value,
    configuredFormats: selectedProvider.value?.api_formats ?? [],
    providerType: selectedProvider.value?.provider_type ?? null,
  }))

  const selectedProtocolState = computed(() =>
    protocolOptions.value.find(option => option.key === protocol.value) ?? null,
  )

  const protocolWarning = computed(() => {
    if (sourceMode.value !== 'provider') return ''
    const badge = selectedProtocolState.value?.badge
    if (badge === '未配置，可试测') {
      return '当前协议尚未正式配置到该渠道。P0 仅支持已配置协议的真实发送，探测能力会在后续实现。'
    }
    if (badge === '高风险') {
      return '当前渠道与所选协议组合风险较高，建议先切回已配置协议。'
    }
    return ''
  })

  const currentModelName = computed(() => {
    if (sourceMode.value === 'global') {
      return selectedGlobalModel.value?.name ?? ''
    }
    return selectedProviderModelName.value
  })

  const previewMessages = computed<PlaygroundMessage[]>(() => {
    const result = [...messages.value]
    const normalizedDraft = draftInput.value.trim()
    if (normalizedDraft) {
      result.push({ role: 'user', content: normalizedDraft })
    }
    return result
  })

  const requestPreview = computed<PlaygroundRequestPreview | null>(() => {
    const model = currentModelName.value.trim()
    if (!model) return null

    let requestBodyOverrides: Record<string, unknown> | null = null
    try {
      requestBodyOverrides = parseJsonObject(requestBodyText.value, '请求体覆盖')
    } catch {
      return null
    }

    return buildPlaygroundRequestPreview({
      protocol: protocol.value,
      model,
      systemPrompt: systemPrompt.value,
      messages: previewMessages.value,
      stream: stream.value,
      reasoningEffort: reasoningEffort.value === '' ? null : reasoningEffort.value as 'low' | 'medium' | 'high',
      temperature: parseOptionalNumber(temperature.value),
      maxOutputTokens: parseOptionalNumber(maxOutputTokens.value),
      topP: parseOptionalNumber(topP.value),
      requestBodyOverrides,
    })
  })

  const availableModelCount = computed(() =>
    sourceMode.value === 'global' ? globalModels.value.length : providerModels.value.length,
  )

  const currentTargetLabel = computed(() => {
    if (sourceMode.value === 'global') {
      return selectedGlobalModel.value?.display_name || selectedGlobalModel.value?.name || '未选择'
    }
    return selectedProviderModelName.value || '未选择'
  })

  const conversationRounds = computed(() =>
    messages.value.filter(message => message.role === 'user').length,
  )

  const canSend = computed(() => {
    if (!draftInput.value.trim()) return false
    if (!requestPreview.value) return false
    if (sourceMode.value === 'global') return Boolean(selectedGlobalModel.value)
    return Boolean(selectedProvider.value && selectedProviderModelName.value.trim())
  })

  const statusBadge = computed(() => {
    if (runStatus.value === 'running') return '请求中'
    if (runStatus.value === 'success') return '已完成'
    if (runStatus.value === 'error') return '失败'
    return '就绪'
  })

  const statusVariant = computed<'default' | 'secondary' | 'destructive' | 'outline' | 'success'>(() => {
    if (runStatus.value === 'success') return 'success'
    if (runStatus.value === 'error') return 'destructive'
    if (runStatus.value === 'running') return 'default'
    return 'secondary'
  })

  const statusText = computed(() => {
    if (runStatus.value === 'running') return '请求正在发送，请观察中栏响应和右侧调试面板。'
    if (runStatus.value === 'success') return '最近一次测试已完成，可在右侧查看请求与响应明细。'
    if (runStatus.value === 'error') return '最近一次测试失败，可根据右侧调试信息继续排查。'
    return '支持全局模型与渠道模型两种测试模式。'
  })

  const helperText = computed(() => {
    if (sourceMode.value === 'provider' && selectedProtocolState.value?.badge !== '已配置') {
      return '当前协议将走临时探测，请结合右侧请求与响应面板判断是否值得补正式配置。'
    }
    return '发送后会把协议预览、真实请求和真实响应同步写到右侧调试面板。'
  })

  const runModeLabel = computed(() => {
    if (sourceMode.value === 'provider' && selectedProtocolState.value?.badge !== '已配置') {
      return '临时协议探测 · 本次成功不代表该协议已正式接入'
    }
    return sourceMode.value === 'global' ? '正式配置测试 · 平台全局模型路由' : '正式配置测试 · 渠道模型'
  })

  async function loadGlobalModels() {
    const response = await getGlobalModels({ is_active: true, limit: 1000 })
    globalModels.value = response.models || []
    if (!selectedGlobalModelId.value && globalModels.value.length > 0) {
      selectedGlobalModelId.value = globalModels.value[0].id
    }
  }

  async function loadProviders() {
    const response = await getProvidersSummary({ page: 1, page_size: 500 })
    providers.value = response.items || []
  }

  async function loadProviderModels(providerId: string) {
    providerModelsLoading.value = true
    try {
      const configured = await getProviderModels(providerId, { is_active: true, limit: 1000 })
      const merged = new Map<string, ProviderModelOption>()

      for (const model of configured) {
        merged.set(model.provider_model_name, {
          name: model.provider_model_name,
          source: 'configured',
        })
      }

      try {
        const upstream = await adminApi.queryProviderModels(providerId, undefined, false)
        for (const model of upstream.data?.models || []) {
          const modelName = String(model.display_name || model.id || '').trim()
          if (!modelName || merged.has(modelName)) continue
          merged.set(modelName, { name: modelName, source: 'upstream' })
        }
      } catch {
        // 上游模型查询失败时仍允许使用本地已配置模型
      }

      providerModels.value = [...merged.values()]
      if (
        providerModels.value.length > 0
        && !providerModels.value.some(model => model.name === selectedProviderModelName.value)
      ) {
        selectedProviderModelName.value = providerModels.value[0].name
      }
    } finally {
      providerModelsLoading.value = false
    }
  }

  async function initialize() {
    loading.value = true
    try {
      await Promise.all([loadGlobalModels(), loadProviders()])
    } catch (err: unknown) {
      showError(`加载操练场初始数据失败: ${parseApiError(err, '初始化失败')}`)
    } finally {
      loading.value = false
    }
  }

  watch(sourceMode, (mode) => {
    lastError.value = ''
    if (mode === 'global') {
      selectedProviderId.value = ''
      selectedProviderModelName.value = ''
      providerModels.value = []
    } else {
      selectedGlobalModelId.value = ''
    }
  })

  watch(selectedProviderId, async (providerId) => {
    selectedProviderModelName.value = ''
    providerModels.value = []
    if (!providerId) return
    await loadProviderModels(providerId)
  })

  onMounted(() => {
    void initialize()
  })

  function stopCurrent() {
    if (activeAbortController) {
      activeAbortController.abort()
      activeAbortController = null
    }
    if (sending.value) {
      sending.value = false
      runStatus.value = 'idle'
      lastError.value = '请求已手动停止。'
    }
  }

  function clearConversation() {
    stopCurrent()
    messages.value = []
    draftInput.value = ''
    lastSubmittedInput.value = ''
    lastResult.value = null
    lastRequestPreview.value = null
    lastRawRequest.value = null
    lastRawResponse.value = null
    requestMeta.value = []
    lastError.value = ''
    runStatus.value = 'idle'
  }

  async function sendCurrent() {
    const currentInput = draftInput.value.trim()
    if (!currentInput) {
      showError('请输入测试消息')
      return
    }

    const preview = requestPreview.value
    if (!preview) {
      showError('当前参数无法生成请求预览，请检查模型和 JSON 覆盖内容')
      return
    }

    let requestHeaders: Record<string, unknown> | null = null
    try {
      requestHeaders = parseJsonObject(requestHeadersText.value, '附加请求头')
    } catch (err: unknown) {
      showError(err instanceof Error ? err.message : '附加请求头解析失败')
      return
    }

    const userMessage: PlaygroundMessage = { role: 'user', content: currentInput }
    const nextMessages = [...messages.value, userMessage]
    const isProbeMode = sourceMode.value === 'provider' && selectedProtocolState.value?.badge !== '已配置'

    lastRequestPreview.value = preview
    lastRawRequest.value = preview.body
    lastRawResponse.value = null
    requestMeta.value = [
      sourceMode.value === 'global' ? '全局模型' : '渠道模型',
      preview.transportLabel,
      sourceMode.value === 'global'
        ? '正式配置测试'
        : (isProbeMode ? '临时协议探测' : '已配置协议测试'),
    ]
    lastError.value = ''
    draftInput.value = ''
    messages.value = nextMessages
    lastSubmittedInput.value = currentInput
    sending.value = true
    runStatus.value = 'running'

    const abortController = new AbortController()
    activeAbortController = abortController
    const requestId = createRequestId()

    try {
      let result: TestModelFailoverResponse
      if (sourceMode.value === 'global') {
        const modelName = selectedGlobalModel.value?.name
        if (!modelName) throw new Error('请选择全局模型')
        result = await testGlobalModelPlayground({
          model_name: modelName,
          api_format: preview.apiFormat,
          request_headers: requestHeaders ?? undefined,
          request_body: preview.body,
          request_id: requestId,
          concurrency: 1,
        }, { signal: abortController.signal })
      } else {
        if (!selectedProviderId.value || !selectedProviderModelName.value) {
          throw new Error('请选择渠道商和渠道模型')
        }
        if (isProbeMode) {
          result = await runProviderPlaygroundProbe({
            provider_id: selectedProviderId.value,
            model_name: selectedProviderModelName.value,
            api_format: preview.apiFormat,
            request_headers: requestHeaders ?? undefined,
            request_body: preview.body,
            request_id: requestId,
            concurrency: 1,
          }, { signal: abortController.signal })
        } else {
          result = await testModelFailover({
            provider_id: selectedProviderId.value,
            mode: 'direct',
            model_name: selectedProviderModelName.value,
            api_format: preview.apiFormat,
            request_headers: requestHeaders ?? undefined,
            request_body: preview.body,
            request_id: requestId,
            concurrency: 1,
          }, { signal: abortController.signal })
        }
      }

      lastResult.value = result
      const successAttempt = result.attempts.find(attempt => attempt.status === 'success')
      const fallbackAttempt = successAttempt ?? result.attempts.find(attempt => attempt.request_body || attempt.response_body)
      lastRawRequest.value = (fallbackAttempt?.request_body as Record<string, unknown> | null) ?? preview.body
      lastRawResponse.value = fallbackAttempt?.response_body ?? result.data?.response ?? result

      if (result.success) {
        const assistantText = extractAssistantText(result)
        if (assistantText) {
          messages.value = [...messages.value, { role: 'assistant', content: assistantText }]
        }
        runStatus.value = 'success'
        showSuccess('模型操练场请求成功')
      } else {
        runStatus.value = 'error'
        lastError.value = result.error || '请求失败'
      }
    } catch (err: unknown) {
      if (abortController.signal.aborted) {
        lastError.value = '请求已手动停止。'
        runStatus.value = 'idle'
        return
      }
      lastError.value = parseApiError(err, '操练场请求失败')
      runStatus.value = 'error'
    } finally {
      if (activeAbortController === abortController) {
        activeAbortController = null
      }
      sending.value = false
    }
  }

  async function retryLast() {
    if (!lastSubmittedInput.value) {
      showError('暂无可重试的消息')
      return
    }
    draftInput.value = lastSubmittedInput.value
    await sendCurrent()
  }

  return {
    loading,
    providerModelsLoading,
    sending,
    sourceMode,
    protocol,
    debugTab,
    globalModelSearch,
    selectedGlobalModelId,
    providerSearch,
    selectedProviderId,
    providerModelSearch,
    selectedProviderModelName,
    systemPrompt,
    stream,
    reasoningEffort,
    temperature,
    maxOutputTokens,
    topP,
    requestHeadersText,
    requestBodyText,
    draftInput,
    messages,
    lastError,
    filteredGlobalModels,
    filteredProviders,
    filteredProviderModels,
    selectedProvider,
    protocolOptions,
    protocolWarning,
    requestPreview,
    availableModelCount,
    currentTargetLabel,
    conversationRounds,
    canSend,
    statusBadge,
    statusVariant,
    statusText,
    helperText,
    runModeLabel,
    lastRequestPreview,
    lastRawRequest,
    lastRawResponse,
    requestMeta,
    sendCurrent,
    stopCurrent,
    clearConversation,
    retryLast,
  }
}
