<template>
  <div 
    class="event-card group" 
    :class="cardClasses"
    role="button"
    tabindex="0"
    @click="emitOpenDetail"
    @keydown.enter.prevent="emitOpenDetail"
    @keydown.space.prevent="emitOpenDetail"
  >
    <!-- Top Right Status -->
    <div class="event-card__status">
      <span class="status-text">{{ statusText }}</span>
      <span class="status-dot" :class="statusDotClass"></span>
    </div>

    <!-- Content -->
    <div class="event-card__content">
      <p class="event-desc">{{ eventMeta }}</p>
      <h3 class="event-title">{{ props.event.name }}</h3>
    </div>

    <!-- Action Button -->
    <div class="event-action-row">
      <button class="event-action" :class="actionBtnClass" type="button" :disabled="isActionDisabled" @click.stop="emitClick">
        <div class="action-icon">
          <ArrowRight :size="16" />
        </div>
        <span class="action-text">{{ actionText }}</span>
      </button>

      <button
        class="attendance-toggle"
        :class="{
          'attendance-toggle--open': isAttendanceOpen,
          'attendance-toggle--present': attendanceAppearance.tone === 'present',
          'attendance-toggle--absent': attendanceAppearance.tone === 'absent',
          'attendance-toggle--late': attendanceAppearance.tone === 'late',
          'attendance-toggle--neutral': attendanceAppearance.tone === 'neutral',
          'attendance-toggle--unmarked': attendanceAppearance.isUnmarked,
          'attendance-toggle--desktop-pill': !isMobile,
          'attendance-toggle--desktop-icon': !isMobile && attendanceAppearance.isUnmarked,
          'attendance-toggle--revealed': !isMobile && (isAttendanceHovered || isAttendanceOpen),
        }"
        type="button"
        :aria-label="attendanceAppearance.label"
        :title="attendanceAppearance.label"
        @mouseenter="isAttendanceHovered = true"
        @mouseleave="isAttendanceHovered = false"
        @focus="isAttendanceHovered = true"
        @blur="isAttendanceHovered = false"
        @click.stop="handleAttendanceToggle"
      >
        <span class="attendance-toggle__icon">
          <component :is="attendanceAppearance.icon" :size="18" />
        </span>
        <span v-if="showDesktopAttendanceText || !isMobile" class="attendance-toggle__text">
          {{ attendanceAppearance.label }}
        </span>
      </button>
    </div>

    <!-- Collapsible Attendance Status (mobile only) -->
    <div
      class="attendance-panel"
      :class="{ 'attendance-panel--open': isAttendanceOpen && isMobile }"
    >
      <div class="attendance-panel__inner">
        <div class="attendance-status-card" :class="attendanceAppearance.cardClass">
          <span class="attendance-status-card__icon">
            <component :is="attendanceAppearance.icon" :size="18" />
          </span>
          <div class="attendance-status-card__content">
            <span class="attendance-status-card__label">{{ attendanceAppearance.label }}</span>
            <span class="attendance-status-card__meta">{{ attendanceAppearance.meta }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { ArrowRight, Check, Clock3, Minus, X } from 'lucide-vue-next'
import {
  formatCompactDuration,
  hasSignedInAttendance,
  hasSignedOutAttendance,
  resolveAttendanceDisplayStatus,
  resolveEventTimeStatusMoment,
  resolveEventLifecycleStatus,
  resolveAttendanceActionState,
  resolveSignOutOpenDate,
} from '@/services/attendanceFlow.js'

const props = defineProps({
  event: {
    type: Object,
    required: true,
  },
  isAttended: {
    type: Boolean,
    default: false,
  },
  attendanceRecord: {
    type: Object,
    default: null,
  },
  eventTimeStatus: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['click', 'open-detail'])

// ── Derived State ───────────────────────────────────────────────────

const STATUS_CONFIG = {
  ongoing: {
    label: 'On Going',
    dotClass: 'dot--red',
    cardClass: 'event-card--lime',
    actionText: 'Attendance Now',
    actionBtnClass: 'action-btn--white',
  },
  upcoming: {
    label: 'Upcoming',
    dotClass: 'dot--yellow',
    cardClass: 'event-card--white',
    actionText: 'View Event',
    actionBtnClass: 'action-btn--lime',
  },
  completed: {
    label: 'Done',
    dotClass: 'dot--green',
    cardClass: 'event-card--white',
    actionText: 'View Event',
    actionBtnClass: 'action-btn--lime',
  },
  cancelled: {
    label: 'Cancelled',
    dotClass: 'dot--gray',
    cardClass: 'event-card--white',
    actionText: 'View Event',
    actionBtnClass: 'action-btn--lime',
  },
}

const normalizedStatus = computed(() => {
  return resolveEventLifecycleStatus(props.event, props.eventTimeStatus) || 'upcoming'
})

const statusConfig = computed(() => STATUS_CONFIG[normalizedStatus.value] ?? STATUS_CONFIG.upcoming)
const actionState = computed(() => resolveAttendanceActionState({
  event: props.event,
  eventStatus: normalizedStatus.value,
  attendanceRecord: props.attendanceRecord,
  timeStatus: props.eventTimeStatus,
  now: new Date(effectiveNowMs.value),
}))
const opensAttendanceFlow = computed(() => ['sign-in', 'sign-out'].includes(actionState.value))
const isWaitingSignOut = computed(() => actionState.value === 'waiting-sign-out')
const isSignOutReady = computed(() => actionState.value === 'sign-out')
const isActionDisabled = computed(() => isWaitingSignOut.value)

const statusText = computed(() => statusConfig.value.label)
const actionText = computed(() => {
  if (isWaitingSignOut.value) {
    return 'Waiting for Sign Out'
  }
  if (isSignOutReady.value) {
    return 'Sign Out'
  }
  if (actionState.value === 'sign-in') {
    return 'Attendance Now'
  }
  return 'View Event'
})
const cardClasses = computed(() => statusConfig.value.cardClass)
const statusDotClass = computed(() => statusConfig.value.dotClass)
const actionBtnClass = computed(() => {
  if (!opensAttendanceFlow.value || isWaitingSignOut.value || isSignOutReady.value) {
    return 'action-btn--white'
  }
  return statusConfig.value.actionBtnClass
})

const eventMeta = computed(() => props.event.location ?? '')

const isOngoing = computed(() => normalizedStatus.value === 'ongoing')
const normalizedAttendanceStatus = computed(() => {
  const raw = resolveAttendanceDisplayStatus(props.attendanceRecord)
  return raw || null
})
const hasSignedIn = computed(() => hasSignedInAttendance(props.attendanceRecord))
const hasSignedOut = computed(() => hasSignedOutAttendance(props.attendanceRecord))

const attendanceAppearance = computed(() => {
  const sharedMeta = isOngoing.value
    ? 'Tap to see your attendance state for this event.'
    : 'Attendance state loaded from your backend record.'

  if (hasSignedIn.value && !hasSignedOut.value) {
    return {
      label:
        actionState.value === 'closed'
          ? 'Attendance Closed'
          : isSignOutReady.value
            ? 'Ready for Sign Out'
            : 'Waiting for Sign Out',
      icon: Clock3,
      tone: 'neutral',
      cardClass: 'attendance-status-card--neutral',
      meta:
        actionState.value === 'closed'
          ? 'The sign-out window is already closed for this event.'
          : isSignOutReady.value
            ? 'The backend sign-out window is open for this event.'
            : waitingSignOutCountdown.value
              ? `Your sign-in is saved. Sign-out opens in ${waitingSignOutCountdown.value}.`
              : 'Your sign-in is saved. Waiting for the backend sign-out window.',
      isUnmarked: false,
    }
  }

  if (normalizedAttendanceStatus.value === 'present') {
    return {
      label: 'Present',
      icon: Check,
      tone: 'present',
      cardClass: 'attendance-status-card--present',
      meta: sharedMeta,
      isUnmarked: false,
    }
  }

  if (normalizedAttendanceStatus.value === 'absent') {
    return {
      label: 'Absent',
      icon: X,
      tone: 'absent',
      cardClass: 'attendance-status-card--absent',
      meta: sharedMeta,
      isUnmarked: false,
    }
  }

  if (normalizedAttendanceStatus.value === 'late') {
    return {
      label: 'Late',
      icon: Clock3,
      tone: 'late',
      cardClass: 'attendance-status-card--late',
      meta: sharedMeta,
      isUnmarked: false,
    }
  }

  return {
    label: 'Unmarked',
    icon: Minus,
    tone: 'neutral',
    cardClass: 'attendance-status-card--neutral',
    meta: 'No attendance status has been returned by the API for this event yet.',
    isUnmarked: true,
  }
})

const showDesktopAttendanceText = computed(() => !isMobile.value && !attendanceAppearance.value.isUnmarked)

const isMobile = ref(false)
const isAttendanceOpen = ref(false)
const isAttendanceHovered = ref(false)
const countdownTickMs = ref(Date.now())
const timeStatusObservedAtMs = ref(Date.now())
let countdownIntervalId = null

const timeStatusCurrentTimeMs = computed(() => {
  const parsed = resolveEventTimeStatusMoment(props.eventTimeStatus?.current_time)
  return parsed ? parsed.getTime() : null
})

const effectiveNowMs = computed(() => {
  if (Number.isFinite(timeStatusCurrentTimeMs.value)) {
    return timeStatusCurrentTimeMs.value + Math.max(0, countdownTickMs.value - timeStatusObservedAtMs.value)
  }
  return countdownTickMs.value
})

const signOutOpenAtMs = computed(() => {
  const signOutOpenAt = resolveSignOutOpenDate(props.event, props.eventTimeStatus)
  return signOutOpenAt ? signOutOpenAt.getTime() : null
})

const waitingSignOutCountdown = computed(() => {
  if (!isWaitingSignOut.value || !Number.isFinite(signOutOpenAtMs.value)) {
    return ''
  }

  const diffMs = signOutOpenAtMs.value - effectiveNowMs.value
  if (!Number.isFinite(diffMs) || diffMs <= 0) {
    return 'less than 1 min'
  }

  return formatCompactDuration(diffMs)
})

function stopCountdownTimer() {
  if (countdownIntervalId != null) {
    clearInterval(countdownIntervalId)
    countdownIntervalId = null
  }
}

function startCountdownTimer() {
  stopCountdownTimer()
  countdownTickMs.value = Date.now()
  countdownIntervalId = window.setInterval(() => {
    countdownTickMs.value = Date.now()
  }, 30_000)
}

function updateMedia() {
  isMobile.value = window.matchMedia('(max-width: 767px)').matches
}

function handleAttendanceToggle() {
  if (!isMobile.value && !attendanceAppearance.value.isUnmarked) return
  isAttendanceOpen.value = !isAttendanceOpen.value
}

function emitOpenDetail() {
  emit('open-detail', props.event)
}

function emitClick() {
  if (isActionDisabled.value) {
    return
  }
  if (!opensAttendanceFlow.value) {
    emitOpenDetail()
    return
  }
  emit('click', props.event)
}

onMounted(() => {
  updateMedia()
  window.addEventListener('resize', updateMedia)
})

onUnmounted(() => {
  stopCountdownTimer()
  window.removeEventListener('resize', updateMedia)
})

watch(isMobile, (next) => {
  if (!next) {
    isAttendanceOpen.value = false
  }
})

watch(
  () => props.eventTimeStatus,
  () => {
    timeStatusObservedAtMs.value = Date.now()
    countdownTickMs.value = Date.now()
  },
  { immediate: true, deep: true }
)

watch(
  isWaitingSignOut,
  (waiting) => {
    if (waiting) {
      startCountdownTimer()
      return
    }
    stopCountdownTimer()
  },
  { immediate: true }
)
</script>

<style scoped>
.event-card {
  position: relative;
  width: 100%;
  border-radius: 32px;
  padding: 28px 24px 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 200px;
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
  overflow: hidden;
  cursor: pointer;
}

.event-card:active {
  transform: scale(0.98);
}

.event-card:focus-visible {
  outline: 3px solid rgba(255, 255, 255, 0.7);
  outline-offset: 3px;
}

/* ── Card Color Variants ── */
.event-card--lime {
  background: var(--color-primary); /* #AAFF00 normally */
  color: var(--color-banner-text);
}

.event-card--white {
  background: var(--color-surface);
  color: var(--color-surface-text);
}

/* ── Top Status ── */
.event-card__status {
  position: absolute;
  top: 18px;
  right: 22px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-text {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: -0.2px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot--red { background: #FF2B2B; }
.dot--yellow { background: #FFDD00; }
.dot--green { background: #00E676; }
.dot--gray { background: #ccc; }

/* ── Main Content ── */
.event-card__content {
  margin-top: 18px;
  margin-bottom: 18px;
}

.event-desc {
  font-size: 12px;
  font-weight: 600;
  opacity: 0.75;
  margin-bottom: 6px;
  /* Keep to a single line like the reference */
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.event-title {
  font-size: 26px;
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.6px;
}

/* ── Action Pill Button ── */
.event-action {
  align-self: flex-start;
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 999px;
  padding: 6px 18px 6px 6px;
  border: none;
  cursor: pointer;
  width: fit-content;
  transition: transform 0.15s ease;
}

.event-action:disabled {
  cursor: default;
  opacity: 0.72;
}

.event-action-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.event-action:active {
  transform: scale(0.95);
}

.event-action:disabled:active {
  transform: none;
}

.action-btn--white { background: var(--color-surface); }
.action-btn--lime { background: var(--color-primary); }

.action-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--color-nav);
  color: var(--color-nav-text);
  border-radius: 50%;
}

.action-text {
  font-size: 10px;
  font-weight: 600;
}

.action-btn--white .action-text {
  color: var(--color-surface-text);
}

.action-btn--lime .action-text {
  color: var(--color-banner-text);
}

.attendance-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  max-width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid var(--color-surface-border);
  background: var(--color-surface);
  color: var(--color-surface-text);
  cursor: pointer;
  transition:
    transform 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    background-color 0.26s ease,
    color 0.26s ease,
    max-width 0.42s cubic-bezier(0.22, 1, 0.36, 1),
    padding 0.42s cubic-bezier(0.22, 1, 0.36, 1),
    gap 0.42s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.26s ease;
  will-change: transform;
  position: relative;
  overflow: hidden;
}

.attendance-toggle__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.attendance-toggle__text {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.02em;
  max-width: 0;
  opacity: 0;
  overflow: hidden;
  white-space: nowrap;
  transform: translateX(-8px);
  transition:
    max-width 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.24s ease,
    transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.attendance-toggle--desktop-pill {
  min-width: 44px;
  border-radius: 999px;
  padding: 0;
  justify-content: flex-start;
  gap: 0;
}

.attendance-toggle--desktop-icon {
  width: 44px;
  min-width: 44px;
  padding: 0;
  justify-content: center;
}

.attendance-toggle--desktop-pill .attendance-toggle__icon,
.attendance-toggle--desktop-icon .attendance-toggle__icon {
  width: 44px;
  min-width: 44px;
  height: 44px;
}

.attendance-toggle--revealed {
  max-width: 168px;
  min-width: 168px;
  padding-right: 18px;
  gap: 12px;
}

.attendance-toggle--revealed .attendance-toggle__text {
  max-width: 104px;
  opacity: 1;
  transform: translateX(0);
}

.attendance-toggle--open {
  transform: scale(0.96);
}

.attendance-toggle--present {
  color: #9dce00;
}

.attendance-toggle--absent {
  color: #ff3b30;
}

.attendance-toggle--late {
  color: #ff9f0a;
}

.attendance-toggle--neutral {
  color: #6b7280;
}

.attendance-panel {
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  transform: translateY(-4px);
  margin-top: 0;
  transition:
    grid-template-rows 0.38s cubic-bezier(0.16, 1, 0.3, 1),
    opacity 0.2s ease,
    transform 0.2s ease,
    margin-top 0.2s ease;
  will-change: opacity, transform;
  width: 100%;
}

.attendance-panel--open {
  grid-template-rows: 1fr;
  opacity: 1;
  transform: translateY(0);
  margin-top: 12px;
}

.attendance-panel__inner {
  min-height: 0;
  overflow: hidden;
}

.attendance-status-card {
  border-radius: 22px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: color-mix(in srgb, var(--color-surface) 92%, transparent);
  border: 1px solid var(--color-surface-border);
}

.attendance-status-card__icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-surface-text) 8%, transparent);
  flex: 0 0 auto;
}

.attendance-status-card__content {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.attendance-status-card__label {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-surface-text);
}

.attendance-status-card__meta {
  font-size: 11px;
  line-height: 1.35;
  color: var(--color-surface-text-muted);
  margin-top: 2px;
}

.attendance-status-card--present .attendance-status-card__icon {
  color: #9dce00;
}

.attendance-status-card--absent .attendance-status-card__icon {
  color: #ff3b30;
}

.attendance-status-card--late .attendance-status-card__icon {
  color: #ff9f0a;
}

.attendance-status-card--neutral .attendance-status-card__icon {
  color: #6b7280;
}

@media (min-width: 768px) {
  .attendance-panel {
    display: none;
  }
}

@media (max-width: 767px) {
  .attendance-toggle {
    flex: 0 0 auto;
    max-width: none;
  }

  .attendance-toggle__text {
    max-width: none;
    opacity: 1;
    transform: none;
  }
}
</style>
