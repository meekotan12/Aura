<template>
  <div class="flex flex-col gap-5 px-4 md:pl-10 md:pr-[30%] pb-6 pt-2">
    <!-- TopBar -->
    <TopBar
      :user="currentUser"
      :unread-count="unreadAnnouncements"
      @toggle-notifications="showNotifications = !showNotifications"
    />

    <!-- Page Title -->
    <div class="mt-1 px-1">
      <h1 class="text-[26px] font-extrabold" style="color: var(--color-text-primary);">Home</h1>
    </div>

    <!-- Search bar + Talk to Aura AI row -->
    <div class="flex items-start gap-3 mb-1">
      <!-- Search bar -->
      <div class="relative flex-1 z-20">
        <div class="search-shell" :class="{ 'search-shell--open': searchActive }">
          <div class="search-input-row">
            <input
              v-model="searchQuery"
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

      <!-- Talk to Aura AI (mobile only — desktop has it in the sidebar) -->
      <button
        class="md:hidden flex flex-col items-center justify-center gap-1 transition-all duration-200 hover:brightness-110 hover:scale-105 active:scale-95 flex-shrink-0"
        style="background: var(--color-primary); border-radius: 26px; width: 80px; height: 50px;"
        aria-label="Talk to Aura AI"
      >
        <div class="flex items-center gap-1.5 pt-0.5">
          <img
            :src="activeAuraLogo"
            alt="Aura"
            class="w-4 h-4 object-contain opacity-90"
          />
          <span
            class="text-[9px] font-extrabold text-left leading-[1.1] transition-colors duration-200"
            style="color: var(--color-banner-text);"
          >
            Talk to<br>Aura Ai
          </span>
        </div>
      </button>
    </div>

    <!-- Cards grid: stacked on mobile, side-by-side on desktop -->
    <div class="flex flex-col md:flex-row gap-6 md:gap-6 mt-1">
      <!-- University Banner -->
      <Transition name="card-slide" appear>
        <UniversityBanner
          class="md:flex-1"
          :school-name="schoolSettings.school_name"
          :school-logo="schoolSettings.logo_url"
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
    <div v-if="!searchActive && upcomingEvents.length > 1" class="mt-4">
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
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from 'lucide-vue-next'
import TopBar from '@/components/dashboard/TopBar.vue'
import UniversityBanner from '@/components/dashboard/UniversityBanner.vue'
import EventsCard from '@/components/dashboard/EventsCard.vue'

import { mockCurrentUser, mockEvents, mockSchoolSettings } from '@/data/mockData.js'
import { mockAnnouncements } from '@/data/mockAnnouncements.js'
import { loadTheme, applyTheme, activeAuraLogo } from '@/config/theme.js'

// --- State ---
const searchQuery = ref('')
const showNotifications = ref(false)
const router = useRouter()

// --- Data (swap with API calls in production) ---
const currentUser = ref(mockCurrentUser)
const events = ref(mockEvents)
const schoolSettings = ref(mockSchoolSettings)
const announcements = ref(mockAnnouncements)

// --- Computed ---
const displayEvents = computed(() =>
  events.value.filter((e) => {
    const status = normalizeStatus(e.status)
    return status === 'upcoming' || status === 'ongoing'
  })
)

const searchActive = computed(() => searchQuery.value.trim().length > 0)

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

  let candidates = displayEvents.value
  if (statusFilters.length) {
    candidates = candidates.filter((event) => statusFilters.includes(normalizeStatus(event.status)))
  }

  if (!tokens.length) return candidates

  return candidates.filter((event) => {
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
  })
})

const upcomingEvents = computed(() => filteredEvents.value)

const unreadAnnouncements = computed(() =>
  announcements.value.filter((a) => !a.is_read).length
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
  // TODO: navigate to announcements page or open modal
  console.log('Announcement clicked')
}

function handleSeeEvent(event) {
  if (!event?.id) return
  if (event.status === 'ongoing') {
    router.push(`/dashboard/schedule/${event.id}/attendance`)
    return
  }
  router.push(`/dashboard/schedule/${event.id}`)
}

function handleSearchResult(event) {
  if (!event?.id) return
  router.push(`/dashboard/schedule/${event.id}`)
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
/* Search expand UI */
.search-shell {
  display: grid;
  grid-template-rows: auto 0fr;
  background: var(--color-surface);
  border-radius: 30px;
  padding: 10px 16px;
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.06);
  transition: grid-template-rows 0.25s ease, box-shadow 0.25s ease;
}

.search-shell--open {
  grid-template-rows: auto 1fr;
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.08);
}

.search-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-input {
  width: 100%;
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

.search-icon {
  display: block;
}

.search-icon-wrap {
  margin-left: auto;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1.5px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.search-results {
  overflow: hidden;
  min-height: 0;
}

.search-results-inner {
  padding: 12px 2px 4px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

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

.search-item:hover {
  opacity: 0.8;
}

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

@media (max-width: 767px) {
  .search-shell {
    border-radius: 28px;
    padding: 12px 16px 12px;
  }

  .search-shell--open {
    padding-bottom: 16px;
    min-height: 150px;
  }

  .search-input {
    font-size: 12px;
    padding-left: 6px;
  }

  .search-results-inner {
    padding: 14px 2px 6px;
    align-items: center;
    justify-content: center;
    min-height: 70px;
  }

  .search-item {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .search-pill {
    width: min(220px, 80%);
    justify-content: center;
    font-size: 13px;
    padding: 8px 20px;
  }

  .search-meta {
    display: none;
  }

  .search-icon-wrap {
    width: 24px;
    height: 24px;
    border: 1.5px solid rgba(0, 0, 0, 0.1);
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
