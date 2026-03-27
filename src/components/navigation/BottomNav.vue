<template>
  <!-- Mobile Bottom Navigation -->
  <nav
    class="bottom-nav fixed bottom-5 left-1/2 -translate-x-1/2 z-50 md:hidden flex items-center justify-center gap-2"
    aria-label="Mobile navigation"
  >
    <div class="bottom-nav__shell" :style="bottomNavStyle">
      <button
        v-for="item in navItems"
        :key="item.name"
        @click="navigate(item.route)"
        :aria-label="item.name"
        class="bottom-nav__button"
        :class="isActive(item) ? 'bottom-nav__button--active' : 'bottom-nav__button--idle'"
      >
        <!-- Active glowing background -->
        <span
          v-if="isActive(item)"
          class="bottom-nav__glow"
          style="background: radial-gradient(circle, var(--color-primary) 0%, transparent 60%); opacity: 0.15;"
        />
        
        <component
          :is="item.icon"
          :size="20"
          :stroke-width="isActive(item) ? 2.5 : 2"
          :color="isActive(item) ? 'var(--color-primary)' : '#ffffff'"
          class="bottom-nav__icon"
          :class="{ 'bottom-nav__icon--active': isActive(item) }"
        />

        <!-- Active Dot Indicator -->
        <span
          v-if="isActive(item)"
          class="bottom-nav__dot"
          style="background: var(--color-primary);"
        />
      </button>
    </div>

    <!-- Student Council Button -->
    <button
      v-if="isCouncilMember"
      class="bottom-nav__council-btn"
      :class="isCouncilActive ? 'bottom-nav__council-btn--active' : 'bottom-nav__council-btn--idle'"
      aria-label="Student Council Workspace"
      @click="navigate(resolveCouncilWorkspaceLocation(route))"
    >
      <span
        v-if="isCouncilActive"
        class="bottom-nav__glow"
        style="background: radial-gradient(circle, var(--color-primary) 0%, transparent 60%); opacity: 0.15;"
      />
      
      <span 
        class="bottom-nav__council-text" 
        :style="{ color: isCouncilActive ? 'var(--color-primary)' : '#ffffff' }"
        :class="{ 'bottom-nav__council-text--active': isCouncilActive }"
      >
        {{ councilAcronym }}
      </span>

      <span
        v-if="isCouncilActive"
        class="bottom-nav__dot"
        style="background: var(--color-primary);"
      />
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getNavigationItemsForRoute } from '@/components/navigation/navigationItems.js'
import { useStudentCouncilAccess } from '@/composables/useStudentCouncilAccess.js'
import { isCouncilWorkspaceContext, resolveCouncilWorkspaceLocation } from '@/services/routeWorkspace.js'

const router = useRouter()
const route = useRoute()
const { isCouncilMember, acronym: councilAcronym } = useStudentCouncilAccess()
const navItems = computed(() => getNavigationItemsForRoute(route))
const bottomNavStyle = computed(() => ({
  '--nav-count': String(navItems.value.length),
}))

const isCouncilActive = computed(() => {
  return isCouncilWorkspaceContext(route)
})

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
  const target = typeof path === 'string' ? path : router.resolve(path).path
  if (target && route.path === target) return
  router.push(path)
}
</script>

<style scoped>
.bottom-nav__shell {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: flex;
  align-items: center;
  height: 60px;
  padding: 0 12px;
  gap: 4px;
  border-radius: 999px;
  background: var(--color-nav-glass-bg);
  border: 1px solid var(--color-nav-glass-border);
  box-shadow: var(--color-nav-glass-shadow);
}

.bottom-nav__shell::before,
.bottom-nav__shell::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
}

.bottom-nav__shell::before {
  z-index: -2;
  background: var(--color-nav-glass-layer);
  box-shadow: inset 0 1px 0 var(--color-nav-glass-inset);
}

.bottom-nav__shell::after {
  z-index: -1;
  background:
    var(--color-nav-glass-light),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0) 42%, rgba(255, 255, 255, 0.06) 100%);
}

.bottom-nav__button {
  position: relative;
  width: 52px;
  height: 60px;
  border-radius: 999px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: opacity 200ms ease, transform 220ms ease;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  cursor: pointer;
  user-select: none;
}

.bottom-nav__button--idle {
  opacity: 0.4;
}

.bottom-nav__button--idle:active {
  transform: scale(0.96);
}

.bottom-nav__glow {
  position: absolute;
  inset: 0;
  border-radius: 999px;
}

.bottom-nav__icon {
  position: relative;
  z-index: 10;
  transition: transform 220ms ease, opacity 200ms ease;
}

.bottom-nav__icon--active {
  margin-bottom: 8px;
  transform: scale(1.04);
}

.bottom-nav__dot {
  position: absolute;
  bottom: 8px;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .bottom-nav__shell {
    -webkit-backdrop-filter: blur(var(--nav-glass-blur)) saturate(135%);
    backdrop-filter: blur(var(--nav-glass-blur)) saturate(135%);
  }
}

@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .bottom-nav__shell {
    background: var(--color-nav-glass-bg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .bottom-nav__button,
  .bottom-nav__icon,
  .bottom-nav__council-btn {
    transition: none;
  }
}

.bottom-nav__council-btn {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  min-width: 60px;
  padding: 0 16px;
  border-radius: 999px;
  background: var(--color-nav-glass-bg);
  border: 1px solid var(--color-nav-glass-border);
  box-shadow: var(--color-nav-glass-shadow);
  transition: transform 200ms ease, opacity 200ms ease;
  flex-shrink: 0;
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

/* Frosted glass layers — identical to .bottom-nav__shell */
.bottom-nav__council-btn::before,
.bottom-nav__council-btn::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
}

.bottom-nav__council-btn::before {
  z-index: -2;
  background: var(--color-nav-glass-layer);
  box-shadow: inset 0 1px 0 var(--color-nav-glass-inset);
}

.bottom-nav__council-btn::after {
  z-index: -1;
  background:
    var(--color-nav-glass-light),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0) 42%, rgba(255, 255, 255, 0.06) 100%);
}

@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .bottom-nav__council-btn {
    -webkit-backdrop-filter: blur(var(--nav-glass-blur)) saturate(135%);
    backdrop-filter: blur(var(--nav-glass-blur)) saturate(135%);
  }
}

.bottom-nav__council-btn--idle:active {
  transform: scale(0.96);
}

.bottom-nav__council-text {
  position: relative;
  z-index: 1;
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
  transition: transform 220ms ease;
}

.bottom-nav__council-text--active {
  margin-bottom: 8px;
  transform: scale(1.04);
}
</style>
