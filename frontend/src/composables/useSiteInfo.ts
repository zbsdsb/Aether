import { ref, watch } from 'vue'
import apiClient from '@/api/client'

interface SiteInfo {
  site_name: string
  site_subtitle: string
}

interface SiteInfoFallback {
  siteName: string
  siteSubtitle: string
}

export function normalizeSiteInfoPayload(
  payload: unknown,
  fallback: SiteInfoFallback,
): SiteInfoFallback {
  const data = payload && typeof payload === 'object'
    ? payload as Partial<SiteInfo>
    : {}

  return {
    siteName: typeof data.site_name === 'string' && data.site_name.trim().length > 0
      ? data.site_name
      : fallback.siteName,
    siteSubtitle: typeof data.site_subtitle === 'string' && data.site_subtitle.trim().length > 0
      ? data.site_subtitle
      : fallback.siteSubtitle,
  }
}

// 模块级缓存，所有组件共享同一份数据
const siteName = ref('Aether')
const siteSubtitle = ref('AI Gateway')
const loaded = ref(false)
let fetchPromise: Promise<void> | null = null

async function fetchSiteInfo() {
  try {
    const response = await apiClient.get<SiteInfo>('/api/public/site-info')
    const normalized = normalizeSiteInfoPayload(response.data, {
      siteName: siteName.value,
      siteSubtitle: siteSubtitle.value,
    })
    siteName.value = normalized.siteName
    siteSubtitle.value = normalized.siteSubtitle
    loaded.value = true
  } catch {
    // 加载失败时保持默认值，允许后续重试
    fetchPromise = null
  }
}

async function refreshSiteInfo() {
  fetchPromise = null
  loaded.value = false
  fetchPromise = fetchSiteInfo()
  await fetchPromise
}

export function useSiteInfo() {
  if (!loaded.value && !fetchPromise) {
    fetchPromise = fetchSiteInfo()
  }
  return { siteName, siteSubtitle, refreshSiteInfo }
}

// 站点名称变化时同步更新 document.title
watch(siteName, (name) => {
  document.title = name
}, { immediate: true })
