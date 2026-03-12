<template>
  <!-- Events Card: left side shows "Latest Event" label, right shows event details -->
  <div class="rounded-3xl overflow-hidden w-full" style="background: var(--color-surface);">
    <div class="flex h-full">
      <!-- Left: Label + CTA -->
      <div class="flex flex-col justify-between p-5 flex-1">
        <div>
          <h3 class="text-[26px] font-extrabold leading-tight" style="color: var(--color-text-always-dark);">
            Latest<br>Event
          </h3>
        </div>

        <!-- See Event button -->
        <button
          @click="$emit('see-event', latestEvent)"
          class="flex items-center gap-2.5 rounded-full pl-2 pr-4 py-2 self-start transition-all duration-150 hover:scale-105 active:scale-95"
          style="background: var(--color-primary);"
        >
          <span
            class="flex items-center justify-center w-7 h-7 rounded-full"
            style="background: var(--color-text-always-dark);"
          >
            <ArrowRight :size="13" color="white" :stroke-width="2.5" />
          </span>
          <span class="text-[12px] font-semibold" style="color: var(--color-banner-text);">See Event</span>
        </button>
      </div>

      <!-- Divider -->
      <div class="w-px my-4" style="background: var(--color-bg);" />

      <!-- Right: Event Info -->
      <div class="flex flex-col justify-center p-5 flex-1 relative" style="border-radius: 0 24px 24px 0;">
        <!-- Slight tint to differentiate the right panel -->
        <div class="absolute inset-0 bg-black/5 mix-blend-multiply pointer-events-none" style="border-radius: 0 24px 24px 0;"></div>
        
        <div class="relative z-10">
          <template v-if="latestEvent">
            <h4
              class="text-[14px] font-bold leading-tight mb-2"
              style="color: var(--color-primary);"
            >
              {{ latestEvent.name }}
            </h4>
            <p class="text-[12px] leading-relaxed mb-2" style="color: var(--color-text-secondary);">
              {{ truncate(latestEvent.location, 80) }}
            </p>
            <p class="text-[11px] font-medium" style="color: var(--color-text-muted);">
              {{ formatDate(latestEvent.start_datetime) }}
            </p>
          </template>
          <template v-else>
            <p class="text-[13px]" style="color: var(--color-text-muted);">No upcoming events</p>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ArrowRight } from 'lucide-vue-next'

const props = defineProps({
  events: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['see-event'])

const latestEvent = computed(() => {
  const upcoming = props.events.filter((e) => e.status === 'upcoming' || e.status === 'ongoing')
  return upcoming[0] ?? null
})

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '…' : str
}

function formatDate(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  return d.toLocaleDateString('en-PH', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>
