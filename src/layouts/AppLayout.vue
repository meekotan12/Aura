<template>
  <!-- Shared layout for all student dashboard pages -->
  <div class="min-h-screen" style="background: var(--color-bg); font-family: 'Manrope', sans-serif;">
    <!-- Desktop Sidebar (left) -->
    <SideNav />

    <!-- Main content area -->
    <main
      class="min-h-screen"
      :class="[
        'md:ml-[80px]',   // sidebar width offset on desktop
        'pb-28 md:pb-8',  // bottom padding for mobile nav
      ]"
    >
      <RouterView v-slot="{ Component, route }">
        <Suspense timeout="0">
          <template #default>
            <Transition name="page-fade">
              <component :is="Component" :key="route.fullPath" />
            </Transition>
          </template>

          <template #fallback>
            <section class="app-layout__route-loading" aria-live="polite">
              <div class="app-layout__route-loading-card">
                <div class="app-layout__route-loading-spinner" aria-hidden="true"></div>
                <p class="app-layout__route-loading-title">Loading screen</p>
                <p class="app-layout__route-loading-copy">Preparing the next dashboard view.</p>
              </div>
            </section>
          </template>
        </Suspense>
      </RouterView>
    </main>

    <!-- Mobile Bottom Nav -->
    <BottomNav />
  </div>
</template>

<script setup>
import { watchEffect } from 'vue'
import { useRouter, RouterView } from 'vue-router'
import SideNav from '@/components/navigation/SideNav.vue'
import BottomNav from '@/components/navigation/BottomNav.vue'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { useIdleTimeout } from '@/composables/useIdleTimeout.js'

const router = useRouter()
const { currentUser, isAdminSession, isSchoolItSession, clearDashboardSession } = useDashboardSession()

const { start: startIdleTimer, stop: stopIdleTimer } = useIdleTimeout(() => {
  clearDashboardSession()
  router.push({ name: 'Login' })
  // Optional: A small visual feedback that they were logged out for security
  alert('For your security, you have been automatically signed out due to inactivity.')
}, { 
  immediate: false, 
  timeoutMs: 10 * 60 * 1000 // 10 minutes
})

watchEffect(() => {
  const user = currentUser.value
  if (user && (isAdminSession(user) || isSchoolItSession(user))) {
    startIdleTimer()
  } else {
    stopIdleTimer()
  }
})
</script>

<style scoped>
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.26s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: opacity, transform;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.995);
}

.app-layout__route-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100dvh - 120px);
  padding: 32px 20px;
}

.app-layout__route-loading-card {
  width: min(100%, 320px);
  border-radius: 28px;
  padding: 26px 24px;
  background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,248,248,0.98));
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.08);
  text-align: center;
}

.app-layout__route-loading-spinner {
  width: 42px;
  height: 42px;
  margin: 0 auto 14px;
  border-radius: 999px;
  border: 3px solid rgba(10, 10, 10, 0.08);
  border-top-color: var(--color-primary);
  animation: app-layout-spin 0.85s linear infinite;
}

.app-layout__route-loading-title {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: var(--color-text-primary);
}

.app-layout__route-loading-copy {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text-muted);
}

@keyframes app-layout-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
