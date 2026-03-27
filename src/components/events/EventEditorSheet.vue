<template>
  <Transition name="event-editor-sheet">
    <div
      v-if="isOpen"
      class="event-editor__backdrop"
      @click.self="emit('close')"
    >
      <section class="event-editor__sheet">
        <header class="event-editor__header">
          <div>
            <h2 class="event-editor__title">{{ title }}</h2>
            <p class="event-editor__copy">{{ description }}</p>
          </div>

          <button
            class="event-editor__close"
            type="button"
            aria-label="Close event editor"
            :disabled="saving"
            @click="emit('close')"
          >
            <X :size="18" />
          </button>
        </header>

        <form class="event-editor__form" @submit.prevent="handleSubmit">
          <div class="event-editor__grid">
            <label class="event-editor__field event-editor__field--wide">
              <span class="event-editor__field-label">Event Name</span>
              <input
                v-model="draft.name"
                class="event-editor__field-input"
                type="text"
                name="event_name"
                placeholder="e.g. Campus Orientation"
              >
            </label>

            <label class="event-editor__field event-editor__field--wide">
              <span class="event-editor__field-label">Location</span>
              <input
                v-model="draft.location"
                class="event-editor__field-input"
                type="text"
                name="event_location"
                placeholder="e.g. University Campus"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Start date & time</span>
              <input
                v-model="draft.startTime"
                class="event-editor__field-input"
                type="datetime-local"
                name="event_start_datetime"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">End date & time</span>
              <input
                v-model="draft.endTime"
                class="event-editor__field-input"
                type="datetime-local"
                name="event_end_datetime"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Status</span>
              <select
                v-model="draft.status"
                class="event-editor__field-input event-editor__field-input--select"
                name="event_status"
              >
                <option
                  v-for="option in statusOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Max GPS Accuracy</span>
              <input
                v-model="draft.maxAccuracyM"
                class="event-editor__field-input"
                type="number"
                min="1"
                step="1"
                name="event_geo_max_accuracy"
                placeholder="e.g. 50"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Open check-in before start</span>
              <input
                v-model="draft.earlyCheckInMinutes"
                class="event-editor__field-input"
                type="number"
                min="0"
                step="1"
                name="event_early_check_in_minutes"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Mark late after</span>
              <input
                v-model="draft.lateThresholdMinutes"
                class="event-editor__field-input"
                type="number"
                min="0"
                step="1"
                name="event_late_threshold_minutes"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Sign-out grace</span>
              <input
                v-model="draft.signOutGraceMinutes"
                class="event-editor__field-input"
                type="number"
                min="0"
                step="1"
                name="event_sign_out_grace_minutes"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Sign-out open delay</span>
              <input
                v-model="draft.signOutOpenDelayMinutes"
                class="event-editor__field-input"
                type="number"
                min="0"
                step="1"
                name="event_sign_out_open_delay_minutes"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Latitude</span>
              <input
                v-model="draft.latitude"
                class="event-editor__field-input"
                type="number"
                step="any"
                name="event_geo_latitude"
                placeholder="e.g. 8.656681"
              >
            </label>

            <label class="event-editor__field">
              <span class="event-editor__field-label">Longitude</span>
              <input
                v-model="draft.longitude"
                class="event-editor__field-input"
                type="number"
                step="any"
                name="event_geo_longitude"
                placeholder="e.g. 123.423068"
              >
            </label>

            <label class="event-editor__field event-editor__field--wide">
              <span class="event-editor__field-label">Allowed Radius</span>
              <input
                v-model="draft.radiusM"
                class="event-editor__field-input"
                type="number"
                min="1"
                step="1"
                name="event_geo_radius_m"
                placeholder="e.g. 100"
              >
            </label>
          </div>

          <label class="event-editor__checkbox">
            <input
              v-model="draft.geoRequired"
              type="checkbox"
              name="event_geo_required"
            >
            <span class="event-editor__checkbox-mark"></span>
            Require students to be inside the event geofence to sign in.
          </label>

          <p class="event-editor__note">
            This form updates the real backend event fields supported by `PATCH /api/events/{id}`.
          </p>

          <p
            v-if="feedbackMessage"
            class="event-editor__feedback"
            :class="{ 'event-editor__feedback--error': feedbackTone === 'error' }"
          >
            {{ feedbackMessage }}
          </p>

          <div class="event-editor__actions">
            <button
              class="event-editor__secondary"
              type="button"
              :disabled="saving"
              @click="emit('close')"
            >
              Cancel
            </button>

            <button
              class="event-editor__primary"
              type="submit"
              :disabled="saving"
            >
              {{ saving ? 'Saving...' : submitLabel }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </Transition>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import {
  buildEventUpdatePayloadFromDraft,
  createEventEditorDraft,
  EVENT_STATUS_OPTIONS,
} from '@/services/eventEditor.js'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false,
  },
  event: {
    type: Object,
    default: null,
  },
  title: {
    type: String,
    default: 'Edit Event',
  },
  description: {
    type: String,
    default: 'Update the event details using the live backend event fields.',
  },
  submitLabel: {
    type: String,
    default: 'Save Event',
  },
  saving: {
    type: Boolean,
    default: false,
  },
  errorMessage: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close', 'save'])

const draft = ref(createEventEditorDraft())
const localError = ref('')

const statusOptions = EVENT_STATUS_OPTIONS

const feedbackMessage = computed(() => localError.value || props.errorMessage)
const feedbackTone = computed(() => (localError.value || props.errorMessage ? 'error' : 'info'))

watch(
  () => [props.isOpen, props.event],
  ([isOpen]) => {
    if (!isOpen) return
    draft.value = createEventEditorDraft(props.event)
    localError.value = ''
  },
  { immediate: true }
)

function handleSubmit() {
  try {
    localError.value = ''
    emit('save', buildEventUpdatePayloadFromDraft(draft.value))
  } catch (error) {
    localError.value = error?.message || 'Unable to prepare the event update.'
  }
}
</script>

<style scoped>
.event-editor__backdrop{position:fixed;inset:0;z-index:120;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(10,10,10,.32);backdrop-filter:blur(10px)}
.event-editor__sheet{width:min(100%,760px);max-height:calc(100dvh - 48px);overflow:auto;padding:28px;border-radius:34px;background:var(--color-surface);box-shadow:0 22px 56px rgba(0,0,0,.18)}
.event-editor__header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}
.event-editor__title{margin:0;font-size:26px;font-weight:800;letter-spacing:-.04em;color:var(--color-text-always-dark,#111827)}
.event-editor__copy{margin:8px 0 0;font-size:13px;line-height:1.5;color:var(--color-text-secondary,#6b7280)}
.event-editor__close{width:42px;height:42px;border:none;border-radius:999px;background:rgba(17,24,39,.06);color:var(--color-text-always-dark,#111827);display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0}
.event-editor__form{display:flex;flex-direction:column;gap:18px}
.event-editor__grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.event-editor__field{display:flex;flex-direction:column;gap:8px}
.event-editor__field--wide{grid-column:1 / -1}
.event-editor__field-label{font-size:12px;font-weight:800;letter-spacing:.02em;color:var(--color-text-secondary,#6b7280);text-transform:uppercase}
.event-editor__field-input{width:100%;min-height:48px;padding:12px 16px;border:1px solid rgba(17,24,39,.1);border-radius:18px;background:#fff;font-size:14px;font-weight:600;color:var(--color-text-always-dark,#111827);outline:none;box-sizing:border-box}
.event-editor__field-input:focus{border-color:color-mix(in srgb,var(--color-primary,#3b82f6) 55%,white);box-shadow:0 0 0 4px color-mix(in srgb,var(--color-primary,#3b82f6) 16%,transparent)}
.event-editor__field-input--select{appearance:none}
.event-editor__checkbox{display:flex;align-items:flex-start;gap:12px;font-size:14px;font-weight:600;line-height:1.5;color:var(--color-text-always-dark,#111827);cursor:pointer}
.event-editor__checkbox input{display:none}
.event-editor__checkbox-mark{position:relative;flex-shrink:0;width:22px;height:22px;border-radius:999px;border:1.5px solid rgba(17,24,39,.14);background:#fff}
.event-editor__checkbox input:checked + .event-editor__checkbox-mark::after{content:'';position:absolute;inset:5px;border-radius:999px;background:var(--color-primary,#3b82f6)}
.event-editor__note{margin:0;font-size:12px;line-height:1.6;color:var(--color-text-secondary,#6b7280)}
.event-editor__feedback{margin:0;padding:12px 14px;border-radius:16px;background:rgba(37,99,235,.08);font-size:13px;font-weight:700;color:#1d4ed8}
.event-editor__feedback--error{background:rgba(220,38,38,.08);color:#b91c1c}
.event-editor__actions{display:flex;justify-content:flex-end;gap:12px}
.event-editor__secondary,.event-editor__primary{border:none;border-radius:999px;padding:14px 22px;font-size:14px;font-weight:800;cursor:pointer}
.event-editor__secondary{background:rgba(17,24,39,.06);color:var(--color-text-always-dark,#111827)}
.event-editor__primary{background:var(--color-primary,#3b82f6);color:var(--color-primary-text,#fff)}
.event-editor__secondary:disabled,.event-editor__primary:disabled,.event-editor__close:disabled{opacity:.6;cursor:not-allowed}
.event-editor-sheet-enter-active,.event-editor-sheet-leave-active{transition:opacity .24s ease}
.event-editor-sheet-enter-active .event-editor__sheet,.event-editor-sheet-leave-active .event-editor__sheet{transition:transform .36s cubic-bezier(.22,1,.36,1),opacity .24s ease}
.event-editor-sheet-enter-from,.event-editor-sheet-leave-to{opacity:0}
.event-editor-sheet-enter-from .event-editor__sheet,.event-editor-sheet-leave-to .event-editor__sheet{transform:translateY(24px);opacity:0}

@media (max-width: 760px){
  .event-editor__backdrop{padding:12px}
  .event-editor__sheet{width:100%;max-height:calc(100dvh - 24px);padding:22px 18px 18px;border-radius:30px}
  .event-editor__grid{grid-template-columns:1fr}
  .event-editor__field--wide{grid-column:auto}
  .event-editor__actions{flex-direction:column}
  .event-editor__secondary,.event-editor__primary{width:100%}
}
</style>
