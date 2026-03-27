<template>
  <!-- Desktop Left Sidebar -->
  <aside
    class="nav-rail hidden md:flex fixed left-4 z-50"
    :style="navRailStyle"
    aria-label="Desktop navigation"
  >
    <div class="nav-rail__shell">
      <div class="nav-rail__content">
        <!-- Nav icons (top section) -->
        <div class="nav-rail__nav">
          <button
            v-for="item in navItems"
            :key="item.name"
            @click="navigate(item.route)"
            :aria-label="item.name"
            class="nav-rail__button"
            :class="isActive(item) ? 'nav-rail__button--active' : 'nav-rail__button--idle'"
          >
            <!-- Active glowing background -->
            <span
              v-if="isActive(item)"
              class="nav-rail__glow"
              style="background: radial-gradient(circle, var(--color-primary) 0%, transparent 65%); opacity: 0.15; top: 50%; transform: translateY(-50%);"
            />

            <!-- Icon -->
            <component
              :is="item.icon"
              :size="19"
              :stroke-width="isActive(item) ? 2.2 : 1.6"
              :color="isActive(item) ? 'var(--color-primary)' : 'var(--color-nav-text)'"
              class="nav-rail__icon"
            />
            <!-- Active dot below icon -->
            <span
              class="nav-rail__dot"
              :style="isActive(item)
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
      </div>
    </div>
  </aside>

  <!-- ── Full floating chat window (teleported to body) ────── -->
  <AuraChatWindow />
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Maximize2, Send } from 'lucide-vue-next'
import { activeAuraLogo } from '@/config/theme.js'
import { useChat } from '@/composables/useChat.js'
import AuraChatWindow from '@/components/ui/AuraChatWindow.vue'
import { getNavigationItemsForRoute } from '@/components/navigation/navigationItems.js'

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
const router = useRouter()
const route  = useRoute()
const navItems = computed(() => getNavigationItemsForRoute(route))
const railHeight = computed(() => Math.max(380, 150 + (navItems.value.length * 58)))
const navRailStyle = computed(() => ({
  '--nav-rail-height': `${railHeight.value}px`,
  height: `${railHeight.value}px`,
  top: `calc(50vh - ${railHeight.value / 2}px)`,
}))

function isActive(item) {
  const path = item?.route
  if (
    path === '/dashboard' ||
    path === '/exposed/dashboard' ||
    path === '/workspace' ||
    path === '/exposed/workspace' ||
    path === '/admin' ||
    path === '/exposed/admin' ||
    path === '/sg' ||
    path === '/exposed/sg'
  ) {
    return route.path === path || route.path === `${path}/`
  }

  const matchPrefixes = Array.isArray(item?.matchPrefixes) ? item.matchPrefixes : []
  return route.path.startsWith(path) || matchPrefixes.some((prefix) => route.path.startsWith(prefix))
}

function navigate(path) {
  if (route.path === path) return
  router.push(path)
}
</script>

<style scoped>
.nav-rail {
  position: fixed;
  left: 16px;
  width: 52px;
  height: var(--nav-rail-height);
  min-height: 380px;
}

.nav-rail__shell {
  position: relative;
  isolation: isolate;
  overflow: visible;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  height: 100%;
  border-radius: 32px;
  background: var(--color-nav-glass-bg);
  border: 1px solid var(--color-nav-glass-border);
  box-shadow: var(--color-nav-glass-shadow);
}

.nav-rail__shell::before,
.nav-rail__shell::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
}

.nav-rail__shell::before {
  z-index: -2;
  background: var(--color-nav-glass-layer);
  box-shadow: inset 0 1px 0 var(--color-nav-glass-inset);
}

.nav-rail__shell::after {
  z-index: -1;
  background:
    var(--color-nav-glass-light),
    linear-gradient(180deg, rgba(255, 255, 255, 0.06) 0%, rgba(255, 255, 255, 0.01) 48%, rgba(255, 255, 255, 0.08) 100%);
}

.nav-rail__content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  height: 100%;
}

.nav-rail__nav {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding: 18px 0 12px;
  gap: 2px;
  flex: 1;
}

.nav-rail__button {
  position: relative;
  width: 100%;
  min-height: 54px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: opacity 200ms ease, transform 220ms ease;
}

.nav-rail__button--idle {
  opacity: 0.35;
}

.nav-rail__button--idle:hover {
  opacity: 0.65;
  transform: translateY(-1px);
}

.nav-rail__button--active {
  opacity: 1;
}

.nav-rail__glow {
  position: absolute;
  width: 48px;
  height: 48px;
  border-radius: 999px;
  pointer-events: none;
}

.nav-rail__icon {
  position: relative;
  z-index: 10;
  transition: transform 220ms ease, opacity 200ms ease;
}

.nav-rail__button--active .nav-rail__icon {
  transform: scale(1.04);
}

.nav-rail__dot {
  width: 4px;
  height: 4px;
  border-radius: 999px;
  transition: opacity 200ms ease, background-color 200ms ease, transform 220ms ease;
}

.nav-rail__button--active .nav-rail__dot {
  transform: translateY(1px);
}

@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .nav-rail__shell {
    -webkit-backdrop-filter: blur(var(--nav-glass-blur)) saturate(135%);
    backdrop-filter: blur(var(--nav-glass-blur)) saturate(135%);
  }
}

@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .nav-rail__shell {
    background: var(--color-nav-glass-bg);
  }
}

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
  background: var(--color-surface);
  color: var(--color-surface-text);
  border: 1px solid var(--color-surface-border);
}

.mini-bubble--user {
  align-self: flex-end;
  background: rgba(0,0,0,0.10);
  color: var(--color-primary-text);
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
