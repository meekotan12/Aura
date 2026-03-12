<template>
  <div class="events-page">
    
    <!-- ── Header ─────────────────────────────────────────────────────── -->
    <TopBar
      :user="user"
      :unread-count="unreadAnnouncements"
      @toggle-notifications="showNotifications = !showNotifications"
    />

    <!-- ── Title & Filters ────────────────────────────────────────────── -->
    <div class="events-content">
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
      <div v-if="filteredEvents.length > 0" class="events-grid">
        <EventCard 
          v-for="event in filteredEvents" 
          :key="event.id" 
          :event="event"
          @click="handleEventClick"
          @open-detail="handleOpenDetail"
        />
      </div>
      
      <div v-else class="empty-state">
        <p>No events found for this category.</p>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import EventCard from '@/components/dashboard/EventCard.vue'
import TopBar from '@/components/dashboard/TopBar.vue'

// ── Mock Data (swap with actual API calls later) ──────────────────────
import { mockCurrentUser, mockEvents } from '@/data/mockData.js'
import { mockAnnouncements } from '@/data/mockAnnouncements.js'

// User Data Compute
const user = ref(mockCurrentUser)
const showNotifications = ref(false)
const announcements = ref(mockAnnouncements)
const unreadAnnouncements = computed(() =>
  announcements.value.filter((a) => !a.is_read).length
)

const router = useRouter()

// ── Filters & Events Logic ────────────────────────────────────────────
const events = ref(mockEvents)
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
  let items = events.value
  if (activeFilter.value !== 'all' && activeFilter.value !== 'maps') {
    items = items.filter(e => normalizeStatus(e.status) === activeFilter.value)
  }
  if (activeFilter.value === 'maps') return []
  return [...items].sort((a, b) => {
    const aRank = statusRank[normalizeStatus(a.status)] ?? 99
    const bRank = statusRank[normalizeStatus(b.status)] ?? 99
    if (aRank !== bRank) return aRank - bRank
    return new Date(a.start_datetime) - new Date(b.start_datetime)
  })
})

function handleEventClick(event) {
  if (!event?.id) return
  if (event.status === 'ongoing') {
    router.push(`/dashboard/schedule/${event.id}/attendance`)
    return
  }
  router.push(`/dashboard/schedule/${event.id}`)
}

function handleOpenDetail(event) {
  if (!event?.id) return
  router.push(`/dashboard/schedule/${event.id}`)
}
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
  background: var(--color-primary); /* Lime */
  border-color: var(--color-primary);
  color: var(--color-banner-text);
  font-weight: 600;
}

.filter-pill--outline {
  border-color: var(--color-primary);
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
