<template>
  <section class="school-it-program-students">
    <div class="school-it-program-students__shell">
      <SchoolItTopHeader
        class="dashboard-enter dashboard-enter--1"
        :avatar-url="avatarUrl"
        :school-name="activeSchoolSettings?.school_name || activeUser?.school_name || ''"
        :display-name="displayName"
        :initials="initials"
        @logout="handleLogout"
      />

      <div class="school-it-program-students__body">
        <h1 class="school-it-program-students__title dashboard-enter dashboard-enter--2">
          {{ selectedProgram?.name || 'Program' }}
        </h1>

        <section
          class="school-it-program-students__toolbar dashboard-enter dashboard-enter--3"
          :class="{
            'school-it-program-students__toolbar--searching': searchActive,
            'school-it-program-students__toolbar--sorting': isSortMenuOpen,
          }"
        >
          <div class="school-it-program-students__search-wrap" :class="{ 'school-it-program-students__search-wrap--active': searchActive }">
            <div
              class="school-it-program-students__search-shell"
              :class="{ 'school-it-program-students__search-shell--open': searchActive }"
            >
              <div class="school-it-program-students__search-input-row">
                <input
                  v-model="searchQuery"
                  v-bind="studentSearchInputAttrs"
                  class="school-it-program-students__search-input"
                  type="text"
                  placeholder="Search students"
                >
                <span class="school-it-program-students__search-icon-wrap" aria-hidden="true">
                  <Search class="school-it-program-students__search-icon" :size="14" />
                </span>
              </div>

              <div class="school-it-program-students__search-results">
                <div class="school-it-program-students__search-results-inner">
                  <template v-if="searchActive">
                    <button
                      v-for="student in searchResults"
                      :key="student.id"
                      class="school-it-program-students__search-result"
                      type="button"
                      @click="handleSearchResult(student)"
                    >
                      <span class="school-it-program-students__search-pill">{{ student.studentId }}</span>
                      <span class="school-it-program-students__search-result-name">{{ student.fullName }}</span>
                    </button>

                    <p
                      v-if="!searchResults.length"
                      class="school-it-program-students__search-empty"
                    >
                      No matching students.
                    </p>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <div
            class="school-it-program-students__sort-wrap"
            :class="{ 'school-it-program-students__sort-wrap--open': isSortMenuOpen }"
          >
            <button
              class="school-it-program-students__sort-pill"
              type="button"
              :aria-expanded="isSortMenuOpen ? 'true' : 'false'"
              @click="isSortMenuOpen = !isSortMenuOpen"
            >
              <ChevronDown :size="18" />
              Sort
            </button>

            <div
              class="school-it-program-students__sort-menu"
              :class="{ 'school-it-program-students__sort-menu--open': isSortMenuOpen }"
              role="menu"
              :aria-hidden="isSortMenuOpen ? 'false' : 'true'"
              aria-label="Sort students"
            >
              <button
                v-for="option in sortOptions"
                :key="option.id"
                class="school-it-program-students__sort-option"
                :class="{ 'school-it-program-students__sort-option--active': option.id === sortMode }"
                type="button"
                role="menuitemradio"
                :aria-checked="option.id === sortMode ? 'true' : 'false'"
                :tabindex="isSortMenuOpen ? 0 : -1"
                @click="selectSortMode(option.id)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <button
            class="school-it-program-students__add-pill"
            type="button"
            :disabled="!selectedProgram || isSavingStudent"
            @click="openAddStudentSheet"
          >
            <span class="school-it-program-students__add-pill-icon">
              <Plus :size="16" />
            </span>
            <span>Add Student</span>
          </button>
        </section>

        <section
          v-if="selectedProgram"
          class="school-it-program-students__card dashboard-enter dashboard-enter--4"
        >
          <h2 class="school-it-program-students__section-title">Students</h2>

          <div v-if="visibleStudents.length" class="school-it-program-students__list">
            <article
              v-for="student in visibleStudents"
              :key="student.id"
              :ref="(element) => setStudentRowRef(student.id, element)"
              class="school-it-program-students__row"
              :class="{ 'school-it-program-students__row--highlighted': highlightedStudentId === student.id }"
            >
              <div class="school-it-program-students__row-copy">
                <span class="school-it-program-students__student-id">{{ student.studentId }}</span>
                <span class="school-it-program-students__student-name">{{ student.fullName }}</span>
              </div>

              <div class="school-it-program-students__row-actions">
                <button
                  class="school-it-program-students__icon-button school-it-program-students__icon-button--danger"
                  type="button"
                  :disabled="student.isMutating || props.preview"
                  aria-label="Delete student"
                  @click="deleteStudent(student)"
                >
                  <Trash2 :size="18" />
                </button>

                <button
                  class="school-it-program-students__icon-button"
                  type="button"
                  :disabled="student.isMutating || isSavingEditedStudent"
                  aria-label="Edit student"
                  @click="openEditStudentSheet(student)"
                >
                  <Pencil :size="18" />
                </button>
              </div>
            </article>
          </div>

          <p v-else class="school-it-program-students__empty">
            {{ emptyMessage }}
          </p>

          <div
            v-if="feedbackMessage"
            class="school-it-program-students__feedback"
            :class="{ 'school-it-program-students__feedback--error': feedbackTone === 'error' }"
          >
            <p class="school-it-program-students__feedback-title">{{ feedbackMessage }}</p>
            <p v-if="feedbackDetail" class="school-it-program-students__feedback-detail">
              {{ feedbackDetail }}
            </p>
          </div>
        </section>

        <p
          v-else-if="isProgramDataLoading"
          class="school-it-program-students__empty dashboard-enter dashboard-enter--4"
        >
          Loading program details...
        </p>

        <p
          v-else-if="isProgramDataUnavailable"
          class="school-it-program-students__empty dashboard-enter dashboard-enter--4"
        >
          Program data is unavailable right now.
        </p>

        <p
          v-else
          class="school-it-program-students__empty dashboard-enter dashboard-enter--4"
        >
          This program could not be found.
        </p>
      </div>
    </div>

    <Transition name="school-it-program-students-sheet">
      <div
        v-if="isAddStudentSheetOpen"
        class="school-it-program-students__sheet-backdrop"
        @click.self="closeAddStudentSheet"
      >
        <section class="school-it-program-students__sheet">
          <header class="school-it-program-students__sheet-header">
            <div>
              <h2 class="school-it-program-students__sheet-title">Add Student</h2>
              <p class="school-it-program-students__sheet-copy">
                New student accounts created here will be assigned directly to
                {{ selectedProgram?.name || 'this program' }}.
              </p>
            </div>

            <button
              class="school-it-program-students__sheet-close"
              type="button"
              aria-label="Close add student form"
              @click="closeAddStudentSheet"
            >
              <X :size="18" />
            </button>
          </header>

          <form class="school-it-program-students__form" @submit.prevent="handleAddStudent">
            <div class="school-it-program-students__scope-grid">
              <div class="school-it-program-students__scope-card">
                <span class="school-it-program-students__scope-label">College</span>
                <span class="school-it-program-students__scope-value">{{ selectedDepartment?.name || 'Unassigned department' }}</span>
              </div>

              <div class="school-it-program-students__scope-card">
                <span class="school-it-program-students__scope-label">Program</span>
                <span class="school-it-program-students__scope-value">{{ selectedProgram?.name || 'Unassigned program' }}</span>
              </div>
            </div>

            <div class="school-it-program-students__form-grid">
              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">First Name</span>
                <input
                  v-model="studentDraft.firstName"
                  class="school-it-program-students__field-input"
                  type="text"
                  name="student_first_name"
                  autocomplete="given-name"
                  placeholder="e.g., Juan"
                >
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">Last Name</span>
                <input
                  v-model="studentDraft.lastName"
                  class="school-it-program-students__field-input"
                  type="text"
                  name="student_last_name"
                  autocomplete="family-name"
                  placeholder="e.g., Dela Cruz"
                >
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">Middle Name</span>
                <input
                  v-model="studentDraft.middleName"
                  class="school-it-program-students__field-input"
                  type="text"
                  name="student_middle_name"
                  autocomplete="additional-name"
                  placeholder="Optional"
                >
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">Student ID</span>
                <input
                  v-model="studentDraft.studentId"
                  class="school-it-program-students__field-input"
                  type="text"
                  name="student_id"
                  autocomplete="off"
                  placeholder="e.g., CPE-2026-001"
                >
              </label>

              <label class="school-it-program-students__field school-it-program-students__field--wide">
                <span class="school-it-program-students__field-label">Email</span>
                <input
                  v-model="studentDraft.email"
                  class="school-it-program-students__field-input"
                  type="email"
                  name="student_email"
                  autocomplete="email"
                  placeholder="student@example.com"
                >
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">Year Level</span>
                <select
                  v-model="studentDraft.yearLevel"
                  class="school-it-program-students__field-input school-it-program-students__field-input--select"
                  name="student_year_level"
                >
                  <option value="">Select year</option>
                  <option v-for="year in yearLevelOptions" :key="year" :value="String(year)">
                    Year {{ year }}
                  </option>
                </select>
              </label>
            </div>

            <p class="school-it-program-students__sheet-note">
              The backend creates the student account, links the student to this college and program,
              generates a temporary password, and sends that password through the welcome email.
            </p>

            <p
              v-if="sheetMessage"
              class="school-it-program-students__sheet-feedback"
              :class="{ 'school-it-program-students__sheet-feedback--error': sheetTone === 'error' }"
            >
              {{ sheetMessage }}
            </p>

            <div class="school-it-program-students__sheet-actions">
              <button
                class="school-it-program-students__sheet-secondary"
                type="button"
                :disabled="isSavingStudent"
                @click="closeAddStudentSheet"
              >
                Cancel
              </button>

              <button
                class="school-it-program-students__sheet-primary"
                type="submit"
                :disabled="addStudentSubmitDisabled"
              >
                {{ isSavingStudent ? 'Adding Student...' : 'Add Student' }}
              </button>
            </div>
          </form>
        </section>
      </div>
    </Transition>

    <Transition name="school-it-program-students-sheet">
      <div
        v-if="isEditStudentSheetOpen"
        class="school-it-program-students__sheet-backdrop"
        @click.self="closeEditStudentSheet"
      >
        <section class="school-it-program-students__sheet">
          <header class="school-it-program-students__sheet-header">
            <div>
              <h2 class="school-it-program-students__sheet-title">Edit Student</h2>
              <p class="school-it-program-students__sheet-copy">
                Campus Admin can update the student's account info, student ID, year level,
                college, and program from this screen.
              </p>
            </div>

            <button
              class="school-it-program-students__sheet-close"
              type="button"
              aria-label="Close edit student form"
              @click="closeEditStudentSheet"
            >
              <X :size="18" />
            </button>
          </header>

          <form class="school-it-program-students__form" @submit.prevent="handleEditStudent">
            <div class="school-it-program-students__form-grid">
              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">First Name</span>
                <input
                  v-model="editStudentDraft.firstName"
                  class="school-it-program-students__field-input"
                  type="text"
                  name="edit_student_first_name"
                  autocomplete="given-name"
                  placeholder="e.g., Juan"
                >
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">Last Name</span>
                <input
                  v-model="editStudentDraft.lastName"
                  class="school-it-program-students__field-input"
                  type="text"
                  name="edit_student_last_name"
                  autocomplete="family-name"
                  placeholder="e.g., Dela Cruz"
                >
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">Middle Name</span>
                <input
                  v-model="editStudentDraft.middleName"
                  class="school-it-program-students__field-input"
                  type="text"
                  name="edit_student_middle_name"
                  autocomplete="additional-name"
                  placeholder="Optional"
                >
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">Student ID</span>
                <input
                  v-model="editStudentDraft.studentId"
                  class="school-it-program-students__field-input"
                  type="text"
                  name="edit_student_id"
                  autocomplete="off"
                  placeholder="e.g., CPE-2026-001"
                >
              </label>

              <label class="school-it-program-students__field school-it-program-students__field--wide">
                <span class="school-it-program-students__field-label">Email</span>
                <input
                  v-model="editStudentDraft.email"
                  class="school-it-program-students__field-input"
                  type="email"
                  name="edit_student_email"
                  autocomplete="email"
                  placeholder="student@example.com"
                >
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">Year Level</span>
                <select
                  v-model="editStudentDraft.yearLevel"
                  class="school-it-program-students__field-input school-it-program-students__field-input--select"
                  name="edit_student_year_level"
                >
                  <option value="">Select year</option>
                  <option v-for="year in yearLevelOptions" :key="year" :value="String(year)">
                    Year {{ year }}
                  </option>
                </select>
              </label>

              <label class="school-it-program-students__field">
                <span class="school-it-program-students__field-label">College</span>
                <select
                  v-model="editStudentDraft.departmentId"
                  class="school-it-program-students__field-input school-it-program-students__field-input--select"
                  name="edit_student_department"
                >
                  <option value="">Select college</option>
                  <option
                    v-for="department in normalizedDepartments"
                    :key="department.id"
                    :value="String(department.id)"
                  >
                    {{ department.name }}
                  </option>
                </select>
              </label>

              <label class="school-it-program-students__field school-it-program-students__field--wide">
                <span class="school-it-program-students__field-label">Program</span>
                <select
                  v-model="editStudentDraft.programId"
                  class="school-it-program-students__field-input school-it-program-students__field-input--select"
                  name="edit_student_program"
                  :disabled="!editStudentDraft.departmentId"
                >
                  <option value="">Select program</option>
                  <option
                    v-for="program in availableProgramsForEditDraft"
                    :key="program.id"
                    :value="String(program.id)"
                  >
                    {{ program.name }}
                  </option>
                </select>
              </label>
            </div>

            <p class="school-it-program-students__sheet-note">
              Password changes are not part of the backend student edit routes. This screen updates
              the user account and student profile fields that Campus Admin is allowed to edit.
            </p>

            <p
              v-if="editSheetMessage"
              class="school-it-program-students__sheet-feedback"
              :class="{ 'school-it-program-students__sheet-feedback--error': editSheetTone === 'error' }"
            >
              {{ editSheetMessage }}
            </p>

            <div class="school-it-program-students__sheet-actions">
              <button
                class="school-it-program-students__sheet-secondary"
                type="button"
                :disabled="isSavingEditedStudent"
                @click="closeEditStudentSheet"
              >
                Cancel
              </button>

              <button
                class="school-it-program-students__sheet-primary"
                type="submit"
                :disabled="editStudentSubmitDisabled"
              >
                {{ isSavingEditedStudent ? 'Saving...' : 'Save Changes' }}
              </button>
            </div>
          </form>
        </section>
      </div>
    </Transition>

    <Transition name="school-it-program-students-sheet">
      <div
        v-if="createdStudentSummary"
        class="school-it-program-students__sheet-backdrop"
        @click.self="closeCreatedStudentDialog"
      >
        <section class="school-it-program-students__sheet school-it-program-students__sheet--success">
          <header class="school-it-program-students__sheet-header">
            <div>
              <h2 class="school-it-program-students__sheet-title">Account Created Successfully</h2>
              <p class="school-it-program-students__sheet-copy">
                {{ createdStudentSummary.fullName }} was added to {{ createdStudentSummary.programName }}.
              </p>
            </div>

            <button
              class="school-it-program-students__sheet-close"
              type="button"
              aria-label="Close student creation confirmation"
              @click="closeCreatedStudentDialog"
            >
              <X :size="18" />
            </button>
          </header>

          <div class="school-it-program-students__success-grid">
            <div class="school-it-program-students__scope-grid">
              <div class="school-it-program-students__scope-card">
                <span class="school-it-program-students__scope-label">College</span>
                <span class="school-it-program-students__scope-value">{{ createdStudentSummary.departmentName }}</span>
              </div>

              <div class="school-it-program-students__scope-card">
                <span class="school-it-program-students__scope-label">Program</span>
                <span class="school-it-program-students__scope-value">{{ createdStudentSummary.programName }}</span>
              </div>
            </div>

            <div class="school-it-program-students__success-card">
              <div class="school-it-program-students__success-row">
                <span class="school-it-program-students__success-label">Student</span>
                <strong class="school-it-program-students__success-value">{{ createdStudentSummary.fullName }}</strong>
              </div>

              <div class="school-it-program-students__success-row">
                <span class="school-it-program-students__success-label">Student ID</span>
                <strong class="school-it-program-students__success-value">{{ createdStudentSummary.studentIdValue }}</strong>
              </div>

              <div class="school-it-program-students__success-row">
                <span class="school-it-program-students__success-label">Email</span>
                <strong class="school-it-program-students__success-value school-it-program-students__success-value--break">
                  {{ createdStudentSummary.email }}
                </strong>
              </div>

              <div class="school-it-program-students__success-row">
                <span class="school-it-program-students__success-label">Credential Delivery</span>
                <strong class="school-it-program-students__success-value school-it-program-students__success-value--break">
                  {{ createdStudentSummary.deliveryValue }}
                </strong>
              </div>
            </div>
          </div>

          <p class="school-it-program-students__sheet-note">
            {{ createdStudentSummary.emailStatus }}
          </p>

          <div class="school-it-program-students__sheet-actions">
            <button
              class="school-it-program-students__sheet-secondary"
              type="button"
              @click="closeCreatedStudentDialog"
            >
              Exit
            </button>

            <button
              class="school-it-program-students__sheet-primary"
              type="button"
              @click="addAnotherStudent"
            >
              Add Again
            </button>
          </div>
        </section>
      </div>
    </Transition>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronDown, Pencil, Plus, Search, Trash2, X } from 'lucide-vue-next'
import SchoolItTopHeader from '@/components/dashboard/SchoolItTopHeader.vue'
import { schoolItPreviewData } from '@/data/schoolItPreview.js'
import { useAuth } from '@/composables/useAuth.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { usePreviewTheme } from '@/composables/usePreviewTheme.js'
import { useSchoolItWorkspaceData } from '@/composables/useSchoolItWorkspaceData.js'
import {
  BackendApiError,
  createStudentAccount,
  deleteUser,
  updateStudentProfile,
  updateUser,
} from '@/services/backendApi.js'
import { createSearchFieldAttrs } from '@/services/searchFieldAttrs.js'
import { filterWorkspaceEntitiesBySchool } from '@/services/workspaceScope.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const sortOptions = [
  { id: 'first-name-asc', label: 'First Name A-Z' },
  { id: 'first-name-desc', label: 'First Name Z-A' },
  { id: 'last-name-asc', label: 'Last Name A-Z' },
  { id: 'last-name-desc', label: 'Last Name Z-A' },
  { id: 'id-asc', label: 'ID Number 0-9' },
  { id: 'id-desc', label: 'ID Number 9-0' },
]
const yearLevelOptions = [1, 2, 3, 4, 5]

const route = useRoute()
const searchQuery = ref('')
const studentSearchInputAttrs = createSearchFieldAttrs('school-it-student-search')
const sortMode = ref(sortOptions[0].id)
const isSortMenuOpen = ref(false)
const isAddStudentSheetOpen = ref(false)
const isSavingStudent = ref(false)
const isEditStudentSheetOpen = ref(false)
const isSavingEditedStudent = ref(false)
const feedbackMessage = ref('')
const feedbackDetail = ref('')
const feedbackTone = ref('info')
const sheetMessage = ref('')
const sheetTone = ref('info')
const editSheetMessage = ref('')
const editSheetTone = ref('info')
const createdStudentSummary = ref(null)
const mutatingStudentIds = ref([])
const highlightedStudentId = ref(null)
const studentRowRefs = new Map()
const isSelectingSearchResult = ref(false)
const previewUsersSnapshot = ref(
  Array.isArray(schoolItPreviewData.users) ? schoolItPreviewData.users.map((user) => ({ ...user })) : []
)
const studentDraft = ref(createEmptyStudentDraft())
const editingStudent = ref(null)
const editStudentDraft = ref(createEmptyEditStudentDraft())

const { logout } = useAuth()
const { currentUser, schoolSettings, apiBaseUrl } = useDashboardSession()
const {
  departments,
  programs,
  users,
  statuses: workspaceStatuses,
  initializeSchoolItWorkspaceData,
  refreshSchoolItWorkspaceData,
  setUsersSnapshot,
} = useSchoolItWorkspaceData()

const departmentId = computed(() => normalizeRouteId(route.params.departmentId))
const programId = computed(() => normalizeRouteId(route.params.programId))
const activeUser = computed(() => props.preview ? schoolItPreviewData.user : currentUser.value)
const activeSchoolSettings = computed(() => props.preview ? schoolItPreviewData.schoolSettings : schoolSettings.value)
const activeDepartments = computed(() => props.preview ? schoolItPreviewData.departments : departments.value)
const activePrograms = computed(() => props.preview ? schoolItPreviewData.programs : programs.value)
const activeUsers = computed(() => props.preview ? previewUsersSnapshot.value : users.value)

usePreviewTheme(() => props.preview, activeSchoolSettings)
const schoolId = computed(() => Number(activeUser.value?.school_id ?? activeSchoolSettings.value?.school_id))
const filteredDepartments = computed(() => filterWorkspaceEntitiesBySchool(activeDepartments.value, schoolId.value))
const filteredPrograms = computed(() => filterWorkspaceEntitiesBySchool(activePrograms.value, schoolId.value))
const filteredUsers = computed(() => filterWorkspaceEntitiesBySchool(activeUsers.value, schoolId.value))
const normalizedDepartments = computed(() => filteredDepartments.value.filter(isWorkspaceRecord))
const normalizedPrograms = computed(() => filteredPrograms.value.filter(isWorkspaceRecord))
const normalizedUsers = computed(() => filteredUsers.value.filter(isWorkspaceRecord))
const studentUsers = computed(() => normalizedUsers.value.filter(isStudentUser))
const departmentsStatus = computed(() => workspaceStatuses.value?.departments || 'idle')
const programsStatus = computed(() => workspaceStatuses.value?.programs || 'idle')
const usersStatus = computed(() => workspaceStatuses.value?.users || 'idle')
const avatarUrl = computed(() => activeUser.value?.avatar_url || '')
const displayName = computed(() => {
  const first = activeUser.value?.first_name || ''
  const middle = activeUser.value?.middle_name || ''
  const last = activeUser.value?.last_name || ''
  return [first, middle, last].filter(Boolean).join(' ') || activeUser.value?.email?.split('@')[0] || 'School IT'
})
const initials = computed(() => buildInitials(displayName.value))

const selectedDepartment = computed(() => (
  normalizedDepartments.value.find((department) => Number(department?.id) === departmentId.value) || null
))

const selectedProgram = computed(() => {
  const match = normalizedPrograms.value.find((program) => Number(program?.id) === programId.value)
  if (!match) return null

  const programDepartmentIds = Array.isArray(match.department_ids) ? match.department_ids.map(Number) : []
  if (departmentId.value != null && programDepartmentIds.length && !programDepartmentIds.includes(departmentId.value)) {
    return null
  }

  return match
})

const isProgramDataLoading = computed(() => (
  !selectedProgram.value &&
  ['idle', 'loading'].includes(programsStatus.value)
))

const isProgramDataUnavailable = computed(() => (
  !selectedProgram.value &&
  ['blocked', 'error'].includes(programsStatus.value)
))

const programStudents = computed(() => (
  studentUsers.value
    .filter((user) => Number(user?.student_profile?.program_id) === programId.value)
    .map((user) => ({
      id: Number(user.id),
      userId: Number(user.id),
      firstName: String(user.first_name || '').trim(),
      middleName: String(user.middle_name || '').trim(),
      lastName: String(user.last_name || '').trim(),
      email: String(user.email || '').trim(),
      fullName: [user.first_name, user.last_name].filter(Boolean).join(' ').trim() || user.email || 'Student',
      studentId: String(user?.student_profile?.student_id || user.id || ''),
      profileId: Number(user?.student_profile?.id),
      profile: user?.student_profile || null,
      departmentId: normalizeRouteId(user?.student_profile?.department_id),
      programId: normalizeRouteId(user?.student_profile?.program_id),
      yearLevel: normalizeRouteId(user?.student_profile?.year_level),
      sourceUser: user,
      searchText: [
        user?.student_profile?.student_id,
        user.first_name,
        user.middle_name,
        user.last_name,
        user.email,
      ].filter(Boolean).join(' ').toLowerCase(),
      isMutating: mutatingStudentIds.value.includes(Number(user.id)),
    }))
))

const visibleStudents = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const filtered = !query
    ? programStudents.value
    : programStudents.value.filter((student) => student.searchText.includes(query))

  return [...filtered].sort((left, right) => {
    if (sortMode.value === 'first-name-asc') {
      return left.firstName.localeCompare(right.firstName) || left.fullName.localeCompare(right.fullName)
    }
    if (sortMode.value === 'first-name-desc') {
      return right.firstName.localeCompare(left.firstName) || right.fullName.localeCompare(left.fullName)
    }
    if (sortMode.value === 'last-name-asc') {
      return left.lastName.localeCompare(right.lastName) || left.fullName.localeCompare(right.fullName)
    }
    if (sortMode.value === 'last-name-desc') {
      return right.lastName.localeCompare(left.lastName) || right.fullName.localeCompare(left.fullName)
    }
    if (sortMode.value === 'id-desc') {
      return right.studentId.localeCompare(left.studentId, undefined, { numeric: true, sensitivity: 'base' })
    }
    return left.studentId.localeCompare(right.studentId, undefined, { numeric: true, sensitivity: 'base' })
  })
})

const searchActive = computed(() => searchQuery.value.trim().length > 0)
const addStudentSubmitDisabled = computed(() => (
  isSavingStudent.value
  || !selectedProgram.value
  || !selectedDepartment.value
  || !canSubmitStudentDraft(studentDraft.value)
))
const availableProgramsForEditDraft = computed(() => {
  const normalizedDepartmentId = normalizeRouteId(editStudentDraft.value.departmentId)
  if (normalizedDepartmentId == null) return []

  return normalizedPrograms.value.filter((program) => {
    const departmentIds = Array.isArray(program?.department_ids) ? program.department_ids.map(Number) : []
    return !departmentIds.length || departmentIds.includes(normalizedDepartmentId)
  })
})
const editStudentSubmitDisabled = computed(() => (
  isSavingEditedStudent.value
  || !editingStudent.value
  || !canSubmitEditStudentDraft(editStudentDraft.value)
))
const searchResults = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return []
  return programStudents.value
    .filter((student) => student.searchText.includes(query))
    .slice(0, 8)
})

const emptyMessage = computed(() => {
  if (searchQuery.value.trim()) {
    return 'No students match this search.'
  }
  if ((usersStatus.value === 'idle' || usersStatus.value === 'loading') && programStudents.value.length <= 0) {
    return 'Loading students...'
  }
  if (['blocked', 'error'].includes(usersStatus.value) && programStudents.value.length <= 0) {
    return 'Students are unavailable right now.'
  }
  return 'No students are assigned to this program yet.'
})

watch([apiBaseUrl, () => activeUser.value?.id, () => props.preview], async ([resolvedApiBaseUrl, userId, preview]) => {
  if (preview) return
  if (!resolvedApiBaseUrl || !userId) return
  await initializeSchoolItWorkspaceData()
}, { immediate: true })

watch(searchQuery, () => {
  feedbackMessage.value = ''
  feedbackDetail.value = ''
  if (!isSelectingSearchResult.value) {
    highlightedStudentId.value = null
  }
  isSortMenuOpen.value = false
})

watch(isAddStudentSheetOpen, (open) => {
  if (!open) {
    resetStudentDraft()
  }
})

watch(isEditStudentSheetOpen, (open) => {
  if (!open) {
    resetEditStudentDraft()
  }
})

watch(() => editStudentDraft.value.departmentId, (departmentIdValue) => {
  const normalizedDepartmentId = normalizeRouteId(departmentIdValue)
  if (normalizedDepartmentId == null) {
    editStudentDraft.value.programId = ''
    return
  }

  const hasMatchingProgram = availableProgramsForEditDraft.value.some((program) => (
    Number(program?.id) === normalizeRouteId(editStudentDraft.value.programId)
  ))
  if (!hasMatchingProgram) {
    editStudentDraft.value.programId = ''
  }
})

onBeforeUnmount(() => {
  isSortMenuOpen.value = false
  studentRowRefs.clear()
})

function normalizeRouteId(value) {
  const normalized = Number(value)
  return Number.isFinite(normalized) ? normalized : null
}

function buildInitials(value) {
  const parts = String(value || '').split(' ').filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  return String(value || '').slice(0, 2).toUpperCase()
}

function isWorkspaceRecord(value) {
  return Boolean(value) && typeof value === 'object'
}

function isStudentUser(user) {
  const roles = Array.isArray(user?.roles)
    ? user.roles.map((role) => String(role?.role?.name || role?.name || '').toLowerCase())
    : []
  return Boolean(user?.student_profile) || roles.includes('student')
}

function selectSortMode(nextSortMode) {
  sortMode.value = nextSortMode
  isSortMenuOpen.value = false
}

function createEmptyStudentDraft() {
  return {
    firstName: '',
    middleName: '',
    lastName: '',
    email: '',
    studentId: '',
    yearLevel: '',
  }
}

function createEmptyEditStudentDraft() {
  return {
    firstName: '',
    middleName: '',
    lastName: '',
    email: '',
    studentId: '',
    yearLevel: '',
    departmentId: '',
    programId: '',
  }
}

function resetStudentDraft() {
  studentDraft.value = createEmptyStudentDraft()
  sheetMessage.value = ''
  sheetTone.value = 'info'
}

function resetEditStudentDraft() {
  editingStudent.value = null
  editStudentDraft.value = createEmptyEditStudentDraft()
  editSheetMessage.value = ''
  editSheetTone.value = 'info'
}

function closeCreatedStudentDialog() {
  createdStudentSummary.value = null
}

function addAnotherStudent() {
  closeCreatedStudentDialog()
  openAddStudentSheet()
}

function canSubmitStudentDraft(draft) {
  const email = String(draft?.email || '').trim()
  return (
    String(draft?.firstName || '').trim().length > 0
    && String(draft?.lastName || '').trim().length > 0
    && String(draft?.studentId || '').trim().length > 0
    && String(draft?.yearLevel || '').trim().length > 0
    && email.length > 0
    && /\S+@\S+\.\S+/.test(email)
  )
}

function canSubmitEditStudentDraft(draft) {
  const email = String(draft?.email || '').trim()
  return (
    String(draft?.firstName || '').trim().length > 0
    && String(draft?.lastName || '').trim().length > 0
    && String(draft?.studentId || '').trim().length > 0
    && String(draft?.yearLevel || '').trim().length > 0
    && String(draft?.departmentId || '').trim().length > 0
    && String(draft?.programId || '').trim().length > 0
    && email.length > 0
    && /\S+@\S+\.\S+/.test(email)
  )
}

function openAddStudentSheet() {
  if (!selectedProgram.value) return
  resetStudentDraft()
  closeCreatedStudentDialog()
  isAddStudentSheetOpen.value = true
  isSortMenuOpen.value = false
}

function closeAddStudentSheet(force = false) {
  if (isSavingStudent.value && !force) return
  isAddStudentSheetOpen.value = false
}

function openEditStudentSheet(student) {
  if (!student) return

  editingStudent.value = student
  editStudentDraft.value = {
    firstName: student.firstName || '',
    middleName: student.middleName || '',
    lastName: student.lastName || '',
    email: student.email || '',
    studentId: student.studentId || '',
    yearLevel: student.yearLevel != null ? String(student.yearLevel) : '',
    departmentId: student.departmentId != null ? String(student.departmentId) : '',
    programId: student.programId != null ? String(student.programId) : '',
  }
  editSheetMessage.value = ''
  editSheetTone.value = 'info'
  isSortMenuOpen.value = false
  isEditStudentSheetOpen.value = true
}

function closeEditStudentSheet(force = false) {
  if (isSavingEditedStudent.value && !force) return
  isEditStudentSheetOpen.value = false
}

function sortUsersByLastName(items) {
  return [...items].sort((left, right) => (
    String(left?.last_name || '').localeCompare(String(right?.last_name || ''))
    || String(left?.first_name || '').localeCompare(String(right?.first_name || ''))
    || String(left?.email || '').localeCompare(String(right?.email || ''))
  ))
}

function buildStudentSnapshot(user) {
  const nextUsers = activeUsers.value
    .map((entry) => Number(entry?.id) === Number(user?.id) ? user : entry)
    .concat(activeUsers.value.some((entry) => Number(entry?.id) === Number(user?.id)) ? [] : [user])

  return sortUsersByLastName(nextUsers)
}

function buildDeletedStudentSnapshot(userId) {
  return sortUsersByLastName(
    activeUsers.value.filter((entry) => Number(entry?.id) !== Number(userId))
  )
}

function buildOptimisticCreatedStudentRecord(createdUser, createdStudent, draft, options = {}) {
  const normalizedUserId = Number(createdStudent?.id ?? createdStudent?.user_id ?? createdUser?.id)
  const normalizedSchoolId = Number(
    createdStudent?.school_id
    ?? createdUser?.school_id
    ?? schoolId.value
  )
  const useDraftStudentIdFallback = options.useDraftStudentIdFallback !== false

  return {
    ...createdUser,
    ...createdStudent,
    id: normalizedUserId,
    email: createdUser?.email || draft.email,
    first_name: createdUser?.first_name || draft.firstName,
    middle_name: createdUser?.middle_name ?? (draft.middleName || null),
    last_name: createdUser?.last_name || draft.lastName,
    school_id: Number.isFinite(normalizedSchoolId) ? normalizedSchoolId : null,
    is_active: createdUser?.is_active !== false,
    created_at: createdUser?.created_at || new Date().toISOString(),
    roles: Array.isArray(createdUser?.roles) && createdUser.roles.length
      ? createdUser.roles
      : [{ role: { name: 'student' } }],
    student_profile: {
      ...(createdUser?.student_profile || {}),
      ...(createdStudent?.student_profile || {}),
      id: Number(createdStudent?.student_profile?.id ?? createdStudent?.id ?? normalizedUserId),
      user_id: normalizedUserId,
      school_id: Number.isFinite(normalizedSchoolId) ? normalizedSchoolId : null,
      student_id: String(
        createdStudent?.student_profile?.student_id
        ?? createdStudent?.student_id
        ?? createdUser?.student_profile?.student_id
        ?? (useDraftStudentIdFallback ? draft.studentId : '')
      ),
      department_id: Number(
        createdStudent?.student_profile?.department_id
        ?? createdStudent?.department_id
        ?? selectedDepartment.value?.id
      ),
      program_id: Number(
        createdStudent?.student_profile?.program_id
        ?? createdStudent?.program_id
        ?? selectedProgram.value?.id
      ),
      year_level: Number(
        createdStudent?.student_profile?.year_level
        ?? createdStudent?.year_level
        ?? draft.yearLevel
      ),
      attendances: Array.isArray(createdStudent?.student_profile?.attendances)
        ? createdStudent.student_profile.attendances
        : [],
      is_face_registered: Boolean(createdStudent?.student_profile?.is_face_registered),
      registration_complete: Boolean(createdStudent?.student_profile?.registration_complete),
    },
  }
}

function applyStudentSnapshot(user) {
  const nextUsers = buildStudentSnapshot(user)
  if (props.preview) {
    previewUsersSnapshot.value = nextUsers
    return
  }
  setUsersSnapshot(nextUsers)
}

function applyCreatedStudent(user) {
  applyStudentSnapshot(user)
}

function buildOptimisticUpdatedStudentRecord(student, draft) {
  const sourceUser = student?.sourceUser || {}
  const normalizedDepartmentId = normalizeRouteId(draft?.departmentId)
  const normalizedProgramId = normalizeRouteId(draft?.programId)
  const normalizedYearLevel = normalizeRouteId(draft?.yearLevel)

  return {
    ...sourceUser,
    id: Number(student?.userId ?? sourceUser?.id),
    email: String(draft?.email || '').trim(),
    first_name: String(draft?.firstName || '').trim(),
    middle_name: String(draft?.middleName || '').trim() || null,
    last_name: String(draft?.lastName || '').trim(),
    roles: Array.isArray(sourceUser?.roles) ? sourceUser.roles : [{ role: { name: 'student' } }],
    student_profile: {
      ...(sourceUser?.student_profile || {}),
      id: Number(student?.profileId ?? sourceUser?.student_profile?.id),
      user_id: Number(student?.userId ?? sourceUser?.id),
      school_id: Number(sourceUser?.student_profile?.school_id ?? sourceUser?.school_id ?? schoolId.value),
      student_id: String(draft?.studentId || '').trim().toUpperCase(),
      department_id: normalizedDepartmentId,
      program_id: normalizedProgramId,
      year_level: normalizedYearLevel,
      attendances: Array.isArray(sourceUser?.student_profile?.attendances)
        ? sourceUser.student_profile.attendances
        : [],
      is_face_registered: Boolean(sourceUser?.student_profile?.is_face_registered),
      registration_complete: Boolean(sourceUser?.student_profile?.registration_complete),
    },
  }
}

function resolveSelectedProgramNameById(targetProgramId) {
  return normalizedPrograms.value.find((program) => Number(program?.id) === Number(targetProgramId))?.name || 'the selected program'
}

async function handleEditStudent() {
  if (editStudentSubmitDisabled.value || !editingStudent.value) return

  const activeStudent = editingStudent.value
  const token = localStorage.getItem('aura_token') || ''
  const draft = {
    firstName: String(editStudentDraft.value.firstName || '').trim(),
    middleName: String(editStudentDraft.value.middleName || '').trim(),
    lastName: String(editStudentDraft.value.lastName || '').trim(),
    email: String(editStudentDraft.value.email || '').trim(),
    studentId: String(editStudentDraft.value.studentId || '').trim().toUpperCase(),
    yearLevel: normalizeRouteId(editStudentDraft.value.yearLevel),
    departmentId: normalizeRouteId(editStudentDraft.value.departmentId),
    programId: normalizeRouteId(editStudentDraft.value.programId),
  }

  editSheetMessage.value = ''
  editSheetTone.value = 'info'
  isSavingEditedStudent.value = true

  try {
    if (props.preview) {
      const previewUser = buildOptimisticUpdatedStudentRecord(activeStudent, draft)
      applyStudentSnapshot(previewUser)
      closeEditStudentSheet(true)
      feedbackTone.value = 'info'
      feedbackMessage.value = `${draft.firstName} ${draft.lastName} was updated in preview mode.`
      feedbackDetail.value = ''
      if (draft.programId === programId.value) {
        await highlightCreatedStudent(previewUser.id)
      }
      return
    }

    let updatedUser = activeStudent.sourceUser || null

    updatedUser = await updateUser(apiBaseUrl.value, token, activeStudent.userId, {
      email: draft.email,
      first_name: draft.firstName,
      middle_name: draft.middleName || null,
      last_name: draft.lastName,
    })

    updatedUser = await updateStudentProfile(apiBaseUrl.value, token, activeStudent.profileId, {
      student_id: draft.studentId,
      department_id: draft.departmentId,
      program_id: draft.programId,
      year_level: draft.yearLevel,
    })

    applyStudentSnapshot(updatedUser)
    refreshSchoolItWorkspaceData().catch(() => {})
    closeEditStudentSheet(true)

    const movedOutsideCurrentProgram = Number(draft.programId) !== Number(programId.value)
    feedbackTone.value = 'info'
    feedbackMessage.value = `${draft.firstName} ${draft.lastName} was updated successfully.`
    feedbackDetail.value = movedOutsideCurrentProgram
      ? `${draft.firstName} ${draft.lastName} is now assigned to ${resolveSelectedProgramNameById(draft.programId)} and was removed from this program list.`
      : ''

    if (!movedOutsideCurrentProgram) {
      await highlightCreatedStudent(updatedUser?.id ?? activeStudent.userId)
    } else {
      highlightedStudentId.value = null
    }
  } catch (error) {
    if (!props.preview) {
      refreshSchoolItWorkspaceData().catch(() => {})
    }
    editSheetTone.value = 'error'
    editSheetMessage.value = resolveStudentUpdateError(error)
  } finally {
    isSavingEditedStudent.value = false
  }
}

async function handleAddStudent() {
  if (addStudentSubmitDisabled.value || !selectedProgram.value || !selectedDepartment.value) return

  sheetMessage.value = ''
  sheetTone.value = 'info'
  isSavingStudent.value = true
  sheetMessage.value = 'Creating account...'

  const token = localStorage.getItem('aura_token') || ''
  const draft = {
    firstName: studentDraft.value.firstName.trim(),
    middleName: studentDraft.value.middleName.trim(),
    lastName: studentDraft.value.lastName.trim(),
    email: studentDraft.value.email.trim(),
    studentId: studentDraft.value.studentId.trim().toUpperCase(),
    yearLevel: normalizeRouteId(studentDraft.value.yearLevel),
  }

  try {
    if (props.preview) {
      const previewUserId = resolveNextPreviewUserId()
      applyCreatedStudent({
        id: previewUserId,
        email: draft.email,
        first_name: draft.firstName,
        middle_name: draft.middleName || null,
        last_name: draft.lastName,
        school_id: schoolId.value,
        is_active: true,
        created_at: new Date().toISOString(),
        roles: [{ role: { name: 'student' } }],
        student_profile: {
          id: previewUserId,
          user_id: previewUserId,
          school_id: schoolId.value,
          student_id: draft.studentId,
          department_id: selectedDepartment.value.id,
          program_id: selectedProgram.value.id,
          year_level: draft.yearLevel,
          attendances: [],
          is_face_registered: false,
          registration_complete: false,
        },
      })
      feedbackTone.value = 'info'
      feedbackMessage.value = `${draft.firstName} ${draft.lastName} was added to ${selectedProgram.value.name}.`
      feedbackDetail.value = 'Preview mode created the student locally for this program.'
      closeAddStudentSheet(true)
      await highlightCreatedStudent(previewUserId)
      return
    }

    let createdUser = null
    let createdStudent = null
    let studentIdSaveError = null

    sheetMessage.value = 'Creating student account and sending welcome email...'
    createdUser = await createStudentAccount(apiBaseUrl.value, token, {
      email: draft.email,
      first_name: draft.firstName,
      middle_name: draft.middleName || null,
      last_name: draft.lastName,
      department_id: Number(selectedDepartment.value.id),
      program_id: Number(selectedProgram.value.id),
      year_level: draft.yearLevel,
    })
    createdStudent = createdUser

    const createdProfileId = Number(createdUser?.student_profile?.id)
    if (draft.studentId && Number.isFinite(createdProfileId)) {
      try {
        sheetMessage.value = 'Saving student ID...'
        createdStudent = await updateStudentProfile(apiBaseUrl.value, token, createdProfileId, {
          student_id: draft.studentId,
        })
      } catch (error) {
        studentIdSaveError = error
      }
    } else if (draft.studentId) {
      studentIdSaveError = new BackendApiError(
        'The student account was created, but Aura could not confirm the student profile needed to save the student ID.',
        { status: 0 },
      )
    }

    await finalizeCreatedStudentCreation({ createdUser, createdStudent, studentIdSaveError }, draft)
    closeAddStudentSheet(true)
    await highlightCreatedStudent(createdStudent?.id ?? createdUser?.id)
  } catch (error) {
    sheetTone.value = 'error'
    sheetMessage.value = resolveStudentCreationError(error)
  } finally {
    isSavingStudent.value = false
  }
}

async function finalizeCreatedStudentCreation(creationOutcome, draft) {
  const studentIdSaveError = creationOutcome?.studentIdSaveError ?? null
  const resolvedCreatedStudent = buildOptimisticCreatedStudentRecord(
    creationOutcome?.createdUser,
    creationOutcome?.createdStudent,
    draft,
    {
      useDraftStudentIdFallback: !studentIdSaveError,
    },
  )
  const studentIdValue = String(resolvedCreatedStudent?.student_profile?.student_id || '').trim() || 'Pending follow-up'
  const studentIdFollowUpMessage = studentIdSaveError
    ? `${resolveStudentUpdateError(studentIdSaveError)} You can finish the student ID from Edit Student without recreating the account.`
    : ''
  const emailStatus = studentIdFollowUpMessage
    ? `The backend created the account and sent the temporary password by welcome email, but the requested student ID still needs follow-up. ${studentIdFollowUpMessage}`
    : 'The backend created the account and sent the generated temporary password to the student email address.'

  applyCreatedStudent(resolvedCreatedStudent)
  refreshSchoolItWorkspaceData().catch(() => {})
  feedbackTone.value = 'info'
  feedbackMessage.value = `${draft.firstName} ${draft.lastName} was added to ${selectedProgram.value.name}.`
  feedbackDetail.value = studentIdFollowUpMessage || 'The temporary password was delivered through the welcome email.'
  createdStudentSummary.value = {
    fullName: `${draft.firstName} ${draft.lastName}`.trim(),
    studentIdValue,
    email: draft.email,
    departmentName: selectedDepartment.value.name,
    programName: selectedProgram.value.name,
    deliveryValue: 'Temporary password sent by email',
    emailStatus,
  }
}

function delay(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function resolveNextPreviewUserId() {
  const existingIds = normalizedUsers.value
    .map((user) => Number(user?.id))
    .filter((id) => Number.isFinite(id))
  const maxId = existingIds.length ? Math.max(...existingIds) : 1000
  return maxId + 1
}

function setStudentRowRef(studentId, element) {
  const normalizedStudentId = Number(studentId)
  if (!Number.isFinite(normalizedStudentId)) return

  if (element) {
    studentRowRefs.set(normalizedStudentId, element)
  } else {
    studentRowRefs.delete(normalizedStudentId)
  }
}

async function highlightCreatedStudent(studentId) {
  const normalizedStudentId = Number(studentId)
  if (!Number.isFinite(normalizedStudentId)) return

  searchQuery.value = ''
  highlightedStudentId.value = normalizedStudentId
  await nextTick()
  scrollStudentRowIntoView(normalizedStudentId)
}

async function handleSearchResult(student) {
  isSelectingSearchResult.value = true
  highlightedStudentId.value = student.id
  searchQuery.value = ''
  await nextTick()
  scrollStudentRowIntoView(Number(student.id))
  window.setTimeout(() => {
    isSelectingSearchResult.value = false
  }, 180)
}

async function deleteStudent(student) {
  if (student.isMutating) return

  const confirmed = typeof window.confirm === 'function'
    ? window.confirm(`Delete ${student.fullName}?`)
    : true
  if (!confirmed) return

  mutatingStudentIds.value = [...mutatingStudentIds.value, student.id]
  feedbackMessage.value = ''
  feedbackDetail.value = ''

  const previousUsers = [...activeUsers.value]
  const nextUsers = buildDeletedStudentSnapshot(student.userId)

  if (props.preview) {
    previewUsersSnapshot.value = nextUsers
  } else {
    setUsersSnapshot(nextUsers)
  }

  try {
    if (!props.preview) {
      await deleteUser(
        apiBaseUrl.value,
        localStorage.getItem('aura_token') || '',
        student.userId,
      )
      refreshSchoolItWorkspaceData().catch(() => {})
    }

    feedbackTone.value = 'info'
    feedbackMessage.value = `${student.fullName} was deleted successfully.`
    feedbackDetail.value = ''
  } catch (error) {
    if (props.preview) {
      previewUsersSnapshot.value = previousUsers
    } else {
      setUsersSnapshot(previousUsers)
    }
    feedbackTone.value = 'error'
    feedbackMessage.value = resolveStudentDeletionError(error)
    feedbackDetail.value = ''
  } finally {
    mutatingStudentIds.value = mutatingStudentIds.value.filter((userId) => userId !== student.id)
  }
}

function scrollStudentRowIntoView(studentId) {
  const row = studentRowRefs.get(Number(studentId))
  if (typeof row?.scrollIntoView !== 'function') return
  row.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function resolveStudentDeletionError(error) {
  if (!(error instanceof BackendApiError)) {
    return 'Unable to delete this student right now.'
  }

  if (error.status === 403) {
    return 'This session is not allowed to delete this student right now.'
  }

  if (error.status === 404) {
    return 'This student could not be found on the backend anymore.'
  }

  return error.message || 'Unable to delete this student right now.'
}

function resolveStudentUpdateError(error) {
  if (!(error instanceof BackendApiError)) {
    return 'Unable to update this student right now.'
  }

  if (error.status === 400) {
    return error.message || 'The backend rejected one of the updated student fields.'
  }

  if (error.status === 403) {
    return 'This session is not allowed to edit this student right now.'
  }

  if (error.status === 404) {
    return 'This student record could not be found on the backend anymore.'
  }

  if (error.status === 422) {
    return 'Some student fields are invalid. Check the email, student ID, year level, college, and program.'
  }

  return error.message || 'Unable to update this student right now.'
}

function resolveStudentCreationError(error) {
  if (!(error instanceof BackendApiError)) {
    return 'Unable to add this student right now.'
  }

  if (error.status === 400) {
    return error.message || 'This student could not be created with the current data.'
  }

  if (error.status === 403) {
    return 'This session is not allowed to add students right now.'
  }

  if (error.status === 404) {
    return 'The student creation route is unavailable on the current backend.'
  }

  if (error.status === 422) {
    return 'Some student fields are invalid. Please check the email, student ID, and year level.'
  }

  if (error.status === 502) {
    return error.message || 'The backend could not deliver the welcome email, so the student account was not created.'
  }

  return error.message || 'Unable to add this student right now.'
}

async function handleLogout() {
  await logout()
}
</script>

<style scoped>
.school-it-program-students {
  min-height: 100vh;
  padding: 30px 28px 120px;
  font-family: 'Manrope', sans-serif;
}

.school-it-program-students__shell {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
}

.school-it-program-students__body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 24px;
}

.school-it-program-students__title {
  margin: 0;
  font-size: clamp(26px, 7.4vw, 42px);
  line-height: 0.94;
  letter-spacing: -0.06em;
  font-weight: 700;
  color: var(--color-text-primary);
  word-break: break-word;
}

.school-it-program-students__toolbar {
  position: relative;
  z-index: 5;
  display: flex;
  align-items: stretch;
  gap: clamp(8px, 2.6vw, 12px);
}

.school-it-program-students__search-wrap {
  flex: 0 1 clamp(88px, 24vw, 108px);
  min-width: 0;
  max-width: clamp(88px, 24vw, 108px);
  transition: flex 0.3s ease, max-width 0.3s ease;
}

.school-it-program-students__search-wrap--active {
  flex: 1 1 100%;
  max-width: none;
}

.school-it-program-students__search-shell {
  display: grid;
  grid-template-rows: auto 0fr;
  min-height: clamp(60px, 15vw, 64px);
  padding: 12px clamp(14px, 4vw, 18px);
  border-radius: 30px;
  background: var(--color-surface);
  transition:
    grid-template-rows 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    border-radius 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

.school-it-program-students__search-shell--open {
  grid-template-rows: auto 1fr;
  border-radius: 28px;
}

.school-it-program-students__search-input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: clamp(8px, 2.5vw, 10px);
  min-height: clamp(36px, 9vw, 40px);
}

.school-it-program-students__search-input {
  width: 100%;
  min-width: 0;
  border: none;
  background: transparent;
  outline: none;
  color: var(--color-text-always-dark);
  font-size: clamp(13px, 3.8vw, 14px);
  font-weight: 500;
}

.school-it-program-students__search-input::placeholder {
  color: var(--color-text-muted);
}

.school-it-program-students__search-icon-wrap {
  width: clamp(30px, 8vw, 32px);
  height: clamp(30px, 8vw, 32px);
  border-radius: 999px;
  border: 1px solid var(--color-surface-border);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  flex-shrink: 0;
  place-self: center;
}

.school-it-program-students__search-icon {
  display: block;
  width: clamp(15px, 4.2vw, 18px);
  height: clamp(15px, 4.2vw, 18px);
}

.school-it-program-students__search-results {
  overflow: hidden;
  min-height: 0;
}

.school-it-program-students__search-results-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 0 6px;
}

.school-it-program-students__search-result {
  width: 100%;
  padding: 12px 14px;
  border: none;
  border-radius: 22px;
  background: color-mix(in srgb, var(--color-surface) 88%, var(--color-bg));
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  text-align: left;
}

.school-it-program-students__search-pill {
  min-width: 88px;
  min-height: 30px;
  padding: 0 14px;
  border-radius: 999px;
  background: var(--color-search-pill-bg);
  color: var(--color-search-pill-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.school-it-program-students__search-result-name {
  min-width: 0;
  font-size: 13px;
  line-height: 1.2;
  font-weight: 600;
  color: var(--color-text-always-dark);
}

.school-it-program-students__search-empty {
  margin: 0;
  padding: 4px 6px 2px;
  font-size: 13px;
  line-height: 1.35;
  font-weight: 600;
  color: var(--color-text-muted);
  text-align: center;
}

.school-it-program-students__sort-wrap {
  position: relative;
  flex-shrink: 0;
  z-index: 6;
  transition:
    opacity 0.22s ease,
    transform 0.22s ease,
    max-width 0.22s ease,
    flex-basis 0.22s ease,
    background-color 0.24s ease,
    padding 0.24s ease,
    border-radius 0.24s ease;
}

.school-it-program-students__add-pill {
  min-width: clamp(112px, 30vw, 128px);
  min-height: clamp(60px, 15vw, 64px);
  padding: 0 clamp(12px, 3vw, 16px);
  border: none;
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: clamp(13px, 3.5vw, 14px);
  font-weight: 700;
  flex-shrink: 0;
  transition: opacity 0.22s ease, transform 0.22s ease, max-width 0.22s ease, flex-basis 0.22s ease;
}

.school-it-program-students__add-pill:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.school-it-program-students__add-pill-icon {
  width: auto;
  height: auto;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.school-it-program-students__sort-pill {
  width: clamp(108px, 30vw, 122px);
  min-height: clamp(60px, 15vw, 64px);
  padding: 0 clamp(14px, 4vw, 18px);
  border: none;
  border-radius: 999px;
  background: var(--color-primary);
  color: var(--color-banner-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: clamp(13px, 3.5vw, 14px);
  font-weight: 700;
}

.school-it-program-students__sort-menu {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  z-index: 20;
  min-width: 172px;
  padding: 10px;
  border-radius: 22px;
  background: var(--color-surface);
  border: 1px solid var(--color-surface-border);
  display: flex;
  flex-direction: column;
  gap: 8px;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-6px);
  transition: opacity 0.2s ease, transform 0.22s ease;
}

.school-it-program-students__sort-menu--open {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.school-it-program-students__sort-option {
  min-height: 44px;
  padding: 0 14px;
  border: none;
  border-radius: 16px;
  background: color-mix(in srgb, var(--color-surface) 88%, var(--color-bg));
  color: var(--color-text-always-dark);
  text-align: left;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.school-it-program-students__sort-option--active {
  background: color-mix(in srgb, var(--color-primary) 18%, var(--color-surface));
}

.school-it-program-students__card {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 28px 20px 24px;
  border-radius: 32px;
  background: var(--color-surface);
}

.school-it-program-students__section-title {
  margin: 0;
  font-size: clamp(18px, 5.2vw, 20px);
  line-height: 1;
  letter-spacing: -0.04em;
  font-weight: 700;
  color: var(--color-primary);
}

.school-it-program-students__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.school-it-program-students__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  background: color-mix(in srgb, var(--color-surface) 78%, var(--color-bg));
  border-radius: 22px;
  transition: background 0.24s ease, transform 0.24s ease;
}

.school-it-program-students__row--highlighted {
  background: color-mix(in srgb, var(--color-primary) 14%, var(--color-surface));
  transform: translateY(-1px);
}

.school-it-program-students__row-copy {
  min-width: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 12px;
}

.school-it-program-students__student-id {
  min-width: 88px;
  min-height: 30px;
  padding: 0 14px;
  border-radius: 999px;
  background: var(--color-primary);
  color: var(--color-banner-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.school-it-program-students__student-name {
  min-width: 0;
  font-size: 13px;
  line-height: 1.2;
  font-weight: 500;
  color: var(--color-text-always-dark);
}

.school-it-program-students__row-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.school-it-program-students__icon-button {
  width: 34px;
  height: 34px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-always-dark);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
}

.school-it-program-students__icon-button--danger {
  color: #FF3B30;
}

.school-it-program-students__icon-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.school-it-program-students__empty {
  margin: 0;
  padding: 10px 4px 2px;
  font-size: 14px;
  line-height: 1.4;
  font-weight: 600;
  color: var(--color-text-muted);
  text-align: center;
}

.school-it-program-students__feedback {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 12px 14px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--color-primary) 10%, var(--color-surface));
  color: var(--color-text-always-dark);
}

.school-it-program-students__feedback--error {
  background: color-mix(in srgb, #FF3B30 9%, var(--color-surface));
  color: #B42318;
}

.school-it-program-students__feedback-title {
  margin: 0;
  font-size: 13px;
  line-height: 1.35;
  font-weight: 700;
}

.school-it-program-students__feedback-detail {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  font-weight: 600;
  color: inherit;
}

.school-it-program-students__sheet-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 24px 18px calc(24px + env(safe-area-inset-bottom));
  background: rgba(15, 23, 42, 0.28);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.school-it-program-students__sheet {
  width: min(100%, 720px);
  max-height: min(88vh, 900px);
  overflow: auto;
  border-radius: 34px;
  background: var(--color-surface);
  padding: 22px 18px 18px;
}

.school-it-program-students__sheet--success {
  width: min(100%, 560px);
}

.school-it-program-students__sheet-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 16px;
}

.school-it-program-students__sheet-title {
  margin: 0;
  font-size: clamp(26px, 7.6vw, 34px);
  line-height: 0.94;
  letter-spacing: -0.05em;
  font-weight: 700;
  color: var(--color-text-primary);
}

.school-it-program-students__sheet-copy {
  margin: 10px 0 0;
  max-width: 48ch;
  font-size: 13px;
  line-height: 1.5;
  font-weight: 600;
  color: var(--color-text-muted);
}

.school-it-program-students__sheet-close {
  width: 42px;
  height: 42px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-surface) 88%, var(--color-bg));
  color: var(--color-text-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.school-it-program-students__form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 18px;
}

.school-it-program-students__success-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 18px;
}

.school-it-program-students__scope-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.school-it-program-students__scope-card {
  min-width: 0;
  padding: 16px 18px;
  border-radius: 24px;
  background: color-mix(in srgb, var(--color-surface) 82%, var(--color-bg));
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.school-it-program-students__success-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  border-radius: 24px;
  background: color-mix(in srgb, var(--color-surface) 82%, var(--color-bg));
}

.school-it-program-students__success-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.school-it-program-students__success-label {
  font-size: 11px;
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.school-it-program-students__success-value {
  font-size: 14px;
  line-height: 1.4;
  font-weight: 700;
  color: var(--color-text-primary);
}

.school-it-program-students__success-value--break {
  overflow-wrap: anywhere;
}

.school-it-program-students__scope-label {
  font-size: 11px;
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.school-it-program-students__scope-value {
  font-size: 14px;
  line-height: 1.35;
  font-weight: 700;
  color: var(--color-text-primary);
}

.school-it-program-students__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 12px;
}

.school-it-program-students__field {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.school-it-program-students__field--wide {
  grid-column: 1 / -1;
}

.school-it-program-students__field-label {
  font-size: 13px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--color-text-primary);
}

.school-it-program-students__field-input {
  width: 100%;
  min-height: 54px;
  padding: 0 18px;
  border: 1px solid transparent;
  border-radius: 22px;
  background: color-mix(in srgb, var(--color-surface) 82%, var(--color-bg));
  color: var(--color-text-primary);
  font-size: 14px;
  line-height: 1.2;
  font-weight: 600;
  outline: none;
  transition: border-color 0.22s ease, background-color 0.22s ease;
}

.school-it-program-students__field-input::placeholder {
  color: var(--color-text-muted);
}

.school-it-program-students__field-input:focus {
  border-color: color-mix(in srgb, var(--color-primary) 32%, transparent);
}

.school-it-program-students__field-input--select {
  appearance: none;
  background-image:
    linear-gradient(45deg, transparent 50%, currentColor 50%),
    linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position:
    calc(100% - 22px) calc(50% - 2px),
    calc(100% - 16px) calc(50% - 2px);
  background-size: 6px 6px, 6px 6px;
  background-repeat: no-repeat;
}

.school-it-program-students__sheet-note {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  font-weight: 600;
  color: var(--color-text-muted);
}

.school-it-program-students__sheet-feedback {
  margin: 0;
  font-size: 13px;
  line-height: 1.4;
  font-weight: 600;
  color: var(--color-text-muted);
}

.school-it-program-students__sheet-feedback--error {
  color: #B42318;
}

.school-it-program-students__sheet-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.school-it-program-students__sheet-secondary,
.school-it-program-students__sheet-primary {
  min-height: 52px;
  padding: 0 22px;
  border: none;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.18s ease, opacity 0.18s ease;
}

.school-it-program-students__sheet-secondary {
  background: color-mix(in srgb, var(--color-surface) 82%, var(--color-bg));
  color: var(--color-text-primary);
}

.school-it-program-students__sheet-primary {
  min-width: 154px;
  background: var(--color-primary);
  color: var(--color-banner-text);
}

.school-it-program-students__sheet-secondary:disabled,
.school-it-program-students__sheet-primary:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.school-it-program-students-sheet-enter-active,
.school-it-program-students-sheet-leave-active {
  transition: opacity 0.22s ease;
}

.school-it-program-students-sheet-enter-active .school-it-program-students__sheet,
.school-it-program-students-sheet-leave-active .school-it-program-students__sheet {
  transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.22s ease;
}

.school-it-program-students-sheet-enter-from,
.school-it-program-students-sheet-leave-to {
  opacity: 0;
}

.school-it-program-students-sheet-enter-from .school-it-program-students__sheet,
.school-it-program-students-sheet-leave-to .school-it-program-students__sheet {
  opacity: 0;
  transform: translateY(18px) scale(0.985);
}

@media (min-width: 768px) {
  .school-it-program-students {
    padding: 40px 36px 56px;
  }

  .school-it-program-students__body {
    margin-top: 30px;
    gap: 22px;
  }

  .school-it-program-students__toolbar,
  .school-it-program-students__card {
    max-width: 820px;
  }

  .school-it-program-students__card {
    padding: 32px 24px 26px;
  }

  .school-it-program-students__toolbar {
    gap: 12px;
  }

  .school-it-program-students__sheet {
    padding: 26px 24px 22px;
  }

  .school-it-program-students__sheet--success {
    width: min(100%, 600px);
  }

  .school-it-program-students__student-name {
    font-size: 14px;
  }

  .school-it-program-students__search-result-name {
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .school-it-program-students__toolbar {
    flex-wrap: nowrap;
    gap: 8px;
    align-items: stretch;
  }

  .school-it-program-students__toolbar--searching {
    flex-wrap: nowrap;
  }

  .school-it-program-students__toolbar--sorting {
    flex-wrap: wrap;
  }

  .school-it-program-students__search-wrap {
    flex: 0 0 clamp(82px, 23vw, 94px);
    max-width: clamp(82px, 23vw, 94px);
    transition: opacity 0.22s ease, transform 0.22s ease, flex-basis 0.28s cubic-bezier(0.22, 1, 0.36, 1), max-width 0.28s cubic-bezier(0.22, 1, 0.36, 1);
  }

  .school-it-program-students__toolbar--searching .school-it-program-students__search-wrap {
    flex: 1 1 100%;
    max-width: 100%;
  }

  .school-it-program-students__toolbar--searching .school-it-program-students__sort-wrap,
  .school-it-program-students__toolbar--searching .school-it-program-students__add-pill {
    display: none;
  }

  .school-it-program-students__sort-wrap {
    flex: 0 0 clamp(110px, 32vw, 118px);
    max-width: clamp(110px, 32vw, 118px);
    display: grid;
    grid-template-rows: auto 0fr;
    overflow: hidden;
    transition:
      grid-template-rows 0.34s cubic-bezier(0.22, 1, 0.36, 1),
      flex-basis 0.34s cubic-bezier(0.22, 1, 0.36, 1),
      max-width 0.34s cubic-bezier(0.22, 1, 0.36, 1),
      padding 0.28s ease,
      background-color 0.28s ease,
      border-radius 0.28s ease,
      opacity 0.22s ease,
      transform 0.22s ease;
  }

  .school-it-program-students__toolbar--sorting .school-it-program-students__sort-wrap {
    flex: 1 1 100%;
    max-width: 100%;
    grid-template-rows: auto 1fr;
    padding: 12px;
    border-radius: 32px;
    background: var(--color-primary);
  }

  .school-it-program-students__sort-pill {
    width: 100%;
    padding-inline: 12px;
  }

  .school-it-program-students__toolbar--sorting .school-it-program-students__sort-pill {
    min-height: 42px;
    padding-inline: 10px;
    justify-content: space-between;
    background: transparent;
    color: var(--color-text-primary);
  }

  .school-it-program-students__add-pill {
    flex: 0 0 clamp(108px, 31vw, 116px);
    max-width: clamp(108px, 31vw, 116px);
    min-width: 0;
    padding-inline: 12px;
    gap: 6px;
    font-size: 12px;
    transition: opacity 0.22s ease, transform 0.22s ease, flex-basis 0.28s cubic-bezier(0.22, 1, 0.36, 1), max-width 0.28s cubic-bezier(0.22, 1, 0.36, 1);
  }

  .school-it-program-students__toolbar--sorting .school-it-program-students__search-wrap,
  .school-it-program-students__toolbar--sorting .school-it-program-students__add-pill {
    opacity: 0;
    pointer-events: none;
    transform: scale(0.96);
    flex-basis: 0;
    max-width: 0;
    min-width: 0;
    overflow: hidden;
  }

  .school-it-program-students__search-result {
    grid-template-columns: 1fr;
    gap: 8px;
    align-items: stretch;
  }

  .school-it-program-students__toolbar--sorting .school-it-program-students__sort-menu {
    position: static;
    top: auto;
    right: auto;
    min-width: 0;
    margin-top: 0;
    padding: 0;
    border: none;
    border-radius: 0;
    background: transparent;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
    max-height: none;
    opacity: 1;
    overflow: hidden;
    pointer-events: auto;
    transform: none;
    transition: opacity 0.24s ease, margin-top 0.24s ease, padding-top 0.24s ease;
  }

  .school-it-program-students__toolbar--sorting .school-it-program-students__sort-menu--open {
    margin-top: 8px;
    padding-top: 4px;
    opacity: 1;
    pointer-events: auto;
  }

  .school-it-program-students__toolbar--sorting .school-it-program-students__sort-option {
    min-height: 48px;
    border-radius: 999px;
    background: var(--color-surface);
    color: var(--color-text-primary);
    text-align: center;
    justify-content: center;
  }

  .school-it-program-students__toolbar--sorting .school-it-program-students__sort-option--active {
    background: color-mix(in srgb, var(--color-surface) 82%, var(--color-primary));
  }

  .school-it-program-students__search-pill {
    width: fit-content;
  }

  .school-it-program-students__search-empty {
    padding-inline: 10px;
  }

  .school-it-program-students__search-input::placeholder {
    color: transparent;
  }

  .school-it-program-students__student-name {
    font-size: 12px;
  }

  .school-it-program-students__sheet-backdrop {
    padding-inline: 10px;
    padding-bottom: calc(12px + env(safe-area-inset-bottom));
  }

  .school-it-program-students__sheet {
    max-height: min(92vh, 900px);
    padding: 18px 16px 16px;
    border-radius: 28px;
  }

  .school-it-program-students__sheet--success {
    width: min(100%, 100%);
  }

  .school-it-program-students__scope-grid,
  .school-it-program-students__form-grid {
    grid-template-columns: 1fr;
  }

  .school-it-program-students__sheet-actions {
    flex-direction: column-reverse;
    align-items: stretch;
  }

  .school-it-program-students__sheet-secondary,
  .school-it-program-students__sheet-primary {
    width: 100%;
  }
}
</style>
