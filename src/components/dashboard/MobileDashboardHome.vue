<template>
  <section class="mobile-dashboard">
    <header class="mobile-dashboard__header">
      <button
        class="mobile-dashboard__profile"
        type="button"
        aria-label="Open profile"
        @click="router.push({ name: preview ? 'PreviewDashboardProfile' : 'Profile' })"
      >
        <img
          v-if="avatarUrl"
          :src="avatarUrl"
          :alt="displayName"
          class="mobile-dashboard__avatar"
        >
        <span v-else class="mobile-dashboard__avatar mobile-dashboard__avatar--fallback">{{ initials }}</span>

        <span class="mobile-dashboard__profile-copy">
          <span class="mobile-dashboard__eyebrow">Welcome Back</span>
          <span class="mobile-dashboard__name">{{ displayName }}</span>
        </span>
      </button>

      <button class="mobile-dashboard__notify" type="button" aria-label="Notifications">
        <Bell :size="18" :stroke-width="2" />
      </button>
    </header>

    <div class="mobile-dashboard__body">
      <h1 class="mobile-dashboard__title">Dashboard</h1>

      <section class="mobile-dashboard__search-block">
        <div class="mobile-dashboard__search-row">
          <div class="mobile-dashboard__search-wrap" :class="{ 'mobile-dashboard__search-wrap--active': searchActive }">
            <div class="mobile-dashboard__search-shell" :class="{ 'mobile-dashboard__search-shell--open': searchActive }">
              <div class="mobile-dashboard__search-input-row">
                <input
                  v-model="searchQuery"
                  v-bind="analyticsSearchInputAttrs"
                  type="text"
                  placeholder="Search attendance insight"
                  class="mobile-dashboard__search-input"
                >
                <button class="mobile-dashboard__search-icon" type="button" aria-label="Search">
                  <Search :size="18" />
                </button>
              </div>

              <div class="mobile-dashboard__search-results">
                <div class="mobile-dashboard__search-results-inner">
                  <template v-if="searchActive">
                    <button
                      v-for="result in analyticsSearchResults"
                      :key="result.key"
                      class="mobile-dashboard__search-result"
                      type="button"
                      @click="openEvent(result.event)"
                    >
                      <div class="mobile-dashboard__search-result-top">
                        <span class="mobile-dashboard__search-result-name">{{ result.name }}</span>
                        <span
                          class="mobile-dashboard__search-status"
                          :class="`mobile-dashboard__search-status--${result.status}`"
                        >
                          {{ result.statusLabel }}
                        </span>
                      </div>
                      <span class="mobile-dashboard__search-result-meta">{{ result.meta }}</span>
                    </button>
                    <p v-if="!analyticsSearchResults.length" class="mobile-dashboard__empty">
                      No attendance insight found for this filter.
                    </p>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <button
            v-show="!searchActive"
            class="mobile-dashboard__ai-pill"
            type="button"
            aria-label="Talk to Aura AI"
            :aria-expanded="isAiOpen ? 'true' : 'false'"
            @click="toggleAi"
          >
            <img :src="secondaryAuraLogo" alt="Aura" class="mobile-dashboard__ai-logo">
            <span class="mobile-dashboard__ai-copy">Talk to<br>Aura Ai</span>
          </button>
        </div>

        <Transition name="mobile-search">
          <div v-if="isAiOpen" class="mobile-dashboard__ai-panel">
            <div class="mobile-dashboard__ai-messages" ref="scrollEl">
              <div
                v-for="message in messages"
                :key="message.id"
                :class="['mobile-dashboard__bubble', message.sender === 'ai' ? 'mobile-dashboard__bubble--ai' : 'mobile-dashboard__bubble--user']"
              >
                {{ message.text }}
              </div>
            </div>

            <div class="mobile-dashboard__ai-input">
              <input
                ref="mobileInputEl"
                v-model="inputText"
                type="text"
                placeholder="Ask Aura..."
                class="mobile-dashboard__ai-field"
                :disabled="isTyping"
                @keyup.enter="sendMessage"
              >
              <button
                class="mobile-dashboard__ai-send"
                type="button"
                aria-label="Send message"
                :disabled="!inputText.trim() || isTyping"
                @click="sendMessage"
              >
                <Send :size="15" />
              </button>
            </div>
          </div>
        </Transition>
      </section>

      <section class="mobile-dashboard__tabs" aria-label="Dashboard sections">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="mobile-dashboard__tab"
          :class="{ 'mobile-dashboard__tab--active': activeTab === tab.key }"
          type="button"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </section>

      <Transition name="mobile-dashboard__panel-switch" mode="out-in">
        <div :key="activeTab" class="mobile-dashboard__panel-stack">
          <section class="mobile-dashboard__stats mobile-dashboard__panel-card mobile-dashboard__panel-card--stats">
            <article v-for="card in statCards" :key="card.label" class="mobile-dashboard__stat-card">
              <span class="mobile-dashboard__stat-value">{{ card.value }}</span>
              <span class="mobile-dashboard__stat-label">{{ card.label }}</span>
            </article>
          </section>

          <section class="mobile-dashboard__chart-card mobile-dashboard__panel-card mobile-dashboard__panel-card--chart">
            <div class="mobile-dashboard__bars">
              <div v-for="bar in chartBars" :key="bar.label" class="mobile-dashboard__bar-group">
                <span class="mobile-dashboard__bar" :style="{ height: `${bar.height}%` }" />
                <span class="mobile-dashboard__bar-label">{{ bar.label }}</span>
              </div>
            </div>
            <h2 class="mobile-dashboard__chart-title">{{ chartTitle }}</h2>
          </section>

          <section class="mobile-dashboard__overview mobile-dashboard__panel-card mobile-dashboard__panel-card--overview">
            <div class="mobile-dashboard__overview-head">
              <img :src="surfaceAuraLogo" alt="Aura" class="mobile-dashboard__overview-logo">
              <h2 class="mobile-dashboard__overview-title">{{ aiOverview.title }}</h2>
            </div>
            <p class="mobile-dashboard__overview-copy">{{ aiOverview.message }}</p>
          </section>
        </div>
      </Transition>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, Search, Send } from 'lucide-vue-next'
import { secondaryAuraLogo, surfaceAuraLogo } from '@/config/theme.js'
import { useChat } from '@/composables/useChat.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { studentDashboardPreviewData } from '@/data/studentDashboardPreview.js'
import {
  getAttendanceRecordTimestamp,
  getLatestAttendanceRecordsByEvent,
  isValidCompletedAttendanceRecord,
  resolveAttendanceDisplayStatus,
} from '@/services/attendanceFlow.js'
import { resolveDashboardAiOverview } from '@/services/dashboardAiOverview.js'
import { primeLocationAccess } from '@/services/devicePermissions.js'
import { createSearchFieldAttrs } from '@/services/searchFieldAttrs.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const router = useRouter()
const searchQuery = ref('')
const analyticsSearchInputAttrs = createSearchFieldAttrs('student-analytics-search')
const isAiOpen = ref(false)
const mobileInputEl = ref(null)
const activeTab = ref('main')
const tabs = [
  { key: 'main', label: 'Main' },
  { key: 'missed', label: 'Missed' },
  { key: 'late', label: 'Late' },
  { key: 'attended', label: 'Attended' },
]

const { currentUser, events, attendanceRecords, hasAttendanceForEvent, hasOpenAttendanceForEvent } = useDashboardSession()
const { messages, inputText, isTyping, scrollEl, sendMessage, closeAll } = useChat()
const activeUser = computed(() => props.preview ? studentDashboardPreviewData.user : currentUser.value)
const activeEvents = computed(() => props.preview ? studentDashboardPreviewData.events : events.value)
const activeAttendanceRecords = computed(() => props.preview ? studentDashboardPreviewData.attendanceRecords : attendanceRecords.value)
const searchActive = computed(() => searchQuery.value.trim().length > 0)

const schoolEvents = computed(() => {
  const schoolId = Number(activeUser.value?.school_id)
  return activeEvents.value.filter((event) => !Number.isFinite(schoolId) || Number(event?.school_id) === schoolId)
})

const eventLookup = computed(() => Object.fromEntries(schoolEvents.value.map((event) => [Number(event.id), event])))
const displayName = computed(() => [activeUser.value?.first_name, activeUser.value?.middle_name, activeUser.value?.last_name].filter(Boolean).join(' ') || activeUser.value?.email?.split('@')[0] || 'User Full Name')
const initials = computed(() => {
  const parts = displayName.value.split(' ').filter(Boolean)
  return parts.length >= 2 ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase() : displayName.value.slice(0, 2).toUpperCase()
})
const avatarUrl = computed(() => activeUser.value?.student_profile?.photo_url || activeUser.value?.student_profile?.avatar_url || activeUser.value?.avatar_url || '')
const searchableEvents = computed(() => schoolEvents.value.filter((event) => ['upcoming', 'ongoing'].includes(normalizeStatus(event.status))))
const filteredEvents = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return searchableEvents.value
  return searchableEvents.value.filter((event) => [event.name, event.location, event.status].filter(Boolean).join(' ').toLowerCase().includes(query))
})

const latestAttendanceRecords = computed(() => getLatestAttendanceRecordsByEvent(activeAttendanceRecords.value))

const latestAnalyticsEntries = computed(() => {
  return latestAttendanceRecords.value.map((record) => {
    const eventId = Number(record?.event_id)
    const event = eventLookup.value[eventId]
    const status = resolveAnalyticsStatus(record)
    const timestamp = getAttendanceRecordTimestamp(record)

    return {
      key: `${eventId}-${timestamp}`,
      event,
      eventId,
      status,
      statusLabel: attendanceStatusLabel(status),
      name: event?.name || `Event ${eventId}`,
      meta: buildAnalyticsSearchMeta(event, record, status),
      timestamp,
    }
  })
})

const analyticsSearchResults = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const entries = latestAnalyticsEntries.value.filter((entry) => matchesActiveTab(entry.status))
  if (!query) return entries

  return entries.filter((entry) =>
    [
      entry.name,
      entry.meta,
      entry.statusLabel,
      entry.status,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
      .includes(query)
  )
})

const summary = computed(() => latestAttendanceRecords.value.reduce((acc, record) => {
  const status = resolveAnalyticsStatus(record)
  if (status === 'present') acc.present += 1
  if (status === 'late') acc.late += 1
  if (status === 'absent') acc.absent += 1
  return acc
}, { present: 0, late: 0, absent: 0 }))

const attendedCount = computed(() => summary.value.present + summary.value.late)
const absentCount = computed(() => summary.value.absent)
const lateCount = computed(() => summary.value.late)
const markedCount = computed(() => attendedCount.value + absentCount.value)
const attendanceRate = computed(() => markedCount.value ? Math.round((attendedCount.value / markedCount.value) * 100) : 0)
const aiOverview = computed(() => resolveDashboardAiOverview())

const statCards = computed(() => {
  if (activeTab.value === 'missed') return [{ value: absentCount.value, label: 'Missed Events' }, { value: `${attendanceRate.value}%`, label: 'Attendance Rate' }]
  if (activeTab.value === 'late') return [{ value: lateCount.value, label: 'Late Events' }, { value: attendedCount.value, label: 'Attended' }]
  if (activeTab.value === 'attended') return [{ value: attendedCount.value, label: 'Attended' }, { value: absentCount.value, label: 'Missed Events' }]
  return [{ value: absentCount.value, label: 'Missed Events' }, { value: attendedCount.value, label: 'Attended' }]
})

const chartTitle = computed(() => activeTab.value === 'missed' ? 'Monthly Missed Events' : activeTab.value === 'late' ? 'Monthly Late Arrival' : 'Monthly Attendance')
const chartBars = computed(() => buildChartBars(latestAttendanceRecords.value, activeTab.value))

watch(isAiOpen, (open) => {
  if (open) {
    closeAll()
    nextTick(() => setTimeout(() => mobileInputEl.value?.focus(), 120))
  }
})

watch(searchQuery, (value) => {
  if (value.trim()) isAiOpen.value = false
})

function toggleAi() {
  isAiOpen.value = !isAiOpen.value
}

function openEvent(event) {
  if (!event?.id) return

  const normalizedEventId = Number(event.id)
  const shouldRouteToAttendance = (
    hasOpenAttendanceForEvent(normalizedEventId)
    || (normalizeStatus(event.status) === 'ongoing' && !hasAttendanceForEvent(normalizedEventId))
  )

  if (!props.preview && shouldRouteToAttendance) {
    void primeLocationAccess()
    router.push(`/dashboard/schedule/${event.id}/attendance`)
    return
  }
  router.push(props.preview ? `/exposed/dashboard/schedule/${event.id}` : `/dashboard/schedule/${event.id}`)
}

function normalizeStatus(status) {
  return status === 'done' ? 'completed' : String(status ?? '').toLowerCase()
}

function normalizeAttendanceStatus(status) {
  return String(status ?? '').trim().toLowerCase()
}

function resolveAnalyticsStatus(record) {
  const displayStatus = resolveAttendanceDisplayStatus(record)

  if (displayStatus === 'absent') return 'absent'
  if (displayStatus === 'late' && isValidCompletedAttendanceRecord(record)) return 'late'
  if (displayStatus === 'present' && isValidCompletedAttendanceRecord(record)) return 'present'
  if (displayStatus === 'excused') return 'excused'
  if (displayStatus === 'incomplete') return 'incomplete'
  return 'unmarked'
}

function attendanceStatusLabel(status) {
  if (status === 'absent') return 'Missed'
  if (status === 'late') return 'Late'
  if (status === 'present') return 'Attended'
  if (status === 'incomplete') return 'Waiting for Sign Out'
  if (status === 'excused') return 'Excused'
  return 'Unmarked'
}

function matchesActiveTab(status) {
  if (activeTab.value === 'missed') return status === 'absent'
  if (activeTab.value === 'late') return status === 'late'
  if (activeTab.value === 'attended') return status === 'present' || status === 'late'
  return ['present', 'late', 'absent', 'incomplete', 'excused'].includes(status)
}

function formatSearchMeta(event) {
  const pieces = []
  if (event.location) pieces.push(event.location)
  if (event.start_datetime) {
    const dateText = new Date(event.start_datetime).toLocaleDateString('en-PH', { month: 'short', day: 'numeric' })
    const timeText = new Date(event.start_datetime).toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit' })
    pieces.push(`${dateText} · ${timeText}`)
  }
  return pieces.join(' • ') || 'Event details'
}

function buildAnalyticsSearchMeta(event, record, status) {
  const pieces = []

  if (event?.location) pieces.push(event.location)

  const raw = record?.time_in || record?.created_at || record?.updated_at
  if (raw) {
    const parsed = new Date(raw)
    if (!Number.isNaN(parsed.getTime())) {
      pieces.push(parsed.toLocaleDateString('en-PH', { month: 'short', day: 'numeric' }))
    }
  }

  pieces.push(attendanceStatusLabel(status))
  return pieces.join(' • ')
}

function timestamp(record) {
  const raw = record?.time_in || record?.created_at || record?.updated_at
  if (!raw) return null
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function buildChartBars(records, mode) {
  const referenceDates = records.map(timestamp).filter(Boolean)
  const reference = new Date(Math.max(...referenceDates.map((date) => date.getTime()), Date.now()))
  const weekStart = startOfWeek(reference)
  const bars = []

  for (let index = 3; index >= 0; index -= 1) {
    const start = new Date(weekStart)
    start.setDate(weekStart.getDate() - (index * 7))
    const end = new Date(start)
    end.setDate(start.getDate() + 6)
    end.setHours(23, 59, 59, 999)

    const value = records.filter((record) => {
      const date = timestamp(record)
      if (!date || date < start || date > end) return false
      const status = resolveAnalyticsStatus(record)
      if (mode === 'missed') return status === 'absent'
      if (mode === 'late') return status === 'late'
      return status === 'present' || status === 'late'
    }).length

    bars.push({ label: `Week ${4 - index}`, value })
  }

  const maxValue = Math.max(...bars.map((bar) => bar.value), 1)
  return bars.map((bar) => ({
    ...bar,
    height: Math.max(16, Math.round((bar.value / maxValue) * 100)),
  }))
}

function startOfWeek(date) {
  const next = new Date(date)
  const day = next.getDay()
  const diff = day === 0 ? -6 : 1 - day
  next.setDate(next.getDate() + diff)
  next.setHours(0, 0, 0, 0)
  return next
}
</script>

<style scoped>
.mobile-dashboard { padding: 34px 28px 120px; font-family: 'Manrope', sans-serif; }
.mobile-dashboard__header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.mobile-dashboard__profile { display: inline-flex; align-items: center; gap: 12px; min-height: 52px; padding: 6px 16px 6px 6px; border: none; border-radius: 999px; background: var(--color-surface); color: var(--color-text-always-dark); }
.mobile-dashboard__avatar { width: 40px; height: 40px; border-radius: 999px; flex-shrink: 0; object-fit: cover; }
.mobile-dashboard__avatar--fallback { display: inline-flex; align-items: center; justify-content: center; background: var(--color-nav); color: #fff; font-size: 14px; font-weight: 700; }
.mobile-dashboard__profile-copy { display: flex; flex-direction: column; align-items: flex-start; line-height: 1.05; }
.mobile-dashboard__eyebrow { font-size: 10px; font-weight: 500; color: var(--color-text-muted); }
.mobile-dashboard__name { margin-top: 2px; font-size: 14px; font-weight: 600; }
.mobile-dashboard__notify { width: 52px; height: 52px; border: none; border-radius: 999px; background: var(--color-surface); color: var(--color-text-always-dark); display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.mobile-dashboard__body { display: flex; flex-direction: column; gap: 18px; margin-top: 30px; }
.mobile-dashboard__title { margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.04em; color: var(--color-text-primary); }
.mobile-dashboard__search-block { display: flex; flex-direction: column; gap: 10px; }
.mobile-dashboard__search-row { display: flex; gap: 10px; }
.mobile-dashboard__search-wrap { flex: 1; min-width: 0; transition: flex 0.3s ease; }
.mobile-dashboard__search-wrap--active { flex: 1 1 100%; }
.mobile-dashboard__search-shell { display: grid; grid-template-rows: auto 0fr; background: var(--color-surface); border-radius: 30px; padding: 12px 16px; transition: grid-template-rows 300ms cubic-bezier(0.22, 1, 0.36, 1), border-radius 300ms cubic-bezier(0.22, 1, 0.36, 1); }
.mobile-dashboard__search-shell--open { grid-template-rows: auto 1fr; border-radius: 28px; }
.mobile-dashboard__search-input-row { display: flex; align-items: center; gap: 8px; min-height: 36px; }
.mobile-dashboard__search-input { flex: 1; min-width: 0; border: none; background: transparent; outline: none; color: var(--color-text-always-dark); font-size: 14px; font-weight: 500; }
.mobile-dashboard__search-input::placeholder { color: var(--color-text-muted); }
.mobile-dashboard__search-icon {
  width: 30px;
  height: 30px;
  border: 1px solid var(--color-surface-border);
  border-radius: 999px;
  background: transparent;
  color: var(--color-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  align-self: center;
}
.mobile-dashboard__ai-pill { width: 118px; min-height: 60px; border: none; border-radius: 999px; background: var(--color-search-pill-bg); color: var(--color-search-pill-text); display: inline-flex; align-items: center; justify-content: center; gap: 10px; padding: 0 14px; flex-shrink: 0; }
.mobile-dashboard__ai-logo { width: 32px; height: 32px; object-fit: contain; }
.mobile-dashboard__ai-copy { font-size: 13px; font-weight: 700; line-height: 0.98; text-align: left; }
.mobile-dashboard__search-results { overflow: hidden; min-height: 0; }
.mobile-dashboard__search-results-inner,
.mobile-dashboard__ai-panel { display: flex; flex-direction: column; gap: 10px; }
.mobile-dashboard__search-results-inner { padding: 14px 0 6px; }
.mobile-dashboard__search-result { width: 100%; border: none; border-radius: 22px; background: rgba(10,0,0,0.03); padding: 14px 16px; text-align: left; display: flex; flex-direction: column; gap: 8px; }
.mobile-dashboard__search-result-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.mobile-dashboard__search-result-name { font-size: 14px; font-weight: 700; color: var(--color-text-always-dark); }
.mobile-dashboard__search-status { display: inline-flex; align-items: center; justify-content: center; min-height: 28px; padding: 0 12px; border-radius: 999px; font-size: 11px; font-weight: 800; letter-spacing: 0.02em; flex-shrink: 0; }
.mobile-dashboard__search-status--absent { background: rgba(229, 53, 53, 0.12); color: #b42318; }
.mobile-dashboard__search-status--late { background: rgba(255, 184, 0, 0.18); color: #8a5b00; }
.mobile-dashboard__search-status--present { background: rgba(0, 200, 100, 0.14); color: #006633; }
.mobile-dashboard__search-result-meta,.mobile-dashboard__empty { font-size: 12px; color: var(--color-text-muted); }
.mobile-dashboard__ai-panel { padding: 16px; border-radius: 28px; background: var(--color-primary); }
.mobile-dashboard__ai-messages { max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; scrollbar-width: none; }
.mobile-dashboard__ai-messages::-webkit-scrollbar { display: none; }
.mobile-dashboard__bubble { max-width: 88%; padding: 12px 16px; border-radius: 24px; font-size: 13px; line-height: 1.5; font-weight: 600; }
.mobile-dashboard__bubble--ai { align-self: flex-start; background: var(--color-surface); color: var(--color-text-always-dark); }
.mobile-dashboard__bubble--user { align-self: flex-end; background: rgba(0,0,0,0.12); color: var(--color-banner-text); }
.mobile-dashboard__ai-input { margin-top: 12px; display: flex; }
.mobile-dashboard__ai-field { flex: 1; min-width: 0; min-height: 46px; padding: 0 16px; border: none; border-radius: 999px 0 0 999px; background: rgba(0,0,0,0.08); color: var(--color-banner-text); outline: none; }
.mobile-dashboard__ai-field::placeholder { color: var(--color-banner-text); opacity: 0.7; }
.mobile-dashboard__ai-send { width: 46px; border: none; border-radius: 0 999px 999px 0; background: rgba(0,0,0,0.12); color: var(--color-banner-text); display: inline-flex; align-items: center; justify-content: center; }
.mobile-dashboard__tabs { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: none; }
.mobile-dashboard__tabs::-webkit-scrollbar { display: none; }
.mobile-dashboard__tab { min-width: 96px; min-height: 52px; padding: 0 20px; border: none; border-radius: 999px; background: var(--color-surface); color: var(--color-text-always-dark); font-size: 15px; font-weight: 500; flex-shrink: 0; }
.mobile-dashboard__tab--active { background: var(--color-pill-row-active-bg); color: var(--color-pill-row-active-text); }
.mobile-dashboard__panel-stack { display: flex; flex-direction: column; gap: 18px; }
.mobile-dashboard__panel-card { will-change: transform, opacity; }
.mobile-dashboard__panel-card--stats { animation: mobile-dashboard-card-rise 560ms cubic-bezier(0.22, 1, 0.36, 1) both; animation-delay: 30ms; }
.mobile-dashboard__panel-card--chart { animation: mobile-dashboard-card-rise 620ms cubic-bezier(0.22, 1, 0.36, 1) both; animation-delay: 90ms; }
.mobile-dashboard__panel-card--overview { animation: mobile-dashboard-card-rise 680ms cubic-bezier(0.22, 1, 0.36, 1) both; animation-delay: 150ms; }
.mobile-dashboard__stats { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 18px; }
.mobile-dashboard__stat-card { min-height: 152px; border-radius: 28px; background: var(--color-surface); padding: 26px 20px; display: flex; align-items: center; gap: 14px; }
.mobile-dashboard__stat-value { font-size: 48px; font-weight: 700; letter-spacing: -0.06em; line-height: 0.9; color: var(--color-text-always-dark); }
.mobile-dashboard__stat-label { font-size: 16px; line-height: 1.15; font-weight: 500; color: var(--color-text-always-dark); }
.mobile-dashboard__chart-card { border-radius: 28px; background: var(--color-primary); color: var(--color-banner-text); padding: 18px 18px 16px; }
.mobile-dashboard__bars { display: flex; align-items: end; gap: 18px; height: 150px; }
.mobile-dashboard__bar-group { display: flex; flex-direction: column; align-items: center; gap: 8px; width: 36px; flex-shrink: 0; }
.mobile-dashboard__bar { width: 20px; min-height: 18px; border-radius: 999px; background: var(--color-surface); }
.mobile-dashboard__bar-label { font-size: 12px; font-weight: 500; white-space: nowrap; }
.mobile-dashboard__chart-title { margin: 4px 0 0; font-size: 19px; font-weight: 800; letter-spacing: -0.04em; }
.mobile-dashboard__overview { border-radius: 28px; background: var(--color-surface); padding: 20px 22px 22px; display: flex; flex-direction: column; gap: 16px; }
.mobile-dashboard__overview-head { display: flex; align-items: center; gap: 10px; }
.mobile-dashboard__overview-logo { width: 28px; height: 28px; object-fit: contain; }
.mobile-dashboard__overview-title { margin: 0; font-size: 18px; font-weight: 700; letter-spacing: -0.04em; color: var(--color-text-always-dark); }
.mobile-dashboard__overview-copy { margin: 0; font-size: 14px; line-height: 1.42; color: var(--color-text-always-dark); }
.mobile-search-enter-active,.mobile-search-leave-active { transition: opacity 0.22s ease, transform 0.22s ease; }
.mobile-search-enter-from,.mobile-search-leave-to { opacity: 0; transform: translateY(-8px); }
.mobile-dashboard__panel-switch-enter-active,
.mobile-dashboard__panel-switch-leave-active { transition: opacity 300ms cubic-bezier(0.22, 1, 0.36, 1), transform 360ms cubic-bezier(0.22, 1, 0.36, 1); }
.mobile-dashboard__panel-switch-enter-from,
.mobile-dashboard__panel-switch-leave-to { opacity: 0; transform: translateY(10px) scale(0.988); }

@keyframes mobile-dashboard-card-rise {
  0% {
    opacity: 0;
    transform: translateY(16px) scale(0.986);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
