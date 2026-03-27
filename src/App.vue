<template>
  <div class="app-safe-area">
    <Transition name="app-boot-fade">
      <div v-if="showInitialBootScreen" class="app-boot-screen" aria-live="polite">
        <div class="app-boot-card">
          <div class="app-boot-spinner" aria-hidden="true"></div>
          <p class="app-boot-title">Loading Aura</p>
          <p class="app-boot-subtitle">Preparing the login and dashboard experience.</p>
        </div>
      </div>
    </Transition>

    <!-- Offline Banner -->
    <Transition name="offline-banner">
      <div v-if="!networkOnline" class="offline-banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="1" y1="1" x2="23" y2="23" />
          <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
          <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
          <path d="M10.71 5.05A16 16 0 0 1 22.56 9" />
          <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
          <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
          <line x1="12" y1="20" x2="12.01" y2="20" />
        </svg>
        <span>You're offline</span>
      </div>
    </Transition>

    <section v-if="fatalErrorMessage" class="app-fatal-screen">
      <div class="app-fatal-card">
        <h1 class="app-fatal-title">Aura needs a refresh</h1>
        <p class="app-fatal-message">{{ fatalErrorMessage }}</p>
        <div class="app-fatal-actions">
          <button type="button" class="app-fatal-btn app-fatal-btn--primary" @click="reloadApp">
            Reload app
          </button>
          <button type="button" class="app-fatal-btn" @click="goToLogin">
            Go to login
          </button>
        </div>
      </div>
    </section>

    <RouterView v-else />

    <Transition name="mobile-fullscreen-hint">
      <button
        v-if="mobileFullscreenHintVisible"
        type="button"
        class="mobile-fullscreen-hint"
        @click="requestMobileFullscreen"
      >
        Tap anywhere to enter fullscreen
      </button>
    </Transition>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterView } from 'vue-router'
import { mobileFullscreenHintVisible, requestMobileFullscreen } from '@/services/mobileFullscreen.js'
import { isOnline } from '@/composables/useNetworkStatus.js'
import { appFatalErrorMessage, clearAppFatalError } from '@/services/appBootstrap.js'
import { isNavigationPending } from '@/services/navigationState.js'
import { clearDashboardSession } from '@/composables/useDashboardSession.js'
import { useRouter } from 'vue-router'

const router = useRouter()
const networkOnline = computed(() => isOnline.value)
const fatalErrorMessage = computed(() => appFatalErrorMessage.value)
const hasResolvedInitialRoute = ref(false)
const showInitialBootScreen = computed(() => !hasResolvedInitialRoute.value && isNavigationPending.value)

watch(
  isNavigationPending,
  (pending) => {
    if (!pending) {
      hasResolvedInitialRoute.value = true
    }
  },
  { immediate: true }
)

function reloadApp() {
  clearAppFatalError()
  window.location.reload()
}

function goToLogin() {
  clearDashboardSession()
  clearAppFatalError()
  router.replace({ name: 'Login' }).catch(() => null)
}
</script>

<style>
.app-safe-area {
  min-height: 100dvh;
  padding-top: env(safe-area-inset-top, 0px);
}

.app-boot-screen,
.app-fatal-screen {
  position: fixed;
  inset: 0;
  z-index: 11000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at top, rgba(255,255,255,0.92), rgba(235,235,235,0.98)),
    #ebebeb;
}

.app-boot-card,
.app-fatal-card {
  width: min(100%, 360px);
  border-radius: 24px;
  padding: 28px 24px;
  background: rgba(255,255,255,0.92);
  box-shadow: 0 18px 48px rgba(10,10,10,0.08);
  text-align: center;
  font-family: 'Manrope', sans-serif;
}

.app-boot-spinner {
  width: 42px;
  height: 42px;
  margin: 0 auto 16px;
  border-radius: 999px;
  border: 3px solid rgba(10, 10, 10, 0.08);
  border-top-color: var(--color-primary, #0A0A0A);
  animation: app-boot-spin 0.8s linear infinite;
}

.app-boot-title,
.app-fatal-title {
  margin: 0;
  color: #0A0A0A;
  font-size: 22px;
  font-weight: 800;
}

.app-boot-subtitle,
.app-fatal-message {
  margin: 10px 0 0;
  color: #555555;
  font-size: 14px;
  line-height: 1.55;
}

.app-fatal-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.app-fatal-btn {
  min-width: 132px;
  border: none;
  border-radius: 999px;
  padding: 12px 18px;
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: #0A0A0A;
  background: rgba(10,10,10,0.08);
  cursor: pointer;
}

.app-fatal-btn--primary {
  background: var(--color-primary, #0A0A0A);
  color: var(--color-primary-text, #FFFFFF);
}

.app-boot-fade-enter-active,
.app-boot-fade-leave-active {
  transition: opacity 0.22s ease;
}

.app-boot-fade-enter-from,
.app-boot-fade-leave-to {
  opacity: 0;
}

@keyframes app-boot-spin {
  to {
    transform: rotate(360deg);
  }
}

/* Offline Banner */
.offline-banner {
  position: fixed;
  top: env(safe-area-inset-top, 0px);
  left: 0;
  right: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(30, 30, 32, 0.92);
  color: #f5f5f5;
  font-family: 'Manrope', sans-serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.01em;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.offline-banner-enter-active,
.offline-banner-leave-active {
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.3s ease;
}

.offline-banner-enter-from,
.offline-banner-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}
</style>
