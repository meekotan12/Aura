<template>
  <section class="sg-sub-page">
    <header class="sg-sub-header dashboard-enter dashboard-enter--1">
      <button class="sg-sub-back" type="button" @click="goBack">
        <ArrowLeft :size="20" />
      </button>
      <h1 class="sg-sub-title">Manage Members</h1>
    </header>

    <div v-if="isLoading" class="sg-sub-loading dashboard-enter dashboard-enter--2">
      <p>Loading members...</p>
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
            placeholder="Search members"
          />
          <Search :size="14" style="color: var(--color-text-muted);" />
        </div>
        <button class="sg-sub-action" type="button" @click="openAddSheet">
          <Plus :size="16" />
          <span>Add</span>
        </button>
      </div>

      <div class="sg-sub-card dashboard-enter dashboard-enter--3">
        <h2 class="sg-sub-card-title">Members ({{ filteredMembers.length }})</h2>
        <div v-if="filteredMembers.length" class="sg-members-list">
          <article
            v-for="member in filteredMembers"
            :key="member.id"
            class="sg-member-row"
            @click="openMemberDetail(member)"
          >
            <div class="sg-member-info">
              <span class="sg-member-name">{{ member.fullName }}</span>
              <span class="sg-member-position">{{ member.position }}</span>
            </div>
            <button
              class="sg-member-edit-btn"
              type="button"
              aria-label="Edit member"
              @click.stop="startEditing(member)"
            >
              <SquarePen :size="16" />
            </button>
          </article>
        </div>
        <p v-else class="sg-sub-empty">No members match your search.</p>
      </div>
    </template>

    <!-- Add/Edit Member Sheet -->
    <Transition name="sg-sheet">
      <div
        v-if="isSheetOpen"
        class="sg-sheet-backdrop"
        @click.self="closeSheet"
      >
        <div class="sg-sheet">
          <StudentCouncilMemberStage
            class="sg-sheet-content"
            :title="editingMemberId ? 'Edit Member' : 'Add Member'"
            :search-query="memberDraft.searchQuery"
            :selected-student="selectedStudent"
            :position="memberDraft.position"
            :filtered-students="candidateResults"
            :search-expanded="isCandidateSearchOpen && !selectedStudent"
            :show-permissions="showPermissions"
            :permission-catalog="permissionCatalog"
            :selected-permission-ids="memberDraft.permissionIds"
            :submit-label="submitLabel"
            :submit-disabled="submitDisabled"
            :is-editing="Boolean(editingMemberId)"
            :show-delete="Boolean(editingMemberId)"
            :delete-disabled="isDeleting || isSaving"
            delete-label="Delete member"
            show-close
            @cancel="closeSheet"
            @delete="handleDelete"
            @focus-search="isCandidateSearchOpen = true"
            @select-student="selectCandidate"
            @submit="handleSubmit"
            @toggle-permission="togglePermission"
            @update:position="memberDraft.position = $event"
            @update:searchQuery="updateCandidateQuery"
          />
        </div>
      </div>
    </Transition>

    <!-- Member Detail Sheet -->
    <Transition name="sg-sheet">
      <div
        v-if="isDetailOpen && detailMember"
        class="sg-sheet-backdrop"
        @click.self="closeDetail"
      >
        <div class="sg-sheet sg-sheet--detail">
          <section class="sg-detail">
            <div class="sg-detail-header">
              <h2 class="sg-detail-title">Member</h2>
              <button class="sg-detail-close" type="button" @click="closeDetail">
                <X :size="18" />
              </button>
            </div>
            <div class="sg-detail-field">
              <span class="sg-detail-label">Name</span>
              <div class="sg-detail-value">{{ detailMember.fullName }}</div>
            </div>
            <div class="sg-detail-field">
              <span class="sg-detail-label">ID Number</span>
              <div class="sg-detail-value">{{ detailMember.studentId }}</div>
            </div>
            <div class="sg-detail-field">
              <span class="sg-detail-label">Position</span>
              <div class="sg-detail-value">{{ detailMember.position }}</div>
            </div>
            <div class="sg-detail-field">
              <span class="sg-detail-label">Permissions</span>
              <div class="sg-detail-perms">
                <span
                  v-for="perm in detailMemberPermLabels"
                  :key="perm"
                  class="sg-detail-perm"
                >{{ perm }}</span>
                <span v-if="!detailMemberPermLabels.length" class="sg-detail-perm sg-detail-perm--empty">
                  No permissions assigned
                </span>
              </div>
            </div>
            <div class="sg-detail-actions">
              <button class="sg-sub-action" type="button" @click="startEditing(detailMember)">
                <SquarePen :size="16" />
                <span>Edit Member</span>
              </button>
              <button
                class="sg-detail-delete"
                type="button"
                :disabled="isDeleting"
                @click="handleDeleteDetail"
              >
                {{ isDeleting ? 'Deleting...' : 'Delete Member' }}
              </button>
            </div>
          </section>
        </div>
      </div>
    </Transition>
  </section>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Search, Plus, SquarePen, X } from 'lucide-vue-next'
import StudentCouncilMemberStage from '@/components/council/StudentCouncilMemberStage.vue'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { useSgDashboard } from '@/composables/useSgDashboard.js'
import {
  getGovernanceUnitDetail,
  assignGovernanceMember,
  updateGovernanceMember,
  deleteGovernanceMember,
  searchGovernanceStudentCandidates,
} from '@/services/backendApi.js'
import {
  createEmptyCouncilMemberDraft,
  defaultStudentCouncilPermissionCatalog,
  normalizePermissionCatalog,
  formatGovernancePermissionLabel,
  mapGovernanceMemberToCouncilMember,
  mapGovernanceStudentCandidateToCouncilCandidate,
  mapUiPermissionIdsToBackend,
} from '@/services/studentCouncilManagement.js'
import { resolvePreferredGovernanceUnit } from '@/services/governanceScope.js'

const router = useRouter()
const { apiBaseUrl } = useDashboardSession()
const { isLoading: sgLoading, error: sgError, permissionCodes } = useSgDashboard()

const isLoading = ref(true)
const loadError = ref('')
const members = ref([])
const searchQuery = ref('')
const isSheetOpen = ref(false)
const isDetailOpen = ref(false)
const isSaving = ref(false)
const isDeleting = ref(false)
const editingMemberId = ref(null)
const detailMember = ref(null)
const isCandidateSearchOpen = ref(false)
const showPermissions = ref(false)
const candidateResults = ref([])
const governanceUnitId = ref(null)
let candidateTimer = null

const memberDraft = ref({ ...createEmptyCouncilMemberDraft(), searchQuery: '', selectedStudent: null })
const permissionCatalog = computed(() => normalizePermissionCatalog(defaultStudentCouncilPermissionCatalog))

const selectedStudent = computed(() => {
  const id = Number(memberDraft.value.studentId)
  return candidateResults.value.find((c) => c.userId === id) || memberDraft.value.selectedStudent || null
})

const submitLabel = computed(() => {
  if (isSaving.value) return editingMemberId.value ? 'Saving...' : 'Adding...'
  if (!showPermissions.value) return 'Continue'
  return editingMemberId.value ? 'Save Student' : 'Add Student'
})

const submitDisabled = computed(() => {
  if (!selectedStudent.value?.userId || !memberDraft.value.position.trim() || isSaving.value) return true
  if (!showPermissions.value) return false
  return memberDraft.value.permissionIds.length === 0
})

const filteredMembers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return members.value
  return members.value.filter((m) =>
    [m.studentId, m.fullName, m.position].filter(Boolean).join(' ').toLowerCase().includes(q)
  )
})

const detailMemberPermLabels = computed(() => {
  if (!detailMember.value) return []
  return (detailMember.value.permissionIds || [])
    .map((id) => formatGovernancePermissionLabel(id))
    .filter(Boolean)
})

// Resolve governance unit from access
const { isLoading: dashLoading } = useSgDashboard()
watch(
  [() => sgLoading.value, () => sgError.value],
  () => {
    if (sgLoading.value) return
    if (sgError.value) {
      loadError.value = sgError.value
      isLoading.value = false
    }
  },
  { immediate: true }
)

watch(
  [apiBaseUrl, () => sgLoading.value],
  async ([url]) => {
    if (!url || sgLoading.value) return
    await loadUnit(url)
  },
  { immediate: true }
)

async function loadUnit(url) {
  isLoading.value = true
  loadError.value = ''
  const token = localStorage.getItem('aura_token') || ''
  try {
    const access = await import('@/services/backendApi.js').then((m) => m.getGovernanceAccess(url, token))
    const governanceUnit = resolvePreferredGovernanceUnit(access, {
      requiredPermissionCode: 'manage_members',
    })
    if (!governanceUnit) { loadError.value = 'No governance unit found.'; return }
    governanceUnitId.value = governanceUnit.governance_unit_id
    const detail = await getGovernanceUnitDetail(url, token, governanceUnit.governance_unit_id)
    members.value = (detail?.members || []).map(mapGovernanceMemberToCouncilMember)
  } catch (e) {
    loadError.value = e?.message || 'Unable to load members.'
  } finally {
    isLoading.value = false
  }
}

async function reload() {
  if (apiBaseUrl.value) await loadUnit(apiBaseUrl.value)
}

function goBack() { router.push('/sg') }

function resetDraft() {
  memberDraft.value = { ...createEmptyCouncilMemberDraft(), searchQuery: '', selectedStudent: null }
  editingMemberId.value = null
  showPermissions.value = false
  isCandidateSearchOpen.value = false
  candidateResults.value = []
}

function openAddSheet() { resetDraft(); isSheetOpen.value = true }
function closeSheet() { isSheetOpen.value = false; resetDraft() }
function openMemberDetail(m) { detailMember.value = m; isDetailOpen.value = true }
function closeDetail() { isDetailOpen.value = false; detailMember.value = null }

function startEditing(member) {
  closeDetail()
  resetDraft()
  editingMemberId.value = member.id
  memberDraft.value.studentId = member.userId
  memberDraft.value.position = member.position || ''
  memberDraft.value.permissionIds = [...(member.permissionIds || [])]
  memberDraft.value.searchQuery = member.fullName
  memberDraft.value.selectedStudent = { userId: member.userId, fullName: member.fullName, studentId: member.studentId }
  showPermissions.value = true
  isSheetOpen.value = true
}

function selectCandidate(candidate) {
  memberDraft.value.studentId = Number(candidate.userId)
  memberDraft.value.searchQuery = candidate.fullName
  memberDraft.value.selectedStudent = candidate
  isCandidateSearchOpen.value = false
  candidateResults.value = [candidate]
}

function togglePermission(id) {
  const next = new Set(memberDraft.value.permissionIds)
  if (next.has(id)) next.delete(id); else next.add(id)
  memberDraft.value.permissionIds = [...next]
}

function updateCandidateQuery(val) {
  memberDraft.value.searchQuery = val
  isCandidateSearchOpen.value = true
}

watch(
  [() => memberDraft.value.searchQuery, isCandidateSearchOpen, selectedStudent],
  ([query, open, selected]) => {
    clearTimeout(candidateTimer)
    if (!open || selected) return
    candidateTimer = setTimeout(() => searchCandidates(query), 200)
  }
)

onBeforeUnmount(() => clearTimeout(candidateTimer))

async function searchCandidates(query) {
  if (!apiBaseUrl.value || !governanceUnitId.value) return
  try {
    const token = localStorage.getItem('aura_token') || ''
    const results = await searchGovernanceStudentCandidates(apiBaseUrl.value, token, {
      q: query || null,
      governance_unit_id: governanceUnitId.value,
      limit: 12,
    })
    candidateResults.value = results
      .map(mapGovernanceStudentCandidateToCouncilCandidate)
      .filter((c) => !c.isCurrentGovernanceMember)
      .filter((c) => !members.value.some((m) => m.userId === c.userId))
  } catch { candidateResults.value = [] }
}

async function handleSubmit() {
  if (submitDisabled.value) return
  if (!showPermissions.value) { showPermissions.value = true; return }

  isSaving.value = true
  const token = localStorage.getItem('aura_token') || ''
  const permCodes = mapUiPermissionIdsToBackend(memberDraft.value.permissionIds)

  try {
    if (editingMemberId.value) {
      await updateGovernanceMember(apiBaseUrl.value, token, editingMemberId.value, {
        user_id: Number(memberDraft.value.studentId),
        position_title: memberDraft.value.position.trim(),
        permission_codes: permCodes,
      })
    } else {
      await assignGovernanceMember(apiBaseUrl.value, token, governanceUnitId.value, {
        user_id: Number(memberDraft.value.studentId),
        position_title: memberDraft.value.position.trim(),
        permission_codes: permCodes,
      })
    }
    closeSheet()
    await reload()
  } catch (e) {
    loadError.value = e?.message || 'Unable to save member.'
  } finally {
    isSaving.value = false
  }
}

async function handleDelete() {
  if (!editingMemberId.value || isDeleting.value) return
  isDeleting.value = true
  try {
    const token = localStorage.getItem('aura_token') || ''
    await deleteGovernanceMember(apiBaseUrl.value, token, editingMemberId.value)
    closeSheet()
    await reload()
  } catch (e) {
    loadError.value = e?.message || 'Unable to delete member.'
  } finally { isDeleting.value = false }
}

async function handleDeleteDetail() {
  if (!detailMember.value?.id || isDeleting.value) return
  isDeleting.value = true
  try {
    const token = localStorage.getItem('aura_token') || ''
    await deleteGovernanceMember(apiBaseUrl.value, token, detailMember.value.id)
    closeDetail()
    await reload()
  } catch (e) {
    loadError.value = e?.message || 'Unable to delete member.'
  } finally { isDeleting.value = false }
}
</script>

<style scoped>
@import '@/assets/css/sg-sub-views.css';

.sg-members-list { display: flex; flex-direction: column; gap: 2px; }
.sg-member-row { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-radius: 14px; cursor: pointer; transition: background 0.15s; }
.sg-member-row:hover { background: var(--color-surface-border); }
.sg-member-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.sg-member-name { font-size: 14px; font-weight: 600; color: var(--color-text-primary); }
.sg-member-position { font-size: 12px; color: var(--color-text-muted); }
.sg-member-edit-btn { background: none; border: none; color: var(--color-text-muted); cursor: pointer; padding: 6px; border-radius: 8px; }
.sg-member-edit-btn:hover { color: var(--color-primary); }

.sg-detail { padding: 24px; }
.sg-detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.sg-detail-title { font-size: 20px; font-weight: 800; color: var(--color-text-primary); }
.sg-detail-close { background: none; border: none; cursor: pointer; color: var(--color-text-muted); padding: 4px; }
.sg-detail-field { margin-bottom: 16px; }
.sg-detail-label { font-size: 12px; font-weight: 600; color: var(--color-primary); display: block; margin-bottom: 4px; }
.sg-detail-value { font-size: 14px; font-weight: 500; color: var(--color-text-primary); background: var(--color-surface-border); padding: 10px 14px; border-radius: 12px; }
.sg-detail-perms { display: flex; flex-wrap: wrap; gap: 6px; }
.sg-detail-perm { font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: 20px; background: var(--color-primary); color: var(--color-banner-text); }
.sg-detail-perm--empty { background: var(--color-surface-border); color: var(--color-text-muted); }
.sg-detail-actions { display: flex; gap: 12px; margin-top: 24px; }
.sg-detail-delete { background: none; border: none; color: #e74c3c; font-size: 13px; font-weight: 600; cursor: pointer; }
.sg-detail-delete:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
