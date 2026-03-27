<template>
  <div class="analytics-page">
    <div class="md:hidden">
      <MobileDashboardHome :preview="preview" />
    </div>

    <div class="analytics-desktop hidden md:block">
      <TopBar
        class="dashboard-enter dashboard-enter--1"
        :user="activeUser"
        :unread-count="activeUnreadAnnouncements"
        @toggle-notifications="showNotifications = !showNotifications"
      />

      <section class="analytics-desktop__content">
        <header class="analytics-desktop__hero dashboard-enter dashboard-enter--2">
          <div>
            <p class="analytics-desktop__eyebrow">Attendance Analytics</p>
            <h1 class="analytics-desktop__title">Analytics</h1>
          </div>
          <p class="analytics-desktop__subtitle">
            Monitor attendance movement, missed events, and weekly performance using your current school data.
          </p>
        </header>

        <section class="analytics-desktop__stats dashboard-enter dashboard-enter--3">
          <article
            v-for="card in statCards"
            :key="card.label"
            class="analytics-stat-card"
            :class="{ 'analytics-stat-card--primary': card.tone === 'primary' }"
          >
            <span class="analytics-stat-card__label">{{ card.label }}</span>
            <strong class="analytics-stat-card__value">{{ card.value }}</strong>
            <span class="analytics-stat-card__meta">{{ card.meta }}</span>
          </article>
        </section>

        <section class="analytics-panel dashboard-enter dashboard-enter--4">
          <div class="analytics-panel__top">
            <div>
              <p class="analytics-panel__eyebrow">Weekly Trend</p>
              <h2 class="analytics-panel__title">Attendance rate over time</h2>
            </div>

            <div class="analytics-panel__badge">
              <span>{{ trendRangeLabel }}</span>
            </div>
          </div>

          <div class="analytics-panel__body">
            <div class="analytics-chart">
              <svg
                class="analytics-chart__svg"
                viewBox="0 0 720 320"
                preserveAspectRatio="none"
                role="img"
                aria-label="Attendance trend chart"
              >
                <line
                  v-for="gridLine in gridLines"
                  :key="`grid-${gridLine.value}`"
                  class="analytics-chart__grid-line"
                  x1="24"
                  :y1="gridLine.y"
                  x2="696"
                  :y2="gridLine.y"
                />

                <line
                  v-for="week in chartPoints"
                  :key="`vertical-${week.label}`"
                  class="analytics-chart__vertical-line"
                  :x1="week.x"
                  y1="30"
                  :x2="week.x"
                  y2="262"
                />

                <path
                  class="analytics-chart__area"
                  :d="areaPath"
                />
                <path
                  class="analytics-chart__line"
                  :d="linePath"
                  pathLength="1"
                />

                <g
                  v-for="(point, index) in chartPoints"
                  :key="point.label"
                  class="analytics-chart__point-group"
                  :style="{ '--point-delay': `${index * 110}ms` }"
                >
                  <circle
                    class="analytics-chart__point-ring"
                    :cx="point.x"
                    :cy="point.y"
                    r="9"
                  />
                  <circle
                    class="analytics-chart__point-core"
                    :cx="point.x"
                    :cy="point.y"
                    r="4.5"
                  />
                </g>
              </svg>

              <div class="analytics-chart__labels">
                <div
                  v-for="point in chartPoints"
                  :key="`label-${point.label}`"
                  class="analytics-chart__label"
                >
                  <span class="analytics-chart__label-top">{{ point.shortLabel }}</span>
                  <span class="analytics-chart__label-bottom">{{ point.rate }}%</span>
                </div>
              </div>
            </div>

            <aside class="analytics-side">
              <article class="analytics-side__card">
                <span class="analytics-side__label">Best Week</span>
                <strong class="analytics-side__value">{{ bestWeek.label }}</strong>
                <p class="analytics-side__copy">{{ bestWeek.rate }}% attendance rate with {{ bestWeek.attended }} marked arrivals.</p>
              </article>

              <article class="analytics-side__card">
                <span class="analytics-side__label">Latest Snapshot</span>
                <strong class="analytics-side__value">{{ latestWeek.label }}</strong>
                <p class="analytics-side__copy">
                  {{ latestWeek.attended }} attended, {{ latestWeek.absent }} missed, and {{ latestWeek.late }} late this week.
                </p>
              </article>

              <article class="analytics-side__card analytics-side__card--overview">
                <div class="analytics-side__overview-head">
                  <img :src="surfaceAuraLogo" alt="Aura" class="analytics-side__overview-logo">
                  <span class="analytics-side__overview-title">{{ aiOverview.title }}</span>
                </div>
                <p class="analytics-side__copy">{{ aiOverview.message }}</p>
              </article>
            </aside>
          </div>
        </section>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import TopBar from '@/components/dashboard/TopBar.vue'
import MobileDashboardHome from '@/components/dashboard/MobileDashboardHome.vue'
import { surfaceAuraLogo } from '@/config/theme.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { usePreviewTheme } from '@/composables/usePreviewTheme.js'
import { studentDashboardPreviewData } from '@/data/studentDashboardPreview.js'
import {
  getAttendanceRecordTimestamp,
  getLatestAttendanceRecordsByEvent,
  isValidCompletedAttendanceRecord,
  resolveAttendanceDisplayStatus,
} from '@/services/attendanceFlow.js'
import { resolveDashboardAiOverview } from '@/services/dashboardAiOverview.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const showNotifications = ref(false)
const {
  currentUser,
  attendanceRecords,
  unreadAnnouncements,
} = useDashboardSession()
const activeUser = computed(() => props.preview ? studentDashboardPreviewData.user : currentUser.value)
const activeAttendanceRecords = computed(() => props.preview ? studentDashboardPreviewData.attendanceRecords : attendanceRecords.value)
const activeUnreadAnnouncements = computed(() => props.preview ? 0 : unreadAnnouncements.value)
const activeSchoolSettings = computed(() => props.preview ? studentDashboardPreviewData.schoolSettings : null)

usePreviewTheme(() => props.preview, activeSchoolSettings)

const aiOverview = computed(() => resolveDashboardAiOverview())
const latestAttendanceRecords = computed(() => getLatestAttendanceRecordsByEvent(activeAttendanceRecords.value))

const attendanceSummary = computed(() => latestAttendanceRecords.value.reduce((summary, record) => {
  const status = resolveAnalyticsStatus(record)
  if (status === 'present') summary.present += 1
  if (status === 'late') summary.late += 1
  if (status === 'absent') summary.absent += 1
  return summary
}, { present: 0, late: 0, absent: 0 }))

const attendedCount = computed(() => attendanceSummary.value.present + attendanceSummary.value.late)
const missedCount = computed(() => attendanceSummary.value.absent)
const lateCount = computed(() => attendanceSummary.value.late)
const markedCount = computed(() => attendedCount.value + missedCount.value)
const attendanceRate = computed(() => (
  markedCount.value ? Math.round((attendedCount.value / markedCount.value) * 100) : 0
))

const statCards = computed(() => [
  {
    label: 'Attendance Rate',
    value: `${attendanceRate.value}%`,
    meta: `${markedCount.value} total marked events`,
    tone: 'primary',
  },
  {
    label: 'Attended',
    value: String(attendedCount.value),
    meta: `${attendanceSummary.value.present} present and ${lateCount.value} late`,
    tone: 'surface',
  },
  {
    label: 'Missed',
    value: String(missedCount.value),
    meta: 'Marked absent by the backend',
    tone: 'surface',
  },
  {
    label: 'Late Arrivals',
    value: String(lateCount.value),
    meta: 'Late attendance records',
    tone: 'surface',
  },
])

const trendWeeks = computed(() => buildWeeklyTrend(latestAttendanceRecords.value, 6))

const bestWeek = computed(() => {
  if (!trendWeeks.value.length) {
    return { label: 'No data yet', rate: 0, attended: 0 }
  }

  return [...trendWeeks.value].sort((left, right) => {
    if (right.rate !== left.rate) return right.rate - left.rate
    return right.attended - left.attended
  })[0]
})

const latestWeek = computed(() => trendWeeks.value[trendWeeks.value.length - 1] ?? {
  label: 'This week',
  attended: 0,
  absent: 0,
  late: 0,
})

const trendRangeLabel = computed(() => {
  if (!trendWeeks.value.length) return 'No recent attendance data'
  const first = trendWeeks.value[0]
  const last = trendWeeks.value[trendWeeks.value.length - 1]
  return `${first.shortLabel} - ${last.shortLabel}`
})

const gridLines = computed(() => {
  const steps = [0, 25, 50, 75, 100]
  return steps.map((value) => ({
    value,
    y: chartY(value),
  }))
})

const chartPoints = computed(() => {
  const weeks = trendWeeks.value
  if (!weeks.length) return []

  const width = 720
  const left = 42
  const right = 678
  const count = weeks.length
  const step = count > 1 ? (right - left) / (count - 1) : 0

  return weeks.map((week, index) => ({
    ...week,
    x: count > 1 ? left + (step * index) : (left + right) / 2,
    y: chartY(week.rate),
  }))
})

const linePath = computed(() => {
  if (!chartPoints.value.length) return ''
  return chartPoints.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')
})

const areaPath = computed(() => {
  if (!chartPoints.value.length) return ''
  const baseline = chartY(0)
  const first = chartPoints.value[0]
  const last = chartPoints.value[chartPoints.value.length - 1]
  return `${linePath.value} L ${last.x} ${baseline} L ${first.x} ${baseline} Z`
})

function chartY(rate) {
  const top = 30
  const bottom = 262
  const usableHeight = bottom - top
  return top + usableHeight * (1 - (rate / 100))
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

function buildWeeklyTrend(records, totalWeeks = 6) {
  const normalized = records
    .map((record) => {
      const timestamp = getAttendanceRecordTimestamp(record)
      if (!timestamp) return null
      return {
        status: resolveAnalyticsStatus(record),
        date: new Date(timestamp),
      }
    })
    .filter(Boolean)

  const reference = normalized.length
    ? new Date(Math.max(...normalized.map((record) => record.date.getTime())))
    : new Date()

  const currentWeek = startOfWeek(reference)
  const weeks = []

  for (let index = totalWeeks - 1; index >= 0; index -= 1) {
    const start = new Date(currentWeek)
    start.setDate(start.getDate() - (index * 7))
    const end = new Date(start)
    end.setDate(start.getDate() + 6)
    end.setHours(23, 59, 59, 999)

    const weekRecords = normalized.filter((record) => record.date >= start && record.date <= end)
    const attended = weekRecords.filter((record) => record.status === 'present' || record.status === 'late').length
    const absent = weekRecords.filter((record) => record.status === 'absent').length
    const late = weekRecords.filter((record) => record.status === 'late').length
    const marked = attended + absent
    const rate = marked ? Math.round((attended / marked) * 100) : 0

    weeks.push({
      label: formatWeekRange(start, end),
      shortLabel: formatShortWeek(start),
      attended,
      absent,
      late,
      marked,
      rate,
    })
  }

  return weeks
}

function startOfWeek(date) {
  const next = new Date(date)
  const day = next.getDay()
  const diff = day === 0 ? -6 : 1 - day
  next.setDate(next.getDate() + diff)
  next.setHours(0, 0, 0, 0)
  return next
}

function formatWeekRange(start, end) {
  return `${start.toLocaleDateString('en-PH', { month: 'short', day: 'numeric' })} - ${end.toLocaleDateString('en-PH', { month: 'short', day: 'numeric' })}`
}

function formatShortWeek(start) {
  return start.toLocaleDateString('en-PH', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.analytics-page {
  min-height: 100vh;
  padding: 0;
}

.analytics-desktop {
  min-height: 100vh;
  padding: 36px 36px 40px;
}

.analytics-desktop__content {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.analytics-desktop__hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}

.analytics-desktop__eyebrow,
.analytics-panel__eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.analytics-desktop__title {
  margin: 0;
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.06em;
  color: var(--color-text-primary);
}

.analytics-desktop__subtitle {
  max-width: 420px;
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.analytics-desktop__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.analytics-stat-card {
  min-height: 150px;
  border-radius: 28px;
  padding: 22px 22px 20px;
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid rgba(10, 10, 10, 0.06);
}

.analytics-stat-card--primary {
  background: var(--color-primary);
  color: var(--color-banner-text);
  border-color: transparent;
}

.analytics-stat-card__label {
  font-size: 13px;
  font-weight: 700;
  color: inherit;
  opacity: 0.78;
}

.analytics-stat-card__value {
  font-size: 44px;
  line-height: 0.95;
  font-weight: 800;
  letter-spacing: -0.06em;
  color: inherit;
}

.analytics-stat-card__meta {
  font-size: 13px;
  line-height: 1.45;
  color: inherit;
  opacity: 0.68;
}

.analytics-panel {
  display: flex;
  flex-direction: column;
  gap: 22px;
  min-height: 540px;
  padding: 28px;
  border-radius: 32px;
  background: var(--color-surface);
  border: 1px solid rgba(10, 10, 10, 0.06);
}

.analytics-panel__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.analytics-panel__title {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.05em;
  color: var(--color-text-always-dark);
}

.analytics-panel__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 18px;
  border-radius: 999px;
  background: rgba(10, 10, 10, 0.05);
  color: var(--color-text-always-dark);
  font-size: 13px;
  font-weight: 700;
}

.analytics-panel__body {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.9fr);
  gap: 24px;
  min-height: 0;
  flex: 1;
}

.analytics-chart {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 380px;
  padding: 18px 18px 14px;
  border-radius: 28px;
  background: rgba(10, 10, 10, 0.02);
}

.analytics-chart__svg {
  width: 100%;
  height: 320px;
  overflow: visible;
}

.analytics-chart__grid-line {
  stroke: rgba(10, 10, 10, 0.08);
  stroke-width: 1;
  stroke-dasharray: 4 8;
}

.analytics-chart__vertical-line {
  stroke: rgba(10, 10, 10, 0.05);
  stroke-width: 1;
}

.analytics-chart__area {
  fill: rgba(170, 255, 0, 0.16);
  opacity: 0;
  animation: analytics-area-fade 0.9s ease-out 280ms forwards;
}

.analytics-chart__line {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 4;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: analytics-line-draw 1.35s cubic-bezier(0.22, 1, 0.36, 1) 120ms forwards;
}

.analytics-chart__point-group {
  opacity: 0;
  animation: analytics-point-rise 0.75s cubic-bezier(0.22, 1, 0.36, 1) var(--point-delay) forwards;
}

.analytics-chart__point-ring {
  fill: rgba(170, 255, 0, 0.22);
}

.analytics-chart__point-core {
  fill: var(--color-primary);
}

.analytics-chart__labels {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin-top: 8px;
}

.analytics-chart__label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.analytics-chart__label-top {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-always-dark);
}

.analytics-chart__label-bottom {
  font-size: 12px;
  color: var(--color-text-muted);
}

.analytics-side {
  display: grid;
  gap: 16px;
  align-content: start;
}

.analytics-side__card {
  border-radius: 24px;
  padding: 20px 20px 18px;
  background: rgba(10, 10, 10, 0.03);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.analytics-side__card--overview {
  min-height: 170px;
}

.analytics-side__label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.analytics-side__value {
  font-size: 24px;
  line-height: 1.08;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: var(--color-text-always-dark);
}

.analytics-side__copy {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
  color: var(--color-text-secondary);
}

.analytics-side__overview-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.analytics-side__overview-logo {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.analytics-side__overview-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--color-text-always-dark);
}

@keyframes analytics-line-draw {
  0% { stroke-dashoffset: 1; }
  100% { stroke-dashoffset: 0; }
}

@keyframes analytics-area-fade {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

@keyframes analytics-point-rise {
  0% {
    opacity: 0;
    transform: translateY(18px) scale(0.82);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .analytics-chart__area,
  .analytics-chart__line,
  .analytics-chart__point-group {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
</style>
