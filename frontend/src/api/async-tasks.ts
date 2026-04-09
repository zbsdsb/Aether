import apiClient from './client'

export type AsyncTaskStatus =
  | 'pending'
  | 'submitted'
  | 'queued'
  | 'processing'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type AsyncTaskType = 'video' | 'provider_import' | 'provider_refresh_sync' | 'provider_proxy_probe'

export interface AsyncTaskItem {
  id: string
  task_type: AsyncTaskType
  status: AsyncTaskStatus
  stage: string
  title: string
  summary: string
  provider_id: string | null
  provider_name: string | null
  model: string | null
  progress_percent: number
  created_at: string | null
  updated_at: string | null
  completed_at: string | null
  source_task_id: string
}

export interface AsyncTaskDetail extends AsyncTaskItem {
  detail: Record<string, unknown> | null
}

export interface AsyncTaskListResponse {
  items: AsyncTaskItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface AsyncTaskStatsResponse {
  total: number
  by_status: Record<string, number>
  by_task_type: Record<string, number>
  today_count: number
  processing_count: number
}

export interface AsyncTaskQueryParams {
  status?: AsyncTaskStatus
  task_type?: AsyncTaskType
  model?: string
  page?: number
  page_size?: number
}

function getVideoSourceTaskId(taskId: string): string {
  return taskId.startsWith('video:') ? taskId.slice('video:'.length) : taskId
}

export const asyncTasksApi = {
  async list(params: AsyncTaskQueryParams = {}): Promise<AsyncTaskListResponse> {
    const searchParams = new URLSearchParams()
    if (params.status) searchParams.append('status', params.status)
    if (params.task_type) searchParams.append('task_type', params.task_type)
    if (params.model) searchParams.append('model', params.model)
    if (params.page) searchParams.append('page', params.page.toString())
    if (params.page_size) searchParams.append('page_size', params.page_size.toString())

    const query = searchParams.toString()
    const url = query ? `/api/admin/async-tasks?${query}` : '/api/admin/async-tasks'
    const response = await apiClient.get<AsyncTaskListResponse>(url)
    return response.data
  },

  async getStats(): Promise<AsyncTaskStatsResponse> {
    const response = await apiClient.get<AsyncTaskStatsResponse>('/api/admin/async-tasks/stats')
    return response.data
  },

  async getDetail(taskId: string): Promise<AsyncTaskDetail> {
    const response = await apiClient.get<AsyncTaskDetail>(`/api/admin/async-tasks/${taskId}`)
    return response.data
  },

  async cancel(taskId: string): Promise<{ id: string; status: string; message: string }> {
    const sourceTaskId = getVideoSourceTaskId(taskId)
    const response = await apiClient.post<{ id: string; status: string; message: string }>(
      `/api/admin/video-tasks/${sourceTaskId}/cancel`,
    )
    return response.data
  },
}

export default asyncTasksApi
