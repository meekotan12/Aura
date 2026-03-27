<template>
  <section class="school-it-department-programs">
    <div class="school-it-department-programs__shell">
      <SchoolItTopHeader
        class="dashboard-enter dashboard-enter--1"
        :avatar-url="avatarUrl"
        :school-name="activeSchoolSettings?.school_name || activeUser?.school_name || ''"
        :display-name="displayName"
        :initials="initials"
        @logout="handleLogout"
      />

      <div class="school-it-department-programs__body">
        <h1 class="school-it-department-programs__title dashboard-enter dashboard-enter--2">Students</h1>

        <section class="school-it-department-programs__toolbar dashboard-enter dashboard-enter--3">
          <div class="school-it-department-programs__toolbar-row">
            <div class="school-it-department-programs__search-shell">
              <input
                v-model="searchQuery"
                v-bind="programSearchInputAttrs"
                class="school-it-department-programs__search-input"
                type="text"
                placeholder="Search programs"
              >
              <button class="school-it-department-programs__search-icon" type="button" aria-label="Search programs">
                <Search :size="18" />
              </button>
            </div>

            <button
              v-show="selectedDepartment && !isAddProgramOpen"
              class="school-it-department-programs__add-pill"
              type="button"
              :aria-expanded="isAddProgramOpen ? 'true' : 'false'"
              aria-controls="school-it-department-programs-add-panel"
              @click="openAddProgramPanel"
            >
              <Plus :size="18" :stroke-width="2.4" />
              <span class="school-it-department-programs__add-pill-copy">Add<br>Program</span>
            </button>
          </div>

          <Transition
            name="school-it-department-programs-panel"
            @before-enter="onProgramPanelBeforeEnter"
            @enter="onProgramPanelEnter"
            @after-enter="onProgramPanelAfterEnter"
            @before-leave="onProgramPanelBeforeLeave"
            @leave="onProgramPanelLeave"
            @after-leave="onProgramPanelAfterLeave"
          >
            <div
              v-if="selectedDepartment && isAddProgramOpen"
              id="school-it-department-programs-add-panel"
              class="school-it-department-programs__panel"
              role="region"
              :aria-label="programPanelAriaLabel"
            >
              <div class="school-it-department-programs__panel-inner">
                <div class="school-it-department-programs__panel-header">
                  <button
                    class="school-it-department-programs__panel-close"
                    type="button"
                    aria-label="Close program panel"
                    @click="closeAddProgramPanel"
                  >
                    <X :size="18" :stroke-width="2.4" />
                  </button>
                  <span class="school-it-department-programs__panel-title">{{ programPanelTitle }}</span>
                </div>

                <div class="school-it-department-programs__panel-form">
                  <div class="school-it-department-programs__panel-input-shell">
                    <input
                      ref="programInputEl"
                      v-model="programDraftName"
                      class="school-it-department-programs__panel-input"
                      type="text"
                      placeholder="e.g., BS Computer Engineering"
                      :disabled="isSavingProgram"
                      @keyup.enter="submitProgram"
                    >
                  </div>

                  <button
                    class="school-it-department-programs__panel-submit"
                    type="button"
                    :disabled="programSubmitDisabled"
                    @click="submitProgram"
                  >
                    {{ programSubmitLabel }}
                  </button>
                </div>

                <p
                  v-if="programPanelMessage"
                  class="school-it-department-programs__panel-message"
                  :class="{ 'school-it-department-programs__panel-message--error': programPanelError }"
                >
                  {{ programPanelMessage }}
                </p>
              </div>
            </div>
          </Transition>
        </section>

        <template v-if="selectedDepartment">
          <section class="school-it-department-programs__hero dashboard-enter dashboard-enter--4">
            <DepartmentProgramRingChart
              v-if="!chartRenderFailed"
              v-model="selectedProgramId"
              :items="ringItems"
            />

            <div v-else class="school-it-department-programs__chart-fallback" aria-live="polite">
              <span class="school-it-department-programs__chart-fallback-value">
                {{ Math.round(fallbackRingItem.percentage || 0) }}%
              </span>
              <span class="school-it-department-programs__chart-fallback-label">
                {{ fallbackRingItem.shortLabel || 'No Data' }}
              </span>
            </div>

            <div class="school-it-department-programs__hero-copy">
              <h2 class="school-it-department-programs__hero-title">{{ selectedDepartment.name }}</h2>

              <div v-if="ringItems.length" class="school-it-department-programs__legend">
                <button
                  v-for="program in ringItems"
                  :key="program.id"
                  class="school-it-department-programs__legend-item"
                  :class="{
                    'school-it-department-programs__legend-item--active': Number(program.id) === Number(activeProgramId),
                  }"
                  type="button"
                  @click="selectedProgramId = program.id"
                >
                  <span
                    class="school-it-department-programs__legend-dot"
                    :class="{
                      'school-it-department-programs__legend-dot--light': program.tone === 'light',
                    }"
                    :style="{ background: program.color }"
                  />
                  <span class="school-it-department-programs__legend-label">{{ program.name }}</span>
                </button>
              </div>

              <p v-else class="school-it-department-programs__hero-empty">
                No programs linked to this college yet.
              </p>
            </div>
          </section>

          <section v-if="visibleProgramCards.length" class="school-it-department-programs__program-list">
            <div
              v-for="(program, index) in visibleProgramCards"
              :key="program.id"
              class="school-it-department-programs__program-swipe dashboard-enter"
              :class="[
                `dashboard-enter--${Math.min(index + 5, 9)}`,
                { 'school-it-department-programs__program-swipe--open': isProgramSwipeOpen(program.id) },
              ]"
            >
              <div class="school-it-department-programs__program-action-rail" aria-hidden="true">
                <button
                  class="school-it-department-programs__program-action school-it-department-programs__program-action--delete"
                  type="button"
                  :disabled="isSavingProgram"
                  aria-label="Delete program"
                  @click.stop="deleteProgramItem(program)"
                >
                  <Trash2 :size="18" />
                </button>

                <button
                  class="school-it-department-programs__program-action school-it-department-programs__program-action--edit"
                  type="button"
                  :disabled="isSavingProgram"
                  aria-label="Edit program"
                  @click.stop="openEditProgramPanel(program)"
                >
                  <Pencil :size="18" />
                </button>
              </div>

              <article
                class="school-it-department-programs__program-card"
                :style="getProgramSwipeStyle(program.id)"
                @click.capture="handleProgramCardClick(program.id, $event)"
                @pointerdown="onProgramPointerDown(program.id, $event)"
                @pointermove="onProgramPointerMove(program.id, $event)"
                @pointerup="onProgramPointerEnd(program.id, $event)"
                @pointercancel="onProgramPointerCancel(program.id, $event)"
                @lostpointercapture="onProgramPointerCancel(program.id, $event)"
              >
                <h3 class="school-it-department-programs__program-title">{{ program.name }}</h3>

                <button
                  class="school-it-department-programs__manage-pill"
                  type="button"
                  @pointerdown.stop
                  @click.stop="manageProgram(program)"
                >
                  <span class="school-it-department-programs__manage-pill-icon">
                    <ArrowRight :size="18" />
                  </span>
                  Manage
                </button>
              </article>
            </div>
          </section>

          <p
            v-else
            class="school-it-department-programs__empty dashboard-enter dashboard-enter--5"
          >
            {{ programEmptyMessage }}
          </p>
        </template>

        <p
          v-else-if="isDepartmentDataLoading"
          class="school-it-department-programs__empty dashboard-enter dashboard-enter--4"
        >
          Loading college details...
        </p>

        <p
          v-else-if="isDepartmentDataUnavailable"
          class="school-it-department-programs__empty dashboard-enter dashboard-enter--4"
        >
          College data is unavailable right now.
        </p>

        <p
          v-else
          class="school-it-department-programs__empty dashboard-enter dashboard-enter--4"
        >
          This college could not be found.
        </p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onErrorCaptured, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Pencil, Plus, Search, Trash2, X } from 'lucide-vue-next'
import DepartmentProgramRingChart from '@/components/dashboard/DepartmentProgramRingChart.vue'
import SchoolItTopHeader from '@/components/dashboard/SchoolItTopHeader.vue'
import { schoolItPreviewData } from '@/data/schoolItPreview.js'
import { useAuth } from '@/composables/useAuth.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { usePreviewTheme } from '@/composables/usePreviewTheme.js'
import { useSchoolItWorkspaceData } from '@/composables/useSchoolItWorkspaceData.js'
import { BackendApiError, createProgram, deleteProgram, updateProgram } from '@/services/backendApi.js'
import { createSearchFieldAttrs } from '@/services/searchFieldAttrs.js'
import { filterWorkspaceEntitiesBySchool } from '@/services/workspaceScope.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const PROGRAM_RING_PALETTE = [
  { color: 'var(--color-surface)', tone: 'light' },
  { color: 'rgba(10, 10, 10, 0.38)', tone: 'muted' },
  { color: 'var(--color-nav)', tone: 'dark' },
  { color: 'rgba(255, 255, 255, 0.72)', tone: 'light' },
  { color: 'rgba(10, 10, 10, 0.62)', tone: 'dark' },
]

const route = useRoute()
const router = useRouter()
const searchQuery = ref('')
const programSearchInputAttrs = createSearchFieldAttrs('school-it-program-search')
const selectedProgramId = ref(null)
const chartRenderFailed = ref(false)
const isAddProgramOpen = ref(false)
const isSavingProgram = ref(false)
const programPanelMode = ref('create')
const programDraftName = ref('')
const programInputEl = ref(null)
const programPanelMessage = ref('')
const programPanelError = ref(false)
const editingProgramId = ref(null)
const previewDepartmentOverrides = ref([])
const previewProgramOverrides = ref([])
const programSwipeOffsets = ref({})
const programSwipeDragId = ref(null)
const programSwipePointerId = ref(null)
const programSwipeStartX = ref(0)
const programSwipeStartY = ref(0)
const programSwipeStartOffset = ref(0)
const programSwipeAxisLock = ref(null)
const programSwipeDidDrag = ref(false)
const PROGRAM_SWIPE_ACTION_WIDTH = 100
const PROGRAM_SWIPE_OPEN_THRESHOLD = 34
const PROGRAM_SWIPE_GESTURE_THRESHOLD = 8

const { logout } = useAuth()
const { currentUser, schoolSettings, apiBaseUrl } = useDashboardSession()
const {
  departments,
  programs,
  users,
  statuses: workspaceStatuses,
  initializeSchoolItWorkspaceData,
  refreshSchoolItWorkspaceData,
  setProgramsSnapshot,
} = useSchoolItWorkspaceData()

const schoolId = computed(() => Number(activeUser.value?.school_id ?? activeSchoolSettings.value?.school_id))
const settingsRouteName = computed(() => props.preview ? 'PreviewSchoolItSettings' : 'SchoolItSettings')
const programRouteName = computed(() => props.preview ? 'PreviewSchoolItProgramStudents' : 'SchoolItProgramStudents')
const departmentId = computed(() => {
  const normalized = Number(route.params.departmentId)
  return Number.isFinite(normalized) ? normalized : null
})
const activeUser = computed(() => props.preview ? schoolItPreviewData.user : currentUser.value)
const activeSchoolSettings = computed(() => props.preview ? schoolItPreviewData.schoolSettings : schoolSettings.value)
const activeDepartments = computed(() => props.preview ? previewDepartments.value : departments.value)
const activePrograms = computed(() => props.preview ? previewPrograms.value : programs.value)
const activeUsers = computed(() => props.preview ? schoolItPreviewData.users : users.value)

usePreviewTheme(() => props.preview, activeSchoolSettings)
const filteredDepartments = computed(() => filterWorkspaceEntitiesBySchool(activeDepartments.value, schoolId.value))
const filteredPrograms = computed(() => filterWorkspaceEntitiesBySchool(activePrograms.value, schoolId.value))
const filteredUsers = computed(() => filterWorkspaceEntitiesBySchool(activeUsers.value, schoolId.value))
const studentUsers = computed(() => filteredUsers.value.filter(isStudentUser))
const departmentsStatus = computed(() => workspaceStatuses.value?.departments || 'idle')
const programsStatus = computed(() => workspaceStatuses.value?.programs || 'idle')
const avatarUrl = computed(() => activeUser.value?.avatar_url || '')
const displayName = computed(() => {
  const first = activeUser.value?.first_name || ''
  const middle = activeUser.value?.middle_name || ''
  const last = activeUser.value?.last_name || ''
  return [first, middle, last].filter(Boolean).join(' ') || activeUser.value?.email?.split('@')[0] || 'School IT'
})
const initials = computed(() => buildInitials(displayName.value))
const previewDepartmentStorageKey = computed(() => (
  Number.isFinite(schoolId.value)
    ? `aura_exposed_departments_${schoolId.value}`
    : 'aura_exposed_departments'
))
const previewProgramStorageKey = computed(() => (
  Number.isFinite(schoolId.value)
    ? `aura_exposed_programs_${schoolId.value}`
    : 'aura_exposed_programs'
))
const previewDepartments = computed(() => (
  previewDepartmentOverrides.value.length
    ? previewDepartmentOverrides.value
    : schoolItPreviewData.departments
))
const previewPrograms = computed(() => (
  previewProgramOverrides.value.length
    ? previewProgramOverrides.value
    : schoolItPreviewData.programs
))

const selectedDepartment = computed(() => (
  filteredDepartments.value.find((department) => Number(department.id) === departmentId.value) || null
))
const isDepartmentDataLoading = computed(() => (
  !selectedDepartment.value &&
  ['idle', 'loading'].includes(departmentsStatus.value)
))
const isDepartmentDataUnavailable = computed(() => (
  !selectedDepartment.value &&
  ['blocked', 'error'].includes(departmentsStatus.value)
))

const departmentPrograms = computed(() => (
  filteredPrograms.value
    .filter((program) => Array.isArray(program.department_ids) && program.department_ids.includes(departmentId.value))
    .sort((left, right) => String(left?.name || '').localeCompare(String(right?.name || '')))
))

const departmentStudents = computed(() => (
  studentUsers.value.filter((user) => Number(user?.student_profile?.department_id) === departmentId.value)
))

const activeProgramSearch = computed(() => searchQuery.value.trim().toLowerCase())
const programStats = computed(() => {
  const totalStudents = departmentStudents.value.length

  return departmentPrograms.value.map((program) => {
    const relatedStudents = departmentStudents.value.filter((user) => Number(user?.student_profile?.program_id) === Number(program.id))
    const rawPercentage = totalStudents > 0 ? (relatedStudents.length / totalStudents) * 100 : 0

    return {
      ...program,
      students: relatedStudents,
      studentCount: relatedStudents.length,
      percentage: rawPercentage,
      shortLabel: buildProgramShortLabel(program.name),
    }
  })
})

const visibleProgramCards = computed(() => {
  if (!activeProgramSearch.value) return programStats.value
  return programStats.value.filter((program) => String(program.name || '').toLowerCase().includes(activeProgramSearch.value))
})

const ringItems = computed(() => {
  const rankedPrograms = [...visibleProgramCards.value]
    .sort((left, right) => (
      right.studentCount - left.studentCount
      || String(left?.name || '').localeCompare(String(right?.name || ''))
    ))

  return rankedPrograms.map((program, index) => {
    const paletteEntry = PROGRAM_RING_PALETTE[index % PROGRAM_RING_PALETTE.length]

    return {
      id: program.id,
      name: program.name,
      shortLabel: program.shortLabel,
      percentage: program.percentage,
      color: paletteEntry.color,
      tone: paletteEntry.tone,
    }
  })
})

const fallbackRingItem = computed(() => (
  ringItems.value[0]
  || {
    id: null,
    percentage: 0,
    shortLabel: 'No Data',
  }
))

const activeProgramId = computed(() => {
  const selectedProgram = ringItems.value.find((program) => Number(program.id) === Number(selectedProgramId.value))
  return selectedProgram?.id ?? ringItems.value[0]?.id ?? null
})

const resolvedEditingProgramId = computed(() => normalizeWorkspaceEntityId(editingProgramId.value))
const isEditingProgram = computed(() => programPanelMode.value === 'edit' && resolvedEditingProgramId.value != null)
const programPanelAriaLabel = computed(() => isEditingProgram.value ? 'Edit program' : 'Add program')
const programPanelTitle = computed(() => isEditingProgram.value ? 'Edit Program' : 'Add Program')
const programSubmitLabel = computed(() => isEditingProgram.value ? 'Save' : 'Add')
const programSubmitDisabled = computed(() => {
  const normalizedName = programDraftName.value.trim()
  return !selectedDepartment.value || isSavingProgram.value || normalizedName.length < 2 || normalizedName.length > 100
})

const programNameLookup = computed(() => new Map(
  departmentPrograms.value
    .map((program) => [String(program?.name || '').trim().toLowerCase(), Number(program?.id)])
    .filter(([name]) => Boolean(name))
))

const programEmptyMessage = computed(() => {
  if ((programsStatus.value === 'idle' || programsStatus.value === 'loading') && departmentPrograms.value.length <= 0) {
    return 'Loading programs...'
  }

  if (['blocked', 'error'].includes(programsStatus.value) && departmentPrograms.value.length <= 0) {
    return 'Programs are unavailable right now.'
  }

  if (departmentPrograms.value.length <= 0) {
    return 'No programs linked to this college yet.'
  }

  if (activeProgramSearch.value) {
    return 'No programs match this search.'
  }

  return 'No programs linked to this college yet.'
})

const nextFrame = (callback) => requestAnimationFrame(() => requestAnimationFrame(callback))
const hasOpenProgramSwipe = computed(() => Object.values(programSwipeOffsets.value).some((offset) => offset > 0))

watch([apiBaseUrl, () => activeUser.value?.id, () => props.preview], async ([resolvedApiBaseUrl, userId, preview]) => {
  if (preview) return
  if (!resolvedApiBaseUrl || !userId) return
  await initializeSchoolItWorkspaceData()
}, { immediate: true })

watch(() => props.preview, (preview) => {
  if (!preview) {
    previewDepartmentOverrides.value = []
    previewProgramOverrides.value = []
    return
  }

  previewDepartmentOverrides.value = readPreviewCollection(previewDepartmentStorageKey.value, schoolItPreviewData.departments)
  previewProgramOverrides.value = readPreviewCollection(previewProgramStorageKey.value, schoolItPreviewData.programs)
}, { immediate: true })

watch(ringItems, (items) => {
  chartRenderFailed.value = false
  const selectedExists = items.some((program) => Number(program.id) === Number(selectedProgramId.value))
  if (selectedExists) return
  selectedProgramId.value = items[0]?.id ?? null
}, { immediate: true })

onErrorCaptured((error, instance) => {
  const componentName = instance?.type?.__name || instance?.type?.name || ''
  if (componentName === 'DepartmentProgramRingChart') {
    chartRenderFailed.value = true
    console.error('Department program ring failed to render:', error)
    return false
  }

  return undefined
})

watch(isAddProgramOpen, (open) => {
  if (!open) return
  nextTick(() => {
    setTimeout(() => programInputEl.value?.focus(), 220)
  })
})

watch(isAddProgramOpen, (open) => {
  if (open) closeAllProgramSwipes()
})

watch(activeProgramSearch, (query) => {
  if (!query) return
  closeAllProgramSwipes()
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

function isStudentUser(user) {
  const roles = Array.isArray(user?.roles)
    ? user.roles.map((role) => String(role?.role?.name || role?.name || '').toLowerCase())
    : []
  return Boolean(user?.student_profile) || roles.includes('student')
}

function buildProgramShortLabel(programName) {
  const parts = String(programName || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return 'Program'
  return parts.slice(0, Math.min(2, parts.length)).join(' ')
}

function normalizeWorkspaceEntityId(value) {
  const normalizedValue = Number(value)
  return Number.isInteger(normalizedValue) && normalizedValue > 0 ? normalizedValue : null
}

function openAddProgramPanel() {
  if (!selectedDepartment.value) return
  closeAllProgramSwipes()
  programPanelMode.value = 'create'
  editingProgramId.value = null
  programDraftName.value = ''
  programPanelMessage.value = ''
  programPanelError.value = false
  isAddProgramOpen.value = true
}

function openEditProgramPanel(program) {
  const normalizedProgramId = normalizeWorkspaceEntityId(program?.id)
  if (normalizedProgramId == null) return
  closeAllProgramSwipes()
  programPanelMode.value = 'edit'
  editingProgramId.value = normalizedProgramId
  programDraftName.value = String(program.name || '')
  programPanelMessage.value = ''
  programPanelError.value = false
  isAddProgramOpen.value = true
}

function closeAddProgramPanel() {
  isAddProgramOpen.value = false
  programPanelMode.value = 'create'
  programPanelMessage.value = ''
  programPanelError.value = false
  programDraftName.value = ''
  editingProgramId.value = null
}

async function submitProgram() {
  if (programSubmitDisabled.value || !selectedDepartment.value) return

  const normalizedName = programDraftName.value.trim()
  const resolvedProgramId = resolvedEditingProgramId.value
  const mutationMode = isEditingProgram.value ? 'update' : 'create'
  const existingProgramId = programNameLookup.value.get(normalizedName.toLowerCase())
  if (existingProgramId != null && existingProgramId !== resolvedProgramId) {
    programPanelError.value = true
    programPanelMessage.value = `${normalizedName} already exists in this college.`
    return
  }

  isSavingProgram.value = true
  programPanelMessage.value = ''
  programPanelError.value = false

  try {
    const authToken = localStorage.getItem('aura_token') || ''
    const createdProgram = mutationMode === 'update'
      ? (
        props.preview
          ? {
            ...(activePrograms.value.find((program) => Number(program.id) === resolvedProgramId) || {}),
            id: resolvedProgramId,
            school_id: schoolId.value,
            name: normalizedName,
            department_ids: [Number(selectedDepartment.value.id)],
          }
          : await updateProgram(apiBaseUrl.value, authToken, resolvedProgramId, {
            name: normalizedName,
            department_ids: [Number(selectedDepartment.value.id)],
          })
      )
      : (
        props.preview
          ? createPreviewProgram(normalizedName)
          : await createProgram(apiBaseUrl.value, authToken, {
            name: normalizedName,
            department_ids: [Number(selectedDepartment.value.id)],
          })
      )

    const nextPrograms = sortProgramsByName([
      ...activePrograms.value.filter((program) => Number(program.id) !== Number(createdProgram.id)),
      createdProgram,
    ])

    if (props.preview) {
      previewProgramOverrides.value = nextPrograms
      persistPreviewCollection(previewProgramStorageKey.value, nextPrograms)
    } else {
      setProgramsSnapshot(nextPrograms)
      refreshSchoolItWorkspaceData().catch(() => {})
    }

    selectedProgramId.value = createdProgram.id
    programPanelMessage.value = mutationMode === 'update'
      ? `${createdProgram.name} updated successfully.`
      : `${createdProgram.name} added successfully.`
    programDraftName.value = ''
    window.setTimeout(() => {
      closeAddProgramPanel()
    }, 420)
  } catch (error) {
    programPanelError.value = true
    programPanelMessage.value = resolveProgramMutationErrorMessage(error, mutationMode)
  } finally {
    isSavingProgram.value = false
  }
}

async function deleteProgramItem(program) {
  if (!program?.id || isSavingProgram.value) return

  const confirmed = window.confirm(`Delete ${program.name}?`)
  if (!confirmed) return

  isSavingProgram.value = true
  closeAllProgramSwipes()

  try {
    const nextPrograms = activePrograms.value.filter((item) => Number(item.id) !== Number(program.id))

    if (props.preview) {
      previewProgramOverrides.value = sortProgramsByName(nextPrograms)
      persistPreviewCollection(previewProgramStorageKey.value, previewProgramOverrides.value)
    } else {
      await deleteProgram(apiBaseUrl.value, localStorage.getItem('aura_token') || '', program.id)
      setProgramsSnapshot(sortProgramsByName(nextPrograms))
      refreshSchoolItWorkspaceData().catch(() => {})
    }

    if (Number(selectedProgramId.value) === Number(program.id)) {
      selectedProgramId.value = null
    }

    if (resolvedEditingProgramId.value === Number(program.id)) {
      closeAddProgramPanel()
    }
  } catch (error) {
    window.alert(resolveProgramMutationErrorMessage(error, 'delete'))
  } finally {
    isSavingProgram.value = false
  }
}

function manageProgram(program) {
  if (!program?.id || !selectedDepartment.value?.id) return
  closeAllProgramSwipes()
  resetProgramSwipeGesture()
  router.push({
    name: programRouteName.value,
    params: {
      departmentId: selectedDepartment.value.id,
      programId: program.id,
    },
  })
}

function createPreviewProgram(name) {
  return {
    id: Date.now(),
    school_id: schoolId.value,
    name,
    department_ids: [Number(selectedDepartment.value?.id)],
  }
}

function sortProgramsByName(items) {
  return [...items].sort((left, right) => String(left?.name || '').localeCompare(String(right?.name || '')))
}

function readPreviewCollection(storageKey, fallbackItems) {
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return fallbackItems
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : fallbackItems
  } catch {
    return fallbackItems
  }
}

function persistPreviewCollection(storageKey, items) {
  localStorage.setItem(storageKey, JSON.stringify(items))
}

function resolveProgramMutationErrorMessage(error, mode = 'create') {
  const verb = mode === 'delete'
    ? 'delete'
    : mode === 'update'
      ? 'update'
      : 'add'

  if (!(error instanceof BackendApiError)) {
    return `Unable to ${verb} this program right now.`
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
      return 'Program name must be between 2 and 100 characters.'
    }
    if (validationPath.includes('program_id')) {
      return 'The selected program could not be resolved. Please reopen the panel and try again.'
    }
    if (validationMessage) {
      return validationMessage
    }
    return 'Program name must be between 2 and 100 characters.'
  }

  if (error.status === 400 && /already exists/i.test(String(error.message || ''))) {
    return 'A program with this name already exists in this college.'
  }

  if (error.status === 400 && mode === 'delete' && /cannot delete program|referenced by other records/i.test(String(error.message || ''))) {
    return 'This program is still linked to student records and cannot be deleted yet.'
  }

  if (error.status === 403) {
    return `This session is not allowed to ${verb} programs right now.`
  }

  if (error.status === 409) {
    return 'This program is still linked to student records and cannot be deleted yet.'
  }

  return error.message || `Unable to ${verb} this program right now.`
}

function onProgramPanelBeforeEnter(element) {
  element.style.height = '0px'
  element.style.opacity = '0'
  element.style.transform = 'translateY(-8px)'
  element.style.willChange = 'height, opacity, transform'
}

function onProgramPanelEnter(element) {
  const height = element.scrollHeight
  element.style.transition = 'height 560ms cubic-bezier(0.22, 1, 0.36, 1), opacity 320ms ease, transform 460ms cubic-bezier(0.22, 1, 0.36, 1)'
  nextFrame(() => {
    element.style.height = `${height}px`
    element.style.opacity = '1'
    element.style.transform = 'translateY(0)'
  })
}

function onProgramPanelAfterEnter(element) {
  element.style.height = 'auto'
  element.style.transition = ''
  element.style.willChange = ''
}

function onProgramPanelBeforeLeave(element) {
  element.style.height = `${element.scrollHeight}px`
  element.style.opacity = '1'
  element.style.transform = 'translateY(0)'
  element.style.willChange = 'height, opacity, transform'
}

function onProgramPanelLeave(element) {
  element.style.transition = 'height 420ms cubic-bezier(0.4, 0, 0.2, 1), opacity 240ms ease, transform 300ms ease'
  nextFrame(() => {
    element.style.height = '0px'
    element.style.opacity = '0'
    element.style.transform = 'translateY(-6px)'
  })
}

function onProgramPanelAfterLeave(element) {
  element.style.transition = ''
  element.style.height = ''
  element.style.opacity = ''
  element.style.transform = ''
  element.style.willChange = ''
}

async function handleLogout() {
  await logout()
}

function getProgramSwipeOffset(programId) {
  return Number(programSwipeOffsets.value[programId] || 0)
}

function isProgramSwipeOpen(programId) {
  return getProgramSwipeOffset(programId) > 0
}

function getProgramSwipeStyle(programId) {
  return {
    '--program-swipe-offset': `${getProgramSwipeOffset(programId)}px`,
    '--program-swipe-action-width': `${PROGRAM_SWIPE_ACTION_WIDTH}px`,
  }
}

function setProgramSwipeOffset(programId, offset) {
  const normalizedOffset = Math.max(0, Math.min(PROGRAM_SWIPE_ACTION_WIDTH, Number(offset) || 0))
  if (normalizedOffset <= 0) {
    if (!Object.keys(programSwipeOffsets.value).length) return
    programSwipeOffsets.value = {}
    return
  }

  programSwipeOffsets.value = {
    [programId]: normalizedOffset,
  }
}

function closeAllProgramSwipes() {
  if (!hasOpenProgramSwipe.value) return
  programSwipeOffsets.value = {}
}

function handleDocumentPointerDown(event) {
  if (!hasOpenProgramSwipe.value) return
  if (!(event.target instanceof Element)) return
  if (event.target.closest('.school-it-department-programs__program-swipe')) return
  closeAllProgramSwipes()
}

function handleProgramCardClick(programId, event) {
  if (isProgramInteractiveTarget(event.target)) {
    return
  }

  if (programSwipeDidDrag.value) {
    event.preventDefault()
    event.stopPropagation()
    programSwipeDidDrag.value = false
    return
  }

  if (!isProgramSwipeOpen(programId)) return
  if (event.target instanceof Element && event.target.closest('.school-it-department-programs__manage-pill')) return

  event.preventDefault()
  event.stopPropagation()
  setProgramSwipeOffset(programId, 0)
}

function onProgramPointerDown(programId, event) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  if (!(event.currentTarget instanceof HTMLElement)) return
  if (isProgramInteractiveTarget(event.target)) return

  programSwipeDragId.value = programId
  programSwipePointerId.value = event.pointerId
  programSwipeStartX.value = event.clientX
  programSwipeStartY.value = event.clientY
  programSwipeStartOffset.value = getProgramSwipeOffset(programId)
  programSwipeAxisLock.value = null
  programSwipeDidDrag.value = false
  event.currentTarget.setPointerCapture?.(event.pointerId)
}

function onProgramPointerMove(programId, event) {
  if (programSwipeDragId.value !== programId) return
  if (programSwipePointerId.value !== event.pointerId) return

  const deltaX = event.clientX - programSwipeStartX.value
  const deltaY = event.clientY - programSwipeStartY.value

  if (!programSwipeAxisLock.value) {
    if (
      Math.abs(deltaX) < PROGRAM_SWIPE_GESTURE_THRESHOLD
      && Math.abs(deltaY) < PROGRAM_SWIPE_GESTURE_THRESHOLD
    ) {
      return
    }

    programSwipeAxisLock.value = Math.abs(deltaX) > Math.abs(deltaY) ? 'x' : 'y'
  }

  if (programSwipeAxisLock.value !== 'x') return

  programSwipeDidDrag.value = true
  event.preventDefault()
  setProgramSwipeOffset(programId, programSwipeStartOffset.value - deltaX)
}

function onProgramPointerEnd(programId, event) {
  if (programSwipeDragId.value !== programId) return
  if (programSwipePointerId.value !== event.pointerId) return

  const currentOffset = getProgramSwipeOffset(programId)
  const shouldOpen = currentOffset >= PROGRAM_SWIPE_OPEN_THRESHOLD
  setProgramSwipeOffset(programId, shouldOpen ? PROGRAM_SWIPE_ACTION_WIDTH : 0)

  if (event.currentTarget instanceof HTMLElement) {
    event.currentTarget.releasePointerCapture?.(event.pointerId)
  }

  resetProgramSwipeGesture()
}

function onProgramPointerCancel(programId, event) {
  if (programSwipeDragId.value !== programId) return
  if (programSwipePointerId.value !== event.pointerId) return

  const currentOffset = getProgramSwipeOffset(programId)
  const shouldOpen = currentOffset >= PROGRAM_SWIPE_OPEN_THRESHOLD
  setProgramSwipeOffset(programId, shouldOpen ? PROGRAM_SWIPE_ACTION_WIDTH : 0)
  resetProgramSwipeGesture()
}

function resetProgramSwipeGesture() {
  window.setTimeout(() => {
    programSwipeDidDrag.value = false
  }, 0)
  programSwipeDragId.value = null
  programSwipePointerId.value = null
  programSwipeAxisLock.value = null
}

function isProgramInteractiveTarget(target) {
  if (!(target instanceof Element)) return false
  return Boolean(
    target.closest(
      '.school-it-department-programs__manage-pill, .school-it-department-programs__program-action, button, a, input, textarea, select, label'
    )
  )
}
</script>

<style scoped>
.school-it-department-programs {
  min-height: 100vh;
  padding: 30px 28px 120px;
  font-family: 'Manrope', sans-serif;
}

.school-it-department-programs__shell {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
}

.school-it-department-programs__body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 24px;
}

.school-it-department-programs__title {
  margin: 0;
  font-size: 22px;
  line-height: 1;
  letter-spacing: -0.05em;
  font-weight: 800;
  color: var(--color-text-primary);
}

.school-it-department-programs__toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.school-it-department-programs__toolbar-row {
  display: flex;
  align-items: stretch;
  gap: clamp(8px, 3vw, 12px);
}

.school-it-department-programs__search-shell {
  flex: 1;
  min-width: 0;
  min-height: clamp(60px, 15vw, 64px);
  padding: 0 clamp(16px, 4vw, 18px);
  border-radius: 999px;
  background: var(--color-surface);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}

.school-it-department-programs__search-input {
  width: 100%;
  min-width: 0;
  border: none;
  background: transparent;
  outline: none;
  color: var(--color-text-always-dark);
  font-size: clamp(13px, 3.8vw, 14px);
  font-weight: 500;
}

.school-it-department-programs__search-input::placeholder {
  color: var(--color-text-muted);
}

.school-it-department-programs__search-icon {
  width: clamp(30px, 8vw, 32px);
  height: clamp(30px, 8vw, 32px);
  padding: 0;
  border: 1px solid var(--color-surface-border);
  border-radius: 999px;
  background: transparent;
  color: var(--color-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
  flex-shrink: 0;
}

.school-it-department-programs__search-icon :deep(svg) {
  display: block;
}

.school-it-department-programs__add-pill {
  width: clamp(118px, 31vw, 134px);
  min-height: clamp(60px, 15vw, 64px);
  padding: 0 clamp(14px, 4vw, 16px);
  border: none;
  border-radius: 999px;
  background: var(--color-search-pill-bg);
  color: var(--color-search-pill-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: clamp(8px, 2.8vw, 10px);
  flex-shrink: 0;
  transition: opacity 0.2s ease, transform 0.22s ease, filter 0.22s ease;
}

.school-it-department-programs__add-pill:hover {
  filter: brightness(1.05);
  transform: translateY(-1px);
}

.school-it-department-programs__add-pill:active {
  transform: scale(0.96);
}

.school-it-department-programs__add-pill-copy {
  font-size: clamp(12px, 3.4vw, 13px);
  line-height: 0.98;
  font-weight: 700;
  text-align: left;
}

.school-it-department-programs__panel {
  overflow: hidden;
  transform-origin: top center;
}

.school-it-department-programs__panel-inner {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 18px clamp(18px, 5vw, 24px) 22px;
  border-radius: 34px;
  background: var(--color-primary);
  color: var(--color-banner-text);
  box-shadow: 0 18px 36px rgba(0, 0, 0, 0.12);
}

.school-it-department-programs__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.school-it-department-programs__panel-close {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--color-banner-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.school-it-department-programs__panel-title {
  font-size: clamp(17px, 4.6vw, 20px);
  line-height: 1;
  font-weight: 700;
}

.school-it-department-programs__panel-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.school-it-department-programs__panel-input-shell {
  min-height: 64px;
  padding: 0 22px;
  border-radius: 999px;
  background: var(--color-surface);
  display: flex;
  align-items: center;
}

.school-it-department-programs__panel-input {
  width: 100%;
  border: none;
  background: transparent;
  outline: none;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-always-dark);
}

.school-it-department-programs__panel-input::placeholder {
  color: var(--color-text-muted);
}

.school-it-department-programs__panel-submit {
  width: min(100%, 144px);
  min-height: 54px;
  margin: 0 auto;
  border: 1.4px solid color-mix(in srgb, var(--color-text-always-dark) 24%, transparent);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-always-dark);
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  font-weight: 600;
}

.school-it-department-programs__panel-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.school-it-department-programs__panel-message {
  margin: 0;
  font-size: 13px;
  line-height: 1.35;
  font-weight: 600;
  color: var(--color-banner-text);
}

.school-it-department-programs__panel-message--error {
  color: #7A130E;
}

.school-it-department-programs__hero {
  display: grid;
  grid-template-columns: minmax(126px, 148px) minmax(0, 1fr);
  align-items: center;
  gap: clamp(14px, 4vw, 24px);
  padding: 20px 18px 18px;
  border-radius: 32px;
  background: var(--color-primary);
  color: var(--color-banner-text);
  overflow: hidden;
}

.school-it-department-programs__chart-fallback {
  width: clamp(132px, 34vw, 170px);
  aspect-ratio: 1;
  border-radius: 999px;
  border: 24px solid rgba(255, 255, 255, 0.28);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  flex-shrink: 0;
  text-align: center;
}

.school-it-department-programs__chart-fallback-value {
  font-size: clamp(22px, 6vw, 40px);
  line-height: 0.92;
  letter-spacing: -0.06em;
  font-weight: 700;
  color: var(--color-text-always-dark);
}

.school-it-department-programs__chart-fallback-label {
  max-width: 72px;
  font-size: clamp(10px, 2.8vw, 12px);
  line-height: 1.05;
  font-weight: 700;
  color: var(--color-text-always-dark);
}

.school-it-department-programs__hero-copy {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.school-it-department-programs__hero-title {
  margin: 0;
  font-size: clamp(28px, 8vw, 42px);
  line-height: 0.92;
  letter-spacing: -0.06em;
  font-weight: 700;
  color: var(--color-banner-text);
  word-break: break-word;
}

.school-it-department-programs__legend {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.school-it-department-programs__legend-item {
  width: fit-content;
  max-width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--color-banner-text);
  text-align: left;
  transition: opacity 0.2s ease, transform 0.22s ease;
}

.school-it-department-programs__legend-item--active {
  transform: translateX(2px);
}

.school-it-department-programs__legend-item:not(.school-it-department-programs__legend-item--active) {
  opacity: 0.72;
}

.school-it-department-programs__legend-dot {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  flex-shrink: 0;
}

.school-it-department-programs__legend-dot--light {
  box-shadow: inset 0 0 0 1px rgba(10, 10, 10, 0.1);
}

.school-it-department-programs__legend-label {
  font-size: clamp(12px, 3.3vw, 14px);
  line-height: 1.15;
  font-weight: 500;
  word-break: break-word;
}

.school-it-department-programs__hero-empty {
  margin: 0;
  font-size: 14px;
  line-height: 1.35;
  color: color-mix(in srgb, var(--color-banner-text) 78%, transparent);
}

.school-it-department-programs__program-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.school-it-department-programs__program-swipe {
  position: relative;
  border-radius: 30px;
  overflow: hidden;
  touch-action: pan-y;
}

.school-it-department-programs__program-swipe--open .school-it-department-programs__program-action-rail {
  pointer-events: auto;
}

.school-it-department-programs__program-swipe--open .school-it-department-programs__program-action {
  opacity: 1;
  transform: translateX(0);
}

.school-it-department-programs__program-action-rail {
  position: absolute;
  inset: 0 0 0 auto;
  width: var(--program-swipe-action-width, 100px);
  padding: 0 4px 0 0;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}

.school-it-department-programs__program-action {
  width: 42px;
  border: 1px solid color-mix(in srgb, var(--color-text-muted) 22%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-surface) 92%, var(--color-bg));
  color: var(--color-text-always-dark);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0.72;
  transform: translateX(8px);
  transition: transform 0.32s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.24s ease, border-color 0.24s ease;
}

.school-it-department-programs__program-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.school-it-department-programs__program-action:active {
  transform: scale(0.96);
}

.school-it-department-programs__program-action--delete {
  min-height: 86px;
  color: #ff3b30;
  border-color: color-mix(in srgb, #ff3b30 48%, transparent);
}

.school-it-department-programs__program-action--edit {
  width: 40px;
  min-height: 70px;
}

.school-it-department-programs__program-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  min-height: 122px;
  padding: 18px 16px 18px 18px;
  border-radius: 32px;
  background: var(--color-surface);
  transform: translate3d(calc(var(--program-swipe-offset, 0px) * -1), 0, 0);
  transition: transform 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}

.school-it-department-programs__program-title {
  margin: 0;
  max-width: 8.4ch;
  font-size: clamp(21px, 6.8vw, 38px);
  line-height: 0.94;
  letter-spacing: -0.06em;
  font-weight: 700;
  color: var(--color-primary);
}

.school-it-department-programs__manage-pill {
  min-width: 124px;
  min-height: 54px;
  padding: 0 18px 0 6px;
  border: none;
  border-radius: 999px;
  background: var(--color-primary);
  color: var(--color-banner-text);
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  line-height: 1;
  font-weight: 700;
  white-space: nowrap;
  flex-shrink: 0;
  cursor: pointer;
  transition: transform 0.2s ease, filter 0.2s ease;
}

.school-it-department-programs__manage-pill:hover {
  filter: brightness(1.08);
}

.school-it-department-programs__manage-pill:active {
  transform: scale(0.96);
}

.school-it-department-programs__manage-pill-icon {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  background: var(--color-nav);
  color: var(--color-nav-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.school-it-department-programs__empty {
  margin: 0;
  padding: 12px 4px;
  font-size: 15px;
  line-height: 1.4;
  font-weight: 600;
  color: var(--color-text-muted);
  text-align: center;
}

@media (min-width: 768px) {
  .school-it-department-programs {
    padding: 40px 36px 56px;
  }

  .school-it-department-programs__body {
    margin-top: 30px;
    gap: 22px;
  }

  .school-it-department-programs__title {
    font-size: 28px;
  }

  .school-it-department-programs__toolbar {
    max-width: 820px;
  }

  .school-it-department-programs__hero {
    max-width: 820px;
    grid-template-columns: 180px minmax(0, 1fr);
    padding: 24px 22px 22px;
  }

  .school-it-department-programs__program-list {
    max-width: 820px;
  }
}

@media (max-width: 399px) {
  .school-it-department-programs__hero {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
  }

  .school-it-department-programs__hero-copy {
    align-items: center;
  }

  .school-it-department-programs__legend {
    align-items: flex-start;
  }

  .school-it-department-programs__program-card {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .school-it-department-programs__program-swipe {
    border-radius: 28px;
  }

  .school-it-department-programs__program-action-rail {
    width: var(--program-swipe-action-width, 100px);
    padding-right: 4px;
    gap: 8px;
  }

  .school-it-department-programs__program-action {
    width: 40px;
  }

  .school-it-department-programs__program-action--delete {
    min-height: 82px;
  }

  .school-it-department-programs__program-action--edit {
    width: 38px;
    min-height: 66px;
  }

  .school-it-department-programs__program-card {
    min-height: 116px;
    gap: 14px;
    padding: 16px 14px 16px 16px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .school-it-department-programs__add-pill,
  .school-it-department-programs__legend-item,
  .school-it-department-programs__program-card,
  .school-it-department-programs__program-action {
    transition: none;
  }
}
</style>
