<template>
  <section class="sg-sub-page">
    <header class="sg-sub-header dashboard-enter dashboard-enter--1">
      <button class="sg-sub-back" type="button" @click="goBack">
        <ArrowLeft :size="20" />
      </button>
      <h1 class="sg-sub-title">Announcements</h1>
    </header>

    <div v-if="isLoading" class="sg-sub-loading dashboard-enter dashboard-enter--2">
      <p>Loading announcements...</p>
    </div>

    <div v-else-if="loadError" class="sg-sub-error dashboard-enter dashboard-enter--2">
      <p>{{ loadError }}</p>
      <button class="sg-sub-action" type="button" @click="reload">Try Again</button>
    </div>

    <template v-else>
      <div class="sg-sub-toolbar dashboard-enter dashboard-enter--2">
        <div class="sg-sub-search-shell">
          <input
            v-model="searchQuery"
            type="text"
            class="sg-sub-search-input"
            placeholder="Search announcements"
          />
          <Search :size="14" style="color: var(--color-text-muted);" />
        </div>
        <button class="sg-sub-action" type="button" @click="openCreate">
          <Plus :size="16" />
          <span>New</span>
        </button>
      </div>

      <div class="sg-sub-card dashboard-enter dashboard-enter--3">
        <h2 class="sg-sub-card-title">Announcements ({{ filteredAnnouncements.length }})</h2>
        <div v-if="filteredAnnouncements.length" class="sg-ann-list">
          <article
            v-for="ann in filteredAnnouncements"
            :key="ann.id"
            class="sg-ann-row"
          >
            <div class="sg-ann-info">
              <h3 class="sg-ann-title">{{ ann.title }}</h3>
              <p class="sg-ann-body">{{ ann.body }}</p>
              <div class="sg-ann-meta">
                <span class="sg-ann-status" :class="`sg-ann-status--${ann.status}`">{{ ann.status }}</span>
                <span class="sg-ann-date">{{ formatDate(ann.created_at) }}</span>
              </div>
            </div>
            <div class="sg-ann-actions">
              <button class="sg-ann-btn" type="button" @click="startEdit(ann)">
                <SquarePen :size="14" />
              </button>
              <button class="sg-ann-btn sg-ann-btn--danger" type="button" @click="handleDelete(ann)">
                <Trash2 :size="14" />
              </button>
            </div>
          </article>
        </div>
        <p v-else class="sg-sub-empty">No announcements yet.</p>
      </div>
    </template>

    <!-- Create/Edit Sheet -->
    <Transition name="sg-sheet">
      <div v-if="isFormOpen" class="sg-sheet-backdrop" @click.self="closeForm">
        <div class="sg-sheet">
          <form class="sg-ann-form" @submit.prevent="handleSave">
            <h2 class="sg-ann-form-title">{{ editingId ? 'Edit Announcement' : 'New Announcement' }}</h2>
            <label class="sg-ann-field">
              <span class="sg-ann-field-label">Title</span>
              <input v-model="draft.title" class="sg-ann-field-input" type="text" placeholder="Announcement title" />
            </label>
            <label class="sg-ann-field">
              <span class="sg-ann-field-label">Body</span>
              <textarea v-model="draft.body" class="sg-ann-field-input sg-ann-field-input--textarea" placeholder="Write your announcement..." rows="4" />
            </label>
            <label class="sg-ann-field">
              <span class="sg-ann-field-label">Status</span>
              <select v-model="draft.status" class="sg-ann-field-input">
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="archived">Archived</option>
              </select>
            </label>
            <p v-if="formError" class="sg-ann-form-error">{{ formError }}</p>
            <div class="sg-ann-form-actions">
              <button class="sg-ann-form-cancel" type="button" @click="closeForm">Cancel</button>
              <button class="sg-sub-action" type="submit" :disabled="isSaving || !draft.title.trim() || !draft.body.trim()">
                {{ isSaving ? 'Saving...' : (editingId ? 'Save' : 'Create') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>
  </section>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Search, Plus, SquarePen, Trash2 } from 'lucide-vue-next'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { useSgDashboard } from '@/composables/useSgDashboard.js'
import {
  getGovernanceAccess,
  getGovernanceAnnouncements,
  createGovernanceAnnouncement,
  updateGovernanceAnnouncement,
  deleteGovernanceAnnouncement,
} from '@/services/backendApi.js'
import { resolvePreferredGovernanceUnit } from '@/services/governanceScope.js'

const router = useRouter()
const { apiBaseUrl } = useDashboardSession()
const { isLoading: sgLoading } = useSgDashboard()

const isLoading = ref(true)
const loadError = ref('')
const announcements = ref([])
const searchQuery = ref('')
const isFormOpen = ref(false)
const isSaving = ref(false)
const formError = ref('')
const editingId = ref(null)
const draft = ref({ title: '', body: '', status: 'draft' })
const governanceUnitId = ref(null)

const filteredAnnouncements = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return announcements.value
  return announcements.value.filter((a) =>
    [a.title, a.body, a.status].filter(Boolean).join(' ').toLowerCase().includes(q)
  )
})

function formatDate(d) {
  if (!d) return ''
  try { return new Date(d).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) }
  catch { return d }
}

function goBack() { router.push('/sg') }

watch(
  [apiBaseUrl, () => sgLoading.value],
  async ([url]) => {
    if (!url || sgLoading.value) return
    await loadData(url)
  },
  { immediate: true }
)

async function loadData(url) {
  isLoading.value = true
  loadError.value = ''
  try {
    const token = localStorage.getItem('aura_token') || ''
    const access = await getGovernanceAccess(url, token)
    const governanceUnit = resolvePreferredGovernanceUnit(access, {
      requiredPermissionCode: 'manage_announcements',
    })
    if (!governanceUnit) { loadError.value = 'No governance unit found.'; return }
    governanceUnitId.value = governanceUnit.governance_unit_id
    announcements.value = await getGovernanceAnnouncements(url, token, governanceUnit.governance_unit_id)
  } catch (e) {
    loadError.value = e?.message || 'Unable to load announcements.'
  } finally { isLoading.value = false }
}

async function reload() { if (apiBaseUrl.value) await loadData(apiBaseUrl.value) }

function openCreate() {
  editingId.value = null
  draft.value = { title: '', body: '', status: 'draft' }
  formError.value = ''
  isFormOpen.value = true
}

function startEdit(ann) {
  editingId.value = ann.id
  draft.value = { title: ann.title, body: ann.body, status: ann.status || 'draft' }
  formError.value = ''
  isFormOpen.value = true
}

function closeForm() { isFormOpen.value = false; editingId.value = null }

async function handleSave() {
  if (isSaving.value || !draft.value.title.trim() || !draft.value.body.trim()) return
  isSaving.value = true
  formError.value = ''
  const token = localStorage.getItem('aura_token') || ''
  const payload = { title: draft.value.title.trim(), body: draft.value.body.trim(), status: draft.value.status }
  try {
    if (editingId.value) {
      await updateGovernanceAnnouncement(apiBaseUrl.value, token, editingId.value, payload)
    } else {
      await createGovernanceAnnouncement(apiBaseUrl.value, token, governanceUnitId.value, payload)
    }
    closeForm()
    await reload()
  } catch (e) { formError.value = e?.message || 'Unable to save.' }
  finally { isSaving.value = false }
}

async function handleDelete(ann) {
  if (!confirm('Delete this announcement?')) return
  try {
    const token = localStorage.getItem('aura_token') || ''
    await deleteGovernanceAnnouncement(apiBaseUrl.value, token, ann.id)
    await reload()
  } catch (e) { loadError.value = e?.message || 'Unable to delete.' }
}
</script>

<style scoped>
@import '@/assets/css/sg-sub-views.css';

.sg-ann-list { display: flex; flex-direction: column; gap: 10px; }
.sg-ann-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 14px 16px; border-radius: 14px; background: var(--color-surface-border); }
.sg-ann-info { flex: 1; min-width: 0; }
.sg-ann-title { font-size: 14px; font-weight: 700; color: var(--color-text-primary); margin-bottom: 4px; }
.sg-ann-body { font-size: 13px; color: var(--color-text-muted); line-height: 1.4; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.sg-ann-meta { display: flex; gap: 8px; align-items: center; margin-top: 6px; }
.sg-ann-status { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 10px; text-transform: capitalize; }
.sg-ann-status--draft { background: #f0ad4e33; color: #f0ad4e; }
.sg-ann-status--published { background: #27ae6033; color: #27ae60; }
.sg-ann-status--archived { background: #95a5a633; color: #95a5a6; }
.sg-ann-date { font-size: 11px; color: var(--color-text-muted); }
.sg-ann-actions { display: flex; gap: 6px; flex-shrink: 0; }
.sg-ann-btn { background: none; border: none; color: var(--color-text-muted); cursor: pointer; padding: 6px; border-radius: 8px; }
.sg-ann-btn:hover { color: var(--color-primary); }
.sg-ann-btn--danger:hover { color: #e74c3c; }

.sg-ann-form { padding: 24px; display: flex; flex-direction: column; gap: 16px; }
.sg-ann-form-title { font-size: 20px; font-weight: 800; color: var(--color-text-primary); }
.sg-ann-field { display: flex; flex-direction: column; gap: 6px; }
.sg-ann-field-label { font-size: 12px; font-weight: 600; color: var(--color-primary); }
.sg-ann-field-input { background: var(--color-surface-border); border: none; border-radius: 12px; padding: 10px 14px; font-size: 14px; color: var(--color-text-primary); outline: none; font-family: inherit; }
.sg-ann-field-input--textarea { resize: vertical; min-height: 80px; }
.sg-ann-form-error { font-size: 13px; color: #e74c3c; }
.sg-ann-form-actions { display: flex; justify-content: flex-end; gap: 10px; }
.sg-ann-form-cancel { background: none; border: none; color: var(--color-text-muted); font-size: 13px; font-weight: 600; cursor: pointer; }
</style>
