<template>
  <section class="school-it-users">
    <div class="school-it-users__shell">
      <SchoolItTopHeader
        class="dashboard-enter dashboard-enter--1"
        :avatar-url="avatarUrl"
        :school-name="activeSchoolSettings?.school_name || activeUser?.school_name || ''"
        :display-name="displayName"
        :initials="initials"
        @logout="handleLogout"
      />

      <div class="school-it-users__body">
        <h1 class="school-it-users__title dashboard-enter dashboard-enter--2">Students</h1>

        <section class="school-it-users__search dashboard-enter dashboard-enter--3">
            <div class="school-it-users__search-row">
              <div class="school-it-users__search-wrap">
                <div class="school-it-users__search-shell" :class="{ 'school-it-users__search-shell--open': searchActive }">
                <div class="school-it-users__search-input-row">
                  <input
                    v-model="searchQuery"
                    v-bind="schoolSearchInputAttrs"
                    type="text"
                    placeholder="Search school data"
                    class="school-it-users__search-input"
                  >
                  <button class="school-it-users__search-icon" type="button" aria-label="Search">
                    <Search :size="18" />
                  </button>
                </div>

                <div class="school-it-users__search-results">
                  <div class="school-it-users__search-results-inner">
                    <template v-if="searchActive">
                      <button
                        v-for="result in searchResults"
                        :key="result.key"
                        class="school-it-users__search-result"
                        type="button"
                        @click="openSearchResult(result)"
                      >
                        <div class="school-it-users__search-result-top">
                          <span class="school-it-users__search-result-name">{{ result.name }}</span>
                          <span class="school-it-users__search-result-type">{{ result.type }}</span>
                        </div>
                        <span class="school-it-users__search-result-meta">{{ result.meta }}</span>
                      </button>
                      <p v-if="!searchResults.length" class="school-it-users__empty">No matching colleges found.</p>
                    </template>
                  </div>
                </div>
                </div>
              </div>

            <button
              v-show="!searchActive && !isAddCollegeOpen"
              class="school-it-users__add-college-pill"
              type="button"
              aria-label="Add College"
              :aria-expanded="isAddCollegeOpen ? 'true' : 'false'"
              aria-controls="school-it-users-college-panel"
              @click="openAddCollegePanel"
            >
              <Plus :size="18" :stroke-width="2.4" />
              <span class="school-it-users__add-college-copy">Add<br>College</span>
            </button>
          </div>

          <Transition
            name="school-it-users-college-panel"
            @before-enter="onCollegePanelBeforeEnter"
            @enter="onCollegePanelEnter"
            @after-enter="onCollegePanelAfterEnter"
            @before-leave="onCollegePanelBeforeLeave"
            @leave="onCollegePanelLeave"
            @after-leave="onCollegePanelAfterLeave"
          >
            <div
              v-if="isAddCollegeOpen && !searchActive"
              id="school-it-users-college-panel"
              class="school-it-users__college-panel"
              role="region"
              :aria-label="collegePanelAriaLabel"
            >
              <div class="school-it-users__college-panel-inner">
                <div class="school-it-users__college-shell">
                  <div class="school-it-users__college-header">
                    <button
                      class="school-it-users__college-close"
                      type="button"
                      aria-label="Close college panel"
                      @click="closeAddCollegePanel"
                    >
                      <X :size="18" :stroke-width="2.4" />
                    </button>
                    <span class="school-it-users__college-title">{{ collegePanelTitle }}</span>
                  </div>

                  <div class="school-it-users__college-form">
                    <div class="school-it-users__college-input-shell">
                      <input
                        ref="collegeInputEl"
                        v-model="collegeDraftName"
                        class="school-it-users__college-input"
                        type="text"
                        placeholder="e.g., College of Engineering"
                        :disabled="isSavingCollege"
                        @keyup.enter="submitCollege"
                      >
                    </div>

                    <button
                      class="school-it-users__college-submit"
                      type="button"
                      :disabled="collegeSubmitDisabled"
                      @click="submitCollege"
                    >
                      {{ collegeSubmitLabel }}
                    </button>
                  </div>

                  <p
                    v-if="collegePanelMessage"
                    class="school-it-users__college-message"
                    :class="{ 'school-it-users__college-message--error': collegePanelError }"
                  >
                    {{ collegePanelMessage }}
                  </p>
                </div>
              </div>
            </div>
          </Transition>
        </section>

        <section class="school-it-users__overview dashboard-enter dashboard-enter--4">
          <article
            v-for="card in overviewCards"
            :key="card.id"
            class="school-it-users__hero-card"
            :class="[
              card.variant === 'primary'
                ? 'school-it-users__hero-card--primary'
                : 'school-it-users__hero-card--surface',
            ]"
          >
            <div class="school-it-users__hero-card-copy">
              <h2 class="school-it-users__overview-title" v-html="card.titleHtml" />
              <span v-if="card.meta" class="school-it-users__overview-meta">{{ card.meta }}</span>
            </div>

            <button
              class="school-it-users__hero-card-pill"
              :class="{
                'school-it-users__hero-card-pill--surface': card.variant === 'primary',
              }"
              type="button"
              @click="handleOverviewAction(card)"
            >
              <span class="school-it-users__hero-card-pill-icon">
                <ArrowRight :size="18" />
              </span>
              {{ card.actionLabel }}
            </button>
          </article>
        </section>

        <section
          class="school-it-users__alert dashboard-enter dashboard-enter--5"
        >
          <div class="school-it-users__alert-copy school-it-users__alert-copy--management">
            <h2
              class="school-it-users__alert-org-name"
              :class="{ 'school-it-users__alert-org-name--placeholder': !hasStudentCouncilAssigned }"
            >
              {{ studentCouncilEntryText }}
            </h2>
          </div>

          <button
            class="school-it-users__action-pill"
            type="button"
            @click="openCouncilManagement"
          >
            <span class="school-it-users__action-pill-icon">
              <ArrowRight :size="18" />
            </span>
            Manage
          </button>
        </section>

        <section class="school-it-users__alert dashboard-enter dashboard-enter--5">
          <div class="school-it-users__alert-copy school-it-users__alert-copy--management">
            <h2 class="school-it-users__alert-org-name school-it-users__alert-org-name--placeholder">
              Unassigned<br>Students
            </h2>
          </div>

          <button
            class="school-it-users__action-pill"
            type="button"
            @click="openUnassignedStudents"
          >
            <span class="school-it-users__action-pill-icon">
              <ArrowRight :size="18" />
            </span>
            Manage
          </button>
        </section>

        <section v-if="departmentCards.length" class="school-it-users__department-list">
          <div
            v-for="(department, index) in departmentCards"
            :key="department.id"
            class="school-it-users__department-swipe dashboard-enter"
            :class="[
              `dashboard-enter--${Math.min(index + 6, 9)}`,
              { 'school-it-users__department-swipe--open': isDepartmentSwipeOpen(department.id) },
            ]"
          >
            <div class="school-it-users__department-actions" aria-hidden="true">
              <button
                class="school-it-users__department-action school-it-users__department-action--delete"
                type="button"
                :disabled="isSavingCollege"
                aria-label="Delete college"
                @click.stop="deleteCollege(department)"
              >
                <Trash2 :size="18" />
              </button>

              <button
                class="school-it-users__department-action school-it-users__department-action--edit"
                type="button"
                :disabled="isSavingCollege"
                aria-label="Edit college"
                @click.stop="openEditCollegePanel(department)"
              >
                <Pencil :size="18" />
              </button>
            </div>

            <article
              class="school-it-users__department-card"
              :style="getDepartmentSwipeStyle(department.id)"
              @click.capture="handleDepartmentCardClick(department.id, $event)"
              @pointerdown="onDepartmentPointerDown(department.id, $event)"
              @pointermove="onDepartmentPointerMove(department.id, $event)"
              @pointerup="onDepartmentPointerEnd(department.id, $event)"
              @pointercancel="onDepartmentPointerCancel(department.id, $event)"
              @lostpointercapture="onDepartmentPointerCancel(department.id, $event)"
            >
              <div class="school-it-users__department-main">
                <h2 class="school-it-users__department-title">{{ department.name }}</h2>
                <button
                  class="school-it-users__action-pill school-it-users__action-pill--inline"
                  type="button"
                  @pointerdown.stop
                  @click.stop="openDepartment(department)"
                >
                  <span class="school-it-users__action-pill-icon">
                    <ArrowRight :size="18" />
                  </span>
                  View
                </button>
              </div>

              <div class="school-it-users__department-panel">
                <p class="school-it-users__department-label">Programs:</p>
                <ul v-if="department.programs.length" class="school-it-users__program-list">
                  <li
                    v-for="program in department.programs"
                    :key="program.id"
                    class="school-it-users__program-item"
                  >
                    {{ program.name }}
                  </li>
                </ul>
                <p v-else class="school-it-users__program-empty">No programs yet.</p>
              </div>
            </article>
          </div>
        </section>

        <p v-else class="school-it-users__department-empty dashboard-enter dashboard-enter--6">
          {{ departmentEmptyMessage }}
        </p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Pencil, Plus, Search, Trash2, X } from 'lucide-vue-next'
import SchoolItTopHeader from '@/components/dashboard/SchoolItTopHeader.vue'
import { schoolItPreviewData } from '@/data/schoolItPreview.js'
import { useAuth } from '@/composables/useAuth.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { usePreviewTheme } from '@/composables/usePreviewTheme.js'
import { useSchoolItWorkspaceData } from '@/composables/useSchoolItWorkspaceData.js'
import { BackendApiError, createDepartment, deleteDepartment, updateDepartment } from '@/services/backendApi.js'
import { createSearchFieldAttrs } from '@/services/searchFieldAttrs.js'
import {
  createStudentCouncilStorageKey,
  loadStudentCouncilState,
  resolveStudentCouncilAcronym,
} from '@/services/studentCouncilManagement.js'
import { filterWorkspaceEntitiesBySchool } from '@/services/workspaceScope.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const router = useRouter()
const searchQuery = ref('')
const schoolSearchInputAttrs = createSearchFieldAttrs('school-it-college-search')
const isAddCollegeOpen = ref(false)
const collegeInputEl = ref(null)
const collegeDraftName = ref('')
const collegePanelMessage = ref('')
const collegePanelError = ref(false)
const isSavingCollege = ref(false)
const collegePanelMode = ref('create')
const editingDepartmentId = ref(null)
const previewDepartmentOverrides = ref([])
const departmentSwipeOffsets = ref({})
const departmentSwipeDragId = ref(null)
const departmentSwipePointerId = ref(null)
const departmentSwipeStartX = ref(0)
const departmentSwipeStartY = ref(0)
const departmentSwipeStartOffset = ref(0)
const departmentSwipeAxisLock = ref(null)
const departmentSwipeDidDrag = ref(false)
const DEPARTMENT_SWIPE_ACTION_WIDTH = 70
const DEPARTMENT_SWIPE_OPEN_THRESHOLD = 28
const DEPARTMENT_SWIPE_GESTURE_THRESHOLD = 8

const { currentUser, schoolSettings, apiBaseUrl } = useDashboardSession()
const {
  departments,
  programs,
  users,
  campusSsgSetup,
  statuses: workspaceStatuses,
  initializeSchoolItWorkspaceData,
  refreshSchoolItWorkspaceData,
  setDepartmentsSnapshot,
} = useSchoolItWorkspaceData()
const { logout } = useAuth()

const activeUser = computed(() => props.preview ? schoolItPreviewData.user : currentUser.value)
const activeSchoolSettings = computed(() => props.preview ? schoolItPreviewData.schoolSettings : schoolSettings.value)
const activeDepartments = computed(() => props.preview ? previewDepartments.value : departments.value)
const activePrograms = computed(() => props.preview ? schoolItPreviewData.programs : programs.value)
const activeUsers = computed(() => props.preview ? schoolItPreviewData.users : users.value)

usePreviewTheme(() => props.preview, activeSchoolSettings)
const departmentsStatus = computed(() => props.preview ? 'ready' : workspaceStatuses.value?.departments || 'idle')

const schoolId = computed(() => Number(activeUser.value?.school_id ?? activeSchoolSettings.value?.school_id))
const avatarUrl = computed(() => activeUser.value?.avatar_url || '')
const displayName = computed(() => {
  const first = activeUser.value?.first_name || ''
  const middle = activeUser.value?.middle_name || ''
  const last = activeUser.value?.last_name || ''
  return [first, middle, last].filter(Boolean).join(' ') || activeUser.value?.email?.split('@')[0] || 'School IT'
})
const initials = computed(() => buildInitials(displayName.value))
const importRouteName = computed(() => props.preview ? 'PreviewSchoolItImportStudents' : 'SchoolItImportStudents')
const councilRouteName = computed(() => props.preview ? 'PreviewSchoolItStudentCouncil' : 'SchoolItStudentCouncil')
const usersRouteName = computed(() => props.preview ? 'PreviewSchoolItUsers' : 'SchoolItUsers')
const unassignedRouteName = computed(() => props.preview ? 'PreviewSchoolItUnassignedStudents' : 'SchoolItUnassignedStudents')
const departmentProgramsRouteName = computed(() => props.preview ? 'PreviewSchoolItDepartmentPrograms' : 'SchoolItDepartmentPrograms')
const previewCouncilState = computed(() => (
  props.preview
    ? loadStudentCouncilState(createStudentCouncilStorageKey(schoolId.value, true))
    : null
))
const previewDepartmentStorageKey = computed(() => (
  Number.isFinite(schoolId.value)
    ? `aura_exposed_departments_${schoolId.value}`
    : 'aura_exposed_departments'
))
const previewDepartments = computed(() => (
  previewDepartmentOverrides.value.length
    ? previewDepartmentOverrides.value
    : schoolItPreviewData.departments
))

const filteredDepartments = computed(() => filterWorkspaceEntitiesBySchool(activeDepartments.value, schoolId.value))
const filteredPrograms = computed(() => filterWorkspaceEntitiesBySchool(activePrograms.value, schoolId.value))
const filteredUsers = computed(() => filterWorkspaceEntitiesBySchool(activeUsers.value, schoolId.value))
const studentUsers = computed(() => filteredUsers.value.filter(isStudentUser))
const pendingResetUsers = computed(() => studentUsers.value.filter((user) => user.must_change_password))
const pendingResetsCountLabel = computed(() => String(pendingResetUsers.value.length))
const pendingResetsMeta = computed(() => {
  const count = pendingResetUsers.value.length
  if (count <= 0) return ''
  return `${count} pending`
})
const overviewCards = computed(() => ([
  {
    id: 'import-users',
    titleHtml: 'Import<br>User',
    variant: 'primary',
    actionLabel: 'Import',
    route: { name: importRouteName.value },
    meta: '',
  },
  {
    id: 'pending-resets',
    titleHtml: 'Pending<br>Resets',
    variant: 'surface',
    actionLabel: 'Review',
    route: { name: usersRouteName.value, query: { filter: 'pending-resets' } },
    meta: pendingResetsMeta.value,
  },
]))
const studentCouncilRecord = computed(() => {
  if (props.preview) return previewCouncilState.value?.council || null
  return campusSsgSetup.value?.unit || null
})
const studentCouncilAssignedMemberCount = computed(() => {
  if (props.preview) {
    return Array.isArray(previewCouncilState.value?.members)
      ? previewCouncilState.value.members.length
      : 0
  }

  const rawMembers = Array.isArray(campusSsgSetup.value?.unit?.members)
    ? campusSsgSetup.value.unit.members
    : []

  return rawMembers.filter((member) => member?.is_active !== false).length
})
const studentCouncilState = computed(() => (
  props.preview
    ? (studentCouncilRecord.value?.id ? 'ready' : 'absent')
    : workspaceStatuses.value?.council || 'idle'
))
const hasStudentCouncilAssigned = computed(() => (
  studentCouncilState.value === 'ready'
  && Boolean(studentCouncilRecord.value?.id)
  && studentCouncilAssignedMemberCount.value > 0
))
const studentCouncilEntryText = computed(() => {
  const acronym = resolveStudentCouncilAcronym(studentCouncilRecord.value)
  if (!acronym) return 'Student Council'
  return hasStudentCouncilAssigned.value ? `${acronym} is set` : acronym
})

const departmentCards = computed(() => (
  filteredDepartments.value
    .map((department) => ({
      ...department,
      programs: filteredPrograms.value
        .filter((program) => Array.isArray(program.department_ids) && program.department_ids.includes(Number(department.id)))
        .slice(0, 3),
    }))
    .sort((left, right) => String(left?.name || '').localeCompare(String(right?.name || '')))
))
const departmentEmptyMessage = computed(() => {
  if (['idle', 'loading'].includes(departmentsStatus.value)) {
    return 'Loading departments...'
  }

  if (departmentsStatus.value === 'blocked') {
    return 'Departments are unavailable until privileged verification is completed.'
  }

  if (departmentsStatus.value === 'error') {
    return 'Departments could not be loaded right now.'
  }

  return 'No departments please add.'
})

const searchActive = computed(() => searchQuery.value.trim().length > 0)
const resolvedEditingDepartmentId = computed(() => normalizeWorkspaceEntityId(editingDepartmentId.value))
const isEditingCollege = computed(() => collegePanelMode.value === 'edit' && resolvedEditingDepartmentId.value != null)
const collegePanelAriaLabel = computed(() => isEditingCollege.value ? 'Edit college' : 'Add college')
const collegePanelTitle = computed(() => isEditingCollege.value ? 'Edit College' : 'Add College')
const collegeSubmitLabel = computed(() => isEditingCollege.value ? 'Save' : 'Add')
const collegeSubmitDisabled = computed(() => {
  const normalizedName = collegeDraftName.value.trim()
  return isSavingCollege.value || normalizedName.length < 2 || normalizedName.length > 100
})
const departmentNameLookup = computed(() => new Map(
  filteredDepartments.value
    .map((department) => [String(department?.name || '').trim().toLowerCase(), Number(department?.id)])
    .filter(([name]) => Boolean(name))
))
const searchResults = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return []

  const departmentResults = filteredDepartments.value
    .filter((department) => department.name.toLowerCase().includes(query))
    .map((department) => ({
      key: `department-${department.id}`,
      name: department.name,
      type: 'College',
      meta: `${filteredPrograms.value.filter((program) => program.department_ids?.includes(Number(department.id))).length} linked programs`,
      action: () => openDepartment(department),
    }))

  return departmentResults.slice(0, 8)
})

const nextFrame = (callback) => requestAnimationFrame(() => requestAnimationFrame(callback))

const hasOpenDepartmentSwipe = computed(() => Object.values(departmentSwipeOffsets.value).some((offset) => offset > 0))

watch([apiBaseUrl, () => activeUser.value?.id, schoolId, () => props.preview], async ([resolvedApiBaseUrl, userId, , preview]) => {
  if (preview) return
  if (!resolvedApiBaseUrl || !userId) return
  await initializeSchoolItWorkspaceData()
}, { immediate: true })

watch(() => props.preview, (preview) => {
  if (!preview) {
    previewDepartmentOverrides.value = []
    return
  }
  previewDepartmentOverrides.value = readPreviewDepartments()
}, { immediate: true })

watch(isAddCollegeOpen, (open) => {
  if (!open) return
  nextTick(() => {
    setTimeout(() => collegeInputEl.value?.focus(), 220)
  })
})

watch(searchActive, (active) => {
  if (active) {
    isAddCollegeOpen.value = false
    closeAllDepartmentSwipes()
  }
})

watch(isAddCollegeOpen, (open) => {
  if (open) closeAllDepartmentSwipes()
})

onMounted(() => {
  document.addEventListener('pointerdown', handleDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})

function buildInitials(value) {
  const parts = String(value || '').split(' ').filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  return String(value || '').slice(0, 2).toUpperCase()
}

function normalizeWorkspaceEntityId(value) {
  const normalizedValue = Number(value)
  return Number.isInteger(normalizedValue) && normalizedValue > 0 ? normalizedValue : null
}

function isStudentUser(user) {
  const roles = Array.isArray(user?.roles)
    ? user.roles.map((role) => String(role?.role?.name || role?.name || '').toLowerCase())
    : []
  return Boolean(user?.student_profile) || roles.includes('student')
}

function openSearchResult(result) {
  searchQuery.value = ''
  result.action?.()
}

function openDepartment(department) {
  if (!department?.id) return
  router.push({
    name: departmentProgramsRouteName.value,
    params: {
      departmentId: department.id,
    },
  })
}

function openCouncilManagement() {
  router.push({ name: councilRouteName.value })
}

function openUnassignedStudents() {
  router.push({ name: unassignedRouteName.value })
}

function handleOverviewAction(card) {
  if (!card?.route) return
  router.push(card.route)
}

function openAddCollegePanel() {
  closeAllDepartmentSwipes()
  collegePanelMode.value = 'create'
  editingDepartmentId.value = null
  collegeDraftName.value = ''
  collegePanelMessage.value = ''
  collegePanelError.value = false
  isAddCollegeOpen.value = true
}

function openEditCollegePanel(department) {
  const normalizedDepartmentId = normalizeWorkspaceEntityId(department?.id)
  if (normalizedDepartmentId == null) return
  closeAllDepartmentSwipes()
  collegePanelMode.value = 'edit'
  editingDepartmentId.value = normalizedDepartmentId
  collegeDraftName.value = String(department.name || '')
  collegePanelMessage.value = ''
  collegePanelError.value = false
  isAddCollegeOpen.value = true
}

function closeAddCollegePanel() {
  isAddCollegeOpen.value = false
  collegePanelMode.value = 'create'
  collegePanelMessage.value = ''
  collegePanelError.value = false
  collegeDraftName.value = ''
  editingDepartmentId.value = null
}

async function submitCollege() {
  if (collegeSubmitDisabled.value) return

  const normalizedName = collegeDraftName.value.trim()
  const resolvedDepartmentId = resolvedEditingDepartmentId.value
  const mutationMode = isEditingCollege.value ? 'update' : 'create'
  const existingDepartmentId = departmentNameLookup.value.get(normalizedName.toLowerCase())
  if (existingDepartmentId != null && existingDepartmentId !== resolvedDepartmentId) {
    collegePanelError.value = true
    collegePanelMessage.value = `${normalizedName} already exists.`
    return
  }

  isSavingCollege.value = true
  collegePanelMessage.value = ''
  collegePanelError.value = false

  try {
    const authToken = localStorage.getItem('aura_token') || ''
    const createdDepartment = mutationMode === 'update'
      ? (
        props.preview
          ? {
            ...(activeDepartments.value.find((department) => Number(department.id) === resolvedDepartmentId) || {}),
            id: resolvedDepartmentId,
            school_id: schoolId.value,
            name: normalizedName,
          }
          : await updateDepartment(apiBaseUrl.value, authToken, resolvedDepartmentId, {
            name: normalizedName,
          })
      )
      : (
        props.preview
          ? createPreviewDepartment(normalizedName)
          : await createDepartment(apiBaseUrl.value, authToken, {
            name: normalizedName,
          })
      )

    const nextDepartments = sortDepartmentsByName([
      ...activeDepartments.value.filter((department) => Number(department.id) !== Number(createdDepartment.id)),
      createdDepartment,
    ])

    if (props.preview) {
      previewDepartmentOverrides.value = nextDepartments
      persistPreviewDepartments(nextDepartments)
    } else {
      setDepartmentsSnapshot(nextDepartments)
      refreshSchoolItWorkspaceData().catch(() => {})
    }

    collegePanelMessage.value = mutationMode === 'update'
      ? `${createdDepartment.name} updated successfully.`
      : `${createdDepartment.name} added successfully.`
    collegeDraftName.value = ''
    window.setTimeout(() => {
      closeAddCollegePanel()
    }, 420)
  } catch (error) {
    collegePanelError.value = true
    collegePanelMessage.value = resolveDepartmentMutationErrorMessage(error, mutationMode)
  } finally {
    isSavingCollege.value = false
  }
}

async function deleteCollege(department) {
  if (!department?.id || isSavingCollege.value) return

  const confirmed = window.confirm(`Delete ${department.name}?`)
  if (!confirmed) return

  isSavingCollege.value = true
  closeAllDepartmentSwipes()

  try {
    const nextDepartments = activeDepartments.value.filter((item) => Number(item.id) !== Number(department.id))

    if (props.preview) {
      previewDepartmentOverrides.value = sortDepartmentsByName(nextDepartments)
      persistPreviewDepartments(previewDepartmentOverrides.value)
    } else {
      await deleteDepartment(apiBaseUrl.value, localStorage.getItem('aura_token') || '', department.id)
      setDepartmentsSnapshot(sortDepartmentsByName(nextDepartments))
      refreshSchoolItWorkspaceData().catch(() => {})
    }

    if (resolvedEditingDepartmentId.value === Number(department.id)) {
      closeAddCollegePanel()
    }
  } catch (error) {
    window.alert(resolveDepartmentMutationErrorMessage(error, 'delete'))
  } finally {
    isSavingCollege.value = false
  }
}

function onCollegePanelBeforeEnter(element) {
  element.style.height = '0px'
  element.style.opacity = '0'
  element.style.transform = 'translateY(-8px)'
  element.style.willChange = 'height, opacity, transform'
}

function onCollegePanelEnter(element) {
  const height = element.scrollHeight
  element.style.transition = 'height 560ms cubic-bezier(0.22, 1, 0.36, 1), opacity 320ms ease, transform 460ms cubic-bezier(0.22, 1, 0.36, 1)'
  nextFrame(() => {
    element.style.height = `${height}px`
    element.style.opacity = '1'
    element.style.transform = 'translateY(0)'
  })
}

function onCollegePanelAfterEnter(element) {
  element.style.height = 'auto'
  element.style.transition = ''
  element.style.willChange = ''
}

function onCollegePanelBeforeLeave(element) {
  element.style.height = `${element.scrollHeight}px`
  element.style.opacity = '1'
  element.style.transform = 'translateY(0)'
  element.style.willChange = 'height, opacity, transform'
}

function onCollegePanelLeave(element) {
  element.style.transition = 'height 420ms cubic-bezier(0.4, 0, 0.2, 1), opacity 240ms ease, transform 300ms ease'
  nextFrame(() => {
    element.style.height = '0px'
    element.style.opacity = '0'
    element.style.transform = 'translateY(-6px)'
  })
}

function onCollegePanelAfterLeave(element) {
  element.style.transition = ''
  element.style.height = ''
  element.style.opacity = ''
  element.style.transform = ''
  element.style.willChange = ''
}

function createPreviewDepartment(name) {
  return {
    id: Date.now(),
    school_id: schoolId.value,
    name,
  }
}

function sortDepartmentsByName(items) {
  return [...items].sort((left, right) => String(left?.name || '').localeCompare(String(right?.name || '')))
}

function readPreviewDepartments() {
  try {
    const raw = localStorage.getItem(previewDepartmentStorageKey.value)
    if (!raw) return schoolItPreviewData.departments
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? sortDepartmentsByName(parsed) : schoolItPreviewData.departments
  } catch {
    return schoolItPreviewData.departments
  }
}

function persistPreviewDepartments(items) {
  localStorage.setItem(previewDepartmentStorageKey.value, JSON.stringify(items))
}

function resolveDepartmentMutationErrorMessage(error, mode = 'create') {
  const verb = mode === 'delete'
    ? 'delete'
    : mode === 'update'
      ? 'update'
      : 'add'

  if (!(error instanceof BackendApiError)) {
    return `Unable to ${verb} this college right now.`
  }

  const validationDetail = Array.isArray(error?.details?.detail)
    ? error.details.detail.find((item) => item && typeof item === 'object')
    : null
  const validationMessage = typeof validationDetail?.msg === 'string'
    ? validationDetail.msg
    : null
  const validationPath = Array.isArray(validationDetail?.loc)
    ? validationDetail.loc.map((segment) => String(segment).toLowerCase())
    : []

  if (error.status === 422) {
    if (validationPath.includes('name')) {
      return 'College name must be between 2 and 100 characters.'
    }
    if (validationPath.includes('department_id')) {
      return 'The selected college could not be resolved. Please reopen the panel and try again.'
    }
    if (validationMessage) {
      return validationMessage
    }
    if (typeof error?.details?.detail === 'string') {
      return error.details.detail
    }
    if (typeof error?.details?.message === 'string') {
      return error.details.message
    }
    if (error.message && error.message !== '[object Object]') {
      return error.message
    }
    return 'Invalid college details provided.'
  }

  if (error.status === 400 && /already exists/i.test(String(error.message || ''))) {
    return 'A college with this name already exists.'
  }

  if (error.status === 400 && mode === 'delete' && /cannot delete department|referenced by programs/i.test(String(error.message || ''))) {
    return 'This college is still linked to programs and cannot be deleted yet.'
  }

  if (error.status === 403) {
    return `This session is not allowed to ${verb} colleges right now.`
  }

  if (error.status === 409) {
    return 'This college is still linked to other records and cannot be deleted yet.'
  }

  return error.message || `Unable to ${verb} this college right now.`
}

async function handleLogout() {
  await logout()
}

function getDepartmentSwipeOffset(departmentId) {
  return Number(departmentSwipeOffsets.value[departmentId] || 0)
}

function isDepartmentSwipeOpen(departmentId) {
  return getDepartmentSwipeOffset(departmentId) > 0
}

function getDepartmentSwipeStyle(departmentId) {
  return {
    '--department-swipe-offset': `${getDepartmentSwipeOffset(departmentId)}px`,
  }
}

function setDepartmentSwipeOffset(departmentId, offset) {
  const normalizedOffset = Math.max(0, Math.min(DEPARTMENT_SWIPE_ACTION_WIDTH, Number(offset) || 0))
  if (normalizedOffset <= 0) {
    if (!Object.keys(departmentSwipeOffsets.value).length) return
    departmentSwipeOffsets.value = {}
    return
  }

  departmentSwipeOffsets.value = {
    [departmentId]: normalizedOffset,
  }
}

function closeAllDepartmentSwipes() {
  if (!hasOpenDepartmentSwipe.value) return
  departmentSwipeOffsets.value = {}
}

function handleDocumentPointerDown(event) {
  if (!hasOpenDepartmentSwipe.value) return
  if (!(event.target instanceof Element)) return
  if (event.target.closest('.school-it-users__department-swipe')) return
  closeAllDepartmentSwipes()
}

function handleDepartmentCardClick(departmentId, event) {
  if (isDepartmentInteractiveTarget(event.target)) {
    return
  }

  if (departmentSwipeDidDrag.value) {
    event.preventDefault()
    event.stopPropagation()
    departmentSwipeDidDrag.value = false
    return
  }

  if (!isDepartmentSwipeOpen(departmentId)) return
  if (event.target instanceof Element && event.target.closest('.school-it-users__action-pill')) return

  event.preventDefault()
  event.stopPropagation()
  setDepartmentSwipeOffset(departmentId, 0)
}

function onDepartmentPointerDown(departmentId, event) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  if (!(event.currentTarget instanceof HTMLElement)) return
  if (isDepartmentInteractiveTarget(event.target)) return

  departmentSwipeDragId.value = departmentId
  departmentSwipePointerId.value = event.pointerId
  departmentSwipeStartX.value = event.clientX
  departmentSwipeStartY.value = event.clientY
  departmentSwipeStartOffset.value = getDepartmentSwipeOffset(departmentId)
  departmentSwipeAxisLock.value = null
  departmentSwipeDidDrag.value = false
  event.currentTarget.setPointerCapture?.(event.pointerId)
}

function onDepartmentPointerMove(departmentId, event) {
  if (departmentSwipeDragId.value !== departmentId) return
  if (departmentSwipePointerId.value !== event.pointerId) return

  const deltaX = event.clientX - departmentSwipeStartX.value
  const deltaY = event.clientY - departmentSwipeStartY.value

  if (!departmentSwipeAxisLock.value) {
    if (
      Math.abs(deltaX) < DEPARTMENT_SWIPE_GESTURE_THRESHOLD
      && Math.abs(deltaY) < DEPARTMENT_SWIPE_GESTURE_THRESHOLD
    ) {
      return
    }

    departmentSwipeAxisLock.value = Math.abs(deltaX) > Math.abs(deltaY) ? 'x' : 'y'
  }

  if (departmentSwipeAxisLock.value !== 'x') return

  departmentSwipeDidDrag.value = true
  event.preventDefault()
  setDepartmentSwipeOffset(departmentId, departmentSwipeStartOffset.value - deltaX)
}

function onDepartmentPointerEnd(departmentId, event) {
  if (departmentSwipeDragId.value !== departmentId) return
  if (departmentSwipePointerId.value !== event.pointerId) return

  const currentOffset = getDepartmentSwipeOffset(departmentId)
  const shouldOpen = currentOffset >= DEPARTMENT_SWIPE_OPEN_THRESHOLD
  setDepartmentSwipeOffset(departmentId, shouldOpen ? DEPARTMENT_SWIPE_ACTION_WIDTH : 0)

  if (event.currentTarget instanceof HTMLElement) {
    event.currentTarget.releasePointerCapture?.(event.pointerId)
  }

  resetDepartmentSwipeGesture()
}

function onDepartmentPointerCancel(departmentId, event) {
  if (departmentSwipeDragId.value !== departmentId) return
  if (departmentSwipePointerId.value !== event.pointerId) return

  const currentOffset = getDepartmentSwipeOffset(departmentId)
  const shouldOpen = currentOffset >= DEPARTMENT_SWIPE_OPEN_THRESHOLD
  setDepartmentSwipeOffset(departmentId, shouldOpen ? DEPARTMENT_SWIPE_ACTION_WIDTH : 0)
  resetDepartmentSwipeGesture()
}

function resetDepartmentSwipeGesture() {
  window.setTimeout(() => {
    departmentSwipeDidDrag.value = false
  }, 0)
  departmentSwipeDragId.value = null
  departmentSwipePointerId.value = null
  departmentSwipeAxisLock.value = null
}

function isDepartmentInteractiveTarget(target) {
  if (!(target instanceof Element)) return false
  return Boolean(
    target.closest(
      '.school-it-users__action-pill, .school-it-users__department-action, button, a, input, textarea, select, label'
    )
  )
}
</script>

<style scoped>
.school-it-users{min-height:100vh;padding:30px 28px 120px;font-family:'Manrope',sans-serif}
.school-it-users__shell{width:100%;max-width:1120px;margin:0 auto}
.school-it-users__body{display:flex;flex-direction:column;gap:18px;margin-top:24px}
.school-it-users__title{margin:0;font-size:22px;font-weight:800;line-height:1;letter-spacing:-.05em;color:var(--color-text-primary)}
.school-it-users__search{display:flex;flex-direction:column;gap:10px}
.school-it-users__search-row{display:flex;align-items:stretch;gap:clamp(8px,3vw,12px)}
.school-it-users__search-wrap{flex:1;min-width:0}
.school-it-users__search-shell{display:grid;grid-template-rows:auto 0fr;padding:11px clamp(12px,4vw,16px);border-radius:30px;background:var(--color-surface);transition:grid-template-rows .32s cubic-bezier(.22,1,.36,1),border-radius .32s cubic-bezier(.22,1,.36,1)}
.school-it-users__search-shell--open{grid-template-rows:auto 1fr;border-radius:28px}
.school-it-users__search-input-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:clamp(8px,2.5vw,10px);min-height:clamp(38px,10vw,40px)}
.school-it-users__search-input{flex:1;min-width:0;border:none;background:transparent;outline:none;color:var(--color-text-always-dark);font-size:clamp(13px,3.8vw,14px);font-weight:500}
.school-it-users__search-input::placeholder{color:var(--color-text-muted)}
.school-it-users__search-icon{width:clamp(30px,8vw,32px);height:clamp(30px,8vw,32px);padding:0;border:1px solid var(--color-surface-border);border-radius:999px;background:transparent;color:var(--color-primary);display:inline-flex;align-items:center;justify-content:center;line-height:0;appearance:none;flex-shrink:0;place-self:center}
.school-it-users__search-icon :deep(svg){display:block;width:clamp(15px,4.5vw,18px);height:clamp(15px,4.5vw,18px)}
.school-it-users__search-results{overflow:hidden;min-height:0}
.school-it-users__search-results-inner{display:flex;flex-direction:column;gap:10px;padding:14px 0 6px}
.school-it-users__search-result{width:100%;padding:14px 16px;border:none;border-radius:22px;background:color-mix(in srgb,var(--color-surface) 90%,var(--color-bg));display:flex;flex-direction:column;gap:8px;text-align:left}
.school-it-users__search-result-top{display:flex;align-items:center;justify-content:space-between;gap:12px}
.school-it-users__search-result-name{font-size:14px;font-weight:700;color:var(--color-text-always-dark)}
.school-it-users__search-result-type{min-height:28px;padding:0 12px;border-radius:999px;background:color-mix(in srgb,var(--color-primary) 18%,white);color:var(--color-text-always-dark);display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;letter-spacing:.02em;flex-shrink:0}
.school-it-users__search-result-meta,.school-it-users__empty{font-size:12px;color:var(--color-text-muted)}
.school-it-users__add-college-pill{width:clamp(118px,31vw,134px);min-height:clamp(56px,15vw,60px);padding:0 clamp(14px,4vw,16px);border:none;border-radius:999px;background:var(--color-search-pill-bg);color:var(--color-search-pill-text);display:inline-flex;align-items:center;justify-content:center;gap:clamp(8px,2.8vw,10px);flex-shrink:0;transition:opacity .2s ease,transform .22s ease,box-shadow .28s ease,filter .22s ease}
.school-it-users__add-college-pill:hover{filter:brightness(1.06);transform:translateY(-1px)}
.school-it-users__add-college-pill:active{transform:scale(.96)}
.school-it-users__add-college-copy{font-size:clamp(12px,3.4vw,13px);font-weight:700;line-height:.98;text-align:left}
.school-it-users__college-panel{overflow:hidden;transform-origin:top center}
.school-it-users__college-panel-inner{overflow:hidden}
.school-it-users__college-shell{display:flex;flex-direction:column;gap:20px;padding:18px clamp(18px,5vw,24px) 22px;border-radius:34px;background:var(--color-primary);color:var(--color-banner-text);box-shadow:0 18px 36px rgba(0,0,0,.12)}
.school-it-users__college-header{display:flex;align-items:center;justify-content:space-between;gap:12px}
.school-it-users__college-close{width:34px;height:34px;border:none;border-radius:999px;background:transparent;color:var(--color-banner-text);display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.school-it-users__college-title{font-size:clamp(17px,4.6vw,20px);font-weight:700;line-height:1;color:var(--color-banner-text)}
.school-it-users__college-form{display:flex;flex-direction:column;gap:18px}
.school-it-users__college-input-shell{min-height:64px;padding:0 22px;border-radius:999px;background:var(--color-surface);display:flex;align-items:center}
.school-it-users__college-input{width:100%;border:none;background:transparent;outline:none;font-size:14px;font-weight:500;color:var(--color-text-always-dark)}
.school-it-users__college-input::placeholder{color:var(--color-text-muted)}
.school-it-users__college-submit{width:min(100%,144px);min-height:54px;margin:0 auto;border:1.4px solid color-mix(in srgb,var(--color-text-always-dark) 24%, transparent);border-radius:999px;background:transparent;color:var(--color-text-always-dark);font-family:'Manrope',sans-serif;font-size:14px;font-weight:600;transition:transform .18s ease,background .2s ease}
.school-it-users__college-submit:disabled{opacity:.5;cursor:not-allowed}
.school-it-users__college-submit:not(:disabled):active{transform:scale(.97)}
.school-it-users__college-message{margin:0;font-size:13px;font-weight:600;line-height:1.35;color:var(--color-banner-text)}
.school-it-users__college-message--error{color:#7A130E}
.school-it-users__overview{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.school-it-users__hero-card{position:relative;display:flex;flex-direction:column;justify-content:space-between;gap:18px;min-height:188px;padding:26px 22px 20px;border-radius:32px;overflow:hidden}
.school-it-users__hero-card--primary{background:var(--color-primary);color:var(--color-banner-text)}
.school-it-users__hero-card--surface{background:var(--color-surface);color:var(--color-text-always-dark)}
.school-it-users__hero-card-copy{display:flex;flex-direction:column;gap:10px;min-width:0}
.school-it-users__overview-title{margin:0;font-size:clamp(24px,8vw,44px);line-height:.92;letter-spacing:-.06em;font-weight:700}
.school-it-users__overview-meta{font-size:12px;font-weight:700;line-height:1;color:var(--color-primary)}
.school-it-users__hero-card-pill{width:fit-content;min-height:52px;padding:0 18px 0 6px;border:none;border-radius:999px;background:var(--color-primary);color:var(--color-banner-text);display:inline-flex;align-items:center;gap:12px;font-size:12px;font-weight:700;letter-spacing:-.02em;white-space:nowrap}
.school-it-users__hero-card-pill--surface{background:var(--color-surface);color:var(--color-text-always-dark)}
.school-it-users__hero-card-pill-icon{width:40px;height:40px;border-radius:999px;background:var(--color-nav);color:var(--color-nav-text);display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.school-it-users__alert{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:20px;padding:24px 22px;min-height:124px;border-radius:28px;background:var(--color-surface)}
.school-it-users__alert-copy{display:flex;flex-direction:column;gap:4px;min-width:0}
.school-it-users__alert-copy--management{gap:0;max-width:none;align-items:flex-start;justify-self:stretch;text-align:left}
.school-it-users__alert-org-name{margin:0;max-width:11ch;font-size:clamp(24px,7.2vw,40px);line-height:.94;letter-spacing:-.06em;font-weight:700;color:var(--color-text-always-dark);text-align:left}
.school-it-users__alert-org-name--placeholder{color:var(--color-primary)}
.school-it-users__alert-kicker{margin:0;font-size:clamp(18px,5vw,28px);line-height:1;font-weight:800;letter-spacing:-.05em;color:#FF2D20}
.school-it-users__alert-message{margin:0;max-width:16ch;font-size:15px;line-height:1.05;color:var(--color-text-always-dark)}
.school-it-users__action-pill{width:fit-content;min-height:52px;padding:0 18px 0 6px;border:none;border-radius:999px;background:var(--color-primary);color:var(--color-banner-text);display:inline-flex;align-items:center;gap:12px;font-size:12px;font-weight:700;letter-spacing:-.02em;white-space:nowrap;flex-shrink:0;cursor:pointer;transition:transform 0.2s ease, filter 0.2s ease}
.school-it-users__action-pill:hover{filter:brightness(1.08)}
.school-it-users__action-pill:active{transform:scale(0.96)}
.school-it-users__action-pill--inline{min-height:54px;padding-right:18px;font-size:13px}
.school-it-users__action-pill-icon{width:40px;height:40px;border-radius:999px;background:var(--color-nav);color:var(--color-nav-text);display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.school-it-users__department-list{display:flex;flex-direction:column;gap:18px}
.school-it-users__department-empty{margin:0;padding:10px 6px;font-size:15px;font-weight:600;line-height:1.35;color:var(--color-text-muted);text-align:center}
.school-it-users__department-swipe{position:relative;border-radius:32px;overflow:hidden;touch-action:pan-y}
.school-it-users__department-swipe--open .school-it-users__department-actions{pointer-events:auto}
.school-it-users__department-swipe--open .school-it-users__department-action{opacity:1;transform:translateX(0)}
.school-it-users__department-actions{position:absolute;inset:0 0 0 auto;width:70px;padding:10px 4px 10px 0;display:flex;flex-direction:column;justify-content:center;align-items:flex-end;gap:10px;pointer-events:none}
.school-it-users__department-action{width:54px;min-height:74px;border:1px solid color-mix(in srgb,var(--color-text-muted) 22%, transparent);border-radius:999px;background:color-mix(in srgb,var(--color-surface) 92%,var(--color-bg));color:var(--color-text-always-dark);display:inline-flex;align-items:center;justify-content:center;opacity:.72;transform:translateX(8px);transition:transform .32s cubic-bezier(.22,1,.36,1),opacity .24s ease,background-color .24s ease,border-color .24s ease}
.school-it-users__department-action:disabled{opacity:.5;cursor:not-allowed}
.school-it-users__department-action:active{transform:scale(.96)}
.school-it-users__department-action--delete{min-height:88px;color:#FF3B30;border-color:color-mix(in srgb,#FF3B30 48%, transparent)}
.school-it-users__department-action--edit{min-height:72px}
.school-it-users__department-card{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(122px,.8fr);gap:8px;padding:8px;border-radius:32px;background:var(--color-surface);transform:translate3d(calc(var(--department-swipe-offset, 0px) * -1),0,0);transition:transform .42s cubic-bezier(.22,1,.36,1)}
.school-it-users__department-main{display:flex;flex-direction:column;justify-content:space-between;min-height:194px;padding:20px 14px 14px}
.school-it-users__department-title{margin:0;max-width:8.6ch;font-size:clamp(26px,7.4vw,52px);line-height:.92;letter-spacing:-.07em;font-weight:700;color:var(--color-text-always-dark)}
.school-it-users__department-panel{display:flex;flex-direction:column;gap:10px;padding:22px 16px;border-radius:24px;background:color-mix(in srgb,var(--color-surface) 88%,var(--color-bg))}
.school-it-users__department-label{margin:0;font-size:12px;font-weight:700;line-height:1.1;color:var(--color-primary)}
.school-it-users__program-list{display:flex;flex-direction:column;gap:4px;margin:0;padding:0;list-style:none}
.school-it-users__program-item{font-size:14px;line-height:1.15;color:var(--color-text-always-dark)}
.school-it-users__program-empty{margin:0;font-size:13px;line-height:1.3;color:var(--color-text-muted)}
@media (min-width:768px){
  .school-it-users{padding:40px 36px 56px}
  .school-it-users__body{margin-top:30px;gap:22px}
  .school-it-users__title{font-size:28px}
  .school-it-users__search-row,.school-it-users__college-panel{max-width:780px}
  .school-it-users__overview{max-width:780px}
  .school-it-users__alert{max-width:780px;padding:28px 26px}
  .school-it-users__department-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
}

@media (max-width:767px){
  .school-it-users__department-actions{width:66px;padding-right:2px}
  .school-it-users__department-action{width:50px}
  .school-it-users__department-action--delete{min-height:84px}
  .school-it-users__department-action--edit{min-height:68px}
  .school-it-users__department-card{grid-template-columns:minmax(0,1.12fr) minmax(110px,.72fr);gap:6px;padding:6px}
  .school-it-users__department-main{min-height:180px;padding:18px 12px 12px}
  .school-it-users__department-title{max-width:8.2ch;font-size:clamp(22px,8.2vw,34px)}
  .school-it-users__department-panel{gap:8px;padding:18px 14px;border-radius:22px}
  .school-it-users__program-item{font-size:12px;line-height:1.12}
}

@media (prefers-reduced-motion:reduce){
  .school-it-users__add-college-pill,.school-it-users__college-submit,.school-it-users__department-action,.school-it-users__department-card{transition:none;animation:none}
}

</style>
