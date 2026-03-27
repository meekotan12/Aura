<template>
  <section class="school-it-reports">
    <div class="school-it-reports__shell">
      <SchoolItTopHeader
        class="dashboard-enter dashboard-enter--1"
        :avatar-url="avatarUrl"
        :school-name="activeSchoolSettings?.school_name || activeUser?.school_name || ''"
        :display-name="displayName"
        :initials="initials"
        @logout="handleLogout"
      />

      <div class="school-it-reports__body">
        <header class="school-it-reports__header dashboard-enter dashboard-enter--2">
          <button class="school-it-reports__back" type="button" @click="goBack" aria-label="Go Back">
            <ArrowLeft :size="20" />
          </button>
          <div class="school-it-reports__header-copy">
            <h1 class="school-it-reports__title">Event Reports</h1>
            <p class="school-it-reports__subtitle">View and download school-scoped attendance reports for events across your campus.</p>
          </div>
        </header>

        <section class="school-it-reports__content dashboard-enter dashboard-enter--3">
          <div class="school-it-reports__toolbar">
            <div class="school-it-reports__search-shell">
              <input
                v-model="searchQuery"
                class="school-it-reports__search-input"
                type="text"
                placeholder="Search events by name or location"
              >
              <span class="school-it-reports__search-icon" aria-hidden="true">
                <Search :size="18" :stroke-width="2.5" />
              </span>
            </div>

            <button
              v-if="selectedEvent"
              class="school-it-reports__clear-btn"
              type="button"
              @click="clearSelection"
            >
              <X :size="16" />
              Clear Selection
            </button>
          </div>

          <div class="school-it-reports__table-wrap">
            <table class="school-it-reports__table">
              <thead>
                <tr>
                  <th>Event Name</th>
                  <th>Date</th>
                  <th>Location</th>
                  <th class="school-it-reports__cell--actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="event in filteredEvents"
                  :key="event.id"
                  class="school-it-reports__table-row"
                  :class="{ 'school-it-reports__table-row--selected': Number(event.id) === selectedEventId }"
                  @click="viewEvent(event)"
                >
                  <td>
                    <div class="school-it-reports__event-name">{{ event.name }}</div>
                  </td>
                  <td>
                    <div class="school-it-reports__event-date">{{ formatDate(event.start_datetime) }}</div>
                  </td>
                  <td>
                    <div class="school-it-reports__event-loc">{{ event.location || 'Unspecified Location' }}</div>
                  </td>
                  <td class="school-it-reports__cell--actions">
                    <div class="school-it-reports__actions-tray">
                      <button class="school-it-reports__btn school-it-reports__btn--view" type="button" @click.stop="viewEvent(event)">
                        {{ Number(event.id) === selectedEventId ? 'Viewing' : 'View Report' }}
                      </button>
                      <button
                        class="school-it-reports__btn school-it-reports__btn--download"
                        type="button"
                        @click.stop="downloadReport(event, 'csv')"
                        :disabled="isDownloading === `${event.id}:csv`"
                      >
                        <Download :size="14" :stroke-width="2.5" />
                        {{ isDownloading === `${event.id}:csv` ? 'Exporting...' : 'CSV' }}
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!filteredEvents.length">
                  <td colspan="4" class="school-it-reports__empty">
                    {{ isLoading ? 'Loading events...' : 'No events found matching your search.' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <section class="school-it-reports__detail">
            <template v-if="selectedEvent">
              <header class="school-it-reports__detail-header">
                <div class="school-it-reports__detail-copy">
                  <h2 class="school-it-reports__detail-title">{{ selectedEventReport?.event_name || selectedEvent.name }}</h2>
                  <p class="school-it-reports__detail-meta">
                    <span>{{ formatDate(selectedEvent.start_datetime) }}</span>
                    <span>•</span>
                    <span>{{ selectedEventReport?.event_location || selectedEvent.location || 'Unspecified Location' }}</span>
                  </p>
                </div>

                <div class="school-it-reports__detail-actions">
                  <button
                    class="school-it-reports__btn school-it-reports__btn--download"
                    type="button"
                    @click="downloadReport(selectedEvent, 'csv')"
                    :disabled="isDownloading === `${selectedEvent.id}:csv`"
                  >
                    <Download :size="14" :stroke-width="2.5" />
                    {{ isDownloading === `${selectedEvent.id}:csv` ? 'Exporting...' : 'Export CSV' }}
                  </button>
                  <button
                    class="school-it-reports__btn school-it-reports__btn--excel"
                    type="button"
                    @click="downloadReport(selectedEvent, 'excel')"
                    :disabled="isDownloading === `${selectedEvent.id}:excel`"
                  >
                    <FileSpreadsheet :size="14" :stroke-width="2.5" />
                    {{ isDownloading === `${selectedEvent.id}:excel` ? 'Exporting...' : 'Export Excel' }}
                  </button>
                </div>
              </header>

              <p v-if="selectionError" class="school-it-reports__banner school-it-reports__banner--error">
                {{ selectionError }}
              </p>

              <p v-else-if="isLoadingSelection" class="school-it-reports__banner">
                Loading attendance records for this event...
              </p>

              <template v-else-if="selectedEventReport">
                <div class="school-it-reports__stats-grid">
                  <article
                    v-for="card in summaryCards"
                    :key="card.id"
                    class="school-it-reports__stat-card"
                  >
                    <span class="school-it-reports__stat-label">{{ card.label }}</span>
                    <strong class="school-it-reports__stat-value">{{ card.value }}</strong>
                    <span class="school-it-reports__stat-meta">{{ card.meta }}</span>
                  </article>
                </div>

                <div class="school-it-reports__insights-grid">
                  <article class="school-it-reports__panel">
                    <header class="school-it-reports__panel-header">
                      <h3 class="school-it-reports__panel-title">Attendance Breakdown</h3>
                      <p class="school-it-reports__panel-copy">Final backend counts for this event.</p>
                    </header>

                    <div class="school-it-reports__segments">
                      <div
                        v-for="segment in overallSegments"
                        :key="segment.id"
                        class="school-it-reports__segment-row"
                      >
                        <div class="school-it-reports__segment-copy">
                          <span>{{ segment.label }}</span>
                          <strong>{{ segment.count }}</strong>
                        </div>
                        <div class="school-it-reports__segment-track">
                          <span
                            class="school-it-reports__segment-fill"
                            :class="`school-it-reports__segment-fill--${segment.id}`"
                            :style="{ width: `${segment.width}%` }"
                          />
                        </div>
                      </div>
                    </div>
                  </article>

                  <article class="school-it-reports__panel">
                    <header class="school-it-reports__panel-header">
                      <h3 class="school-it-reports__panel-title">Program Statistics</h3>
                      <p class="school-it-reports__panel-copy">Per-program attendance from the backend report.</p>
                    </header>

                    <div v-if="programBreakdownRows.length" class="school-it-reports__program-list">
                      <div
                        v-for="row in programBreakdownRows"
                        :key="row.program"
                        class="school-it-reports__program-row"
                      >
                        <div class="school-it-reports__program-header">
                          <div>
                            <strong>{{ row.program }}</strong>
                            <span>{{ row.total }} total students</span>
                          </div>
                          <strong>{{ row.attendanceRate }}%</strong>
                        </div>
                        <div class="school-it-reports__program-track">
                          <span
                            v-for="segment in row.segments"
                            :key="`${row.program}-${segment.id}`"
                            class="school-it-reports__program-fill"
                            :class="`school-it-reports__program-fill--${segment.id}`"
                            :style="{ width: `${segment.width}%` }"
                          />
                        </div>
                        <div class="school-it-reports__program-meta">
                          <span>Present {{ row.present }}</span>
                          <span>Late {{ row.late }}</span>
                          <span>Waiting {{ row.incomplete }}</span>
                          <span>Absent {{ row.absent }}</span>
                        </div>
                      </div>
                    </div>
                    <p v-else class="school-it-reports__panel-empty">
                      No program breakdown is available for this event yet.
                    </p>
                  </article>
                </div>

                <article class="school-it-reports__panel school-it-reports__panel--records">
                  <header class="school-it-reports__panel-header school-it-reports__panel-header--records">
                    <div class="school-it-reports__panel-copy-wrap">
                      <h3 class="school-it-reports__panel-title">Attendance List</h3>
                      <p class="school-it-reports__panel-copy">
                        Latest backend attendance record per student for this event.
                      </p>
                    </div>

                    <div class="school-it-reports__records-tools">
                      <div class="school-it-reports__search-shell school-it-reports__search-shell--records">
                        <input
                          v-model="attendeeQuery"
                          class="school-it-reports__search-input"
                          type="text"
                          placeholder="Search student name or ID"
                        >
                        <span class="school-it-reports__search-icon" aria-hidden="true">
                          <Search :size="18" :stroke-width="2.5" />
                        </span>
                      </div>

                      <div class="school-it-reports__filters">
                        <button
                          v-for="option in attendeeFilterOptions"
                          :key="option.id"
                          class="school-it-reports__filter-pill"
                          :class="{ 'school-it-reports__filter-pill--active': attendeeFilter === option.id }"
                          type="button"
                          @click="attendeeFilter = option.id"
                        >
                          {{ option.label }}
                        </button>
                      </div>
                    </div>
                  </header>

                  <div class="school-it-reports__records-wrap">
                    <table class="school-it-reports__records-table">
                      <thead>
                        <tr>
                          <th>Student ID</th>
                          <th>Name</th>
                          <th>Status</th>
                          <th>Sign In</th>
                          <th>Sign Out</th>
                          <th>Duration</th>
                          <th>Method</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="row in filteredAttendanceRows" :key="row.key">
                          <td>{{ row.studentId }}</td>
                          <td>{{ row.studentName }}</td>
                          <td>
                            <span class="school-it-reports__status-chip" :class="`school-it-reports__status-chip--${row.category}`">
                              {{ row.statusLabel }}
                            </span>
                          </td>
                          <td>{{ row.timeInLabel }}</td>
                          <td>{{ row.timeOutLabel }}</td>
                          <td>{{ row.durationLabel }}</td>
                          <td>{{ row.methodLabel }}</td>
                        </tr>
                        <tr v-if="!filteredAttendanceRows.length">
                          <td colspan="7" class="school-it-reports__empty">
                            {{ attendanceRows.length ? 'No attendance records matched the current filters.' : 'No attendance records have been recorded for this event yet.' }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </article>
              </template>
            </template>

            <div v-else class="school-it-reports__placeholder">
              <h2>Select an Event</h2>
              <p>
                Choose an event above to load the live attendance summary, student sign-in list,
                and export actions for that event.
              </p>
            </div>
          </section>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Download, FileSpreadsheet, Search, X } from 'lucide-vue-next'
import SchoolItTopHeader from '@/components/dashboard/SchoolItTopHeader.vue'
import { useAuth } from '@/composables/useAuth.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { useStoredAuthMeta } from '@/composables/useStoredAuthMeta.js'
import { filterWorkspaceEntitiesBySchool } from '@/services/workspaceScope.js'
import {
  getEventAttendance,
  getEventAttendanceReport,
  getEvents,
  resolveApiBaseUrl,
} from '@/services/backendApi.js'
import { schoolItPreviewData } from '@/data/schoolItPreview.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const router = useRouter()
const route = useRoute()
const { logout } = useAuth()
const authMeta = useStoredAuthMeta()
const {
  currentUser,
  schoolSettings,
  apiBaseUrl,
  initializeDashboardSession,
  refreshSchoolSettings,
} = useDashboardSession()

const searchQuery = ref('')
const attendeeQuery = ref('')
const attendeeFilter = ref('all')
const isDownloading = ref('')
const eventsList = ref([])
const isLoadingEvents = ref(true)
const selectedEventId = ref(null)
const selectedEventReport = ref(null)
const selectedEventAttendanceRecords = ref([])
const isLoadingSelection = ref(false)
const selectionError = ref('')

const attendeeFilterOptions = [
  { id: 'all', label: 'All' },
  { id: 'waiting', label: 'Waiting' },
  { id: 'present', label: 'Present' },
  { id: 'late', label: 'Late' },
  { id: 'absent', label: 'Absent' },
]

const eventBundleCache = new Map()
let latestSelectionRequest = 0

const activeUser = computed(() => (props.preview ? schoolItPreviewData.user : currentUser.value))
const activeSchoolSettings = computed(() => (props.preview ? schoolItPreviewData.schoolSettings : schoolSettings.value))
const schoolId = computed(() => Number(activeUser.value?.school_id ?? activeSchoolSettings.value?.school_id ?? authMeta.value?.schoolId))
const schoolName = computed(() => (
  activeSchoolSettings.value?.school_name
  || activeUser.value?.school_name
  || authMeta.value?.schoolName
  || 'School'
))

const activeEvents = computed(() => (
  props.preview
    ? (Array.isArray(schoolItPreviewData.events) ? schoolItPreviewData.events : [])
    : eventsList.value
))

const filteredBySchoolEvents = computed(() => filterWorkspaceEntitiesBySchool(activeEvents.value, schoolId.value))

const displayName = computed(() => {
  const first = activeUser.value?.first_name || authMeta.value?.firstName || ''
  const middle = activeUser.value?.middle_name || ''
  const last = activeUser.value?.last_name || authMeta.value?.lastName || ''
  return [first, middle, last].filter(Boolean).join(' ')
    || activeUser.value?.email?.split('@')[0]
    || authMeta.value?.email?.split('@')[0]
    || 'Campus Admin'
})

const initials = computed(() => {
  const parts = String(displayName.value || '').split(' ').filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  return String(displayName.value || '').slice(0, 2).toUpperCase()
})

const avatarUrl = computed(() => activeUser.value?.avatar_url || '')

const filteredEvents = computed(() => {
  const query = String(searchQuery.value || '').trim().toLowerCase()
  const baseList = [...filteredBySchoolEvents.value]
    .sort((left, right) => new Date(right?.start_datetime || 0).getTime() - new Date(left?.start_datetime || 0).getTime())

  if (!query) return baseList

  return baseList.filter((event) => {
    const haystack = [event?.name, event?.location].filter(Boolean).join(' ').toLowerCase()
    return haystack.includes(query)
  })
})

const selectedEvent = computed(() => (
  filteredBySchoolEvents.value.find((event) => Number(event?.id) === Number(selectedEventId.value)) || null
))

const attendanceRows = computed(() => dedupeAttendanceRows(selectedEventAttendanceRecords.value))

const filteredAttendanceRows = computed(() => {
  const query = String(attendeeQuery.value || '').trim().toLowerCase()

  return attendanceRows.value.filter((row) => {
    if (attendeeFilter.value !== 'all' && row.category !== attendeeFilter.value) {
      return false
    }

    if (!query) return true

    return [
      row.studentId,
      row.studentName,
      row.statusLabel,
      row.methodLabel,
    ].filter(Boolean).join(' ').toLowerCase().includes(query)
  })
})

const presentCount = computed(() => Math.max(
  Number(selectedEventReport.value?.attendees || 0) - Number(selectedEventReport.value?.late_attendees || 0),
  0,
))

const summaryCards = computed(() => {
  const report = selectedEventReport.value
  if (!report) return []

  return [
    {
      id: 'participants',
      label: 'Total Participants',
      value: formatWholeNumber(report.total_participants),
      meta: 'Students inside the backend event scope',
    },
    {
      id: 'completed',
      label: 'Completed Attendance',
      value: formatWholeNumber(report.attendees),
      meta: 'Students with finalized sign-in and sign-out',
    },
    {
      id: 'late',
      label: 'Late Attendees',
      value: formatWholeNumber(report.late_attendees),
      meta: 'Marked late after the backend cutoff',
    },
    {
      id: 'waiting',
      label: 'Waiting for Sign Out',
      value: formatWholeNumber(report.incomplete_attendees),
      meta: 'Signed in but not fully finalized yet',
    },
    {
      id: 'absent',
      label: 'Absent',
      value: formatWholeNumber(report.absentees),
      meta: 'No completed attendance returned by the backend',
    },
    {
      id: 'rate',
      label: 'Attendance Rate',
      value: `${formatPercentage(report.attendance_rate)}%`,
      meta: 'Completed attendance versus total participants',
    },
  ]
})

const overallSegments = computed(() => {
  const report = selectedEventReport.value
  if (!report) return []

  const total = Math.max(Number(report.total_participants || 0), 1)
  return [
    {
      id: 'present',
      label: 'Present',
      count: presentCount.value,
      width: roundPercent((presentCount.value / total) * 100),
    },
    {
      id: 'late',
      label: 'Late',
      count: Number(report.late_attendees || 0),
      width: roundPercent((Number(report.late_attendees || 0) / total) * 100),
    },
    {
      id: 'waiting',
      label: 'Waiting',
      count: Number(report.incomplete_attendees || 0),
      width: roundPercent((Number(report.incomplete_attendees || 0) / total) * 100),
    },
    {
      id: 'absent',
      label: 'Absent',
      count: Number(report.absentees || 0),
      width: roundPercent((Number(report.absentees || 0) / total) * 100),
    },
  ].filter((segment) => segment.count > 0 || segment.id === 'present')
})

const programBreakdownRows = computed(() => {
  const rows = Array.isArray(selectedEventReport.value?.program_breakdown)
    ? selectedEventReport.value.program_breakdown
    : []

  return rows.map((row) => {
    const total = Math.max(Number(row?.total || 0), 0)
    const present = Number(row?.present || 0)
    const late = Number(row?.late || 0)
    const incomplete = Number(row?.incomplete || 0)
    const absent = Number(row?.absent || 0)

    return {
      program: row?.program || 'Unknown Program',
      total,
      present,
      late,
      incomplete,
      absent,
      attendanceRate: total > 0 ? roundPercent(((present + late) / total) * 100) : 0,
      segments: [
        { id: 'present', width: total > 0 ? roundPercent((present / total) * 100) : 0 },
        { id: 'late', width: total > 0 ? roundPercent((late / total) * 100) : 0 },
        { id: 'waiting', width: total > 0 ? roundPercent((incomplete / total) * 100) : 0 },
        { id: 'absent', width: total > 0 ? roundPercent((absent / total) * 100) : 0 },
      ].filter((segment) => segment.width > 0),
    }
  })
})

onMounted(async () => {
  if (!props.preview) {
    await initializeDashboardSession().catch(() => null)
    if (!schoolSettings.value) {
      await refreshSchoolSettings().catch(() => null)
    }
  }

  await fetchEvents()
})

watch(
  [() => route.query.eventId, filteredBySchoolEvents, isLoadingEvents],
  () => {
    syncSelectionFromRoute().catch(() => null)
  },
  { immediate: true },
)

async function fetchEvents() {
  isLoadingEvents.value = true

  if (props.preview) {
    isLoadingEvents.value = false
    return
  }

  try {
    const token = localStorage.getItem('aura_token') || ''
    eventsList.value = await getEvents(apiBaseUrl.value || resolveApiBaseUrl(), token)
  } catch (error) {
    selectionError.value = error?.message || 'Unable to load the event list right now.'
  } finally {
    isLoadingEvents.value = false
  }
}

async function syncSelectionFromRoute() {
  const requestedEventId = normalizeEventId(route.query.eventId)

  if (!requestedEventId) {
    if (selectedEventId.value != null) {
      clearSelection({ updateRoute: false })
    }
    return
  }

  if (requestedEventId === Number(selectedEventId.value) && (selectedEventReport.value || isLoadingSelection.value)) {
    return
  }

  const event = filteredBySchoolEvents.value.find((entry) => Number(entry?.id) === requestedEventId)
  if (!event) {
    if (!isLoadingEvents.value) {
      clearSelection({ updateRoute: false })
    }
    return
  }

  await viewEvent(event, { updateRoute: false })
}

async function viewEvent(event, { updateRoute = true, force = false } = {}) {
  const normalizedEventId = Number(event?.id)
  if (!Number.isFinite(normalizedEventId)) return null

  if (updateRoute && normalizeEventId(route.query.eventId) !== normalizedEventId) {
    router.replace({
      query: {
        ...route.query,
        eventId: String(normalizedEventId),
      },
    }).catch(() => null)
  }

  if (!force && selectedEventId.value === normalizedEventId && selectedEventReport.value) {
    return {
      report: selectedEventReport.value,
      records: selectedEventAttendanceRecords.value,
    }
  }

  selectedEventId.value = normalizedEventId
  attendeeQuery.value = ''
  attendeeFilter.value = 'all'
  selectionError.value = ''
  isLoadingSelection.value = true

  const requestId = ++latestSelectionRequest

  try {
    const bundle = await getEventReportBundle(event)
    if (requestId !== latestSelectionRequest) return null

    selectedEventReport.value = bundle.report
    selectedEventAttendanceRecords.value = bundle.records
    return bundle
  } catch (error) {
    if (requestId !== latestSelectionRequest) return null

    selectedEventReport.value = null
    selectedEventAttendanceRecords.value = []
    selectionError.value = resolveSelectionError(error)
    return null
  } finally {
    if (requestId === latestSelectionRequest) {
      isLoadingSelection.value = false
    }
  }
}

async function getEventReportBundle(event) {
  const normalizedEventId = Number(event?.id)
  if (!Number.isFinite(normalizedEventId)) {
    throw new Error('This event could not be opened.')
  }

  if (eventBundleCache.has(normalizedEventId)) {
    return eventBundleCache.get(normalizedEventId)
  }

  const bundle = props.preview
    ? buildPreviewBundle(event)
    : await fetchLiveEventBundle(normalizedEventId)

  eventBundleCache.set(normalizedEventId, bundle)
  return bundle
}

async function fetchLiveEventBundle(eventId) {
  const token = localStorage.getItem('aura_token') || ''
  const resolvedBaseUrl = apiBaseUrl.value || resolveApiBaseUrl()

  const [report, records] = await Promise.all([
    getEventAttendanceReport(resolvedBaseUrl, token, eventId),
    getEventAttendance(resolvedBaseUrl, token, eventId, { active_only: false }),
  ])

  return {
    report,
    records: Array.isArray(records) ? records : [],
  }
}

function buildPreviewBundle(event) {
  const summary = event?.attendance_summary && typeof event.attendance_summary === 'object'
    ? event.attendance_summary
    : {}

  const totalParticipants = Number(summary.total_attendance_records || 0)
  const lateAttendees = Number(summary.late_count || 0)
  const presentAttendees = Number(summary.present_count || 0)
  const incompleteAttendees = Number(summary.incomplete_count || 0)
  const absentees = Number(summary.absent_count || 0)
  const attendees = presentAttendees + lateAttendees

  return {
    report: {
      event_name: event?.name || 'Preview Event',
      event_date: formatDate(event?.start_datetime),
      event_location: event?.location || 'Preview Campus',
      total_participants: totalParticipants,
      attendees,
      late_attendees: lateAttendees,
      incomplete_attendees: incompleteAttendees,
      absentees,
      attendance_rate: totalParticipants > 0 ? roundPercent((attendees / totalParticipants) * 100) : 0,
      programs: [],
      program_breakdown: [],
    },
    records: Array.isArray(event?.attendances) ? event.attendances : [],
  }
}

function clearSelection({ updateRoute = true } = {}) {
  latestSelectionRequest += 1
  selectedEventId.value = null
  selectedEventReport.value = null
  selectedEventAttendanceRecords.value = []
  attendeeQuery.value = ''
  attendeeFilter.value = 'all'
  selectionError.value = ''
  isLoadingSelection.value = false

  if (updateRoute) {
    const nextQuery = { ...route.query }
    delete nextQuery.eventId
    router.replace({ query: nextQuery }).catch(() => null)
  }
}

async function downloadReport(event, format = 'csv') {
  const normalizedEventId = Number(event?.id)
  if (!Number.isFinite(normalizedEventId)) return

  const downloadKey = `${normalizedEventId}:${format}`
  if (isDownloading.value === downloadKey) return
  isDownloading.value = downloadKey

  try {
    const bundle = await viewEvent(event, {
      updateRoute: true,
      force: selectedEventId.value !== normalizedEventId,
    }) || await getEventReportBundle(event)

    const exportRows = dedupeAttendanceRows(bundle?.records || [])
    if (format === 'excel') {
      downloadExcelReport(event, bundle?.report, exportRows)
    } else {
      downloadCsvReport(event, bundle?.report, exportRows)
    }
  } catch (error) {
    selectionError.value = resolveSelectionError(error)
  } finally {
    isDownloading.value = ''
  }
}

function downloadCsvReport(event, report, rows) {
  const csvLines = [
    ['Event', report?.event_name || event?.name || 'Event'],
    ['Date', report?.event_date || formatDate(event?.start_datetime)],
    ['Location', report?.event_location || event?.location || 'N/A'],
    [],
    ['Summary'],
    ['Total Participants', formatWholeNumber(report?.total_participants || 0)],
    ['Completed Attendance', formatWholeNumber(report?.attendees || 0)],
    ['Late Attendees', formatWholeNumber(report?.late_attendees || 0)],
    ['Waiting for Sign Out', formatWholeNumber(report?.incomplete_attendees || 0)],
    ['Absent', formatWholeNumber(report?.absentees || 0)],
    ['Attendance Rate', `${formatPercentage(report?.attendance_rate || 0)}%`],
    [],
    ['Student ID', 'Student Name', 'Status', 'Sign In', 'Sign Out', 'Duration', 'Method'],
    ...rows.map((row) => [
      row.studentId,
      row.studentName,
      row.statusLabel,
      row.timeInLabel,
      row.timeOutLabel,
      row.durationLabel,
      row.methodLabel,
    ]),
  ]

  const csvContent = `\uFEFF${csvLines.map((line) => line.map(toCsvField).join(',')).join('\r\n')}`
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  triggerFileDownload(blob, `${sanitizeFilename(event?.name || report?.event_name || 'event_report')}.csv`)
}

function downloadExcelReport(event, report, rows) {
  const html = `
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          body { font-family: Arial, sans-serif; padding: 24px; }
          h1 { margin-bottom: 6px; }
          p { margin-top: 0; color: #555; }
          table { border-collapse: collapse; width: 100%; margin-top: 18px; }
          th, td { border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }
          th { background: #f3f4f6; font-weight: 700; }
          .meta td:first-child { font-weight: 700; width: 220px; }
        </style>
      </head>
      <body>
        <h1>${escapeHtml(report?.event_name || event?.name || 'Event Report')}</h1>
        <p>${escapeHtml(report?.event_date || formatDate(event?.start_datetime))} | ${escapeHtml(report?.event_location || event?.location || 'N/A')}</p>
        <table class="meta">
          <tbody>
            <tr><td>Total Participants</td><td>${escapeHtml(formatWholeNumber(report?.total_participants || 0))}</td></tr>
            <tr><td>Completed Attendance</td><td>${escapeHtml(formatWholeNumber(report?.attendees || 0))}</td></tr>
            <tr><td>Late Attendees</td><td>${escapeHtml(formatWholeNumber(report?.late_attendees || 0))}</td></tr>
            <tr><td>Waiting for Sign Out</td><td>${escapeHtml(formatWholeNumber(report?.incomplete_attendees || 0))}</td></tr>
            <tr><td>Absent</td><td>${escapeHtml(formatWholeNumber(report?.absentees || 0))}</td></tr>
            <tr><td>Attendance Rate</td><td>${escapeHtml(`${formatPercentage(report?.attendance_rate || 0)}%`)}</td></tr>
          </tbody>
        </table>
        <table>
          <thead>
            <tr>
              <th>Student ID</th>
              <th>Student Name</th>
              <th>Status</th>
              <th>Sign In</th>
              <th>Sign Out</th>
              <th>Duration</th>
              <th>Method</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <td>${escapeHtml(row.studentId)}</td>
                <td>${escapeHtml(row.studentName)}</td>
                <td>${escapeHtml(row.statusLabel)}</td>
                <td>${escapeHtml(row.timeInLabel)}</td>
                <td>${escapeHtml(row.timeOutLabel)}</td>
                <td>${escapeHtml(row.durationLabel)}</td>
                <td>${escapeHtml(row.methodLabel)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </body>
    </html>
  `

  const blob = new Blob([`\uFEFF${html}`], {
    type: 'application/vnd.ms-excel;charset=utf-8;',
  })
  triggerFileDownload(blob, `${sanitizeFilename(event?.name || report?.event_name || 'event_report')}.xls`)
}

function dedupeAttendanceRows(records) {
  const latestByStudent = new Map()

  for (const record of Array.isArray(records) ? records : []) {
    const key = resolveAttendanceStudentKey(record)
    const existing = latestByStudent.get(key)
    if (!existing || getAttendanceSortTimestamp(record) > getAttendanceSortTimestamp(existing)) {
      latestByStudent.set(key, record)
    }
  }

  return Array.from(latestByStudent.values())
    .map((record) => buildAttendanceRow(record))
    .sort((left, right) => left.studentName.localeCompare(right.studentName))
}

function buildAttendanceRow(record) {
  const attendance = record?.attendance || {}
  const category = resolveAttendanceCategory(attendance)

  return {
    key: `${resolveAttendanceStudentKey(record)}:${attendance.id ?? attendance.time_in ?? record?.student_name ?? 'row'}`,
    studentId: String(record?.student_id || 'N/A').trim() || 'N/A',
    studentName: String(record?.student_name || 'Unknown Student').trim() || 'Unknown Student',
    statusLabel: resolveAttendanceStatusLabel(attendance),
    category,
    timeInLabel: formatDateTime(attendance.time_in, category === 'absent' ? 'No sign-in record' : 'Not recorded'),
    timeOutLabel: attendance.time_out
      ? formatDateTime(attendance.time_out, 'Not recorded')
      : category === 'waiting'
      ? 'Waiting for sign out'
      : category === 'absent'
      ? 'No sign-out record'
      : 'Not recorded',
    durationLabel: formatDuration(attendance.duration_minutes),
    methodLabel: resolveMethodLabel(attendance.method),
  }
}

function resolveAttendanceStudentKey(record) {
  const numericProfileId = Number(record?.attendance?.student_id)
  if (Number.isFinite(numericProfileId)) return `profile:${numericProfileId}`

  const studentId = String(record?.student_id || '').trim()
  if (studentId) return `student:${studentId}`

  return `name:${String(record?.student_name || '').trim().toLowerCase()}`
}

function resolveAttendanceCategory(attendance = {}) {
  const completionState = String(attendance?.completion_state || '').toLowerCase()
  const displayStatus = String(attendance?.display_status || attendance?.status || '').toLowerCase()

  if (completionState !== 'completed') return 'waiting'
  if (displayStatus === 'late') return 'late'
  if (displayStatus === 'absent') return 'absent'
  return 'present'
}

function resolveAttendanceStatusLabel(attendance = {}) {
  const category = resolveAttendanceCategory(attendance)
  if (category === 'waiting') return 'Waiting for Sign Out'
  if (category === 'late') return 'Late'
  if (category === 'absent') return 'Absent'
  return 'Present'
}

function resolveMethodLabel(method) {
  const normalized = String(method || '').trim().toLowerCase()
  if (normalized === 'face_scan') return 'Face Scan'
  if (normalized === 'manual') return 'Manual'
  return normalized ? normalized.replace(/_/g, ' ') : 'Unknown'
}

function getAttendanceSortTimestamp(record) {
  const attendance = record?.attendance || {}
  const timestamp = new Date(attendance?.time_out || attendance?.time_in || 0).getTime()
  return Number.isFinite(timestamp) ? timestamp : 0
}

function normalizeEventId(value) {
  const rawValue = Array.isArray(value) ? value[0] : value
  const normalized = Number(rawValue)
  return Number.isFinite(normalized) ? normalized : null
}

function formatDate(isoString) {
  if (!isoString) return 'Unspecified Date'
  const normalizedValue = String(isoString)
  const date = /^\d{4}-\d{2}-\d{2}$/.test(normalizedValue)
    ? new Date(`${normalizedValue}T00:00:00`)
    : new Date(normalizedValue)
  if (Number.isNaN(date.getTime())) return String(isoString)
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

function formatDateTime(value, fallback = 'Not recorded') {
  if (!value) return fallback
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed)
}

function formatDuration(value) {
  const minutes = Number(value)
  if (!Number.isFinite(minutes) || minutes <= 0) return 'Not available'
  if (minutes < 60) return `${Math.round(minutes)}m`

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = Math.round(minutes % 60)
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`
}

function roundPercent(value) {
  const normalized = Number(value)
  if (!Number.isFinite(normalized)) return 0
  return Math.max(0, Math.min(100, Math.round(normalized)))
}

function formatPercentage(value) {
  const normalized = Number(value)
  return Number.isFinite(normalized) ? normalized.toFixed(2).replace(/\.00$/, '') : '0'
}

function formatWholeNumber(value) {
  const normalized = Number(value)
  if (!Number.isFinite(normalized)) return '0'
  return Math.round(normalized).toLocaleString('en-US')
}

function sanitizeFilename(value) {
  return String(value || 'event_report')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    || 'event_report'
}

function toSpreadsheetSafeText(value) {
  const text = String(value ?? '')
  return /^[=+\-@]/.test(text) ? `'${text}` : text
}

function toCsvField(value) {
  return `"${toSpreadsheetSafeText(value).replace(/"/g, '""')}"`
}

function triggerFileDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function escapeHtml(value) {
  return toSpreadsheetSafeText(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function resolveSelectionError(error) {
  return error?.message || 'Unable to load the attendance report for this event right now.'
}

function goBack() {
  if (props.preview) router.push({ name: 'PreviewSchoolItSchedule' })
  else router.push({ name: 'SchoolItSchedule' })
}

async function handleLogout() {
  await logout()
}
</script>

<style scoped>
.school-it-reports {
  min-height: 100vh;
  padding: 30px 28px 120px;
  font-family: 'Manrope', sans-serif;
  background: var(--color-bg, #f3f4f6);
}

.school-it-reports__shell {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
}

.school-it-reports__body {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-top: 32px;
}

.school-it-reports__header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.school-it-reports__back {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--color-text-always-dark, #111827);
  transition: background-color 0.2s;
  flex-shrink: 0;
}

.school-it-reports__back:hover {
  background: rgba(255, 255, 255, 0.38);
}

.school-it-reports__header-copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.school-it-reports__title {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--color-text-always-dark, #111827);
}

.school-it-reports__subtitle {
  margin: 0;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-secondary, #6b7280);
}

.school-it-reports__content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: var(--color-surface, #ffffff);
  border-radius: 32px;
  padding: 28px;
  border: 1px solid var(--color-surface-border, rgba(148, 163, 184, 0.16));
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.08);
}

.school-it-reports__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.school-it-reports__search-shell {
  display: flex;
  align-items: center;
  width: min(100%, 360px);
  height: 46px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--color-surface-border, rgba(148, 163, 184, 0.16));
  padding: 0 6px 0 20px;
  transition: border-color 0.2s;
}

.school-it-reports__search-shell:focus-within {
  border-color: var(--color-primary, #0057B8);
}

.school-it-reports__search-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  font-size: 14px;
  color: var(--color-text-always-dark, #111827);
  background: transparent;
}

.school-it-reports__search-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  flex-shrink: 0;
  color: var(--color-text-muted, #9ca3af);
}

.school-it-reports__table-wrap {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.school-it-reports__table {
  width: 100%;
  min-width: 700px;
  border-collapse: separate;
  border-spacing: 0;
}

.school-it-reports__table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 2px solid #f3f4f6;
}

.school-it-reports__table td {
  padding: 16px;
  vertical-align: middle;
  border-bottom: 1px solid #f3f4f6;
}

.school-it-reports__event-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-primary, #0057B8);
}

.school-it-reports__event-date,
.school-it-reports__event-loc {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-surface-text-secondary, #4b5563);
}

.school-it-reports__cell--actions {
  text-align: right;
  width: 220px;
}

.school-it-reports__actions-tray {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.school-it-reports__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 16px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  border: none;
  transition: transform 0.1s, filter 0.2s;
}

.school-it-reports__btn:active {
  transform: scale(0.96);
}

.school-it-reports__btn--view {
  background: var(--color-primary, #0057B8);
  color: var(--color-primary-text, #ffffff);
}

.school-it-reports__btn--download {
  background: var(--color-text-always-dark, #111827);
  color: #ffffff;
}

.school-it-reports__btn--excel {
  background: var(--color-secondary, #FFD400);
  color: var(--color-secondary-text, #111827);
}

.school-it-reports__btn--download:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.school-it-reports__empty {
  text-align: center !important;
  color: var(--color-surface-text-secondary, #6b7280);
  padding: 40px !important;
  font-size: 14px;
  font-weight: 500;
}

.school-it-reports__clear-btn,
.school-it-reports__filter-pill {
  border: none;
  cursor: pointer;
  font: inherit;
}

.school-it-reports__clear-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text-always-dark, #111827);
  box-shadow: 0 12px 26px rgba(15, 23, 42, 0.08);
}

.school-it-reports__table-row {
  transition: background-color 0.2s ease;
}

.school-it-reports__table-row:hover {
  background: rgba(15, 23, 42, 0.03);
}

.school-it-reports__table-row--selected {
  background: color-mix(in srgb, var(--color-primary, #0057B8) 10%, white);
}

.school-it-reports__detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
  border-radius: 28px;
  background: rgba(248, 250, 252, 0.62);
  padding: 24px;
}

.school-it-reports__detail-header,
.school-it-reports__panel-header,
.school-it-reports__records-tools {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.school-it-reports__detail-copy,
.school-it-reports__panel-copy-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.school-it-reports__detail-title,
.school-it-reports__panel-title {
  margin: 0;
  color: var(--color-text-always-dark, #111827);
}

.school-it-reports__detail-title {
  font-size: 22px;
  font-weight: 800;
}

.school-it-reports__panel-title {
  font-size: 18px;
  font-weight: 800;
}

.school-it-reports__detail-meta,
.school-it-reports__panel-copy {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--color-surface-text-secondary, #64748b);
  font-size: 14px;
}

.school-it-reports__detail-actions,
.school-it-reports__filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.school-it-reports__banner,
.school-it-reports__placeholder {
  border-radius: 24px;
  padding: 18px 20px;
  background: color-mix(in srgb, var(--color-primary, #0057B8) 8%, white);
  color: var(--color-text-always-dark, #111827);
}

.school-it-reports__banner--error {
  background: color-mix(in srgb, #ef4444 12%, white);
  color: #991b1b;
}

.school-it-reports__placeholder {
  text-align: center;
}

.school-it-reports__placeholder h2 {
  margin: 0 0 10px;
}

.school-it-reports__placeholder p {
  margin: 0;
  color: var(--color-surface-text-secondary, #64748b);
  line-height: 1.7;
}

.school-it-reports__stats-grid,
.school-it-reports__insights-grid {
  display: grid;
  gap: 14px;
}

.school-it-reports__stats-grid {
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.school-it-reports__insights-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.school-it-reports__stat-card,
.school-it-reports__panel {
  border-radius: 24px;
  background: #ffffff;
  border: 1px solid var(--color-surface-border, rgba(148, 163, 184, 0.16));
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.06);
}

.school-it-reports__stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 134px;
  padding: 18px;
}

.school-it-reports__stat-label {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-surface-text-secondary, #64748b);
}

.school-it-reports__stat-value {
  font-size: 28px;
  line-height: 1;
  color: var(--color-primary, #0057B8);
}

.school-it-reports__stat-meta {
  font-size: 13px;
  line-height: 1.55;
  color: var(--color-surface-text-secondary, #64748b);
}

.school-it-reports__panel {
  padding: 22px;
}

.school-it-reports__segments,
.school-it-reports__program-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.school-it-reports__segment-row,
.school-it-reports__program-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.school-it-reports__segment-copy,
.school-it-reports__program-header,
.school-it-reports__program-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.school-it-reports__segment-copy,
.school-it-reports__program-meta {
  font-size: 13px;
  color: var(--color-surface-text-secondary, #64748b);
}

.school-it-reports__segment-copy strong,
.school-it-reports__program-header strong {
  color: var(--color-text-always-dark, #111827);
}

.school-it-reports__segment-track,
.school-it-reports__program-track {
  position: relative;
  width: 100%;
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
}

.school-it-reports__segment-fill,
.school-it-reports__program-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
}

.school-it-reports__segment-fill--present,
.school-it-reports__program-fill--present {
  background: var(--color-primary, #0057B8);
}

.school-it-reports__segment-fill--late,
.school-it-reports__program-fill--late {
  background: #f59e0b;
}

.school-it-reports__segment-fill--waiting,
.school-it-reports__program-fill--waiting {
  background: #64748b;
}

.school-it-reports__segment-fill--absent,
.school-it-reports__program-fill--absent {
  background: #ef4444;
}

.school-it-reports__panel-empty {
  margin: 0;
  color: var(--color-surface-text-secondary, #64748b);
  line-height: 1.7;
}

.school-it-reports__panel--records {
  overflow: hidden;
}

.school-it-reports__panel-header--records {
  margin-bottom: 18px;
}

.school-it-reports__search-shell--records {
  width: min(100%, 320px);
}

.school-it-reports__filters {
  justify-content: flex-end;
}

.school-it-reports__filter-pill {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  color: var(--color-surface-text-secondary, #64748b);
  font-size: 13px;
  font-weight: 700;
}

.school-it-reports__filter-pill--active {
  background: var(--color-secondary, #FFD400);
  color: var(--color-secondary-text, #111827);
}

.school-it-reports__records-wrap {
  overflow-x: auto;
}

.school-it-reports__records-table {
  width: 100%;
  min-width: 720px;
  border-collapse: separate;
  border-spacing: 0;
}

.school-it-reports__records-table th,
.school-it-reports__records-table td {
  padding: 16px;
  vertical-align: middle;
  border-bottom: 1px solid #f3f4f6;
}

.school-it-reports__records-table th {
  text-align: left;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-surface-text-secondary, #6b7280);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.school-it-reports__status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.school-it-reports__status-chip--present {
  background: color-mix(in srgb, var(--color-primary, #0057B8) 14%, white);
  color: var(--color-primary, #0057B8);
}

.school-it-reports__status-chip--late {
  background: rgba(245, 158, 11, 0.16);
  color: #b45309;
}

.school-it-reports__status-chip--waiting {
  background: rgba(100, 116, 139, 0.16);
  color: #475569;
}

.school-it-reports__status-chip--absent {
  background: rgba(239, 68, 68, 0.16);
  color: #b91c1c;
}

@media (max-width: 960px) {
  .school-it-reports__insights-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .school-it-reports__content,
  .school-it-reports__detail {
    padding: 20px;
  }

  .school-it-reports__toolbar,
  .school-it-reports__records-tools {
    align-items: stretch;
  }

  .school-it-reports__search-shell,
  .school-it-reports__search-shell--records {
    width: 100%;
  }

  .school-it-reports__stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .school-it-reports__stats-grid {
    grid-template-columns: 1fr;
  }

  .school-it-reports__detail-title {
    font-size: 20px;
  }
}
</style>
