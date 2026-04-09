import type { AsyncTaskItem } from '@/api/async-tasks'

export type AdminAsyncTaskItem = AsyncTaskItem

export interface AsyncTaskNotificationItem {
  id: string
  href: string
  label: string
  message: string
  status: string
}

export interface AsyncTaskNotificationSummary {
  runningCount: number
  failedCount: number
  topItems: AsyncTaskNotificationItem[]
}

export function buildAsyncTaskHref(task: AdminAsyncTaskItem): string {
  if (task.task_type === 'provider_refresh_sync') {
    if (task.provider_id) {
      return `/admin/providers?providerId=${task.provider_id}`
    }
    return '/admin/providers'
  }
  if (task.task_type === 'provider_proxy_probe') {
    if (task.provider_id) {
      return `/admin/providers?providerId=${task.provider_id}`
    }
    return '/admin/async-tasks?taskType=provider_proxy_probe'
  }
  if (task.task_type === 'provider_import') {
    return '/admin/providers'
  }
  return `/admin/async-tasks?task=${task.id}`
}

export function getAsyncTaskDisplayTitle(task: AdminAsyncTaskItem): string {
  if (task.task_type === 'provider_refresh_sync' && task.provider_name) {
    return task.provider_name
  }
  return task.title || task.summary || task.source_task_id
}

export function summarizeAsyncTaskNotifications(
  tasks: AdminAsyncTaskItem[],
): AsyncTaskNotificationSummary {
  const providerTasks = tasks.filter((task) =>
    task.task_type === 'provider_import' || task.task_type === 'provider_refresh_sync',
  )
  const topItems = providerTasks
    .filter((task) => task.status === 'running' || task.status === 'failed')
    .slice(0, 5)
    .map((task) => ({
      id: task.id,
      href: buildAsyncTaskHref(task),
      label: getAsyncTaskDisplayTitle(task),
      message: task.summary || task.title,
      status: task.status,
    }))

  return {
    runningCount: providerTasks.filter((task) => task.status === 'running').length,
    failedCount: providerTasks.filter((task) => task.status === 'failed').length,
    topItems,
  }
}
