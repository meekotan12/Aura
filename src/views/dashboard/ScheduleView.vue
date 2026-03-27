<template>
  <div class="events-page">
    
    <!-- ── Header ─────────────────────────────────────────────────────── -->
    <TopBar
      class="dashboard-enter dashboard-enter--1"
      :user="activeUser"
      :unread-count="activeUnreadAnnouncements"
      @toggle-notifications="showNotifications = !showNotifications"
    />

    <!-- ── Title & Filters ────────────────────────────────────────────── -->
    <div class="events-content dashboard-enter dashboard-enter--2">
      <h1 class="page-title">Events</h1>
      
      <div class="filters-scroll">
        <div class="filters-track">
          <button 
            v-for="filter in filters" 
            :key="filter.id"
            class="filter-pill"
            :class="[
              { 'filter-pill--active': activeFilter === filter.id },
              filter.variant === 'outline' ? 'filter-pill--outline' : ''
            ]"
            @click="activeFilter = filter.id"
          >
            {{ filter.label }}
          </button>
        </div>
      </div>

      <!-- ── Events List ──────────────────────────────────────────────── -->
      <div v-if="filteredEvents.length > 0" class="events-grid dashboard-enter dashboard-enter--3">
        <EventCard 
          v-for="event in filteredEvents" 
          :key="event.id" 
          :event="event"
          :is-attended="isEventAttended(event)"
          :attendance-record="getAttendanceRecord(event)"
          :event-time-status="getEventTimeStatusFor(event)"
          @click="handleEventClick"
          @open-detail="handleOpenDetail"
        />
      </div>
      
      <div v-else class="empty-state dashboard-enter dashboard-enter--3">
        <p>No events found for this category.</p>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EventCard from '@/components/dashboard/EventCard.vue'
import TopBar from '@/components/dashboard/TopBar.vue'

import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { usePreviewTheme } from '@/composables/usePreviewTheme.js'
import { studentDashboardPreviewData } from '@/data/studentDashboardPreview.js'
import { getEventTimeStatus, resolveApiBaseUrl } from '@/services/backendApi.js'
import { resolveAttendanceActionState, resolveEventLifecycleStatus } from '@/services/attendanceFlow.js'
import { primeLocationAccess } from '@/services/devicePermissions.js'
import { resolveAttendanceLocation, resolveEventDetailLocation } from '@/services/routeWorkspace.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const {
  currentUser,
  events,
  attendanceRecords,
  getLatestAttendanceForEvent,
  hasAttendanceForEvent,
  hasOpenAttendanceForEvent,
  refreshAttendanceRecords,
  unreadAnnouncements,
} = useDashboardSession()
const showNotifications = ref(false)

const router = useRouter()
const route = useRoute()
const activeUser = computed(() => props.preview ? studentDashboardPreviewData.user : currentUser.value)
const activeEvents = computed(() => props.preview ? studentDashboardPreviewData.events : events.value)
const activeAttendanceRecords = computed(() => props.preview ? studentDashboardPreviewData.attendanceRecords : attendanceRecords.value)
const activeUnreadAnnouncements = computed(() => props.preview ? 0 : unreadAnnouncements.value)
const activeSchoolSettings = computed(() => props.preview ? studentDashboardPreviewData.schoolSettings : null)
const apiBaseUrl = resolveApiBaseUrl()
const eventTimeStatuses = ref({})
let eventTimeStatusRequestId = 0
let eventTimeStatusIntervalId = null

usePreviewTheme(() => props.preview, activeSchoolSettings)

// ── Filters & Events Logic ────────────────────────────────────────────
const schoolEvents = computed(() => {
  const schoolId = Number(activeUser.value?.school_id)
  return activeEvents.value.filter((event) => !Number.isFinite(schoolId) || Number(event?.school_id) === schoolId)
})
const filters = [
  { id: 'all', label: 'All' },
  { id: 'ongoing', label: 'On Going' },
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'completed', label: 'Done' },
  { id: 'maps', label: 'Calendar & Maps', variant: 'outline' }, // Placeholder for future feature
]

const activeFilter = ref('all')

const statusRank = {
  ongoing: 0,
  upcoming: 1,
  completed: 2,
  cancelled: 3,
}

function normalizeStatus(status) {
  return status === 'done' ? 'completed' : status
}

const filteredEvents = computed(() => {
  let items = schoolEvents.value
  if (activeFilter.value !== 'all' && activeFilter.value !== 'maps') {
    items = items.filter((currentEvent) => {
      return resolveEventLifecycleStatus(currentEvent, getEventTimeStatusFor(currentEvent)) === activeFilter.value
    })
  }
  if (activeFilter.value === 'maps') return []
  return [...items].sort((a, b) => {
    const aRank = statusRank[resolveEventLifecycleStatus(a, getEventTimeStatusFor(a))] ?? 99
    const bRank = statusRank[resolveEventLifecycleStatus(b, getEventTimeStatusFor(b))] ?? 99
    if (aRank !== bRank) return aRank - bRank
    return new Date(a.start_datetime) - new Date(b.start_datetime)
  })
})

const timeStatusCandidateIds = computed(() => {
  if (props.preview) return []

  const ids = new Set()
  for (const currentEvent of schoolEvents.value) {
    const normalizedEventId = Number(currentEvent?.id)
    if (!Number.isFinite(normalizedEventId)) continue

    if (
      ['upcoming', 'ongoing'].includes(normalizeStatus(currentEvent?.status))
      || hasOpenAttendanceForEvent(normalizedEventId)
    ) {
      ids.add(normalizedEventId)
    }
  }

  return [...ids].sort((left, right) => left - right)
})

watch(
  timeStatusCandidateIds,
  (eventIds) => {
    void syncEventTimeStatuses(eventIds)
  },
  { immediate: true }
)

watch(
  () => props.preview,
  (isPreview) => {
    if (isPreview) {
      stopEventTimeStatusPolling()
      return
    }
    startEventTimeStatusPolling()
  },
  { immediate: true }
)

async function syncEventTimeStatuses(eventIds) {
  const requestId = ++eventTimeStatusRequestId

  if (props.preview || !eventIds.length) {
    eventTimeStatuses.value = {}
    return
  }

  const token = localStorage.getItem('aura_token')
  if (!token) {
    eventTimeStatuses.value = {}
    return
  }

  const previousStatuses = eventTimeStatuses.value
  const nextStatuses = {}

  await Promise.all(eventIds.map(async (currentEventId) => {
    try {
      nextStatuses[currentEventId] = await getEventTimeStatus(apiBaseUrl, token, currentEventId)
    } catch {
      nextStatuses[currentEventId] = null
    }
  }))

  if (requestId !== eventTimeStatusRequestId) {
    return
  }

  eventTimeStatuses.value = nextStatuses

  const closedTransitionIds = eventIds.filter((currentEventId) => {
    const previousStatus = previousStatuses?.[currentEventId]?.event_status
    const nextStatus = nextStatuses?.[currentEventId]?.event_status
    return nextStatus === 'closed' && previousStatus !== 'closed'
  })

  if (closedTransitionIds.length) {
    await Promise.allSettled(
      closedTransitionIds.map((currentEventId) => refreshAttendanceRecords({ event_id: currentEventId }))
    )
  }
}

function getEventTimeStatusFor(event) {
  const normalizedEventId = Number(event?.id)
  if (!Number.isFinite(normalizedEventId)) return null
  return eventTimeStatuses.value[normalizedEventId] ?? null
}

function stopEventTimeStatusPolling() {
  if (eventTimeStatusIntervalId != null) {
    clearInterval(eventTimeStatusIntervalId)
    eventTimeStatusIntervalId = null
  }
}

function startEventTimeStatusPolling() {
  stopEventTimeStatusPolling()
  if (props.preview) return

  eventTimeStatusIntervalId = window.setInterval(() => {
    void syncEventTimeStatuses(timeStatusCandidateIds.value)
  }, 15000)
}

function shouldRouteToAttendance(event) {
  if (props.preview || !event?.id) return false

  const normalizedEventId = Number(event.id)
  if (!Number.isFinite(normalizedEventId)) return false

  const actionState = resolveAttendanceActionState({
    event,
    eventStatus: resolveEventLifecycleStatus(event, getEventTimeStatusFor(event)),
    attendanceRecord: getAttendanceRecord(event),
    timeStatus: getEventTimeStatusFor(event),
  })

  return actionState === 'sign-in' || actionState === 'sign-out'
}

function handleEventClick(event) {
  if (!event?.id) return
  if (shouldRouteToAttendance(event)) {
    void primeLocationAccess()
    router.push(resolveAttendanceLocation(route, event.id))
    return
  }
  router.push(resolveEventDetailLocation(route, event.id))
}

function handleOpenDetail(event) {
  if (!event?.id) return
  router.push(resolveEventDetailLocation(route, event.id))
}

function isEventAttended(event) {
  if (props.preview) {
    return activeAttendanceRecords.value.some((attendance) => {
      const status = String(attendance?.status ?? '').toLowerCase()
      const hasTimeIn = Boolean(attendance?.time_in)
      return Number(attendance?.event_id) === Number(event?.id) && (
        status === 'present' ||
        status === 'late' ||
        hasTimeIn
      )
    })
  }
  return hasAttendanceForEvent(event?.id)
}

function getAttendanceRecord(event) {
  if (props.preview) {
    return activeAttendanceRecords.value
      .filter((attendance) => Number(attendance?.event_id) === Number(event?.id))
      .sort((left, right) => {
        const leftTime = new Date(left?.time_in || left?.created_at || 0).getTime()
        const rightTime = new Date(right?.time_in || right?.created_at || 0).getTime()
        return rightTime - leftTime
      })[0] ?? null
  }
  return getLatestAttendanceForEvent(event?.id)
}

onBeforeUnmount(() => {
  stopEventTimeStatusPolling()
})

onMounted(() => {
  if (props.preview) return
  refreshAttendanceRecords({ limit: 200 }).catch(() => null)
})
</script>

<style scoped>
/* ── Page Base ───────────────────────────────────────────────────── */
.events-page {
  min-height: 100vh;
  padding: 28px 22px 100px; /* Bottom padding for mobile nav */
  background: var(--color-bg);
}

/* ── Page Title & Content ────────────────────────────────────────── */
.events-content {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.page-title {
  font-size: 24px;
  font-weight: 800;
  color: var(--color-text-always-dark);
  margin-bottom: 22px;
  letter-spacing: -0.5px;
}

/* ── Filters Scroll Track ────────────────────────────────────────── */
.filters-scroll {
  /* Hide scrollbar but allow horizontal scroll */
  overflow-x: auto;
  -ms-overflow-style: none;  /* IE and Edge */
  scrollbar-width: none;  /* Firefox */
  margin: 0 -22px 28px; /* Pull margins out to bleed edge */
  padding: 0 22px; /* Push content back in */
}

.filters-scroll::-webkit-scrollbar {
  display: none;
}

.filters-track {
  display: flex;
  gap: 10px;
  width: max-content;
}

.filter-pill {
  padding: 10px 22px;
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-always-dark);
  font-size: 14px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.filter-pill--active {
  background: var(--color-pill-row-active-bg);
  border-color: var(--color-pill-row-active-bg);
  color: var(--color-pill-row-active-text);
  font-weight: 600;
}

.filter-pill--outline {
  border-color: var(--color-pill-row-outline);
}

.filter-pill:active {
  transform: scale(0.96);
}

/* ── Events Grid ─────────────────────────────────────────────────── */
.events-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
  color: rgba(0,0,0,0.4);
  font-weight: 500;
}

/* ── Desktop adjustments (md+) ───────────────────────────────────── */
@media (min-width: 768px) {
  .events-page {
    padding: 36px 36px 40px;
  }

  .filters-scroll {
    margin: 0 0 32px 0;
    padding: 0;
  }
  
  .events-content {
    max-width: 960px;
  }
}

@media (min-width: 900px) {
  /* Two-column layout like the reference */
  .events-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 28px;
  }
}
</style>
