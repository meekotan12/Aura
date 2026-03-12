<template>
  <!-- Desktop Left Sidebar -->
  <aside
    class="hidden md:flex fixed left-4 top-1/2 -translate-y-1/2 z-50 flex-col items-center bg-[#0A0A0A] shadow-2xl"
    style="width: 52px; border-radius: 32px; min-height: 380px;"
    aria-label="Desktop navigation"
  >
    <!-- Nav icons (top section) -->
    <div class="flex flex-col items-center gap-0 pt-5 pb-3 flex-1 w-full">
      <button
        v-for="item in navItems"
        :key="item.name"
        @click="navigate(item.route)"
        :aria-label="item.name"
        class="relative flex flex-col items-center justify-center w-full py-3.5 gap-1 transition-all duration-200"
        :class="isActive(item.route) ? '' : 'opacity-35 hover:opacity-65'"
      >
        <!-- Active glowing background -->
        <span
          v-if="isActive(item.route)"
          class="absolute w-12 h-12 rounded-full pointer-events-none"
          style="background: radial-gradient(circle, var(--color-primary) 0%, transparent 65%); opacity: 0.15; top: 50%; transform: translateY(-50%);"
        />

        <!-- Icon -->
        <component
          :is="item.icon"
          :size="19"
          :stroke-width="isActive(item.route) ? 2.2 : 1.6"
          :color="isActive(item.route) ? 'var(--color-primary)' : '#FFFFFF'"
          class="relative z-10 transition-all duration-200"
        />
        <!-- Active dot below icon -->
        <span
          class="w-1 h-1 rounded-full transition-all duration-200"
          :style="isActive(item.route)
            ? 'background: var(--color-primary); opacity: 1;'
            : 'background: transparent; opacity: 0;'"
        />
      </button>
    </div>

    <!-- ── Talk to Aura AI pill ──────────────────────────────── -->
    <div ref="pillRef" class="relative w-[40px] h-[74px] mx-2 mb-1.5 z-50">
      <div
        class="absolute top-0 left-0 flex flex-col overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] shadow-lg origin-left"
        :class="isMiniOpen
          ? 'w-[300px] h-[190px] rounded-[32px] cursor-default'
          : 'w-[40px] h-[74px] rounded-[26px] cursor-pointer hover:brightness-110 hover:scale-105 active:scale-95'"
        style="background: var(--color-primary);"
        @click="!isMiniOpen ? openPill() : null"
      >
        <!-- ── COLLAPSED STATE ─────────────────────────────────── -->
        <div
          class="absolute inset-0 flex flex-col items-center justify-center gap-1 transition-opacity duration-300"
          :class="isMiniOpen ? 'opacity-0 pointer-events-none' : 'opacity-100'"
        >
          <img :src="activeAuraLogo" alt="Aura" class="w-6 h-6 object-contain opacity-90" />
          <span
            class="text-[8px] font-extrabold text-center leading-snug transition-colors duration-200"
            style="color: var(--color-banner-text);"
          >
            Talk to<br>Aura Ai
          </span>
        </div>

        <!-- ── MINI EXPANDED STATE ────────────────────────────── -->
        <div
          class="absolute inset-0 flex flex-col p-3 transition-opacity duration-300 delay-100"
          :class="isMiniOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'"
        >
          <!-- Mini header: logo (close) + expand button -->
          <div class="flex items-center justify-between mb-2">
            <img
              :src="activeAuraLogo"
              alt="Aura"
              class="w-7 h-7 object-contain opacity-90 cursor-pointer transition-transform hover:scale-110"
              title="Collapse chat"
              @click.stop="closeMini"
            />
            <!-- ★ This expand button opens the full floating window -->
            <button
              class="p-1.5 hover:bg-black/10 rounded-full transition-colors"
              aria-label="Expand chat to full window"
              title="Open full chat"
              @click.stop="expandToFull"
            >
              <Maximize2 :size="15" :color="'var(--color-banner-text)'" />
            </button>
          </div>

          <!-- Mini messages (read-only scroll) -->
          <div class="mini-messages flex-1 overflow-y-auto scrollbar-hide pb-1">
            <TransitionGroup name="mini-bubble" tag="div" class="mini-messages-inner">
              <div
                v-for="msg in messages"
                :key="msg.id"
                :class="msg.sender === 'ai' ? 'mini-bubble mini-bubble--ai' : 'mini-bubble mini-bubble--user'"
              >
                {{ msg.text }}
              </div>

              <!-- Typing dots -->
              <div v-if="isTyping" key="typing" class="mini-bubble mini-bubble--ai mini-bubble--typing">
                <div class="w-1.5 h-1.5 rounded-full bg-black/40 animate-bounce" style="animation-delay:0ms"   />
                <div class="w-1.5 h-1.5 rounded-full bg-black/40 animate-bounce" style="animation-delay:150ms" />
                <div class="w-1.5 h-1.5 rounded-full bg-black/40 animate-bounce" style="animation-delay:300ms" />
              </div>
            </TransitionGroup>
          </div>

          <!-- Mini input -->
          <div class="mt-1">
            <div
              class="h-[36px] rounded-full border border-black/20 flex items-center px-3 gap-2 bg-black/5"
              :style="{ borderColor: 'var(--color-banner-text)' }"
            >
              <input
                type="text"
                v-model="inputText"
                class="bg-transparent outline-none text-[11px] w-full placeholder-black/40 font-medium"
                :style="{ color: 'var(--color-banner-text)' }"
                placeholder="Ask Aura..."
                :disabled="isTyping"
                @keyup.enter="sendMessage"
              />
              <button
                @click="sendMessage"
                :disabled="!inputText.trim() || isTyping"
                class="cursor-pointer transition-opacity hover:opacity-100 disabled:opacity-40 flex-shrink-0"
                :class="inputText.trim() ? 'opacity-100' : 'opacity-60'"
              >
                <Send :size="14" :color="'var(--color-banner-text)'" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>

  <!-- ── Full floating chat window (teleported to body) ────── -->
  <AuraChatWindow />
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Home, User, Calendar, BarChart2, Maximize2, Send } from 'lucide-vue-next'
import { activeAuraLogo } from '@/config/theme.js'
import { useChat } from '@/composables/useChat.js'
import AuraChatWindow from '@/components/ui/AuraChatWindow.vue'

// ── Chat state from singleton composable ──────────────────
const {
  messages,
  inputText,
  isTyping,
  isMiniOpen,
  sendMessage,
  openPill,
  closeMini,
  expandToFull,
} = useChat()

// ── Click-outside to close mini pill ─────────────────────
const pillRef = ref(null)

function handleOutsideClick(e) {
  if (isMiniOpen.value && pillRef.value && !pillRef.value.contains(e.target)) {
    closeMini()
  }
}

onMounted(()  => document.addEventListener('mousedown', handleOutsideClick))
onUnmounted(() => document.removeEventListener('mousedown', handleOutsideClick))

// ── Navigation ────────────────────────────────────────────
const navItems = [
  { name: 'Home',      route: '/dashboard',           icon: Home      },
  { name: 'Profile',   route: '/dashboard/profile',   icon: User      },
  { name: 'Schedule',  route: '/dashboard/schedule',  icon: Calendar  },
  { name: 'Analytics', route: '/dashboard/analytics', icon: BarChart2 },
]

const router = useRouter()
const route  = useRoute()

function isActive(path) {
  if (path === '/dashboard') return route.path === '/dashboard' || route.path === '/dashboard/'
  return route.path.startsWith(path)
}

function navigate(path) {
  router.push(path)
}
</script>

<style scoped>
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }

/* ── Mini messages layout ─────────────────────────── */
.mini-messages {
  flex: 1;
  overflow-y: auto;
}

.mini-messages-inner {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ── Mini bubbles ─────────────────────────────────── */
.mini-bubble {
  max-width: 90%;
  padding: 10px 14px;
  border-radius: 25px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.6;
  word-break: break-word;
  font-family: 'Manrope', sans-serif;
}

.mini-bubble--ai {
  align-self: flex-start;
  background: #ffffff;
  color: #0a0a0a;
  border: 1px solid rgba(0,0,0,0.05);
}

.mini-bubble--user {
  align-self: flex-end;
  background: rgba(0,0,0,0.10);
  color: var(--color-banner-text);
  border: 1px solid rgba(255,255,255,0.10);
}

.mini-bubble--typing {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 10px 14px;
}

/* ── iMessage spring pop ──────────────────────────── */
.mini-bubble-enter-active {
  animation: mini-bubble-pop 0.42s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.mini-bubble--ai.mini-bubble-enter-active  { transform-origin: bottom left;  }
.mini-bubble--user.mini-bubble-enter-active { transform-origin: bottom right; }

@keyframes mini-bubble-pop {
  0%   { opacity: 0; transform: scale(0.55); }
  65%  { opacity: 1; transform: scale(1.04); }
  82%  { transform: scale(0.97);             }
  100% { transform: scale(1);                }
}
</style>
