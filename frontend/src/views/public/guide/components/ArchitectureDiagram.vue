<script setup lang="ts">
import { computed } from 'vue'
import { useDarkMode } from '@/composables/useDarkMode'

const { isDark } = useDarkMode()

// Ultra-premium floating aesthetic palette
const colors = computed(() => {
  const brandVal = isDark.value ? '#d4a27f' : '#cc785c'
  return {
    // Pure, infinite canvas 
    bg: isDark.value ? '#080808' : '#fafafa',
    grid: isDark.value ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
    
    // Floating Cards - completely solid, crisp edges
    cardBg: isDark.value ? '#121212' : '#ffffff',
    cardBorder: isDark.value ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
    
    // Core Card 
    coreBg: isDark.value ? '#171615' : '#ffffff',
    coreBorder: isDark.value ? 'rgba(212, 162, 127, 0.3)' : 'rgba(204, 120, 92, 0.25)',
    
    // Text
    textMain: isDark.value ? '#f5f5f5' : '#111111',
    textMuted: isDark.value ? '#888888' : '#777777',
    
    // Thematic Flow Colors
    brand: brandVal, // Ingress
    convertAccent: '#a855f7', // Conversion
    passAccent: '#3b82f6', // Passthrough
    returnAccent: '#10b981', // Loop
    proxyAccent: '#f59e0b', // Proxies

    // The fluid river tracks
    trackMain: isDark.value ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)'
  }
})

// Clean, precise floating shadow
const shadows = computed(() => {
  return isDark.value 
    ? {
        node: '0 8px 30px rgba(0,0,0,0.6)',
        coreGlow: '0 0 40px rgba(212, 162, 127, 0.03)',
      }
    : {
        node: '0 8px 30px rgba(0,0,0,0.06)',
        coreGlow: '0 0 40px rgba(204, 120, 92, 0.03)',
      }
})
</script>

<template>
  <div
    class="relative w-full overflow-hidden rounded-[32px] border diagram-container"
    :style="{ 
      backgroundColor: colors.bg, 
      borderColor: colors.cardBorder,
      /* Hyper-clean infinite Dot Grid Background */
      backgroundImage: `radial-gradient(${colors.grid} 1px, transparent 1px)`,
      backgroundSize: '24px 24px'
    }"
  >
    <!-- Horizontal scroll wrapper for the dynamic wide canvas -->
    <div class="w-full overflow-x-auto pb-4 custom-scrollbar">
      <!-- Absolute, unconstrained canvas simulating an infinite whiteboard -->
      <!-- Width extends far enough to fit all spaced-out floating nodes -->
      <div class="relative min-w-[1300px] h-[680px] mx-auto overflow-visible py-16 px-10">
        <!-- ==================== FLUID SVG "RIVERS" (The glowing tracks) ==================== -->
        <!-- Placed perfectly behind the HTML nodes. Z-0 -->
        <svg
          class="absolute inset-0 w-full h-full pointer-events-none z-0 overflow-visible"
          viewBox="0 0 1300 680"
          preserveAspectRatio="none"
        >
          
          <!-- Defs for beautiful organic gradients -->
          <defs>
            <linearGradient
              id="grad-convert"
              x1="0%"
              y1="0%"
              x2="100%"
              y2="0%"
            >
              <stop
                offset="0%"
                :stop-color="colors.brand"
              />
              <stop
                offset="100%"
                :stop-color="colors.convertAccent"
              />
            </linearGradient>
            <linearGradient
              id="grad-pass"
              x1="0%"
              y1="0%"
              x2="100%"
              y2="100%"
            >
              <stop
                offset="0%"
                :stop-color="colors.brand"
              />
              <stop
                offset="100%"
                :stop-color="colors.passAccent"
              />
            </linearGradient>
            <!-- Soft glow filter for the tracks themselves -->
            <filter
              id="glow-track"
              x="-20%"
              y="-20%"
              width="140%"
              height="140%"
            >
              <feGaussianBlur
                stdDeviation="3"
                result="blur"
              />
              <feComposite
                in="SourceGraphic"
                in2="blur"
                operator="over"
              />
            </filter>
          </defs>

          <!-- The Base Tracks (Ghost Rivers) -->
          <g
            :stroke="colors.trackMain"
            stroke-width="2"
            fill="none"
            stroke-linecap="round"
          >
            
            <!-- Ingress Tributaries: 3 Clients -> 1 Core -->
            <!-- Starting X: 220 (clients), Ending X: 380 (core) -->
            <path
              id="flow-in-1"
              d="M 220 180 C 300 180, 270 300, 380 300"
            />
            <path
              id="flow-in-2"
              d="M 220 300 L 380 300"
            />
            <path
              id="flow-in-3"
              d="M 220 420 C 300 420, 270 300, 380 300"
            />
            
            <!-- Egress Delta: Core -> 2 Flow Engines -->
            <!-- Starting X: 580 (core), Ending X: 750 (engines) -->
            <!-- Beautiful fluid Bezier splits -->
            <path
              id="flow-out-top"
              d="M 580 300 C 650 300, 650 200, 750 200"
            />
            <path
              id="flow-out-bot"
              d="M 580 300 C 650 300, 650 400, 750 400"
            />

            <!-- To the Cloud Delta: Processors -> Destinations -->
            <!-- Starting X: 950 (engines), Ending X: 1100 (destinations) -->
            
            <!-- From Purple Mapping Engine -->
            <path
              id="flow-cloud-1"
              d="M 950 200 C 1030 200, 1030 140, 1100 140"
            />
            <path
              id="flow-cloud-2"
              d="M 950 200 C 1020 200, 1020 200, 1100 200"
            />
            <path
              id="flow-cloud-3"
              d="M 950 200 C 1030 200, 1030 260, 1100 260"
            />

            <!-- From Blue Passthrough Engine -->
            <path
              id="flow-proxy-1"
              d="M 950 400 C 1030 400, 1030 360, 1100 360"
            />
            <path
              id="flow-proxy-2"
              d="M 950 400 C 1030 400, 1030 420, 1100 420"
            />
            <path
              id="flow-proxy-3"
              d="M 950 400 C 1030 400, 1030 480, 1100 480"
            />
          </g>

          <!-- The Majestic Return Arch (Response Loop) -->
          <g
            :stroke="colors.returnAccent"
            stroke-width="2"
            fill="none"
            opacity="0.25"
          >
            <path
              id="flow-return"
              d="M 1150 510 C 1150 630, 950 640, 600 640 C 250 640, 120 600, 120 480"
            />
          </g>

          <!-- ==================== GLOWING DATA PACKET ANIMATIONS ==================== -->
          <!-- We use slightly larger, softer glowing circles to emphasize the "fluid" nature -->
          
          <g style="filter: drop-shadow(0 0 8px currentColor)">
            <!-- Ingress Flow -->
            <circle
              r="4"
              :fill="colors.brand"
            >
              <animateMotion
                dur="2.2s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-in-1" /></animateMotion>
            </circle>
            <circle
              r="4"
              :fill="colors.brand"
            >
              <animateMotion
                dur="1.8s"
                begin="0.5s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-in-2" /></animateMotion>
            </circle>
            <circle
              r="4"
              :fill="colors.brand"
            >
              <animateMotion
                dur="2.4s"
                begin="0.2s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-in-3" /></animateMotion>
            </circle>

            <!-- Delta Splits (Using gradients) -->
            <circle
              r="4.5"
              :fill="colors.convertAccent"
            >
              <animateMotion
                dur="2s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-out-top" /></animateMotion>
            </circle>
            <circle
              r="4.5"
              :fill="colors.passAccent"
            >
              <!-- Make this packet slightly pulsing -->
              <animate
                attributeName="r"
                values="4;5;4"
                dur="1s"
                repeatCount="indefinite"
              />
              <animateMotion
                dur="2.1s"
                begin="0.8s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-out-bot" /></animateMotion>
            </circle>

            <!-- Cloud Destiny -->
            <circle
              r="3.5"
              :fill="colors.convertAccent"
            >
              <animateMotion
                dur="1.5s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-cloud-1" /></animateMotion>
            </circle>
            <circle
              r="3.5"
              :fill="colors.convertAccent"
            >
              <animateMotion
                dur="1.4s"
                begin="0.4s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-cloud-3" /></animateMotion>
            </circle>
            <circle
              r="3.5"
              :fill="colors.passAccent"
            >
              <animateMotion
                dur="1.6s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-proxy-1" /></animateMotion>
            </circle>
            <circle
              r="3.5"
              :fill="colors.passAccent"
            >
              <animateMotion
                dur="1.5s"
                begin="0.7s"
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.2 1"
              ><mpath href="#flow-proxy-3" /></animateMotion>
            </circle>
          </g>

          <!-- Return Path Slow Comets -->
          <circle
            r="5"
            :fill="colors.returnAccent"
            style="filter: drop-shadow(0 0 10px currentColor)"
          >
            <animateMotion
              dur="6s"
              repeatCount="indefinite"
            ><mpath href="#flow-return" /></animateMotion>
          </circle>
          <circle
            r="5"
            :fill="colors.returnAccent"
            style="filter: drop-shadow(0 0 10px currentColor)"
          >
            <animateMotion
              dur="6s"
              begin="3s"
              repeatCount="indefinite"
            ><mpath href="#flow-return" /></animateMotion>
          </circle>

        </svg>

        <!-- ========================================================================= -->
        <!-- FREE FLOATING HTML NODES                                                  -->
        <!-- Beautifully positioned to align exactly with the ends of the SVG rivers   -->
        <!-- ========================================================================= -->
        
        <!-- 1. INGRESS CLIENTS -->
        <div class="absolute left-10 top-[160px] flex flex-col gap-[80px] z-10 w-[140px]">
          <div class="absolute -top-[45px] font-sans text-[11px] font-bold tracking-[0.2em] uppercase opacity-40 ml-4 flex gap-2 items-center">
            <div
              class="w-1.5 h-1.5 rounded-full"
              :style="{ backgroundColor: colors.textMuted }"
            />Sources
          </div>
          <!-- Nodes -->
          <div
            class="h-[40px] rounded-xl flex items-center px-4 gap-3 bg-white dark:bg-[#121212] transition-transform hover:-translate-y-1 cursor-pointer"
            :style="{ border: `1px solid ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <div
              class="w-2 h-2 rounded-full"
              :style="{ backgroundColor: colors.brand }"
            />
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >Claude</span>
          </div>
          <div
            class="h-[40px] rounded-xl flex items-center px-4 gap-3 bg-white dark:bg-[#121212] transition-transform hover:-translate-y-1 cursor-pointer"
            :style="{ border: `1px solid ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <div
              class="w-2 h-2 rounded-full"
              :style="{ backgroundColor: colors.brand }"
            />
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >OpenAI</span>
          </div>
          <div
            class="h-[40px] rounded-xl flex items-center px-4 gap-3 bg-white dark:bg-[#121212] transition-transform hover:-translate-y-1 cursor-pointer"
            :style="{ border: `1px solid ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <div
              class="w-2 h-2 rounded-full"
              :style="{ backgroundColor: colors.brand }"
            />
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >Gemini</span>
          </div>
        </div>


        <!-- 2. THE AETHER NEXUS (Core Gateway) -->
        <!-- Perfectly centered vertically. Y anchors to 300px -->
        <div
          class="absolute left-[380px] top-[140px] w-[200px] rounded-[24px] py-8 px-5 z-20 flex flex-col items-center transition-transform hover:scale-[1.02]"
          :style="{ backgroundColor: colors.coreBg, border: `1px solid ${colors.coreBorder}`, boxShadow: `${shadows.node}, ${shadows.coreGlow}` }"
        >
          <div
            class="absolute -top-3.5 px-3 py-0.5 rounded-full shadow-sm bg-white dark:bg-[#111] text-[10px] font-bold tracking-[0.2em] font-sans" 
            :style="{ color: colors.brand, border: `1px solid ${colors.cardBorder}` }"
          >
            AETHER
          </div>
           
          <h3 class="text-xl font-bold font-sans tracking-[0.1em] mb-8 text-transparent bg-clip-text bg-gradient-to-r from-neutral-800 to-neutral-400 dark:from-white dark:to-neutral-500">
            GATEWAY
          </h3>

          <!-- Internal Micro-Pills -->
          <div class="flex flex-col gap-2.5 w-full">
            <div
              class="h-[32px] rounded-lg border-b flex items-center justify-center font-sans text-[10px] font-medium opacity-70"
              :style="{ borderColor: colors.cardBorder, color: colors.textMain }"
            >
              统一模型名 / 格式聚合
            </div>
              
            <div class="flex gap-2">
              <div
                class="flex-1 rounded-lg flex items-center justify-center py-[7px] font-sans font-bold text-[10px] bg-black/[0.04] dark:bg-white/[0.04]"
                :style="{ color: colors.textMain }"
              >
                鉴定
              </div>
              <div
                class="flex-1 rounded-lg flex items-center justify-center py-[7px] font-sans font-bold text-[10px] bg-black/[0.04] dark:bg-white/[0.04]"
                :style="{ color: colors.textMain }"
              >
                并发
              </div>
            </div>
              
            <div
              class="h-[36px] rounded-lg border flex items-center justify-center font-sans text-[10px] font-bold relative mt-2" 
              :style="{ borderColor: colors.coreBorder, color: colors.textMain, backgroundColor: isDark ? 'rgba(212, 162, 127, 0.05)' : 'rgba(204, 120, 92, 0.03)' }"
            >
              智能分发引擎
              <div
                class="absolute -right-[5px] w-2 h-2 rounded-full bg-current"
                :style="{ color: colors.brand }"
              />
            </div>
          </div>
        </div>


        <!-- 3. EGRESS DELTA ENGINES -->
        <!-- Y perfectly aligned to the flow-out-top (y=200) and flow-out-bot (y=400) -->
        
        <!-- Format Engine (Purple) -->
        <div
          class="absolute left-[750px] top-[165px] w-[200px] h-[70px] rounded-2xl flex flex-col justify-center px-6 z-10 transition-transform hover:-translate-y-1 cursor-pointer"
          :style="{ backgroundColor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, boxShadow: shadows.node }"
        >
          <div
            class="absolute -left-1 w-2 h-6 rounded-full"
            :style="{ backgroundColor: colors.convertAccent }"
          />
          <span
            class="font-sans text-[14px] font-bold tracking-wide flex items-center gap-2 mb-1"
            :style="{ color: colors.textMain }"
          >格式转换流 <div
            class="w-1.5 h-1.5 rounded-full animate-pulse"
            :style="{ backgroundColor: colors.convertAccent }"
          /></span>
          <span
            class="font-sans text-[9px] opacity-50"
            :style="{ color: colors.textMain }"
          >双向翻译协议与模型还原</span>
        </div>

        <!-- Passthrough Engine (Blue) -->
        <div
          class="absolute left-[750px] top-[365px] w-[200px] h-[70px] rounded-2xl flex flex-col justify-center px-6 z-10 transition-transform hover:-translate-y-1 cursor-pointer border-dashed"
          :style="{ backgroundColor: colors.cardBg, borderColor: colors.cardBorder, borderWidth: '2px', boxShadow: shadows.node }"
        >
          <div
            class="absolute -left-1.5 w-2.5 h-6 rounded-full border-2 bg-transparent"
            :style="{ borderColor: colors.passAccent }"
          />
          <span
            class="font-sans text-[14px] font-bold tracking-wide flex items-center gap-2 mb-1"
            :style="{ color: colors.passAccent }"
          >原生直通管道</span>
          <span
            class="font-sans text-[9px] opacity-60"
            :style="{ color: colors.textMain }"
          >同源生态双向超低延迟透传</span>
        </div>


        <!-- 4. UPSTREAM CLOUDS & PROXIES -->
        
        <!-- Standard Cloud Targets (Top Flow: Y=140, 200, 260) -->
        <div class="absolute left-[1100px] top-[120px] flex flex-col gap-[20px] w-[140px] z-10">
          <div
            class="absolute -top-[30px] font-sans text-[11px] font-bold tracking-[0.2em] uppercase"
            :style="{ color: colors.convertAccent }"
          >
            Providers
          </div>
           
          <div
            class="h-[40px] rounded-xl flex items-center justify-between px-4 bg-white dark:bg-[#121212] transition-all hover:ring-2 hover:ring-purple-500/30"
            :style="{ border: `1px solid ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >Claude</span>
            <div
              class="w-1.5 h-1.5 rounded-full"
              :style="{ backgroundColor: colors.textMuted }"
            />
          </div>
          <div
            class="h-[40px] rounded-xl flex items-center justify-between px-4 bg-white dark:bg-[#121212] transition-all hover:ring-2 hover:ring-purple-500/30"
            :style="{ border: `1px solid ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >OpenAI</span>
            <div
              class="w-1.5 h-1.5 rounded-full"
              :style="{ backgroundColor: colors.textMuted }"
            />
          </div>
          <div
            class="h-[40px] rounded-xl flex items-center justify-between px-4 bg-white dark:bg-[#121212] transition-all hover:ring-2 hover:ring-purple-500/30"
            :style="{ border: `1px solid ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >Gemini</span>
            <div
              class="w-1.5 h-1.5 rounded-full"
              :style="{ backgroundColor: colors.textMuted }"
            />
          </div>
        </div>

        <!-- Proxy Targets (Bottom Flow: Y=360, 420, 480) -->
        <div class="absolute left-[1100px] top-[340px] flex flex-col gap-[20px] w-[140px] z-10">
          <div
            class="absolute -top-[30px] font-sans text-[11px] font-bold tracking-[0.2em] uppercase"
            :style="{ color: colors.passAccent }"
          >
            Proxies
          </div>
           
          <div
            class="h-[40px] rounded-xl flex items-center justify-between px-4 bg-white dark:bg-[#121212] transition-all hover:ring-2 hover:ring-blue-500/30"
            :style="{ border: `1px dashed ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >Codex</span>
          </div>
          <div
            class="h-[40px] rounded-xl flex items-center justify-between px-4 bg-white dark:bg-[#121212] transition-all hover:ring-2 hover:ring-blue-500/30"
            :style="{ border: `1px dashed ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >Kiro</span>
          </div>
          <div
            class="h-[40px] rounded-xl flex items-center justify-between px-4 bg-white dark:bg-[#121212] transition-all hover:ring-2 hover:ring-blue-500/30"
            :style="{ border: `1px dashed ${colors.cardBorder}`, boxShadow: shadows.node }"
          >
            <span
              class="font-sans text-[12px] font-semibold tracking-wide"
              :style="{ color: colors.textMain }"
            >Antigrav</span>
          </div>
        </div>


        <!-- 5. THE ORGANIC RETURN LOOP OVERLAYS -->
        <!-- Floating labels sitting precisely on the huge bottom elliptic sweep -->
        
        <!-- Left anchor label -->
        <div
          class="absolute left-[120px] bottom-[20px] bg-white/80 dark:bg-black/60 backdrop-blur-md px-4 py-2 rounded-2xl border" 
          :style="{ borderColor: colors.cardBorder, color: colors.returnAccent, boxShadow: shadows.node }"
        >
          <div class="font-sans text-[10px] font-bold tracking-wide flex items-center gap-2">
            <svg
              class="w-3 h-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            ><polyline points="15 18 9 12 15 6" /></svg>返回兼容格式响应
          </div>
        </div>

        <!-- Center massive anchor -->
        <div
          class="absolute left-[540px] bottom-[15px] bg-white dark:bg-[#121212] px-6 py-2.5 rounded-full border-2 flex items-center gap-4 z-20 cursor-default" 
          :style="{ borderColor: colors.returnAccent, boxShadow: shadows.node }"
        >
          <div
            class="w-2.5 h-2.5 rounded-full animate-ping absolute"
            :style="{ backgroundColor: colors.returnAccent, opacity: 0.4 }"
          />
          <div
            class="w-2.5 h-2.5 rounded-full relative"
            :style="{ backgroundColor: colors.returnAccent }"
          />
          <div class="flex flex-col">
            <span
              class="font-sans text-[13px] font-bold tracking-widest uppercase"
              :style="{ color: colors.returnAccent }"
            >Response Loop</span>
            <span
              class="font-sans text-[10px] font-semibold opacity-60 mt-0.5"
              :style="{ color: colors.textMain }"
            >响应逆向格式转换 / 上游模型实体还原</span>
          </div>
        </div>

        <!-- Right anchor label -->
        <div
          class="absolute right-[120px] bottom-[90px] bg-white/80 dark:bg-black/60 backdrop-blur-md px-4 py-2 rounded-2xl border" 
          :style="{ borderColor: colors.cardBorder, color: colors.returnAccent, boxShadow: shadows.node }"
        >
          <div class="font-sans text-[10px] font-bold tracking-wide flex items-center gap-2">
            拉取上游原始流端<svg
              class="w-3 h-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            ><polyline points="9 18 15 12 9 6" /></svg>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.font-sans {
  font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Custom horizontal scrollbar for tight spaces */
.custom-scrollbar::-webkit-scrollbar {
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(150, 150, 150, 0.2);
  border-radius: 20px;
}
.custom-scrollbar:hover::-webkit-scrollbar-thumb {
  background-color: rgba(150, 150, 150, 0.4);
}
</style>
