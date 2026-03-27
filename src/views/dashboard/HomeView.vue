<template>
  <div class="home-page">
    <!-- TopBar -->
    <TopBar
      class="dashboard-enter dashboard-enter--1"
      :user="activeUser"
      :unread-count="unreadAnnouncements"
      @toggle-notifications="showNotifications = !showNotifications"
    />

    <!-- Page Title -->
    <div class="mt-1 px-1 dashboard-enter dashboard-enter--2">
      <h1 class="text-[26px] font-extrabold" style="color: var(--color-text-primary);">Home</h1>
    </div>

    <!-- Search bar + Talk to Aura AI row -->
    <div class="search-area dashboard-enter dashboard-enter--3">
      <div class="search-row">
        <!-- Search bar — expands to full width when active -->
        <div class="search-wrap" :class="{ 'search-wrap--active': searchActive }">
          <div class="search-shell" :class="{ 'search-shell--open': searchActive }">
            <div class="search-input-row">
              <input
                v-model="searchQuery"
                v-bind="eventSearchInputAttrs"
                type="text"
                placeholder="Event Search Here"
                class="search-input"
              />
              <span class="search-icon-wrap" aria-hidden="true">
                <Search
                  :size="14"
                  class="search-icon"
                  style="color: var(--color-primary);"
                />
              </span>
            </div>

            <div class="search-results">
              <div class="search-results-inner">
                <template v-if="filteredEvents.length">
                  <button
                    v-for="event in filteredEvents"
                    :key="event.id"
                    class="search-item"
                    type="button"
                    @click="handleSearchResult(event)"
                  >
                    <span class="search-pill">{{ event.name }}</span>
                    <span class="search-meta">{{ formatSearchMeta(event) }}</span>
                  </button>
                </template>
                <p v-else class="search-empty">No matching events.</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Talk to Aura AI (mobile only — hides when search is active) -->
        <button
          v-show="!searchActive"
          class="ai-pill md:hidden"
          :class="{ 'ai-pill--open': isMobileAiOpen }"
          aria-label="Talk to Aura AI"
          :aria-expanded="isMobileAiOpen ? 'true' : 'false'"
          aria-controls="mobile-ai-panel"
          type="button"
          @click="toggleMobileAi"
        >
          <img
            :src="secondaryAuraLogo"
            alt="Aura"
            class="w-4 h-4 object-contain opacity-90"
          />
          <span
            class="text-[9px] font-extrabold text-left leading-[1.1]"
            style="color: var(--color-search-pill-text);"
          >
            Talk to<br>Aura Ai
          </span>
        </button>
      </div>

      <!-- Mobile AI panel: expands downward from the search row -->
      <Transition
        name="mobile-ai-panel"
        @before-enter="onMobilePanelBeforeEnter"
        @enter="onMobilePanelEnter"
        @after-enter="onMobilePanelAfterEnter"
        @before-leave="onMobilePanelBeforeLeave"
        @leave="onMobilePanelLeave"
        @after-leave="onMobilePanelAfterLeave"
      >
        <div
          v-if="isMobileAiOpen && !searchActive"
          id="mobile-ai-panel"
          class="mobile-ai-panel md:hidden"
          role="region"
          aria-label="Aura AI chat"
        >
          <div class="mobile-ai-panel-inner">
            <div class="mobile-ai-shell">
              <div class="mobile-ai-messages" ref="scrollEl">
                <TransitionGroup name="mobile-bubble" tag="div" class="mobile-ai-messages-inner">
                  <div
                    v-for="msg in messages"
                    :key="msg.id"
                    :class="['mobile-bubble', msg.sender === 'ai' ? 'mobile-bubble--ai' : 'mobile-bubble--user']"
                  >
                    {{ msg.text }}
                  </div>

                  <div v-if="isTyping" key="typing" class="mobile-bubble mobile-bubble--ai mobile-bubble--typing">
                    <span class="mobile-dot" style="animation-delay: 0ms"   />
                    <span class="mobile-dot" style="animation-delay: 150ms" />
                    <span class="mobile-dot" style="animation-delay: 300ms" />
                  </div>
                </TransitionGroup>
              </div>

              <div class="mobile-ai-input">
                <div class="mobile-ai-input-row">
                  <input
                    ref="mobileInputEl"
                    v-model="inputText"
                    class="mobile-ai-input-field"
                    type="text"
                    placeholder="Ask Aura..."
                    :disabled="isTyping"
                    @keyup.enter="sendMessage"
                  />
                  <button
                    class="mobile-ai-send-btn"
                    :disabled="!inputText.trim() || isTyping"
                    aria-label="Send message"
                    type="button"
                    @click="sendMessage"
                  >
                    <Send :size="15" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Cards grid: stacked on mobile, side-by-side on desktop -->
    <div class="home-hero-grid dashboard-enter dashboard-enter--4">
      <!-- University Banner -->
      <Transition name="card-slide" appear>
        <UniversityBanner
          class="md:flex-1"
          :school-name="resolvedSchoolName"
          :school-logo="resolvedSchoolLogoCandidates[0] || null"
          :school-logo-candidates="resolvedSchoolLogoCandidates"
          @announcement-click="handleAnnouncementClick"
        />
      </Transition>

      <!-- Latest Event card -->
      <Transition name="card-slide-delay" appear>
        <EventsCard
          class="md:flex-1"
          :events="filteredEvents"
          @see-event="handleSeeEvent"
        />
      </Transition>
    </div>

    <!-- Upcoming events list (additional quick-view) -->
    <div v-if="!searchActive && upcomingEvents.length > 1" class="mt-4 dashboard-enter dashboard-enter--5">
      <h2 class="text-[16px] font-bold mb-3 px-1" style="color: var(--color-text-primary);">Upcoming Events</h2>
      <div class="flex flex-col gap-3">
        <TransitionGroup name="list" appear>
          <div
            v-for="(event, i) in upcomingEvents.slice(1)"
            :key="event.id"
            class="rounded-2xl px-4 py-3.5 flex items-center gap-4 cursor-pointer transition-all duration-150 hover:scale-[1.01] active:scale-[0.99]"
            style="background: var(--color-surface);"
            @click="handleSeeEvent(event)"
          >
            <!-- Date badge -->
            <div
              class="flex flex-col items-center justify-center w-10 h-12 rounded-xl flex-shrink-0"
              style="background: var(--color-primary);"
            >
              <span class="text-[10px] font-bold" style="color: var(--color-banner-text);">
                {{ formatMonth(event.start_datetime) }}
              </span>
              <span class="text-[18px] font-extrabold leading-none" style="color: var(--color-banner-text);">
                {{ formatDay(event.start_datetime) }}
              </span>
            </div>

            <!-- Event details -->
            <div class="flex-1 min-w-0">
              <p class="text-[13px] font-bold truncate" style="color: var(--color-text-always-dark);">
                {{ event.name }}
              </p>
              <p class="text-[11px] mt-0.5 truncate" style="color: var(--color-text-muted);">
                {{ event.location }}
              </p>
            </div>

            <!-- Status badge -->
            <span
              class="text-[10px] font-semibold px-2.5 py-1 rounded-full flex-shrink-0"
              :style="statusStyle(event.status)"
            >
              {{ event.status }}
            </span>
          </div>
        </TransitionGroup>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, Send } from 'lucide-vue-next'
import TopBar from '@/components/dashboard/TopBar.vue'
import UniversityBanner from '@/components/dashboard/UniversityBanner.vue'
import EventsCard from '@/components/dashboard/EventsCard.vue'

import { applyTheme, loadTheme, secondaryAuraLogo } from '@/config/theme.js'
import { useChat } from '@/composables/useChat.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { useStoredAuthMeta } from '@/composables/useStoredAuthMeta.js'
import { studentDashboardPreviewData } from '@/data/studentDashboardPreview.js'
import { resolveBackendMediaCandidates } from '@/services/backendMedia.js'
import { primeLocationAccess } from '@/services/devicePermissions.js'
import { createSearchFieldAttrs } from '@/services/searchFieldAttrs.js'
import { resolveAttendanceLocation, resolveEventDetailLocation } from '@/services/routeWorkspace.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

// --- State ---
const searchQuery = ref('')
const eventSearchInputAttrs = createSearchFieldAttrs('student-event-search')
const showNotifications = ref(false)
const isMobileAiOpen = ref(false)
const mobileInputEl = ref(null)
const router = useRouter()
const route = useRoute()
const { currentUser, schoolSettings, events, hasAttendanceForEvent, hasOpenAttendanceForEvent } = useDashboardSession()
const authMeta = useStoredAuthMeta()
const activeUser = computed(() => props.preview ? studentDashboardPreviewData.user : currentUser.value)
const activeSchoolSettings = computed(() => props.preview ? studentDashboardPreviewData.schoolSettings : schoolSettings.value)
const activeEvents = computed(() => props.preview ? studentDashboardPreviewData.events : events.value)

const resolvedSchoolName = computed(() => (
  activeSchoolSettings.value?.school_name ||
  activeUser.value?.school_name ||
  authMeta.value?.schoolName ||
  'University Name'
))

const resolvedSchoolLogoCandidates = computed(() => (
  resolveBackendMediaCandidates([
    activeSchoolSettings.value?.logo_url,
    authMeta.value?.logoUrl,
  ])
))

const schoolEvents = computed(() => {
  const schoolId = Number(activeUser.value?.school_id)
  return activeEvents.value.filter((event) => !Number.isFinite(schoolId) || Number(event?.school_id) === schoolId)
})

const statusRank = {
  ongoing: 0,
  upcoming: 1,
  completed: 2,
  cancelled: 3,
}

function sortHomeEvents(items) {
  return [...items].sort((left, right) => {
    const leftRank = statusRank[normalizeStatus(left?.status)] ?? 99
    const rightRank = statusRank[normalizeStatus(right?.status)] ?? 99
    if (leftRank !== rightRank) return leftRank - rightRank
    return new Date(left?.start_datetime ?? 0) - new Date(right?.start_datetime ?? 0)
  })
}

// --- Computed ---
const displayEvents = computed(() =>
  schoolEvents.value.filter((e) => {
    const status = normalizeStatus(e.status)
    return status === 'upcoming' || status === 'ongoing'
  })
)

const searchActive = computed(() => searchQuery.value.trim().length > 0)

const {
  messages,
  inputText,
  isTyping,
  scrollEl,
  sendMessage,
  closeAll,
} = useChat()

const nextFrame = (cb) => requestAnimationFrame(() => requestAnimationFrame(cb))

function onMobilePanelBeforeEnter(el) {
  el.style.height = '0px'
  el.style.opacity = '0'
  el.style.transform = 'translateY(-8px)'
  el.style.willChange = 'height, opacity, transform'
}

function onMobilePanelEnter(el) {
  const height = el.scrollHeight
  el.style.transition = 'height 520ms cubic-bezier(0.22, 1, 0.36, 1), opacity 320ms ease, transform 420ms cubic-bezier(0.22, 1, 0.36, 1)'
  nextFrame(() => {
    el.style.height = `${height}px`
    el.style.opacity = '1'
    el.style.transform = 'translateY(0)'
  })
}

function onMobilePanelAfterEnter(el) {
  el.style.height = 'auto'
  el.style.transition = ''
  el.style.willChange = ''
}

function onMobilePanelBeforeLeave(el) {
  el.style.height = `${el.scrollHeight}px`
  el.style.opacity = '1'
  el.style.transform = 'translateY(0)'
  el.style.willChange = 'height, opacity, transform'
}

function onMobilePanelLeave(el) {
  el.style.transition = 'height 420ms cubic-bezier(0.4, 0, 0.2, 1), opacity 240ms ease, transform 300ms ease'
  nextFrame(() => {
    el.style.height = '0px'
    el.style.opacity = '0'
    el.style.transform = 'translateY(-6px)'
  })
}

function onMobilePanelAfterLeave(el) {
  el.style.transition = ''
  el.style.height = ''
  el.style.opacity = ''
  el.style.transform = ''
  el.style.willChange = ''
}

function toggleMobileAi() {
  isMobileAiOpen.value = !isMobileAiOpen.value
}

watch(isMobileAiOpen, (open) => {
  if (open) {
    closeAll()
    nextTick(() => {
      setTimeout(() => mobileInputEl.value?.focus(), 220)
    })
  }
})

watch(searchActive, (active) => {
  if (active) isMobileAiOpen.value = false
})

watch(
  [() => props.preview, activeSchoolSettings],
  ([preview, nextSchoolSettings]) => {
    if (!preview || !nextSchoolSettings) return
    applyTheme(loadTheme(nextSchoolSettings))
  },
  { immediate: true }
)

const filteredEvents = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return displayEvents.value

  const compact = (val) => String(val ?? '').toLowerCase().replace(/[\s-]/g, '')
  const compactQuery = compact(query)

  const statusAliases = {
    upcoming: ['upcoming', 'up coming', 'up-coming'],
    ongoing: ['ongoing', 'on going', 'on-going'],
    completed: ['completed', 'done', 'finished'],
    cancelled: ['cancelled', 'canceled'],
  }

  const statusFilters = Object.entries(statusAliases)
    .filter(([, aliases]) => aliases.some((alias) => compactQuery.includes(compact(alias))))
    .map(([status]) => status)

  const stopWords = new Set([
    'event', 'events', 'the', 'a', 'an', 'and', 'of', 'in', 'at', 'on', 'for', 'to',
  ])

  const tokens = query
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => token && !stopWords.has(token))

  let candidates = schoolEvents.value
  if (statusFilters.length) {
    candidates = candidates.filter((event) => statusFilters.includes(normalizeStatus(event.status)))
  }

  if (!tokens.length) return sortHomeEvents(candidates)

  return sortHomeEvents(candidates.filter((event) => {
    const haystack = [
      event.name,
      event.location,
      normalizeStatus(event.status),
      ...(event.departments ?? []).map((d) => d.name),
      ...(event.programs ?? []).map((p) => p.name),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()

    return tokens.some((token) => haystack.includes(token))
  }))
})

const upcomingEvents = computed(() => filteredEvents.value)

const unreadAnnouncements = computed(() =>
  0
)

// --- Formatters ---
function formatMonth(dt) {
  return new Date(dt).toLocaleString('en', { month: 'short' }).toUpperCase()
}

function formatDay(dt) {
  return new Date(dt).getDate()
}

function statusStyle(status) {
  const map = {
    upcoming: { background: 'rgba(170,255,0,0.2)', color: '#3a5c00' },
    ongoing: { background: 'rgba(0,200,100,0.15)', color: '#006633' },
    completed: { background: 'rgba(0,0,0,0.08)', color: '#555' },
    cancelled: { background: 'rgba(255,80,80,0.12)', color: '#cc0000' },
  }
  return map[status] ?? map.upcoming
}

function normalizeStatus(status) {
  return status === 'done' ? 'completed' : status
}

// --- Handlers ---
function handleAnnouncementClick() {
  if (props.preview) return
  // TODO: navigate to announcements page or open modal
  console.log('Announcement clicked')
}

function handleSeeEvent(event) {
  if (props.preview || !event?.id) return

  const normalizedEventId = Number(event.id)
  const shouldRouteToAttendance = (
    hasOpenAttendanceForEvent(normalizedEventId)
    || (event.status === 'ongoing' && !hasAttendanceForEvent(normalizedEventId))
  )

  if (shouldRouteToAttendance) {
    void primeLocationAccess()
    router.push(resolveAttendanceLocation(route, event.id))
    return
  }
  router.push(resolveEventDetailLocation(route, event.id))
}

function handleSearchResult(event) {
  handleSeeEvent(event)
}

function formatSearchMeta(event) {
  const pieces = []
  if (event.location) pieces.push(event.location)
  if (event.start_datetime) {
    const dateText = new Date(event.start_datetime).toLocaleDateString('en-PH', {
      month: 'short',
      day: 'numeric',
    })
    const timeText = new Date(event.start_datetime).toLocaleTimeString('en-PH', {
      hour: 'numeric',
      minute: '2-digit',
    })
    pieces.push(`${dateText} · ${timeText}`)
  }
  return pieces.join(' • ') || 'Event details'
}
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100vh;
  padding: 28px 22px 100px;
}

/* ── Search row shell ─────────────────────────────────── */
.search-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.home-hero-grid {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.search-row {
  display: flex;
  align-items: stretch;
  gap: clamp(8px, 2.8vw, 10px);
}

/* Search wrapper grows/shrinks relative to AI pill */
.search-wrap {
  flex: 1;
  min-width: 0;
  transition: flex 0.3s ease;
}

/* When active on mobile: take full row width */
.search-wrap--active {
  flex: 1 1 100%;
}

/* AI pill */
.ai-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  flex-shrink: 0;
  width: clamp(70px, 21vw, 76px);
  height: clamp(50px, 14vw, 52px);
  border-radius: 26px;
  border: none;
  background: var(--color-search-pill-bg);
  color: var(--color-search-pill-text);
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease, box-shadow 0.25s ease;
}

.ai-pill:hover {
  filter: brightness(1.08);
  transform: scale(1.04);
}

.ai-pill:active {
  transform: scale(0.95);
}

.ai-pill--open {
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.14);
  transform: translateY(1px) scale(0.98);
}

/* ── Mobile AI panel ─────────────────────────────────── */
.mobile-ai-panel {
  overflow: hidden;
  transform-origin: top center;
}

.mobile-ai-panel-inner {
  overflow: hidden;
}

.mobile-ai-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  background: var(--color-primary);
  border-radius: 28px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.14);
  overflow: hidden;
}

.mobile-ai-shell::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(120% 120% at 18% 0%, rgba(255, 255, 255, 0.28), transparent 55%);
  opacity: 0.5;
  pointer-events: none;
}

.mobile-ai-messages {
  position: relative;
  flex: 1;
  min-height: clamp(110px, 22vh, 180px);
  max-height: min(46vh, 320px);
  overflow-y: auto;
  padding: 6px 6px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: none;
  z-index: 1;
}

.mobile-ai-messages::-webkit-scrollbar {
  display: none;
}

.mobile-ai-messages-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-bubble {
  max-width: 88%;
  padding: 12px 16px;
  border-radius: 24px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.6;
  font-family: 'Manrope', sans-serif;
  word-break: break-word;
}

.mobile-bubble--ai {
  align-self: flex-start;
  background: #ffffff;
  color: #0a0a0a;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.08);
}

.mobile-bubble--user {
  align-self: flex-end;
  background: rgba(0, 0, 0, 0.12);
  color: var(--color-banner-text);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.mobile-bubble--typing {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
}

.mobile-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.35);
  animation: mobile-dot-bounce 1s infinite ease-in-out;
}

@keyframes mobile-dot-bounce {
  0%, 100% { transform: translateY(0); }
  40% { transform: translateY(-4px); }
}

.mobile-bubble-enter-active {
  animation: mobile-bubble-pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.mobile-bubble--ai.mobile-bubble-enter-active { transform-origin: bottom left; }
.mobile-bubble--user.mobile-bubble-enter-active { transform-origin: bottom right; }

@keyframes mobile-bubble-pop {
  0%   { opacity: 0; transform: scale(0.55); }
  65%  { opacity: 1; transform: scale(1.04); }
  82%  { transform: scale(0.97); }
  100% { transform: scale(1); }
}

.mobile-ai-input {
  position: relative;
  z-index: 1;
}

.mobile-ai-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.08);
  border: 1.4px solid rgba(0, 0, 0, 0.2);
  border-radius: 999px;
  padding: 0 8px 0 16px;
  height: 44px;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.mobile-ai-input-row:focus-within {
  background: rgba(0, 0, 0, 0.12);
  border-color: rgba(0, 0, 0, 0.35);
}

.mobile-ai-input-field {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-banner-text);
  min-width: 0;
}

.mobile-ai-input-field::placeholder {
  color: var(--color-banner-text);
  opacity: 0.55;
}

.mobile-ai-send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.18);
  color: var(--color-banner-text);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.18s ease, transform 0.15s ease, opacity 0.18s ease;
}

.mobile-ai-send-btn:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.28);
  transform: scale(1.08);
}

.mobile-ai-send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

@media (prefers-reduced-motion: reduce) {
  .ai-pill,
  .mobile-ai-send-btn,
  .mobile-bubble-enter-active {
    transition: none;
    animation: none;
  }
}

@media (min-width: 768px) {
  .ai-pill,
  .mobile-ai-panel {
    display: none !important;
  }

  .home-page {
    padding: 36px 36px 40px;
  }

  .search-area {
    margin-top: 4px;
  }

  .home-hero-grid {
    flex-direction: row;
    gap: 24px;
    margin-top: 10px;
  }
}

/* ── Search shell card ────────────────────────────────── */
.search-shell {
  display: grid;
  grid-template-rows: auto 0fr;
  background: var(--color-surface);
  border-radius: 30px;
  padding: 12px clamp(12px, 4vw, 16px);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.06);
  transition: grid-template-rows 0.28s ease, box-shadow 0.28s ease, border-radius 0.28s ease;
}

.search-shell--open {
  grid-template-rows: auto 1fr;
  border-radius: 28px;
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.09);
}

.search-input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: clamp(8px, 2.5vw, 10px);
  min-height: clamp(30px, 8.5vw, 34px);
}

.search-input {
  width: 100%;
  min-width: 0;
  border: none;
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  outline: none;
  color: var(--color-text-always-dark);
}

.search-input::placeholder {
  color: var(--color-text-muted);
  font-weight: 500;
}

.search-icon { display: block; }

.search-icon-wrap {
  width: clamp(28px, 8vw, 30px);
  height: clamp(28px, 8vw, 30px);
  border-radius: 50%;
  border: 1.5px solid rgba(0, 0, 0, 0.08);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  place-self: center;
}

/* ── Dropdown results ─────────────────────────────────── */
.search-results {
  overflow: hidden;
  min-height: 0;
}

.search-results-inner {
  padding: 14px 0 6px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── Desktop search result (default) — original 2-column pill + meta ── */
.search-item {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 14px;
  padding: 4px 2px;
  background: transparent;
  border: none;
  text-align: left;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.search-item:hover { opacity: 0.8; }

.search-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 18px;
  border-radius: 999px;
  background: var(--color-primary);
  color: var(--color-text-always-dark);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.search-meta {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-muted);
}

.search-empty {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  padding: 6px 2px;
}

/* ── Mobile search result override — full-width lime pill ── */
@media (max-width: 767px) {
  .search-item {
    display: block;
    width: 100%;
    padding: 13px 20px;
    border-radius: 999px;
    background: var(--color-primary);
    text-align: center;
    transition: opacity 0.15s ease, transform 0.15s ease;
  }

  .search-item:hover  { opacity: 0.85; }
  .search-item:active { transform: scale(0.97); }

  /* On mobile the pill span is invisible — the button itself IS the pill */
  .search-pill {
    display: contents;
    font-size: 13px;
    background: transparent;
    padding: 0;
    border-radius: 0;
    color: var(--color-text-always-dark);
  }

  /* Hide meta text on mobile */
  .search-meta { display: none; }

  .search-empty {
    text-align: center;
    padding: 10px 0;
  }
}

/* Card entrance animations */
.card-slide-enter-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.card-slide-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.card-slide-delay-enter-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1) 0.08s;
}
.card-slide-delay-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

/* List item entrance */
.list-enter-active {
  transition: all 0.3s ease;
}
.list-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}
.list-move {
  transition: transform 0.3s ease;
}
</style>
