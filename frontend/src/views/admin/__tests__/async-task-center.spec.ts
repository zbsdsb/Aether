import { describe, expect, it } from 'vitest'

import {
  buildAsyncTaskHref,
  getAsyncTaskDisplayTitle,
  summarizeAsyncTaskNotifications,
  type AdminAsyncTaskItem,
} from '../async-task-center'

const baseTask = {
  status: 'running',
  stage: 'refreshing',
  summary: '',
  provider_id: null,
  provider_name: null,
  model: null,
  progress_percent: 0,
  created_at: '2026-04-09T02:00:00+00:00',
  updated_at: '2026-04-09T02:01:00+00:00',
  completed_at: null,
} satisfies Partial<AdminAsyncTaskItem>

describe('async-task-center', () => {
  it('builds task-specific links for provider tasks', () => {
    const providerImportTask: AdminAsyncTaskItem = {
      ...baseTask,
      id: 'provider_import:job-1',
      task_type: 'provider_import',
      title: 'All-in-Hub 导入',
      source_task_id: 'job-1',
    }

    const providerRefreshTask: AdminAsyncTaskItem = {
      ...baseTask,
      id: 'provider_refresh_sync:job-2',
      task_type: 'provider_refresh_sync',
      title: '刷新并适配 Provider One',
      provider_id: 'provider-1',
      provider_name: 'Provider One',
      source_task_id: 'job-2',
    }

    expect(buildAsyncTaskHref(providerImportTask)).toBe('/admin/providers')
    expect(buildAsyncTaskHref(providerRefreshTask)).toBe('/admin/providers?providerId=provider-1')
  })

  it('prefers provider name for refresh task title and falls back to summary', () => {
    const refreshTask: AdminAsyncTaskItem = {
      ...baseTask,
      id: 'provider_refresh_sync:job-2',
      task_type: 'provider_refresh_sync',
      title: '刷新并适配指定渠道商',
      provider_id: 'provider-1',
      provider_name: 'Provider One',
      summary: '正在刷新 3/10 个渠道商',
      source_task_id: 'job-2',
    }

    const importTask: AdminAsyncTaskItem = {
      ...baseTask,
      id: 'provider_import:job-1',
      task_type: 'provider_import',
      title: 'All-in-Hub 导入',
      summary: '新增 Provider 4 个',
      source_task_id: 'job-1',
    }

    expect(getAsyncTaskDisplayTitle(refreshTask)).toBe('Provider One')
    expect(getAsyncTaskDisplayTitle(importTask)).toBe('All-in-Hub 导入')
  })

  it('summarizes active and failed provider tasks for header notifications', () => {
    const tasks: AdminAsyncTaskItem[] = [
      {
        ...baseTask,
        id: 'provider_refresh_sync:job-2',
        task_type: 'provider_refresh_sync',
        title: '刷新并适配 Provider One',
        provider_id: 'provider-1',
        provider_name: 'Provider One',
        summary: '正在刷新 3/10 个渠道商',
        source_task_id: 'job-2',
      },
      {
        ...baseTask,
        id: 'provider_import:job-3',
        task_type: 'provider_import',
        status: 'failed',
        stage: 'failed',
        title: 'All-in-Hub 导入',
        summary: '2 个站点需要人工复核',
        source_task_id: 'job-3',
      },
      {
        ...baseTask,
        id: 'video:job-4',
        task_type: 'video',
        title: 'veo-3',
        summary: '视频生成中',
        source_task_id: 'job-4',
      },
    ]

    expect(summarizeAsyncTaskNotifications(tasks)).toEqual({
      runningCount: 1,
      failedCount: 1,
      topItems: [
        {
          id: 'provider_refresh_sync:job-2',
          href: '/admin/providers?providerId=provider-1',
          label: 'Provider One',
          message: '正在刷新 3/10 个渠道商',
          status: 'running',
        },
        {
          id: 'provider_import:job-3',
          href: '/admin/providers',
          label: 'All-in-Hub 导入',
          message: '2 个站点需要人工复核',
          status: 'failed',
        },
      ],
    })
  })
})
