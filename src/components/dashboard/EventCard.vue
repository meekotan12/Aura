<template>
  <div 
    class="event-card group" 
    :class="cardClasses"
  >
    <!-- Top Right Status -->
    <div class="event-card__status">
      <span class="status-text">{{ statusText }}</span>
      <span class="status-dot" :class="statusDotClass"></span>
    </div>

    <!-- Content -->
    <div class="event-card__content">
      <p class="event-desc">{{ eventMeta }}</p>
      <h3 class="event-title">{{ event.name }}</h3>
    </div>

    <!-- Action Button -->
    <div class="event-action-row">
      <button class="event-action" :class="actionBtnClass" @click="$emit('click', event)">
        <div class="action-icon">
          <ArrowRight :size="16" />
        </div>
        <span class="action-text">{{ actionText }}</span>
      </button>

      <button
        v-if="canToggleMap"
        class="map-toggle"
        :class="{ 'map-toggle--open': isMapOpen }"
        aria-label="Toggle map"
        @click.stop="handleToggleMap"
      >
        <ChevronDown :size="16" />
      </button>
    </div>

    <!-- Collapsible Map (mobile only) -->
    <div
      v-if="canToggleMap"
      class="map-panel"
      :class="{ 'map-panel--open': isMapOpen }"
    >
      <div class="map-panel__inner">
        <div class="map-shell">
          <iframe
            v-if="isMapOpen && mapUrl"
            class="map-frame"
            :src="mapUrl"
            loading="lazy"
            referrerpolicy="no-referrer-when-downgrade"
            aria-label="Event location map"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { ArrowRight, ChevronDown } from 'lucide-vue-next'

const props = defineProps({
  event: {
    type: Object,
    required: true,
  }
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
  // Backwards compatibility if legacy "done" still appears
  return props.event.status === 'done' ? 'completed' : props.event.status
})

const statusConfig = computed(() => STATUS_CONFIG[normalizedStatus.value] ?? STATUS_CONFIG.upcoming)

const statusText = computed(() => statusConfig.value.label)
const actionText = computed(() => statusConfig.value.actionText)
const cardClasses = computed(() => statusConfig.value.cardClass)
const statusDotClass = computed(() => statusConfig.value.dotClass)
const actionBtnClass = computed(() => statusConfig.value.actionBtnClass)

const eventMeta = computed(() => props.event.location ?? '')

const hasGeo = computed(() =>
  props.event.geo_latitude != null && props.event.geo_longitude != null
)

const canToggleMap = computed(() => normalizedStatus.value === 'ongoing' && hasGeo.value)

const isMobile = ref(false)
const isMapOpen = ref(false)

function updateMedia() {
  isMobile.value = window.matchMedia('(max-width: 767px)').matches
}

function handleToggleMap() {
  if (!canToggleMap.value) return
  if (!isMobile.value) {
    // Desktop behavior: open event detail instead of expanding
    // Use the same payload as the action button
    emitOpenDetail()
    return
  }
  isMapOpen.value = !isMapOpen.value
}

function emitOpenDetail() {
  emit('open-detail', props.event)
}

onMounted(() => {
  updateMedia()
  window.addEventListener('resize', updateMedia)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateMedia)
})

watch(isMobile, (next) => {
  if (!next) isMapOpen.value = false
})

const mapUrl = computed(() => {
  if (!hasGeo.value) return null
  const lat = props.event.geo_latitude
  const lon = props.event.geo_longitude
  const radius = typeof props.event.geo_radius_m === 'number' && props.event.geo_radius_m > 0
    ? props.event.geo_radius_m
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
}

.event-card:active {
  transform: scale(0.98);
}

/* ── Card Color Variants ── */
.event-card--lime {
  background: var(--color-primary); /* #AAFF00 normally */
  color: var(--color-banner-text);
}

.event-card--white {
  background: #FFFFFF;
  color: var(--color-text-always-dark);
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

.event-action-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.event-action:active {
  transform: scale(0.95);
}

.action-btn--white { background: #FFFFFF; }
.action-btn--lime { background: var(--color-primary); }

.action-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--color-text-always-dark);
  color: #fff;
  border-radius: 50%;
}

.action-text {
  font-size: 10px;
  font-weight: 600;
}

.action-btn--white .action-text {
  color: var(--color-text-always-dark);
}

.action-btn--lime .action-text {
  color: var(--color-banner-text);
}

.map-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid rgba(0,0,0,0.08);
  background: #ffffff;
  color: var(--color-text-always-dark);
  cursor: pointer;
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  will-change: transform;
}

.map-toggle--open {
  transform: rotate(180deg);
}

.map-panel {
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
}

.map-panel--open {
  grid-template-rows: 1fr;
  opacity: 1;
  transform: translateY(0);
  margin-top: 12px;
}

.map-panel__inner {
  min-height: 0;
  overflow: hidden;
}

.map-shell {
  border-radius: 20px;
  padding: 0px;
  background: rgba(0,0,0,0.08);
}

.map-frame {
  width: 100%;
  height: 200px;
  border: none;
  border-radius: 20px;
  background: #f6f6f6;
}

@media (min-width: 768px) {
  .map-panel {
    display: none;
  }
}
</style>
