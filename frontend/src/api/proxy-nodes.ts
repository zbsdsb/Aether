import apiClient from './client'

export interface ProxyNode {
  id: string
  name: string
  ip: string
  port: number
  region: string | null
  status: 'online' | 'unhealthy' | 'offline'
  registered_by: string | null
  last_heartbeat_at: string | null
  heartbeat_interval: number
  active_connections: number
  total_requests: number
  avg_latency_ms: number | null
  created_at: string
  updated_at: string
}

export interface ProxyNodeListResponse {
  items: ProxyNode[]
  total: number
  skip: number
  limit: number
}

export const proxyNodesApi = {
  async listProxyNodes(params?: { status?: string; skip?: number; limit?: number }): Promise<ProxyNodeListResponse> {
    const response = await apiClient.get<ProxyNodeListResponse>('/api/admin/proxy-nodes', { params })
    return response.data
  },

  async deleteProxyNode(nodeId: string): Promise<void> {
    await apiClient.delete(`/api/admin/proxy-nodes/${nodeId}`)
  },
}
