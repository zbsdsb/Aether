import { defineStore } from 'pinia'
import { ref } from 'vue'
import { proxyNodesApi, type ProxyNode } from '@/api/proxy-nodes'

export const useProxyNodesStore = defineStore('proxy-nodes', () => {
  const nodes = ref<ProxyNode[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchNodes(params?: { status?: string }) {
    loading.value = true
    error.value = null

    try {
      const data = await proxyNodesApi.listProxyNodes({ ...params, limit: 1000 })
      nodes.value = data.items
      total.value = data.total
    } catch (err: any) {
      error.value = err.response?.data?.error?.message || err.response?.data?.detail || '获取代理节点列表失败'
    } finally {
      loading.value = false
    }
  }

  async function deleteNode(nodeId: string) {
    loading.value = true
    error.value = null

    try {
      await proxyNodesApi.deleteProxyNode(nodeId)
      nodes.value = nodes.value.filter(n => n.id !== nodeId)
      total.value = Math.max(0, total.value - 1)
    } catch (err: any) {
      error.value = err.response?.data?.error?.message || err.response?.data?.detail || '删除代理节点失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    nodes,
    total,
    loading,
    error,
    fetchNodes,
    deleteNode,
  }
})
