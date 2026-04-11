import { beforeEach, describe, expect, it, vi } from 'vitest'

const getAllSystemConfigsMock = vi.fn()
const getSystemConfigMock = vi.fn()
const getSystemVersionMock = vi.fn()
const updateSystemConfigMock = vi.fn()
const successMock = vi.fn()
const errorMock = vi.fn()
const refreshSiteInfoMock = vi.fn()

vi.mock('@/api/admin', () => ({
  adminApi: {
    getAllSystemConfigs: (...args: unknown[]) => getAllSystemConfigsMock(...args),
    getSystemConfig: (...args: unknown[]) => getSystemConfigMock(...args),
    getSystemVersion: (...args: unknown[]) => getSystemVersionMock(...args),
    updateSystemConfig: (...args: unknown[]) => updateSystemConfigMock(...args),
  },
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    success: successMock,
    error: errorMock,
  }),
}))

vi.mock('@/composables/useSiteInfo', () => ({
  useSiteInfo: () => ({
    refreshSiteInfo: refreshSiteInfoMock,
  }),
}))

import { useSystemConfig } from '../useSystemConfig'

function createDeferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void

  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })

  return { promise, resolve, reject }
}

describe('useSystemConfig', () => {
  beforeEach(() => {
    getAllSystemConfigsMock.mockReset()
    getSystemConfigMock.mockReset()
    getSystemVersionMock.mockReset()
    updateSystemConfigMock.mockReset()
    successMock.mockReset()
    errorMock.mockReset()
    refreshSiteInfoMock.mockReset()
  })

  it('loads request log settings from bulk system configs and marks initial loading state', async () => {
    const deferred = createDeferred<Array<{ key: string; value: unknown; description?: string }>>()
    getAllSystemConfigsMock.mockReturnValueOnce(deferred.promise)

    const config = useSystemConfig()
    const loadPromise = config.loadSystemConfig()

    expect(config.configLoading.value).toBe(true)
    expect(getAllSystemConfigsMock).toHaveBeenCalledTimes(1)
    expect(getSystemConfigMock).not.toHaveBeenCalled()

    deferred.resolve([
      { key: 'request_record_level', value: 'headers' },
      { key: 'max_request_body_size', value: 2 * 1024 * 1024 },
      { key: 'max_response_body_size', value: 3 * 1024 * 1024 },
      { key: 'sensitive_headers', value: ['authorization', 'cookie'] },
    ])

    await loadPromise

    expect(config.configLoading.value).toBe(false)
    expect(config.systemConfig.value.request_record_level).toBe('headers')
    expect(config.maxRequestBodySizeKB.value).toBe(2048)
    expect(config.maxResponseBodySizeKB.value).toBe(3072)
    expect(config.sensitiveHeadersStr.value).toBe('authorization, cookie')
    expect(config.originalConfig.value?.request_record_level).toBe('headers')
  })

  it('detects request log dirty state after changing only the record level', async () => {
    getAllSystemConfigsMock.mockResolvedValueOnce([
      { key: 'request_record_level', value: 'basic' },
      { key: 'max_request_body_size', value: 1024 * 1024 },
      { key: 'max_response_body_size', value: 1024 * 1024 },
      { key: 'sensitive_headers', value: ['authorization'] },
    ])

    const config = useSystemConfig()
    await config.loadSystemConfig()

    expect(config.hasLogConfigChanges.value).toBe(false)

    config.systemConfig.value.request_record_level = 'full'

    expect(config.hasLogConfigChanges.value).toBe(true)
  })

  it('persists request log level changes and refreshes the original snapshot after save', async () => {
    getAllSystemConfigsMock.mockResolvedValueOnce([
      { key: 'request_record_level', value: 'basic' },
      { key: 'max_request_body_size', value: 1024 * 1024 },
      { key: 'max_response_body_size', value: 1024 * 1024 },
      { key: 'sensitive_headers', value: ['authorization'] },
    ])
    updateSystemConfigMock.mockResolvedValue({ ok: true })

    const config = useSystemConfig()
    await config.loadSystemConfig()

    config.systemConfig.value.request_record_level = 'headers'
    await config.saveLogConfig()

    expect(updateSystemConfigMock).toHaveBeenCalledWith(
      'request_record_level',
      'headers',
      '请求记录级别',
    )
    expect(config.originalConfig.value?.request_record_level).toBe('headers')
    expect(config.hasLogConfigChanges.value).toBe(false)
    expect(successMock).toHaveBeenCalledWith('请求记录配置已保存')
  })
})
