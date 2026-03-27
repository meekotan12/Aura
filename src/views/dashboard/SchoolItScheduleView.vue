<template>
  <section class="school-it-schedule">
    <div class="school-it-schedule__shell">
      <SchoolItTopHeader
        class="dashboard-enter dashboard-enter--1"
        :avatar-url="avatarUrl"
        :school-name="schoolName"
        :display-name="displayName"
        :initials="initials"
        @logout="handleLogout"
      />

      <div class="school-it-schedule__body">
        <h1 class="school-it-schedule__title dashboard-enter dashboard-enter--2">Students</h1>

        <div class="school-it-schedule__header-row dashboard-enter dashboard-enter--3">
          <div class="school-it-schedule__search-wrapper" :class="{ 'school-it-schedule__search-wrapper--hidden': isEventSettingsOpen }">
            <div class="school-it-schedule__search">
              <input v-model="searchQuery" type="text" placeholder="" class="school-it-schedule__search-input" />
              <button class="school-it-schedule__search-btn" type="button"><Search :size="18" :stroke-width="2.5" color="#bcf00e" /></button>
            </div>
          </div>

          <div
            class="school-it-schedule__settings"
            :class="{ 'school-it-schedule__settings--open': isEventSettingsOpen }"
          >
            <div class="school-it-schedule__settings-header">
              <button
                class="school-it-schedule__settings-toggle"
                type="button"
                @click="toggleEventSettings"
              >
                <Settings :size="18" :stroke-width="2.2" />
                <span class="school-it-schedule__settings-title-span">Event Settings</span>
              </button>
            </div>

            <Transition
              name="school-it-schedule-settings"
              @before-enter="onSettingsBeforeEnter"
              @enter="onSettingsEnter"
              @after-enter="onSettingsAfterEnter"
              @before-leave="onSettingsBeforeLeave"
              @leave="onSettingsLeave"
              @after-leave="onSettingsAfterLeave"
            >
              <div v-show="isEventSettingsOpen" class="school-it-schedule__settings-body">
                <div class="school-it-schedule__settings-fields">
                  <div class="school-it-schedule__settings-field">
                    <label class="school-it-schedule__settings-label">Start checking in</label>
                    <div class="school-it-schedule__settings-input-row">
                      <input v-model.number="eventSettingsForm.earlyCheckIn" type="number" step="1" @blur="saveSettings" />
                      <span>mins</span>
                    </div>
                  </div>
                  <div class="school-it-schedule__settings-field">
                    <label class="school-it-schedule__settings-label">Mark student late after</label>
                    <div class="school-it-schedule__settings-input-row">
                      <input v-model.number="eventSettingsForm.lateThreshold" type="number" step="1" @blur="saveSettings" />
                      <span>mins</span>
                    </div>
                  </div>
                  <div class="school-it-schedule__settings-field">
                    <label class="school-it-schedule__settings-label">Stop signing out</label>
                    <div class="school-it-schedule__settings-input-row">
                      <input v-model.number="eventSettingsForm.signOutGrace" type="number" step="1" @blur="saveSettings" />
                      <span>mins</span>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>
        </div>

        <div class="school-it-schedule__cards dashboard-enter dashboard-enter--4">
          <button class="school-it-schedule__card school-it-schedule__card--monitor" type="button" @click="goToMonitor">
            <h2 class="school-it-schedule__card-title">Attendance<br>Monitor</h2>
            <div class="school-it-schedule__card-action school-it-schedule__card-action--light">
              <span class="school-it-schedule__card-icon">
                <Settings :size="18" :stroke-width="2.5" color="white" />
              </span>
              <span class="school-it-schedule__card-label">Manage</span>
            </div>
          </button>

          <button class="school-it-schedule__card school-it-schedule__card--reports" type="button" @click="goToReports">
            <h2 class="school-it-schedule__reports-title">Reports</h2>
            <div class="school-it-schedule__card-action school-it-schedule__card-action--primary">
              <span class="school-it-schedule__card-icon">
                <ArrowRight :size="18" :stroke-width="2.5" color="white" />
              </span>
              <span class="school-it-schedule__card-label">Review</span>
            </div>
          </button>
        </div>

        <section class="school-it-schedule__events dashboard-enter dashboard-enter--5">
          <template v-if="eventsList.length">
            <div
              v-for="(event, index) in eventsList"
              :key="event.id"
              class="school-it-schedule__swipe"
              :class="[
                `dashboard-enter--${Math.min(index + 6, 9)}`,
                { 'school-it-schedule__swipe--open': isEventSwipeOpen(event.id) }
              ]"
            >
              <div class="school-it-schedule__swipe-actions" aria-hidden="true">
                <button
                  class="school-it-schedule__swipe-btn school-it-schedule__swipe-btn--delete"
                  type="button"
                  :disabled="isSavingEvent"
                  aria-label="Delete event"
                  @click.stop="deleteEvent(event)"
                >
                  <Trash2 :size="18" />
                </button>
                <button
                  class="school-it-schedule__swipe-btn school-it-schedule__swipe-btn--edit"
                  type="button"
                  :disabled="isSavingEvent"
                  aria-label="Edit event"
                  @click.stop="editEvent(event)"
                >
                  <Pencil :size="18" />
                </button>
              </div>

              <article
                class="school-it-schedule__event"
                :style="getEventSwipeStyle(event.id)"
                @click.capture="handleEventCardClick(event.id, $event)"
                @pointerdown="onEventPointerDown(event.id, $event)"
                @pointermove="onEventPointerMove(event.id, $event)"
                @pointerup="onEventPointerEnd(event.id, $event)"
                @pointercancel="onEventPointerCancel(event.id, $event)"
                @lostpointercapture="onEventPointerCancel(event.id, $event)"
              >
                <h2 class="school-it-schedule__event-title">{{ event.name }}</h2>
                
                <button
                  class="school-it-schedule__event-pill"
                  type="button"
                  @pointerdown.stop
                  @click.stop="openEvent(event)"
                >
                  <span class="school-it-schedule__event-pill-icon">
                    <ArrowRight :size="16" color="white" />
                  </span>
                  {{ canManageEvent(event) ? 'Manage' : 'View' }}
                </button>
              </article>
            </div>
          </template>
          <template v-else-if="!isLoadingEvents">
            <div class="school-it-schedule__empty">No event</div>
          </template>
        </section>
      </div>
    </div>
  </section>

  <EventEditorSheet
    :is-open="isEventEditorOpen"
    :event="editingEvent"
    title="Edit Event"
    description="Update this event using the live backend event fields."
    submit-label="Save Event"
    :saving="isSavingEvent"
    :error-message="eventEditorError"
    @close="closeEventEditor"
    @save="saveEventEdits"
  />
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Search, Pencil, Trash2, Settings } from 'lucide-vue-next'
import SchoolItTopHeader from '@/components/dashboard/SchoolItTopHeader.vue'
import EventEditorSheet from '@/components/events/EventEditorSheet.vue'
import { useAuth } from '@/composables/useAuth.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { useStoredAuthMeta } from '@/composables/useStoredAuthMeta.js'
import { schoolItPreviewData } from '@/data/schoolItPreview.js'
import {
  deleteEvent as deleteBackendEvent,
  getEvents,
  resolveApiBaseUrl,
  updateEvent as updateBackendEvent,
  updateSchoolBranding,
} from '@/services/backendApi.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const router = useRouter()
const {
  currentUser,
  schoolSettings,
  initializeDashboardSession,
  refreshSchoolSettings,
} = useDashboardSession()
const { logout } = useAuth()
const authMeta = useStoredAuthMeta()

const searchQuery = ref('')
const isEventSettingsOpen = ref(false)

const eventSettingsForm = ref({
  earlyCheckIn: 30,
  lateThreshold: 30,
  signOutGrace: 30,
})

const activeUser = computed(() => props.preview ? schoolItPreviewData.user : currentUser.value)
const activeSchoolSettings = computed(() => props.preview ? schoolItPreviewData.schoolSettings : schoolSettings.value)

watch(() => activeSchoolSettings.value, (settings) => {
  if (settings) {
    eventSettingsForm.value.earlyCheckIn = settings.event_default_early_check_in_minutes ?? 30
    eventSettingsForm.value.lateThreshold = settings.event_default_late_threshold_minutes ?? 30
    eventSettingsForm.value.signOutGrace = settings.event_default_sign_out_grace_minutes ?? 30
  }
}, { immediate: true })

const schoolName = computed(() => (
  activeSchoolSettings.value?.school_name
  || activeUser.value?.school_name
  || authMeta.value?.schoolName
  || 'University Name'
))

const avatarUrl = computed(() => activeUser.value?.avatar_url || '')

const displayName = computed(() => {
  const first = activeUser.value?.first_name || ''
  const middle = activeUser.value?.middle_name || ''
  const last = activeUser.value?.last_name || ''
  return [first, middle, last].filter(Boolean).join(' ')
    || [authMeta.value?.firstName, authMeta.value?.lastName].filter(Boolean).join(' ')
    || activeUser.value?.email?.split('@')[0]
    || authMeta.value?.email?.split('@')[0]
    || 'School IT'
})

const initials = computed(() => {
  const parts = String(displayName.value || '').split(' ').filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  return String(displayName.value || '').slice(0, 2).toUpperCase()
})

const eventsList = ref([])
const isLoadingEvents = ref(true)
const isSavingEvent = ref(false)
const isEventEditorOpen = ref(false)
const editingEvent = ref(null)
const eventEditorError = ref('')

const eventSwipeOffsets = ref({})
const eventSwipeDragId = ref(null)
const eventSwipePointerId = ref(null)
const eventSwipeStartX = ref(0)
const eventSwipeStartY = ref(0)
const eventSwipeStartOffset = ref(0)
const eventSwipeAxisLock = ref(null)
const eventSwipeDidDrag = ref(false)

const EVENT_SWIPE_ACTION_WIDTH = 130
const EVENT_SWIPE_OPEN_THRESHOLD = 50
const EVENT_SWIPE_GESTURE_THRESHOLD = 8

const hasOpenEventSwipe = computed(() => Object.values(eventSwipeOffsets.value).some((offset) => offset > 0))

onMounted(() => {
  initializeDashboardSession()
    .then(() => {
      if (!schoolSettings.value) {
        return refreshSchoolSettings().catch(() => null)
      }
      return null
    })
    .catch(() => null)
  fetchEvents()
  document.addEventListener('pointerdown', handleDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})

async function fetchEvents() {
  isLoadingEvents.value = true
  if (props.preview) {
    eventsList.value = [
      { id: 1, name: 'Welcome Freshmen' },
      { id: 2, name: 'Intramurals 2026' },
      { id: 3, name: 'Acquaintance Party' },
    ]
    isLoadingEvents.value = false
    return
  }
  try {
    const token = localStorage.getItem('aura_token') || ''
    eventsList.value = await getEvents(resolveApiBaseUrl(), token)
  } catch (err) {
    console.error(err)
  } finally {
    isLoadingEvents.value = false
  }
}

async function handleLogout() {
  await logout()
}

function toggleEventSettings() {
  closeAllEventSwipes()
  isEventSettingsOpen.value = !isEventSettingsOpen.value
}

async function saveSettings() {
  if (props.preview) return
  try {
    const token = localStorage.getItem('aura_token') || ''
    const payload = {
      event_default_early_check_in_minutes: Number(eventSettingsForm.value.earlyCheckIn) || 0,
      event_default_late_threshold_minutes: Number(eventSettingsForm.value.lateThreshold) || 0,
      event_default_sign_out_grace_minutes: Number(eventSettingsForm.value.signOutGrace) || 0,
    }
    await updateSchoolBranding(resolveApiBaseUrl(), token, payload)
    if (schoolSettings.value) {
      schoolSettings.value.event_default_early_check_in_minutes = payload.event_default_early_check_in_minutes
      schoolSettings.value.event_default_late_threshold_minutes = payload.event_default_late_threshold_minutes
      schoolSettings.value.event_default_sign_out_grace_minutes = payload.event_default_sign_out_grace_minutes
    }
  } catch (error) {
    console.error('Failed to save settings:', error)
  }
}

function nextFrame(callback) {
  requestAnimationFrame(() => requestAnimationFrame(callback))
}

function onSettingsBeforeEnter(element) {
  element.style.height = '0px'
  element.style.opacity = '0'
}

function onSettingsEnter(element) {
  const height = element.scrollHeight
  element.style.transition = 'height 400ms cubic-bezier(0.2, 0.8, 0.2, 1), opacity 300ms ease'
  nextFrame(() => {
    element.style.height = `${height}px`
    element.style.opacity = '1'
  })
}

function onSettingsAfterEnter(element) {
  element.style.height = 'auto'
  element.style.transition = ''
}

function onSettingsBeforeLeave(element) {
  element.style.height = `${element.scrollHeight}px`
  element.style.opacity = '1'
}

function onSettingsLeave(element) {
  element.style.transition = 'height 320ms cubic-bezier(0.4, 0, 0.2, 1), opacity 200ms ease'
  nextFrame(() => {
    element.style.height = '0px'
    element.style.opacity = '0'
  })
}

function onSettingsAfterLeave(element) {
  element.style.transition = ''
  element.style.height = ''
  element.style.opacity = ''
}

function goToMonitor() {
  if (props.preview) {
    router.push({ name: 'PreviewSchoolItAttendanceMonitor' })
  } else {
    router.push({ name: 'SchoolItAttendanceMonitor' })
  }
}

function goToReports() {
  if (props.preview) {
    router.push({ name: 'PreviewSchoolItEventReports' })
  } else {
    router.push({ name: 'SchoolItEventReports' })
  }
}

function canManageEvent(event) {
  // Allow all IT to manage for now, or match preview logic
  return true
}

function openEvent(event) {
  if (!event?.id) return
  if (props.preview) {
    router.push({
      name: 'PreviewSchoolItEventReports',
      query: { eventId: String(event.id) },
    })
  } else {
    router.push({
      name: 'SchoolItEventReports',
      query: { eventId: String(event.id) },
    })
  }
}

function editEvent(event) {
  if (!event?.id) return
  closeAllEventSwipes()
  editingEvent.value = { ...event }
  eventEditorError.value = ''
  isEventEditorOpen.value = true
}

async function deleteEvent(event) {
  if (!event?.id || isSavingEvent.value) return
  const eventName = getEventDisplayName(event)
  const confirmed = window.confirm(`Delete ${eventName}?`)
  if (!confirmed) return
  
  isSavingEvent.value = true
  closeAllEventSwipes()

  try {
    if (!props.preview) {
      const token = localStorage.getItem('aura_token') || ''
      await deleteBackendEvent(resolveApiBaseUrl(), token, event.id)
    }

    eventsList.value = eventsList.value.filter((entry) => entry.id !== event.id)
    if (Number(editingEvent.value?.id) === Number(event.id)) {
      closeEventEditor(true)
    }
  } catch (error) {
    window.alert(error?.message || 'Failed to delete event.')
  } finally {
    isSavingEvent.value = false
  }
}

function closeEventEditor(force = false) {
  if (!force && isSavingEvent.value) return
  isEventEditorOpen.value = false
  editingEvent.value = null
  eventEditorError.value = ''
}

function getEventDisplayName(event) {
  return String(event?.name || event?.title || 'this event').trim()
}

function replaceEventInList(nextEvent) {
  const normalizedId = Number(nextEvent?.id)
  if (!Number.isFinite(normalizedId)) return
  const nextEntries = eventsList.value.map((entry) =>
    Number(entry?.id) === normalizedId ? { ...entry, ...nextEvent } : entry
  )
  eventsList.value = nextEntries
}

async function saveEventEdits(payload) {
  if (!editingEvent.value?.id || isSavingEvent.value) return

  isSavingEvent.value = true
  eventEditorError.value = ''

  try {
    if (props.preview) {
      replaceEventInList({
        ...editingEvent.value,
        ...payload,
      })
    } else {
      const token = localStorage.getItem('aura_token') || ''
      const updatedEvent = await updateBackendEvent(
        resolveApiBaseUrl(),
        token,
        editingEvent.value.id,
        payload
      )
      replaceEventInList(updatedEvent)
    }

    closeEventEditor(true)
  } catch (error) {
    eventEditorError.value = error?.message || 'Unable to save the event changes.'
  } finally {
    isSavingEvent.value = false
  }
}

function getEventSwipeOffset(eventId) { return Number(eventSwipeOffsets.value[eventId] || 0) }

function isEventSwipeOpen(eventId) { return getEventSwipeOffset(eventId) > 0 }

function getEventSwipeStyle(eventId) { return { '--event-swipe-offset': `-${getEventSwipeOffset(eventId)}px` } }

function setEventSwipeOffset(eventId, offset) {
  const normalizedOffset = Math.max(0, Math.min(EVENT_SWIPE_ACTION_WIDTH, Number(offset) || 0))
  if (normalizedOffset === 0) {
    if (!Object.keys(eventSwipeOffsets.value).length) return
    eventSwipeOffsets.value = {}
    return
  }
  eventSwipeOffsets.value = { [eventId]: normalizedOffset }
}

function closeAllEventSwipes() {
  if (!hasOpenEventSwipe.value) return
  eventSwipeOffsets.value = {}
}

function handleDocumentPointerDown(event) {
  if (!hasOpenEventSwipe.value) return
  if (event.target.closest('.school-it-schedule__swipe')) return
  closeAllEventSwipes()
}

function handleEventCardClick(eventId, event) {
  if (eventSwipeDidDrag.value) {
    event.stopPropagation()
    eventSwipeDidDrag.value = false
    return
  }
  if (!isEventSwipeOpen(eventId)) return
  event.stopPropagation()
  setEventSwipeOffset(eventId, 0)
}

function onEventPointerDown(eventId, event) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  event.currentTarget.setPointerCapture(event.pointerId)
  eventSwipeDragId.value = eventId
  eventSwipePointerId.value = event.pointerId
  eventSwipeStartX.value = event.clientX
  eventSwipeStartY.value = event.clientY
  eventSwipeStartOffset.value = getEventSwipeOffset(eventId)
  eventSwipeAxisLock.value = null
  eventSwipeDidDrag.value = false
}

function onEventPointerMove(eventId, event) {
  if (eventSwipeDragId.value !== eventId || eventSwipePointerId.value !== event.pointerId) return
  const deltaX = event.clientX - eventSwipeStartX.value
  const deltaY = event.clientY - eventSwipeStartY.value
  if (!eventSwipeAxisLock.value) {
    if (Math.abs(deltaX) > EVENT_SWIPE_GESTURE_THRESHOLD || Math.abs(deltaY) > EVENT_SWIPE_GESTURE_THRESHOLD) {
      eventSwipeAxisLock.value = Math.abs(deltaX) > Math.abs(deltaY) ? 'horizontal' : 'vertical'
    }
  }
  if (eventSwipeAxisLock.value === 'horizontal') {
    eventSwipeDidDrag.value = true
    setEventSwipeOffset(eventId, eventSwipeStartOffset.value - deltaX)
  }
}

function onEventPointerEnd(eventId, event) {
  if (eventSwipeDragId.value !== eventId || eventSwipePointerId.value !== event.pointerId) return
  eventSwipeDragId.value = null
  eventSwipePointerId.value = null
  if (eventSwipeAxisLock.value === 'horizontal' && eventSwipeDidDrag.value) {
    const currentOffset = getEventSwipeOffset(eventId)
    const isOpening = currentOffset > eventSwipeStartOffset.value
    if (isOpening && currentOffset > EVENT_SWIPE_OPEN_THRESHOLD) {
      setEventSwipeOffset(eventId, EVENT_SWIPE_ACTION_WIDTH)
    } else if (!isOpening && currentOffset < EVENT_SWIPE_ACTION_WIDTH - EVENT_SWIPE_OPEN_THRESHOLD) {
      setEventSwipeOffset(eventId, 0)
    } else {
      setEventSwipeOffset(eventId, isOpening ? EVENT_SWIPE_ACTION_WIDTH : 0)
    }
  }
  eventSwipeAxisLock.value = null
}

function onEventPointerCancel(eventId, event) {
  if (eventSwipeDragId.value !== eventId || eventSwipePointerId.value !== event.pointerId) return
  eventSwipeDragId.value = null
  eventSwipePointerId.value = null
  if (eventSwipeStartOffset.value > 0) {
    setEventSwipeOffset(eventId, EVENT_SWIPE_ACTION_WIDTH)
  } else {
    setEventSwipeOffset(eventId, 0)
  }
  eventSwipeAxisLock.value = null
}
</script>

<style scoped>
.school-it-schedule {
  min-height: 100vh;
  padding: 30px 28px 120px;
  font-family: 'Manrope', sans-serif;
  background: var(--color-bg, #f3f4f6);
}

.school-it-schedule__shell {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
}

.school-it-schedule__body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 28px;
}

.school-it-schedule__title {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--color-text-always-dark, #111827);
}

.school-it-schedule__header-row {
  display: flex;
  gap: 16px;
  width: 100%;
  align-items: flex-start;
}

.school-it-schedule__search-wrapper {
  flex: 1;
  max-width: 100%;
  height: 64px;
  overflow: hidden;
  transition: max-width 0.4s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.3s ease, margin 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.school-it-schedule__search-wrapper--hidden {
  max-width: 0px;
  opacity: 0;
  margin-right: -16px;
}

.school-it-schedule__search {
  display: flex;
  align-items: center;
  width: 100%;
  height: 64px;
  border-radius: 999px;
  background: #ffffff;
  padding: 0 8px 0 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
}

.school-it-schedule__search-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  font-size: 16px;
  color: #111827;
  background: transparent;
}

.school-it-schedule__search-input::placeholder {
  color: #9cb3c9;
}

.school-it-schedule__search-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: transparent;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
}

.school-it-schedule__settings {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-primary, #bcf00e);
  border-radius: 999px;
  transition: all 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.school-it-schedule__settings--open {
  flex-grow: 1;
  border-radius: 42px;
}

.school-it-schedule__settings-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  height: 64px;
  padding: 0 24px;
}

.school-it-schedule__settings-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 100%;
  border: none;
  background: transparent;
  color: #111827;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
}

.school-it-schedule__settings-body {
  padding: 0 28px 28px;
}

.school-it-schedule__settings-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.school-it-schedule__settings-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.school-it-schedule__settings-label {
  font-size: 13px;
  font-weight: 500;
  color: #111827;
  padding-left: 8px;
}

.school-it-schedule__settings-input-row {
  display: flex;
  align-items: center;
  height: 48px;
  background: #ffffff;
  border-radius: 999px;
  padding: 0 20px;
}

.school-it-schedule__settings-input-row input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  font-size: 14px;
  color: #111827;
  background: transparent;
}

.school-it-schedule__settings-input-row span {
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
}

.school-it-schedule__cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  width: 100%;
}

.school-it-schedule__card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  text-align: left;
  min-height: 174px;
  padding: 24px 20px;
  border: none;
  border-radius: 36px;
  cursor: pointer;
  transition: transform 0.2s ease, filter 0.2s ease;
}

.school-it-schedule__card:active {
  transform: scale(0.97);
}

.school-it-schedule__card--monitor {
  background: var(--color-primary, #bcf00e);
}

.school-it-schedule__card--monitor:hover {
  filter: brightness(1.04);
}

.school-it-schedule__card--reports {
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.03);
}

.school-it-schedule__card--reports:hover {
  filter: brightness(0.98);
}

.school-it-schedule__card-title,
.school-it-schedule__reports-title {
  margin: 0;
  font-size: 21px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: #111827;
}

.school-it-schedule__card-action {
  display: inline-flex;
  align-items: center;
  gap: 16px;
  width: fit-content;
  min-height: 48px;
  padding: 0 24px 0 6px;
  border-radius: 999px;
  margin-top: 24px;
}

.school-it-schedule__card-action--light {
  background: #ffffff;
}

.school-it-schedule__card-action--primary {
  background: var(--color-primary, #bcf00e);
}

.school-it-schedule__card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: #000000;
  flex-shrink: 0;
}

.school-it-schedule__card-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #111827;
}

.school-it-schedule__events {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 12px;
}

.school-it-schedule__empty {
  font-size: 16px;
  font-weight: 600;
  color: #6b7280;
  text-align: center;
  padding: 40px 0;
}

.school-it-schedule__swipe {
  position: relative;
  width: 100%;
}

.school-it-schedule__swipe-actions {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: 20px;
  z-index: 1;
}

.school-it-schedule__swipe-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 84px;
  border-radius: 28px;
  background: #f3f4f6;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.school-it-schedule__swipe-btn:active {
  transform: scale(0.92);
}

.school-it-schedule__swipe-btn--delete {
  border: 1px solid #ef4444;
  color: #ef4444;
  background: #fef2f2;
}

.school-it-schedule__swipe-btn--edit {
  border: 1px solid #e5e7eb;
  color: #111827;
  background: #ffffff;
}

.school-it-schedule__event {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  height: 84px;
  padding: 0 16px 0 24px;
  background: #ffffff;
  border-radius: 28px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  transform: translateX(var(--event-swipe-offset, 0px));
  transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
  touch-action: pan-y;
  cursor: pointer;
}

.school-it-schedule__swipe--open .school-it-schedule__event {
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.school-it-schedule__event-title {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
  color: var(--color-primary, #bcf00e);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 16px;
}

.school-it-schedule__event-pill {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  height: 48px;
  padding: 0 20px 0 6px;
  background: var(--color-primary, #bcf00e);
  border-radius: 999px;
  border: none;
  font-size: 11px;
  font-weight: 700;
  color: #111827;
  flex-shrink: 0;
}

.school-it-schedule__event-pill-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #000000;
}

@media (min-width: 768px) {
  .school-it-schedule {
    padding: 40px 36px 56px;
  }
}
</style>
