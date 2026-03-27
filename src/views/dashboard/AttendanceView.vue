<template>
  <div class="attendance-page">
    <div class="attendance-shell">
      <template v-if="event">
        <div
          ref="stepTrackEl"
          class="step-track dashboard-enter dashboard-enter--1"
          role="progressbar"
          aria-label="Attendance progress"
          :aria-valuenow="progressValue"
          aria-valuemin="0"
          aria-valuemax="100"
          :class="{ 'step-track--bounce': trackBounce }"
        >
          <div class="step-track-progress" :style="{ width: `${trackFillPx}px` }"></div>

          <div class="step-node" :class="stepNodeClass(0)" :ref="(el) => setStepNode(el, 0)">
            <component :is="stepNodeIcon(0)" :size="16" />
          </div>
          <div class="step-node" :class="stepNodeClass(1)" :ref="(el) => setStepNode(el, 1)">
            <component :is="stepNodeIcon(1)" :size="16" />
          </div>
          <div class="step-node" :class="stepNodeClass(2)" :ref="(el) => setStepNode(el, 2)">
            <component :is="stepNodeIcon(2)" :size="16" />
          </div>

          <ChevronsRight v-if="flowStep === 'face'" class="step-scan-arrow" :size="15" />
        </div>

        <FaceScanPanel
          v-if="flowStep === 'face'"
          class="dashboard-enter dashboard-enter--2"
          :progress="faceScanProgress"
          :is-camera-ready="isCameraReady"
          :face-image-url="faceImageUrl"
          :show-error="showFaceError"
          :video-ref="setVideoEl"
          @retry="retryFaceScan"
        />

        <section v-else-if="flowStep === 'location'" class="step-section step-section--location dashboard-enter dashboard-enter--2">
          <p class="step-caption">{{ locationMessage }}</p>

          <div class="location-map">
            <iframe
              v-if="mapUrl"
              :key="mapUrl"
              class="location-map-frame"
              :src="mapUrl"
              loading="lazy"
              referrerpolicy="no-referrer-when-downgrade"
              aria-label="Your current location map"
            />
            <div v-else class="location-map-fallback" aria-label="Map not available">
              <div class="map-grid"></div>
            </div>

            <div class="location-card">
              <div class="location-card-left">
                <span class="location-card-label">Your</span>
                <span class="location-card-title">Location</span>
              </div>

              <div class="location-card-coords">
                <div class="coord-group">
                  <span class="coord-label">Latitude</span>
                  <span class="coord-value">{{ latitudeText }}</span>
                </div>
                <div class="coord-group">
                  <span class="coord-label">Longitude</span>
                  <span class="coord-value">{{ longitudeText }}</span>
                </div>
              </div>

              <button
                class="location-card-action"
                type="button"
                aria-label="Open location in Google Maps"
                :disabled="!mapDestination"
                @click="openInMaps"
              >
                <ArrowUpRight :size="15" />
              </button>
            </div>
          </div>

          <p
            v-if="showLocationError || locationDetailText"
            class="location-hint"
            :class="{ 'location-hint--ok': !showLocationError && Boolean(locationDetailText) }"
          >
            {{ showLocationError ? locationErrorText : locationDetailText }}
          </p>

          <div v-if="showLocationError" class="location-error-block">
            <button class="location-retry-btn" type="button" @click="retryLocationCheck">
              Try Again
            </button>
          </div>

          <button
            v-else
            class="location-next-btn"
            type="button"
            :disabled="locationStatus !== 'ok'"
            @click="goToSuccess"
          >
            Next
          </button>
        </section>

        <section v-else class="step-section step-section--success dashboard-enter dashboard-enter--3">
          <p class="success-caption">{{ successMessage }}</p>
          <p v-if="successDetailMessage" class="success-detail">{{ successDetailMessage }}</p>
          <button class="success-btn" type="button" @click="goBack">
            <span class="success-btn-icon">
              <ArrowRight :size="16" />
            </span>
            <span class="success-btn-text">Go Back</span>
          </button>
        </section>
      </template>

      <section v-else class="step-section step-section--success dashboard-enter dashboard-enter--2">
        <p class="success-caption">Event not found.</p>
        <button class="success-btn" type="button" @click="goBack">
          <span class="success-btn-icon">
            <ArrowRight :size="16" />
          </span>
          <span class="success-btn-text">Go Back</span>
        </button>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ScanFace,
  ShieldCheck,
  Zap,
  Check,
  ChevronsRight,
  ArrowUpRight,
  ArrowRight,
} from 'lucide-vue-next'
import FaceScanPanel from '@/components/attendance/FaceScanPanel.vue'
import { initFaceScanDetector, resetFaceScanDetector } from '@/composables/useFaceScanDetector.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import {
  buildAttendanceLocationErrorMessage,
  formatCompactDuration,
  getMillisecondsUntilSignOutOpen,
  hasSignedInAttendance,
  hasSignedOutAttendance,
  isOpenAttendanceRecord,
  resolveAttendanceCompletionState,
  resolveAttendanceActionState,
} from '@/services/attendanceFlow.js'
import { getCurrentPositionWithinAccuracyOrThrow } from '@/services/devicePermissions.js'
import {
  getEventTimeStatus,
  recordFaceScanAttendance as postFaceScanAttendance,
  resolveApiBaseUrl,
  verifyEventLocation,
} from '@/services/backendApi.js'
import { hasNavigableHistory, resolveBackFallbackLocation } from '@/services/routeWorkspace.js'

const route = useRoute()
const router = useRouter()
const {
  currentUser,
  ensureDashboardEvent,
  getDashboardEventById,
  getLatestAttendanceForEvent,
  refreshAttendanceRecords,
  upsertAttendanceRecordSnapshot,
} = useDashboardSession()

const eventId = computed(() => Number(route.params.id))
const event = computed(() => getDashboardEventById(eventId.value))
const latestAttendanceRecord = computed(() => getLatestAttendanceForEvent(eventId.value))

const flowStep = ref('face')
const isRunning = ref(false)
const userCoords = ref(null)
const locationCheck = ref(null)
const successReason = ref('recorded')
const eventTimeStatus = ref(null)
const locationMessage = ref('Checking event location...')
const stepTrackEl = ref(null)
const stepNodeEls = ref([null, null, null])
const trackWidthPx = ref(0)
const trackCenters = ref({ left: 0, middle: 0, right: 0 })
const locationStatus = ref('idle')
const locationError = ref('')
const recordingFailed = ref(false)
const videoEl = ref(null)
const capturedFaceDataUrl = ref('')
const mediaStream = ref(null)
const cameraState = ref('idle')
const videoReady = ref(false)
const faceDetected = ref(false)
const faceScanError = ref(false)
const faceScanProgress = ref(0)
let faceDetectRaf = null
let faceProgressRaf = null
let retryResolve = null
let cameraStartPromise = null
let faceDetectorInstance = null
let locationRetryResolve = null
const faceScanTimeoutMs = Number(import.meta.env.VITE_FACE_SCAN_TIMEOUT_MS ?? 3000)
const faceScanProgressMax = Number(import.meta.env.VITE_FACE_SCAN_PROGRESS_MAX ?? 82)
const faceScanProgressDuration = Number(
  import.meta.env.VITE_FACE_SCAN_PROGRESS_DURATION_MS ?? Math.round(faceScanTimeoutMs * 0.6)
)
const faceDetectMinFrames = Number(import.meta.env.VITE_FACE_SCAN_MIN_FRAMES ?? 1)
const faceDetectHoldMs = Number(import.meta.env.VITE_FACE_SCAN_DETECT_HOLD_MS ?? 700)
const faceScanVideoReadyTimeoutMs = Number(
  import.meta.env.VITE_FACE_SCAN_VIDEO_READY_TIMEOUT_MS ?? faceScanTimeoutMs
)
const faceScanGateEnabled = import.meta.env.VITE_FACE_SCAN_GATE !== 'false'
const faceDetectorWasmBaseUrl =
  import.meta.env.VITE_FACE_DETECTOR_WASM_URL ||
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
const faceDetectorModelUrl =
  import.meta.env.VITE_FACE_DETECTOR_MODEL_URL ||
  'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite'
const faceDetectorMinConfidence = Number(import.meta.env.VITE_FACE_DETECTOR_MIN_CONFIDENCE ?? 0.5)
const faceDetectorSuppression = Number(import.meta.env.VITE_FACE_DETECTOR_SUPPRESSION ?? 0.3)
const faceDetectorIntervalMs = Number(import.meta.env.VITE_FACE_DETECTOR_INTERVAL_MS ?? 120)
const geolocationTimeoutMs = Number(import.meta.env.VITE_GEOLOCATION_TIMEOUT_MS ?? 6000)
const geolocationMaxAgeMs = Number(import.meta.env.VITE_GEOLOCATION_MAX_AGE_MS ?? 0)
const geolocationHighAccuracy = import.meta.env.VITE_GEOLOCATION_HIGH_ACCURACY !== 'false'

const steps = [
  { key: 'face', icon: ScanFace },
  { key: 'location', icon: ShieldCheck },
  { key: 'success', icon: Zap },
]

const stepIndex = computed(() => steps.findIndex((step) => step.key === flowStep.value))
const trackFillPx = computed(() => {
  const { middle } = trackCenters.value
  if (!trackWidthPx.value) return 0
  if (flowStep.value === 'face') {
    const end = middle || trackWidthPx.value * 0.5
    return end * (faceScanProgress.value / 100)
  }
  if (flowStep.value === 'location') {
    return middle || trackWidthPx.value * 0.5
  }
  return trackWidthPx.value
})
const progressValue = computed(() => {
  if (!trackWidthPx.value) return 0
  return Math.max(0, Math.round((trackFillPx.value / trackWidthPx.value) * 100))
})
const trackBounce = ref(false)

function stepNodeClass(index) {
  if (flowStep.value === 'success' || stepIndex.value > index) return 'step-node--done'
  if (stepIndex.value === index) return 'step-node--active'
  return 'step-node--pending'
}

function stepNodeIcon(index) {
  if (flowStep.value === 'success' || stepIndex.value > index) return Check
  return steps[index].icon
}

const faceImageUrl = computed(() =>
  currentUser.value?.avatar_url || currentUser.value?.profile_photo_url || ''
)

const isCameraReady = computed(() => cameraState.value === 'ready')
const showFaceError = computed(() =>
  flowStep.value === 'face' && faceScanError.value
)
const showLocationError = computed(() =>
  flowStep.value === 'location' && (locationStatus.value === 'error' || recordingFailed.value)
)
const locationDetailText = computed(() => {
  if (showLocationError.value) return ''

  const distance = Number(locationCheck.value?.distance_m)
  const radius = Number(locationCheck.value?.radius_m)
  if (locationCheck.value?.ok && Number.isFinite(distance) && Number.isFinite(radius)) {
    return `Location confirmed at ${distance.toFixed(1)}m from the event marker. Allowed radius: ${radius.toFixed(0)}m.`
  }

  const accuracy = Number(userCoords.value?.accuracy)
  if (Number.isFinite(accuracy) && accuracy > 0) {
    return `GPS accuracy ${Math.round(accuracy)}m.`
  }

  return ''
})
const setVideoEl = (el) => {
  videoEl.value = el
}
const setStepNode = (el, index) => {
  if (el) {
    stepNodeEls.value[index] = el
  }
}

const eventGeo = computed(() => resolveEventGeo())

const mapCenter = computed(() => {
  const lat = Number(userCoords.value?.latitude)
  const lon = Number(userCoords.value?.longitude)
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  return { latitude: lat, longitude: lon }
})

const locationErrorText = computed(() => locationError.value || 'Unable to verify your location.')

const latitudeText = computed(() => {
  const lat = mapCenter.value?.latitude
  if (lat == null) return '--'
  return new Intl.NumberFormat('en-PH', { maximumFractionDigits: 5 }).format(lat)
})

const longitudeText = computed(() => {
  const lon = mapCenter.value?.longitude
  if (lon == null) return '--'
  return new Intl.NumberFormat('en-PH', { maximumFractionDigits: 5 }).format(lon)
})

const mapUrl = computed(() => {
  if (!mapCenter.value) return null
  const lat = mapCenter.value.latitude
  const lon = mapCenter.value.longitude
  const radius =
    Number.isFinite(eventGeo.value?.radius) && eventGeo.value.radius > 0
      ? Math.max(eventGeo.value.radius, 180)
      : 240

  const latDelta = radius / 111320
  const lonDelta = radius / (111320 * Math.cos((lat * Math.PI) / 180) || 1)
  const bbox = [
    (lon - lonDelta).toFixed(6),
    (lat - latDelta).toFixed(6),
    (lon + lonDelta).toFixed(6),
    (lat + latDelta).toFixed(6),
  ].join(',')

  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`
})

const mapDestination = computed(() => {
  if (mapCenter.value) {
    return `${mapCenter.value.latitude},${mapCenter.value.longitude}`
  }
  if (Number.isFinite(eventGeo.value?.lat) && Number.isFinite(eventGeo.value?.lon)) {
    return `${eventGeo.value.lat},${eventGeo.value.lon}`
  }
  const fallback = event.value?.location?.trim()
  return fallback || ''
})

const apiBaseUrl = resolveApiBaseUrl()
const successMessage = computed(() => {
  if (successReason.value === 'existing') {
    return 'Attendance already recorded.'
  }
  if (successReason.value === 'not-open') {
    return 'Check-in has not opened yet for this event.'
  }
  if (successReason.value === 'closed') {
    return isOpenAttendanceRecord(latestAttendanceRecord.value)
      ? 'The sign-out window is already closed for this event.'
      : 'Attendance is already closed for this event.'
  }
  if (successReason.value === 'missed-check-in') {
    return 'Check-in is already closed. Only students with an active attendance can sign out now.'
  }
  if (successReason.value === 'waiting-sign-out') {
    return 'Your sign-in is saved. Waiting for the backend sign-out window.'
  }
  if (successReason.value === 'signed-in') {
    return 'Face verified and sign-in saved. Waiting for sign out.'
  }
  if (successReason.value === 'signed-out') {
    return 'Attendance completed successfully.'
  }
  return 'Attendance recorded successfully.'
})
const signOutWaitCountdown = computed(() => {
  if (!['waiting-sign-out', 'signed-in'].includes(successReason.value)) {
    return ''
  }

  const diffMs = getMillisecondsUntilSignOutOpen({
    event: event.value,
    timeStatus: eventTimeStatus.value,
  })

  if (!Number.isFinite(diffMs) || diffMs == null) {
    return ''
  }

  return diffMs <= 0 ? 'less than 1 min' : formatCompactDuration(diffMs)
})
const successDetailMessage = computed(() => {
  const details = []
  const distance = Number(locationCheck.value?.distance_m)

  if (locationCheck.value?.ok && Number.isFinite(distance)) {
    details.push(`Location confirmed at ${distance.toFixed(1)}m from the event marker.`)
  }
  else {
    const accuracy = Number(userCoords.value?.accuracy)
    if (Number.isFinite(accuracy) && accuracy > 0) {
      details.push(`GPS accuracy ${Math.round(accuracy)}m.`)
    }
  }

  if (signOutWaitCountdown.value) {
    details.push(`Sign-out opens in ${signOutWaitCountdown.value}.`)
  }

  return details.join(' ')
})

function normalizeFaceScanAction(action) {
  return String(action ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function isFaceScanSignOutAction(action) {
  return ['sign_out', 'signed_out', 'check_out', 'checkout', 'time_out', 'out'].includes(action)
}

function isFaceScanSignInAction(action) {
  return ['sign_in', 'signed_in', 'check_in', 'checkin', 'time_in', 'in'].includes(action)
}

async function loadEventTimeStatus() {
  const normalizedEventId = eventId.value
  if (!Number.isFinite(normalizedEventId)) {
    eventTimeStatus.value = null
    return null
  }

  const token = localStorage.getItem('aura_token')
  if (!token) {
    eventTimeStatus.value = null
    return null
  }

  try {
    eventTimeStatus.value = await getEventTimeStatus(apiBaseUrl, token, normalizedEventId)
  } catch {
    eventTimeStatus.value = null
  }

  return eventTimeStatus.value
}

async function refreshAttendanceContext() {
  const normalizedEventId = eventId.value
  if (!Number.isFinite(normalizedEventId)) {
    return {
      attendanceRecord: latestAttendanceRecord.value,
      timeStatus: eventTimeStatus.value,
    }
  }

  await Promise.allSettled([
    refreshAttendanceRecords({ event_id: normalizedEventId }),
    loadEventTimeStatus(),
  ])

  return {
    attendanceRecord: getLatestAttendanceForEvent(normalizedEventId),
    timeStatus: eventTimeStatus.value,
  }
}

function clearLocationVerificationState() {
  locationCheck.value = null
}

function setLocationVerificationResult(detail = null) {
  locationCheck.value = detail && typeof detail === 'object'
    ? { ...detail }
    : null

  const distance = Number(locationCheck.value?.distance_m)
  if (locationCheck.value?.ok && Number.isFinite(distance)) {
    locationMessage.value = `Location confirmed. You are ${distance.toFixed(1)}m from the event marker.`
    return
  }

  if (locationCheck.value?.ok) {
    locationMessage.value = 'Location verified.'
  }
}

function resolveSuccessReasonFromScanResult(
  result,
  attendanceRecord = latestAttendanceRecord.value,
  timeStatus = eventTimeStatus.value
) {
  const action = normalizeFaceScanAction(result?.action)

  if (result?.time_out || hasSignedOutAttendance(attendanceRecord) || isFaceScanSignOutAction(action)) {
    return 'signed-out'
  }

  const nextActionState = resolveAttendanceActionState({
    event: event.value,
    eventStatus: event.value?.status,
    attendanceRecord,
    timeStatus,
  })

  if (nextActionState === 'waiting-sign-out') {
    return 'waiting-sign-out'
  }

  if (nextActionState === 'done' && hasSignedOutAttendance(attendanceRecord)) {
    return 'signed-out'
  }

  if (result?.time_in || hasSignedInAttendance(attendanceRecord) || isFaceScanSignInAction(action)) {
    return 'signed-in'
  }

  return 'recorded'
}

function buildOptimisticAttendanceRecord(result, existingAttendanceRecord = latestAttendanceRecord.value) {
  const normalizedEventId = Number(eventId.value)
  if (!Number.isFinite(normalizedEventId)) {
    return null
  }

  const attendanceId = Number(result?.attendance_id)
  const action = normalizeFaceScanAction(result?.action)
  const timeIn = result?.time_in ?? existingAttendanceRecord?.time_in ?? null
  const timeOut = result?.time_out ?? existingAttendanceRecord?.time_out ?? null
  const checkInStatus =
    result?.geo?.attendance_decision?.attendance_status
    ?? existingAttendanceRecord?.check_in_status
    ?? existingAttendanceRecord?.status
    ?? null
  const hasCompletedAttendance = Boolean(timeOut) || isFaceScanSignOutAction(action)
  const finalizedStatus =
    existingAttendanceRecord?.check_in_status
    ?? checkInStatus
    ?? existingAttendanceRecord?.status
    ?? 'present'
  const isValidCompletedAttendance = hasCompletedAttendance
    ? ['present', 'late'].includes(String(finalizedStatus || '').trim().toLowerCase())
    : false

  if (!Number.isFinite(attendanceId) && !timeIn && !timeOut) {
    return null
  }

  return {
    ...(existingAttendanceRecord || {}),
    id: Number.isFinite(attendanceId) ? attendanceId : Number(existingAttendanceRecord?.id ?? 0),
    event_id: normalizedEventId,
    student_id:
      existingAttendanceRecord?.student_id
      ?? currentUser.value?.student_profile?.id
      ?? currentUser.value?.student_profile?.student_id
      ?? currentUser.value?.id
      ?? null,
    method: existingAttendanceRecord?.method || 'face_scan',
    status: finalizedStatus,
    display_status: hasCompletedAttendance
      ? finalizedStatus
      : 'incomplete',
    completion_state: hasCompletedAttendance ? 'completed' : 'incomplete',
    check_in_status: checkInStatus,
    check_out_status: hasCompletedAttendance
      ? 'present'
      : null,
    time_in: timeIn,
    time_out: timeOut,
    duration_minutes: result?.duration_minutes ?? existingAttendanceRecord?.duration_minutes ?? null,
    is_valid_attendance: isValidCompletedAttendance,
    notes: hasCompletedAttendance
      ? (
          isValidCompletedAttendance
            ? null
            : existingAttendanceRecord?.notes ?? 'Attendance was completed, but the final result is not valid.'
        )
      : 'Pending sign-out.',
  }
}

function preferCompletedAttendanceRecord(primaryRecord, fallbackRecord) {
  if (!primaryRecord) return fallbackRecord ?? null
  if (!fallbackRecord) return primaryRecord

  const primaryCompleted = resolveAttendanceCompletionState(primaryRecord) === 'completed'
  const fallbackCompleted = resolveAttendanceCompletionState(fallbackRecord) === 'completed'

  if (primaryCompleted !== fallbackCompleted) {
    return primaryCompleted ? primaryRecord : fallbackRecord
  }

  const primaryHasTimeOut = hasSignedOutAttendance(primaryRecord)
  const fallbackHasTimeOut = hasSignedOutAttendance(fallbackRecord)
  if (primaryHasTimeOut !== fallbackHasTimeOut) {
    return primaryHasTimeOut ? primaryRecord : fallbackRecord
  }

  return primaryRecord
}

function resolveLocationErrorMessage(source, fallback = 'Unable to verify your location.') {
  const detail = source?.details ?? source?.detail ?? source
  const hasLocationDetail = detail && typeof detail === 'object' && (
    detail.reason != null
    || detail.distance_m != null
    || detail.radius_m != null
    || detail.accuracy_m != null
  )

  if (hasLocationDetail) {
    return buildAttendanceLocationErrorMessage(detail)
  }

  const message = String(source?.message || '').trim()
  return message || fallback
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function getEventLocation() {
  const desiredAccuracy = Number(event.value?.geo_max_accuracy_m)

  return getCurrentPositionWithinAccuracyOrThrow({
    desiredAccuracy: Number.isFinite(desiredAccuracy) && desiredAccuracy > 0
      ? desiredAccuracy
      : null,
    enableHighAccuracy: geolocationHighAccuracy,
    timeout: Math.max(geolocationTimeoutMs, 9000),
    maximumAge: Math.max(geolocationMaxAgeMs, 45000),
    onAccuracyUpdate: (accuracy) => {
      const latitude = Number(userCoords.value?.latitude)
      const longitude = Number(userCoords.value?.longitude)
      userCoords.value = {
        latitude: Number.isFinite(latitude) ? latitude : null,
        longitude: Number.isFinite(longitude) ? longitude : null,
        accuracy,
        capturedAt: new Date().toISOString(),
      }

      if (Number.isFinite(desiredAccuracy) && desiredAccuracy > 0 && accuracy > desiredAccuracy) {
        locationMessage.value = `Waiting for a precise GPS fix... current accuracy ${Math.round(accuracy)}m.`
        return
      }

      locationMessage.value = `GPS locked at ${Math.round(accuracy)}m accuracy.`
    },
  })
}

function waitForLocationRetry() {
  return new Promise((resolve) => {
    locationRetryResolve = () => {
      locationRetryResolve = null
      resolve()
    }
  })
}

function resolveEventGeo() {
  const data = event.value
  if (!data) return null

  const lat =
    Number(data.geo_latitude ?? data.geoLatitude ?? data.latitude ?? data.location_latitude ?? data.locationLat)
  const lon =
    Number(data.geo_longitude ?? data.geoLongitude ?? data.longitude ?? data.location_longitude ?? data.locationLon)
  const radiusRaw =
    Number(data.geo_radius_m ?? data.geoRadiusM ?? data.radius_m ?? data.radiusM ?? data.location_radius_m)
  const radius = Number.isFinite(radiusRaw) ? radiusRaw : null

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return { lat: null, lon: null, radius }
  }

  return { lat, lon, radius }
}

async function recordFaceScanAttendance() {
  const eventIdValue = eventId.value
  const imageDataUrl = capturedFaceDataUrl.value
  if (!eventIdValue) {
    throw new Error('Event information is missing. Please go back and try again.')
  }
  if (!imageDataUrl) {
    throw new Error('A live face capture is required before attendance can be recorded.')
  }

  const studentIdValue = currentUser.value?.student_profile?.student_id
    || currentUser.value?.id
    || null

  const token = localStorage.getItem('aura_token')
  const rawBase64 = imageDataUrl.includes(',') ? imageDataUrl.split(',')[1] : imageDataUrl
  const payload = {
    eventId: eventIdValue,
    studentId: studentIdValue != null ? String(studentIdValue) : '',
    imageBase64: imageDataUrl,
    latitude: userCoords.value?.latitude ?? null,
    longitude: userCoords.value?.longitude ?? null,
    accuracyM: userCoords.value?.accuracy ?? null,
  }

  let result = null
  try {
    result = await postFaceScanAttendance(apiBaseUrl, token, payload)
  } catch {
    result = await postFaceScanAttendance(apiBaseUrl, token, {
      ...payload,
      imageBase64: rawBase64,
    })
  }

  if (result && !result.ok) {
    throw new Error(result.message || 'The server could not record your attendance.')
  }

  if (result?.geo?.time_status) {
    eventTimeStatus.value = result.geo.time_status
  }

  if (result?.geo) {
    setLocationVerificationResult(result.geo)
  }

  let attendanceContext = {
    attendanceRecord: getLatestAttendanceForEvent(eventIdValue),
    timeStatus: eventTimeStatus.value,
  }

  try {
    attendanceContext = await refreshAttendanceContext()
  } catch {
    // Keep the successful backend face-scan result even if the follow-up refresh fails.
  }

  const optimisticAttendanceRecord = buildOptimisticAttendanceRecord(
    result,
    attendanceContext.attendanceRecord || latestAttendanceRecord.value
  )

  if (optimisticAttendanceRecord) {
    upsertAttendanceRecordSnapshot(optimisticAttendanceRecord)
    attendanceContext = {
      ...attendanceContext,
      attendanceRecord: preferCompletedAttendanceRecord(
        attendanceContext.attendanceRecord,
        optimisticAttendanceRecord,
      ),
    }
  }

  return {
    result,
    attendanceRecord: attendanceContext.attendanceRecord,
    timeStatus: attendanceContext.timeStatus,
  }
}

async function waitForLocationCheck() {
  while (true) {
    locationStatus.value = 'checking'
    locationError.value = ''
    locationMessage.value = 'Checking event location...'
    clearLocationVerificationState()

    const coords = await getEventLocation().catch((error) => {
      locationStatus.value = 'error'
      locationError.value = error?.message || 'Location access is required to continue.'
      return null
    })
    if (!coords) {
      if (!locationError.value) {
        locationStatus.value = 'error'
        locationError.value = 'Unable to determine your location. Make sure location services are on and try again.'
      }
      await waitForLocationRetry()
      continue
    }

    userCoords.value = {
      latitude: coords.latitude,
      longitude: coords.longitude,
      accuracy: coords.accuracy ?? null,
      capturedAt: new Date().toISOString(),
    }

    if (!event.value?.geo_required) {
      locationStatus.value = 'ok'
      locationMessage.value = Number.isFinite(Number(coords.accuracy))
        ? `Location verified. GPS accuracy ${Math.round(Number(coords.accuracy))}m.`
        : 'Location verified.'
      return
    }

    try {
      const token = localStorage.getItem('aura_token')
      const verification = await verifyEventLocation(apiBaseUrl, token, eventId.value, {
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy_m: coords.accuracy ?? null,
      })

      if (verification?.time_status) {
        eventTimeStatus.value = verification.time_status
      }

      setLocationVerificationResult(verification)

      if (!verification?.ok) {
        locationStatus.value = 'error'
        locationError.value = buildAttendanceLocationErrorMessage(verification)
        await waitForLocationRetry()
        continue
      }
    } catch (error) {
      locationStatus.value = 'error'
      locationError.value = resolveLocationErrorMessage(error)
      await waitForLocationRetry()
      continue
    }

    locationStatus.value = 'ok'
    return
  }
}

async function runAttendanceFlow() {
  if (isRunning.value) return
  isRunning.value = true
  recordingFailed.value = false

  try {
    flowStep.value = 'face'
    locationMessage.value = 'Checking event location...'
    await nextTick()
    await startCamera()
    await waitForFaceDetection()
    capturedFaceDataUrl.value = captureVideoFrame()

    flowStep.value = 'location'
    stopCamera()
    await waitForLocationCheck()
    await attemptRecordAttendance()
    flowStep.value = 'success'
  } catch (error) {
    const message = resolveLocationErrorMessage(
      error,
      'Unable to record your attendance right now.'
    )
    if (flowStep.value === 'location') {
      locationStatus.value = 'error'
      locationError.value = message
    } else {
      faceScanError.value = true
    }
  } finally {
    stopCamera()
    isRunning.value = false
  }
}

async function attemptRecordAttendance() {
  while (true) {
    try {
      recordingFailed.value = false
      locationError.value = ''
      const attendanceOutcome = await recordFaceScanAttendance()
      successReason.value = resolveSuccessReasonFromScanResult(
        attendanceOutcome?.result,
        attendanceOutcome?.attendanceRecord,
        attendanceOutcome?.timeStatus,
      )
      return
    } catch (error) {
      recordingFailed.value = true
      locationStatus.value = 'error'
      locationError.value = resolveLocationErrorMessage(
        error,
        'Unable to record your attendance. Please try again.'
      )
      await waitForLocationRetry()
    }
  }
}

function openInMaps() {
  if (!mapDestination.value) return
  const url = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(mapDestination.value)}`
  window.open(url, '_blank', 'noopener')
}

async function goBack() {
  if (['signed-out', 'signed-in', 'waiting-sign-out'].includes(successReason.value)) {
    await refreshAttendanceContext().catch(() => null)
  }

  if (hasNavigableHistory(route)) {
    router.back()
    return
  }

  router.push(resolveBackFallbackLocation(route, { eventId: eventId.value }))
}

function retryFaceScan() {
  faceScanError.value = false
  faceDetected.value = false
  videoReady.value = false
  capturedFaceDataUrl.value = ''
  startCamera()
  if (retryResolve) {
    const resolve = retryResolve
    retryResolve = null
    resolve()
    return
  }
  if (flowStep.value === 'face') startFaceProgress()
}

function captureVideoFrame() {
  const el = videoEl.value
  if (!el || el.videoWidth <= 0 || el.videoHeight <= 0) {
    throw new Error('Unable to capture a face image.')
  }

  const size = Math.min(el.videoWidth, el.videoHeight)
  const sx = Math.max(0, (el.videoWidth - size) / 2)
  const sy = Math.max(0, (el.videoHeight - size) / 2)
  const canvas = document.createElement('canvas')
  canvas.width = 720
  canvas.height = 720
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    throw new Error('Unable to prepare the face image.')
  }

  ctx.drawImage(el, sx, sy, size, size, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', 0.92)
}

function retryLocationCheck() {
  locationError.value = ''
  locationStatus.value = 'checking'
  recordingFailed.value = false
  if (locationRetryResolve) {
    const resolve = locationRetryResolve
    locationRetryResolve = null
    resolve()
  }
}

function goToSuccess() {
  flowStep.value = 'success'
}

function waitForRetry() {
  return new Promise((resolve) => {
    retryResolve = () => {
      retryResolve = null
      resolve()
    }
  })
}

function waitForVideoReady() {
  if (cameraState.value === 'denied' || cameraState.value === 'unsupported') {
    return Promise.resolve(cameraState.value)
  }
  if (cameraState.value === 'ready' && videoReady.value) return Promise.resolve('ready')

  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      stopWatch()
      resolve('timeout')
    }, faceScanVideoReadyTimeoutMs)

    const stopWatch = watch([cameraState, videoReady], ([state, ready]) => {
      if (state === 'denied' || state === 'unsupported') {
        clearTimeout(timer)
        stopWatch()
        resolve(state)
        return
      }
      if (state === 'ready' && ready) {
        clearTimeout(timer)
        stopWatch()
        resolve('ready')
      }
    })
  })
}

async function ensureFaceDetector() {
  if (faceDetectorInstance) return true
  try {
    faceDetectorInstance = await initFaceScanDetector({
      wasmBaseUrl: faceDetectorWasmBaseUrl,
      modelAssetPath: faceDetectorModelUrl,
      minDetectionConfidence: faceDetectorMinConfidence,
      minSuppressionThreshold: faceDetectorSuppression,
      runningMode: 'VIDEO',
    })
    return Boolean(faceDetectorInstance)
  } catch {
    faceDetectorInstance = null
    resetFaceScanDetector()
    return false
  }
}

function stopFaceProgress() {
  if (faceProgressRaf) cancelAnimationFrame(faceProgressRaf)
  faceProgressRaf = null
}

function animateFaceProgress(target, duration) {
  stopFaceProgress()
  const start = faceScanProgress.value
  const delta = target - start
  const startTime = performance.now()

  const tick = (now) => {
    const t = Math.min(1, (now - startTime) / duration)
    const eased = 1 - Math.pow(1 - t, 3)
    faceScanProgress.value = Math.max(0, Math.min(100, start + delta * eased))
    if (t < 1) {
      faceProgressRaf = requestAnimationFrame(tick)
    }
  }

  faceProgressRaf = requestAnimationFrame(tick)
}

function startFaceProgress() {
  faceScanProgress.value = 0
  animateFaceProgress(faceScanProgressMax, faceScanProgressDuration)
}

function waitForFaceOrTimeout() {
  return new Promise((resolve) => {
    if (faceDetected.value) {
      resolve('detected')
      return
    }

    let stopFaceWatch = () => {}
    let stopCameraWatch = () => {}
    let timer = null

    const cleanup = () => {
      if (timer) clearTimeout(timer)
      stopFaceWatch()
      stopCameraWatch()
      stopFaceProgress()
    }

    timer = setTimeout(() => {
      cleanup()
      resolve('timeout')
    }, faceScanTimeoutMs)

    stopFaceWatch = watch(faceDetected, (val) => {
      if (!val) return
      cleanup()
      resolve('detected')
    })

    stopCameraWatch = watch(cameraState, (state) => {
      if (state === 'denied' || state === 'unsupported') {
        cleanup()
        resolve(state)
      }
    })
  })
}

async function completeFaceCaptureFallback() {
  if (faceScanProgress.value <= 0) {
    startFaceProgress()
  } else if (faceScanProgress.value < faceScanProgressMax) {
    animateFaceProgress(faceScanProgressMax, Math.max(180, faceScanProgressDuration / 2))
  }
  await delay(Math.max(320, faceScanProgressDuration))
  animateFaceProgress(100, 260)
  await delay(260)
}

async function waitForFaceDetection() {
  if (!faceScanGateEnabled) {
    animateFaceProgress(100, 240)
    await delay(240)
    return
  }

  while (true) {
    faceScanError.value = false

    const readyState = await waitForVideoReady()
    if (readyState !== 'ready') {
      faceScanError.value = true
      await waitForRetry()
      continue
    }

    const detectorReady = await ensureFaceDetector()
    if (!detectorReady) {
      faceScanError.value = false
      await completeFaceCaptureFallback()
      return
    }

    startFaceDetection()
    startFaceProgress()
    const result = await waitForFaceOrTimeout()

    if (result === 'detected') {
      faceScanError.value = false
      animateFaceProgress(100, 320)
      await delay(320)
      stopFaceDetection()
      return
    }

    stopFaceDetection()

    if (result === 'timeout') {
      faceScanError.value = false
      await completeFaceCaptureFallback()
      return
    }

    faceScanError.value = true
    await waitForRetry()
  }
}

async function attachStreamToVideo() {
  if (!videoEl.value || !mediaStream.value) return false
  const el = videoEl.value

  el.muted = true
  el.autoplay = true
  el.playsInline = true

  if (el.srcObject !== mediaStream.value) {
    el.srcObject = mediaStream.value
  }

  videoReady.value = false
  stopFaceDetection()

  try {
    await el.play().catch(() => null)
  } catch {
    // Ignore play errors (autoplay restrictions are handled by user gesture).
  }

  if (el.readyState >= 2) {
    videoReady.value = true
    return true
  }

  return new Promise((resolve) => {
    let settled = false
    const finish = (ready) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      el.removeEventListener('loadeddata', onReady)
      el.removeEventListener('canplay', onReady)
      el.removeEventListener('error', onError)
      videoReady.value = ready
      resolve(ready)
    }
    const onReady = () => finish(true)
    const onError = () => finish(false)
    const timer = setTimeout(() => finish(false), faceScanVideoReadyTimeoutMs)

    el.addEventListener('loadeddata', onReady, { once: true })
    el.addEventListener('canplay', onReady, { once: true })
    el.addEventListener('error', onError, { once: true })
  })
}

async function startCamera() {
  if (!navigator?.mediaDevices?.getUserMedia) {
    cameraState.value = 'unsupported'
    return
  }

  if (cameraStartPromise) return cameraStartPromise

  cameraStartPromise = (async () => {
    if (!mediaStream.value) {
      cameraState.value = 'requesting'
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user' },
          audio: false,
        })
        mediaStream.value = stream
      } catch {
        cameraState.value = 'denied'
        videoReady.value = false
        return
      }
    }

    cameraState.value = 'ready'
    await attachStreamToVideo()
  })()

  try {
    await cameraStartPromise
  } finally {
    cameraStartPromise = null
  }
}

function stopCamera() {
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach((track) => track.stop())
    mediaStream.value = null
  }
  if (videoEl.value) {
    videoEl.value.srcObject = null
  }
  cameraState.value = 'idle'
  videoReady.value = false
  stopFaceDetection()
  stopFaceProgress()
}

function startFaceDetection() {
  if (!faceDetectorInstance || !videoEl.value) return
  stopFaceDetection()
  let detectionStreak = 0
  let lastFaceSeenAt = 0
  let lastDetectAt = 0

  const detect = (now) => {
    if (!videoEl.value || cameraState.value !== 'ready' || flowStep.value !== 'face') return
    if (now - lastDetectAt < faceDetectorIntervalMs) {
      faceDetectRaf = requestAnimationFrame(detect)
      return
    }
    lastDetectAt = now
    try {
      const result = faceDetectorInstance.detectForVideo(videoEl.value, now)
      const hasFace = Array.isArray(result?.detections) && result.detections.length > 0
      if (hasFace) {
        detectionStreak += 1
        lastFaceSeenAt = now
      } else {
        detectionStreak = 0
      }
      const held = lastFaceSeenAt > 0 && now - lastFaceSeenAt <= faceDetectHoldMs
      faceDetected.value = detectionStreak >= faceDetectMinFrames || held
    } catch {
      faceDetected.value = false
    }
    faceDetectRaf = requestAnimationFrame(detect)
  }

  faceDetectRaf = requestAnimationFrame(detect)
}

function stopFaceDetection() {
  if (faceDetectRaf) cancelAnimationFrame(faceDetectRaf)
  faceDetectRaf = null
  faceDetected.value = false
}

watch(flowStep, (step) => {
  if (step === 'face') {
    faceScanError.value = false
    locationMessage.value = 'Checking event location...'
    clearLocationVerificationState()
    return
  }
  if (step === 'location') {
    locationStatus.value = 'checking'
    locationError.value = ''
    locationMessage.value = 'Checking event location...'
    return
  }
  retryResolve = null
  locationRetryResolve = null
  stopFaceProgress()
  faceScanProgress.value = 0
  stopCamera()
})

watch(
  () => flowStep.value,
  () => {
    trackBounce.value = false
    requestAnimationFrame(() => {
      trackBounce.value = true
      setTimeout(() => {
        trackBounce.value = false
      }, 360)
    })
    nextTick(updateTrackMetrics)
  }
)

watch(
  videoEl,
  (el) => {
    if (el && mediaStream.value) {
      attachStreamToVideo()
    }
  },
  { flush: 'post' }
)

function updateTrackMetrics() {
  const track = stepTrackEl.value
  if (!track) return
  const trackRect = track.getBoundingClientRect()
  if (!trackRect.width) return

  trackWidthPx.value = trackRect.width

  const centers = stepNodeEls.value.map((node) => {
    if (!node) return null
    const rect = node.getBoundingClientRect()
    return rect.left + rect.width / 2 - trackRect.left
  })

  trackCenters.value = {
    left: centers[0] ?? 0,
    middle: centers[1] ?? trackRect.width / 2,
    right: centers[2] ?? trackRect.width,
  }
}

let trackResizeObserver = null

async function initializeAttendanceFlow() {
  await ensureDashboardEvent(eventId.value).catch(() => null)
  if (!event.value) return

  const { attendanceRecord, timeStatus } = await refreshAttendanceContext()
  const actionState = resolveAttendanceActionState({
    event: event.value,
    eventStatus: event.value?.status,
    attendanceRecord,
    timeStatus,
  })

  if (actionState === 'done') {
    successReason.value = 'existing'
    flowStep.value = 'success'
    return
  }

  if (actionState === 'waiting-sign-out') {
    successReason.value = 'waiting-sign-out'
    flowStep.value = 'success'
    return
  }

  if (actionState === 'not-open') {
    successReason.value = 'not-open'
    flowStep.value = 'success'
    return
  }

  if (actionState === 'missed-check-in') {
    successReason.value = 'missed-check-in'
    flowStep.value = 'success'
    return
  }

  if (actionState === 'closed') {
    successReason.value = 'closed'
    flowStep.value = 'success'
    return
  }

  successReason.value = 'recorded'
  void runAttendanceFlow()
}

onMounted(async () => {
  await initializeAttendanceFlow()

  nextTick(updateTrackMetrics)
  if (stepTrackEl.value && typeof ResizeObserver !== 'undefined') {
    trackResizeObserver = new ResizeObserver(() => {
      updateTrackMetrics()
    })
    trackResizeObserver.observe(stepTrackEl.value)
  }
})

onBeforeUnmount(() => {
  stopCamera()
  retryResolve = null
  locationRetryResolve = null
  resetFaceScanDetector()
  faceDetectorInstance = null
  trackResizeObserver?.disconnect?.()
  trackResizeObserver = null
})
</script>

<style scoped>
.attendance-page {
  min-height: 100vh;
  padding: 32px 20px 160px;
  background: var(--color-bg, #f5f4ef);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  --track-width: min(320px, 92%);
  --track-height: 46px;
  --node-size: 34px;
  --track-pad: 8px;
  --scan-size: clamp(240px, 78vw, 300px);
  --scan-thickness: 9px;
  --scan-gap: 8px;
  --scan-media: calc(var(--scan-size) - (var(--scan-thickness) * 2) - (var(--scan-gap) * 2));
  --scan-start-angle: -90deg;
  --map-width: 341px;
  --map-height: 367px;
  --map-radius: 25px;
  --map-card-width: 332px;
  --map-card-height: 147px;
  --map-card-radius: 25px;
  --map-card-action-size: 49px;
  --map-card-bg: var(--color-primary, #aaff00);
  --map-card-text: var(--color-primary-text, #0a0a0a);
  --map-card-action-bg: var(--color-nav, #0a0a0a);
  --map-card-action-color: var(--color-surface, #ffffff);
  --map-card-shadow: 0 18px 26px rgba(0, 0, 0, 0.16);
}

.attendance-shell {
  width: 100%;
  max-width: 380px;
  min-height: calc(100vh - 32px - 160px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}

.step-track {
  position: relative;
  width: var(--track-width);
  height: var(--track-height);
  background: #0a0a0a;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--track-pad);
  overflow: hidden;
}

.step-track-progress {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  background: var(--color-primary);
  border-radius: 999px;
  transition: width 0.45s cubic-bezier(0.22, 1, 0.36, 1);
  transform-origin: left center;
}

.step-node {
  position: relative;
  z-index: 2;
  width: var(--node-size);
  height: var(--node-size);
  border-radius: 50%;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0a0a0a;
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.14);
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.step-node--active {
  color: #0a0a0a;
  transform: scale(1.05);
}

.step-node--done {
  color: var(--color-primary);
  transform: scale(1.03);
}

.step-node--pending {
  color: #0a0a0a;
  opacity: 0.75;
}

.step-scan-arrow {
  position: absolute;
  left: 33.5%;
  top: 50%;
  transform: translate(-50%, -50%);
  color: #0a0a0a;
  opacity: 0.65;
  z-index: 2;
}

.step-track--bounce .step-track-progress {
  animation: trackBounce 0.38s cubic-bezier(0.2, 0.8, 0.2, 1);
}

@keyframes trackBounce {
  0% {
    transform: scaleX(0.985);
  }
  55% {
    transform: scaleX(1.02);
  }
  100% {
    transform: scaleX(1);
  }
}

.step-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  text-align: center;
}

.step-section--location {
  gap: 12px;
  margin-top: 0;
  flex: 1;
  justify-content: center;
}

.step-section--success {
  align-self: stretch;
  gap: 12px;
  justify-content: flex-start;
  padding-top: 6px;
}

.step-caption {
  font-size: 13px;
  font-weight: 600;
  color: #5f5f5f;
  margin: 0;
}

.location-map {
  position: relative;
  width: min(var(--map-width), 100%);
  height: var(--map-height);
  border-radius: var(--map-radius);
  overflow: hidden;
  background: #dedede;
  margin-top: 8px;
  margin-bottom: 24px;
  align-self: center;
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.12);
  border: 1px solid #ececec;
}

.location-map-frame {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
}

.location-map-fallback {
  position: relative;
  width: 100%;
  height: 100%;
  background: #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: center;
}

.map-grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(#e0e0e0 1px, transparent 1px),
    linear-gradient(90deg, #e0e0e0 1px, transparent 1px);
  background-size: 18px 18px;
}

.location-card {
  position: absolute;
  left: 50%;
  bottom: 6px;
  width: min(var(--map-card-width), calc(100% - 8px));
  height: var(--map-card-height);
  transform: translateX(-50%);
  background: var(--map-card-bg);
  border-radius: var(--map-card-radius);
  padding: 18px 18px 18px 20px;
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr) var(--map-card-action-size);
  column-gap: 18px;
  align-items: center;
  box-shadow: var(--map-card-shadow);
  color: var(--map-card-text);
}

.location-card-left {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  min-width: 0;
  font-weight: 800;
  line-height: 1;
  align-self: stretch;
}

.location-card-label {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: -0.02em;
  opacity: 0.72;
}

.location-card-title {
  font-size: 15px;
  letter-spacing: -0.04em;
}

.location-card-coords {
  display: grid;
  gap: 8px;
  align-content: center;
  justify-items: start;
  min-width: 0;
}

.coord-label {
  font-size: 9px;
  font-weight: 500;
  line-height: 1.1;
  letter-spacing: -0.01em;
  opacity: 0.68;
}

.coord-value {
  font-size: 15px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.03em;
}

.coord-group {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.location-card-action {
  width: var(--map-card-action-size);
  height: var(--map-card-action-size);
  border-radius: 50%;
  border: none;
  background: var(--map-card-action-bg);
  color: var(--map-card-action-color);
  display: flex;
  align-items: center;
  justify-content: center;
  justify-self: end;
  align-self: center;
  flex-shrink: 0;
  cursor: pointer;
  box-shadow: 0 10px 18px rgba(0, 0, 0, 0.18);
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.location-card-action:active {
  transform: scale(0.95);
}

.location-card-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.location-hint {
  font-size: 9.5px;
  font-weight: 600;
  color: #d24848;
  margin: 0;
  text-align: center;
  line-height: 1.45;
}

.location-hint--ok {
  color: #1f7a4f;
}

.location-next-btn {
  margin-top: 4px;
  border: none;
  background: #ffffff;
  color: #222222;
  font-size: 11px;
  font-weight: 600;
  padding: 8px 28px;
  border-radius: 999px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: transform 0.15s ease, opacity 0.2s ease;
}

.location-next-btn:active {
  transform: scale(0.97);
}

.location-next-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.location-error-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
}

.location-error {
  font-size: 11px;
  font-weight: 700;
  color: #d24848;
  margin: 0;
}

.location-retry-btn {
  border: none;
  background: #ffffff;
  color: #222222;
  font-size: 11px;
  font-weight: 600;
  padding: 8px 24px;
  border-radius: 999px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.location-retry-btn:active {
  transform: scale(0.97);
}

.success-caption {
  font-size: 13px;
  font-weight: 700;
  color: #1a1a1a;
  text-align: center;
  margin: 0;
  max-width: 160px;
  line-height: 1.3;
  align-self: center;
}

.success-detail {
  margin: -18px 0 0;
  max-width: 220px;
  font-size: 10.5px;
  font-weight: 600;
  line-height: 1.45;
  text-align: center;
  color: #5a6472;
}

.success-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  align-self: center;
  padding: 4px 14px 4px 4px;
  border-radius: 999px;
  border: none;
  background: var(--color-primary);
  color: #0a0a0a;
  cursor: pointer;
  box-shadow: 0 10px 18px rgba(0, 0, 0, 0.14);
  transition: transform 0.15s ease;
}

.success-btn:active {
  transform: scale(0.97);
}

.success-btn-icon {
  width: 29px;
  height: 29px;
  border-radius: 50%;
  background: #0a0a0a;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.success-btn-text {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

@media (min-width: 768px) {
  .attendance-page {
    padding-top: 0;
    padding-bottom: 0;
    justify-content: center;
  }

  .attendance-shell {
    max-width: 380px;
    min-height: auto;
  }
}

</style>
