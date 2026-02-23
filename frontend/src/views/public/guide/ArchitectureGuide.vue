<script setup lang="ts">
import { Network, ArrowRight } from 'lucide-vue-next'
import { panelClasses } from './guide-config'
import ArchitectureDiagram from './components/ArchitectureDiagram.vue'
</script>

<template>
  <div class="space-y-12">
    <!-- Hero 区域 -->
    <div class="space-y-4">
      <div class="inline-flex items-center gap-1.5 rounded-full bg-[#cc785c]/10 dark:bg-[#cc785c]/20 border border-[#cc785c]/20 dark:border-[#cc785c]/40 px-3 py-1 text-xs font-medium text-[#cc785c] dark:text-[#d4a27f]">
        <Network class="h-3 w-3" />
        系统架构
      </div>
      <h1 class="text-3xl font-bold text-[#262624] dark:text-[#f1ead8]">
        架构说明
      </h1>
      <p class="text-base text-[#666663] dark:text-[#a3a094] max-w-2xl">
        Aether 作为一个高性能的 AI API Gateway，其核心在于统一的接入层与灵活的路由调度。我们在下方提供了一个架构的数据流向动画演示，帮助您直观地理解它的工作原理。
      </p>
    </div>

    <!-- 动态架构图 -->
    <div class="mt-10 mb-6">
      <ArchitectureDiagram />
    </div>

    <section>
      <div
        :class="[panelClasses.card]"
        class="p-8 mt-6"
      >
        <ul class="space-y-6">
          <li class="flex items-start gap-4">
            <div class="w-10 h-10 rounded-full bg-[#cc785c]/10 text-[#cc785c] flex items-center justify-center shrink-0 mt-1 shadow-sm">
              <span class="font-bold font-mono">1</span>
            </div>
            <div>
              <h3 class="text-lg font-medium text-[#262624] dark:text-[#f1ead8] m-0 mb-1">
                多维度支持
              </h3>
              <p class="text-sm text-[#666663] dark:text-[#a3a094] leading-relaxed">
                全面兼容并支持多种 API 格式、端点配置及不同的认证方式，保障不同客户端的平滑接入。
              </p>
            </div>
          </li>

          <li class="flex items-start gap-4">
            <div class="w-10 h-10 rounded-full bg-[#cc785c]/10 text-[#cc785c] flex items-center justify-center shrink-0 mt-1 shadow-sm">
              <span class="font-bold font-mono">2</span>
            </div>
            <div>
              <h3 class="text-lg font-medium text-[#262624] dark:text-[#f1ead8] m-0 mb-1">
                统一的模型入口
              </h3>
              <p class="text-sm text-[#666663] dark:text-[#a3a094] leading-relaxed">
                对外暴露统一的模型名称，对内自动映射到各提供商可能不同的内部模型名及其变体，支持多变体优先级选择和基于亲和性的稳定路由，结合负载均衡、故障转移等智能调度策略。
              </p>
            </div>
          </li>

          <li class="flex items-start gap-4">
            <div class="w-10 h-10 rounded-full bg-[#cc785c]/10 text-[#cc785c] flex items-center justify-center shrink-0 mt-1 shadow-sm">
              <span class="font-bold font-mono">3</span>
            </div>
            <div class="w-full">
              <h3 class="text-lg font-medium text-[#262624] dark:text-[#f1ead8] m-0 mb-3">
                格式转换流程 (跨平台转发)
              </h3>
              <div class="flex flex-col md:flex-row items-stretch md:items-center gap-3 bg-[#f5f5f0]/50 dark:bg-[rgba(227,224,211,0.05)] p-4 rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.06)]">
                <div class="flex-1 bg-white dark:bg-[#191714] border border-[#e5e4df] dark:border-white/10 rounded-lg p-3 text-center text-sm font-medium text-[#262624] dark:text-white shadow-sm">
                  多API格式兼容入口
                </div>
                <ArrowRight class="hidden md:block w-5 h-5 text-[#cc785c] mx-1 shrink-0" />
                <div class="md:hidden flex justify-center py-1">
                  <ArrowRight class="w-5 h-5 text-[#cc785c] rotate-90" />
                </div>
                
                <div class="flex-1 bg-[#cc785c]/10 dark:bg-[#cc785c]/20 border border-[#cc785c]/20 rounded-lg p-3 text-center text-sm font-medium text-[#cc785c] dark:text-[#d4a27f]">
                  格式转换
                </div>
                <ArrowRight class="hidden md:block w-5 h-5 text-[#91918d] dark:text-white/30 mx-1 shrink-0" />
                <div class="md:hidden flex justify-center py-1">
                  <ArrowRight class="w-5 h-5 text-[#91918d] dark:text-white/30 rotate-90" />
                </div>

                <div class="flex-1 bg-white dark:bg-[#191714] border border-[#e5e4df] dark:border-white/10 rounded-lg p-3 text-center text-sm font-medium text-[#262624] dark:text-white shadow-sm">
                  上游提供商
                </div>
                <ArrowRight class="hidden md:block w-5 h-5 text-[#91918d] dark:text-white/30 mx-1 shrink-0" />
                <div class="md:hidden flex justify-center py-1">
                  <ArrowRight class="w-5 h-5 text-[#91918d] dark:text-white/30 rotate-90" />
                </div>

                <div class="flex-1 bg-[#cc785c]/10 dark:bg-[#cc785c]/20 border border-[#cc785c]/20 rounded-lg p-3 text-center text-sm font-medium text-[#cc785c] dark:text-[#d4a27f]">
                  格式转换
                </div>
                <ArrowRight class="hidden md:block w-5 h-5 text-[#cc785c] mx-1 shrink-0" />
                <div class="md:hidden flex justify-center py-1">
                  <ArrowRight class="w-5 h-5 text-[#cc785c] rotate-90" />
                </div>
                
                <div class="flex-1 bg-white dark:bg-[#191714] border border-[#e5e4df] dark:border-white/10 rounded-lg p-3 text-center text-sm font-medium text-[#262624] dark:text-white shadow-sm">
                  兼容出口响应
                </div>
              </div>
            </div>
          </li>

          <li class="flex items-start gap-4">
            <div class="w-10 h-10 rounded-full bg-[#cc785c]/10 text-[#cc785c] flex items-center justify-center shrink-0 mt-1 shadow-sm">
              <span class="font-bold font-mono">4</span>
            </div>
            <div class="w-full">
              <h3 class="text-lg font-medium text-[#262624] dark:text-[#f1ead8] m-0 mb-3">
                透传流程 (原生同生态)
              </h3>
              <div class="flex flex-col md:flex-row items-stretch md:items-center gap-3 bg-[#f5f5f0]/50 dark:bg-[rgba(227,224,211,0.05)] p-4 rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.06)]">
                <div class="flex-1 bg-white dark:bg-[#191714] border border-[#e5e4df] dark:border-white/10 rounded-lg p-3 text-center text-sm font-medium text-[#262624] dark:text-white shadow-sm">
                  原生格式 API 入口
                </div>
                <ArrowRight class="hidden md:block w-5 h-5 text-[#cc785c] mx-1 shrink-0" />
                <div class="md:hidden flex justify-center py-1">
                  <ArrowRight class="w-5 h-5 text-[#cc785c] rotate-90" />
                </div>

                <div class="flex-[2] bg-blue-500/5 dark:bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-center text-sm font-medium text-blue-600 dark:text-blue-400">
                  同格式请求原生透传 → 上游提供商 → 原生响应透传
                </div>
                <ArrowRight class="hidden md:block w-5 h-5 text-[#cc785c] mx-1 shrink-0" />
                <div class="md:hidden flex justify-center py-1">
                  <ArrowRight class="w-5 h-5 text-[#cc785c] rotate-90" />
                </div>

                <div class="flex-1 bg-white dark:bg-[#191714] border border-[#e5e4df] dark:border-white/10 rounded-lg p-3 text-center text-sm font-medium text-[#262624] dark:text-white shadow-sm">
                  原生 API 出口
                </div>
              </div>
            </div>
          </li>

          <li class="flex items-start gap-4">
            <div class="w-10 h-10 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 mt-1 shadow-sm">
              <span class="font-bold font-mono">5</span>
            </div>
            <div>
              <h3 class="text-lg font-medium text-[#262624] dark:text-[#f1ead8] m-0 mb-1">
                响应回路
              </h3>
              <p class="text-sm text-[#666663] dark:text-[#a3a094] leading-relaxed">
                上游提供商返回的响应会经过逆向格式转换（跨平台场景）或直接透传（同生态场景），同时将提供商内部的模型名还原为客户端请求时使用的统一模型名，确保客户端收到格式和字段完全兼容的响应。
              </p>
            </div>
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>
