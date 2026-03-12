<template>
  <div class="event-detail">
    <!-- Header -->
    <header class="detail-header">
      <button class="icon-btn icon-btn--ghost icon-btn--back" aria-label="Back" @click="goBack">
        <ArrowLeft :size="18" />
      </button>

      <div class="header-spacer"></div>

      <button class="icon-btn icon-btn--ghost icon-btn--bell" aria-label="Notifications">
        <Bell :size="18" />
      </button>
    </header>

    <section v-if="event" class="detail-body">
      <!-- Title -->
      <div class="title-block">
        <h1 class="event-title">{{ event.name }}</h1>
        <p class="event-subtitle">Event Date & Time</p>
        <p class="event-date">{{ dateRange }}</p>
      </div>

      <!-- Map -->
      <div class="map-shell">
        <iframe
          v-if="mapUrl"
          class="map-frame"
          :src="mapUrl"
          loading="lazy"
          referrerpolicy="no-referrer-when-downgrade"
          aria-label="Event location map"
        />
        <div v-else class="map-fallback" aria-label="Map not available">
          <div class="map-grid"></div>
          <div class="map-fallback-text">
            <span>Map preview unavailable</span>
          </div>
        </div>

        <!-- Floating status pill (desktop) -->
        <div class="status-pill status-pill--overlay">
          <span class="status-dot" :class="statusDotClass"></span>
          <span class="status-text">{{ statusLabel }}</span>
        </div>

        <!-- Location card -->
        <div class="location-card">
          <div class="geo-columns">
            <div class="geo-block">
              <span class="geo-label">Latitude</span>
              <span class="geo-value">{{ latitudeText }}</span>
              <span class="geo-label geo-label--spaced">Longitude</span>
              <span class="geo-value">{{ longitudeText }}</span>
            </div>
            <div class="geo-block geo-block--location">
              <span class="geo-label">Location</span>
              <span class="geo-location">{{ event.location }}</span>
            </div>
          </div>

          <button
            class="geo-action"
            type="button"
            aria-label="Open location in Google Maps"
            :disabled="!mapDestination"
            @click="openInMaps"
          >
            <ArrowUpRight :size="16" />
          </button>
        </div>
      </div>

      <!-- Status pill (mobile) -->
      <div class="status-pill status-pill--below">
        <span class="status-dot" :class="statusDotClass"></span>
        <span class="status-text">{{ statusLabel }}</span>
      </div>
    </section>

    <section v-else class="empty-state">
      <p>Event not found.</p>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowUpRight, Bell } from 'lucide-vue-next'
import { mockEvents } from '@/data/mockData.js'

const route = useRoute()
const router = useRouter()

const events = ref(mockEvents)

const eventId = computed(() => Number(route.params.id))
const event = computed(() => events.value.find((e) => e.id === eventId.value))

function goBack() {
  router.back()
}

const statusConfig = {
  upcoming: { label: 'Up Coming', dot: 'dot--yellow' },
  ongoing: { label: 'On Going', dot: 'dot--red' },
  completed: { label: 'Done', dot: 'dot--green' },
  cancelled: { label: 'Cancelled', dot: 'dot--gray' },
}

const statusLabel = computed(() => statusConfig[event.value?.status]?.label ?? 'Upcoming')
const statusDotClass = computed(() => statusConfig[event.value?.status]?.dot ?? 'dot--yellow')

const dateRange = computed(() => {
  if (!event.value) return ''
  const start = new Date(event.value.start_datetime)
  const end = new Date(event.value.end_datetime)
  const datePart = start.toLocaleDateString('en-PH', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
  const timePart = `${start.toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit' })} – ${end.toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit' })}`
  return `${datePart} · ${timePart}`
})

const hasGeo = computed(() =>
  event.value?.geo_latitude != null && event.value?.geo_longitude != null
)

const latitudeText = computed(() => {
  if (!hasGeo.value) return '--'
  return new Intl.NumberFormat('en-PH', { maximumFractionDigits: 6 }).format(event.value.geo_latitude)
})

const longitudeText = computed(() => {
  if (!hasGeo.value) return '--'
  return new Intl.NumberFormat('en-PH', { maximumFractionDigits: 6 }).format(event.value.geo_longitude)
})

const mapUrl = computed(() => {
  if (!hasGeo.value) return null
  const lat = event.value.geo_latitude
  const lon = event.value.geo_longitude
  const radius = typeof event.value.geo_radius_m === 'number' && event.value.geo_radius_m > 0
    ? event.value.geo_radius_m
    : 350

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
  if (hasGeo.value) {
    return `${event.value.geo_latitude},${event.value.geo_longitude}`
  }
  const fallback = event.value?.location?.trim()
  return fallback || ''
})

function openInMaps() {
  if (!mapDestination.value) return
  const url = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(mapDestination.value)}`
  window.open(url, '_blank', 'noopener')
}
</script>

<style scoped>
.event-detail {
  min-height: 100vh;
  padding: 28px 24px 110px;
  background: var(--color-bg);
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.header-spacer {
  flex: 1;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--color-text-always-dark);
  border: none;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.icon-btn:active {
  transform: scale(0.95);
}

.icon-btn--ghost {
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}

.detail-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
  width: 100%;
}

.title-block {
  margin: 8px 0 14px;
  width: 100%;
  max-width: 360px;
  text-align: left;
}

.event-title {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.6px;
  color: var(--color-text-always-dark);
  margin: 0 0 6px;
}

.event-subtitle {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 0;
}

.event-date {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  margin-top: 4px;
}

.map-shell {
  position: relative;
  width: 100%;
  max-width: 360px;
  height: auto;
  min-height: 320px;
  aspect-ratio: 1.15 / 1;
  border-radius: 28px;
  overflow: hidden;
  background: var(--color-surface);
  box-shadow: 0 10px 30px rgba(0,0,0,0.06);
}

.map-frame {
  width: 100%;
  height: 100%;
  border: none;
}

.map-fallback {
  position: relative;
  width: 100%;
  height: 100%;
  background: #f6f6f6;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.map-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(0,0,0,0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0,0,0,0.04) 1px, transparent 1px);
  background-size: 24px 24px;
}

.map-fallback-text {
  position: relative;
  font-size: 12px;
  font-weight: 600;
  color: rgba(0,0,0,0.4);
  background: rgba(255,255,255,0.9);
  padding: 10px 14px;
  border-radius: 999px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;
  border-radius: 999px;
  padding: 8px 18px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-always-dark);
  box-shadow: 0 10px 20px rgba(0,0,0,0.08);
}

.status-pill--below {
  margin: 16px auto 0;
  width: fit-content;
}

.status-pill--overlay {
  position: absolute;
  top: 14px;
  right: 14px;
  display: none;
  box-shadow: 0 8px 18px rgba(0,0,0,0.08);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot--red { background: #FF2B2B; }
.dot--yellow { background: #FFDD00; }
.dot--green { background: #00E676; }
.dot--gray { background: #cfcfcf; }

.location-card {
  position: absolute;
  left: 50%;
  bottom: 16px;
  right: auto;
  width: min(320px, 88%);
  max-width: calc(100% - 32px);
  transform: translateX(-50%);
  background: var(--color-primary);
  color: var(--color-banner-text);
  border-radius: 26px;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.geo-columns {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 14px;
  align-items: center;
  width: 100%;
}

.geo-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.geo-block--location {
  min-width: 0;
}

.geo-label {
  font-size: 10px;
  font-weight: 600;
  opacity: 0.8;
}

.geo-label--spaced {
  margin-top: 6px;
}

.geo-value {
  font-size: 14px;
  font-weight: 800;
  color: var(--color-banner-text);
}

.geo-location {
  font-size: 15px;
  font-weight: 800;
  line-height: 1.2;
  color: var(--color-banner-text);
  max-width: 190px;
}

.geo-action {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: var(--color-text-always-dark);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.geo-action:active {
  transform: scale(0.95);
}

.geo-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.empty-state {
  text-align: center;
  padding: 60px 0;
  color: rgba(0,0,0,0.5);
  font-weight: 600;
}

@media (min-width: 768px) {
  .event-detail {
    padding: 28px 0 40px 32px;
  }

  .detail-header {
    margin-bottom: 0;
    justify-content: center;
  }

  .icon-btn--back,
  .header-spacer {
    display: none;
  }

  .event-title {
    font-size: 30px;
  }

  .detail-body {
    max-width: 640px;
    align-items: flex-start;
  }

  .title-block {
    margin: 10px 0 18px;
    max-width: 100%;
  }

  .map-shell {
    height: 360px;
    max-width: 100%;
    min-height: 0;
    aspect-ratio: auto;
  }

  .location-card {
    left: 18px;
    bottom: 18px;
    width: 300px;
    transform: none;
  }

  .geo-location {
    max-width: 220px;
  }

  .status-pill--below {
    display: none;
  }

  .status-pill--overlay {
    display: inline-flex;
  }
}
</style>
