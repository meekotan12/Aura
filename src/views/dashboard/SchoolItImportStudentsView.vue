<template>
  <section class="school-it-import">
    <div class="school-it-import__shell">
      <SchoolItTopHeader
        class="dashboard-enter dashboard-enter--1"
        :avatar-url="avatarUrl"
        :school-name="activeSchoolSettings?.school_name || activeUser?.school_name || ''"
        :display-name="displayName"
        :initials="initials"
        @logout="handleLogout"
      />

      <div class="school-it-import__body">
        <section class="school-it-import__title-card dashboard-enter dashboard-enter--2">
          <h1 class="school-it-import__title">Import Student</h1>

          <button
            class="school-it-import__info-button"
            type="button"
            :aria-expanded="infoOpen ? 'true' : 'false'"
            aria-label="Import information"
            @click="infoOpen = !infoOpen"
          >
            <Info :size="18" />
          </button>
        </section>

        <Transition name="school-it-import-info">
          <div
            v-if="infoOpen"
            class="school-it-import__info-note dashboard-enter dashboard-enter--3"
          >
            <p style="margin: 0; margin-bottom: 12px;">
              Upload a <strong>.xlsx</strong> or <strong>.csv</strong> file using the backend template columns:
              Student_ID, Email, Last Name, First Name, Middle Name, Department, and Course.
            </p>
            <button class="school-it-import__download-template" type="button" @click="downloadTemplate">
              <Download :size="14" style="margin-right: 6px" />
              Download Template
            </button>
          </div>
        </Transition>

        <section class="school-it-import__panel dashboard-enter dashboard-enter--4">
          <Transition name="school-it-import-stage" mode="out-in">
            <div
              v-if="stage === 'idle'"
              key="idle"
              class="school-it-import__stage school-it-import__stage--idle"
            >
              <button
                class="school-it-import__dropzone"
                :class="{
                  'school-it-import__dropzone--active': isDragActive,
                  'school-it-import__dropzone--selected': Boolean(selectedFile),
                }"
                type="button"
                @click="openFilePicker"
                @dragover.prevent="isDragActive = true"
                @dragleave.prevent="isDragActive = false"
                @drop.prevent="handleFileDrop"
              >
                <CloudUpload class="school-it-import__dropzone-icon" :size="92" :stroke-width="2.2" />

                <div class="school-it-import__dropzone-copy">
                  <p class="school-it-import__dropzone-title">Click to upload or drag and drop.</p>
                  <p class="school-it-import__dropzone-caption">Supported format: XLSX or CSV</p>
                  <p v-if="selectedFile" class="school-it-import__dropzone-file">{{ selectedFile.name }}</p>
                </div>
              </button>
            </div>

            <div
              v-else-if="stage === 'processing'"
              key="processing"
              class="school-it-import__stage school-it-import__stage--processing"
            >
              <p class="school-it-import__processing-label">{{ processingLabel }}</p>

              <div class="school-it-import__progress-shell" aria-hidden="true">
                <div class="school-it-import__progress-track">
                  <span
                    class="school-it-import__progress-fill"
                    :style="{ width: `${displayProgress}%` }"
                  />
                  <span
                    class="school-it-import__progress-knob"
                    :style="{ left: `clamp(18px, calc(${displayProgress}% - 10px), calc(100% - 18px))` }"
                  />
                </div>
              </div>
            </div>

            <div
              v-else
              key="result"
              class="school-it-import__stage school-it-import__stage--result"
            >
              <div class="school-it-import__result-header">
                <div class="school-it-import__result-copy">
                  <h2 class="school-it-import__result-title">{{ resultTitle }}</h2>
                  <p class="school-it-import__result-summary">{{ resultSummary }}</p>
                </div>

                <button
                  class="school-it-import__result-reset"
                  type="button"
                  @click="resetFlow"
                >
                  Another File
                </button>
              </div>

              <p
                v-if="feedbackMessage"
                class="school-it-import__feedback"
                :class="{ 'school-it-import__feedback--error': feedbackError }"
              >
                {{ feedbackMessage }}
              </p>

              <div
                v-if="showImportSuccessMessage"
                class="school-it-import__success-banner"
              >
                <p class="school-it-import__success-title">Import completed successfully</p>
                <p class="school-it-import__success-copy">{{ importSuccessMessage }}</p>
              </div>

              <div
                v-if="showPreviewRepairActions || showImportErrorDownload"
                class="school-it-import__result-actions"
              >
                <button
                  v-if="showPreviewRepairActions"
                  class="school-it-import__secondary-action"
                  type="button"
                  :disabled="stage === 'processing'"
                  @click="handleDownloadPreviewErrors"
                >
                  Download Errors
                </button>

                <button
                  v-if="showPreviewRepairActions"
                  class="school-it-import__secondary-action"
                  type="button"
                  :disabled="stage === 'processing'"
                  @click="handleDownloadPreviewRetryFile"
                >
                  Retry File
                </button>

                <button
                  v-if="showPreviewRepairActions && canKeepValidRows"
                  class="school-it-import__secondary-action school-it-import__secondary-action--primary"
                  type="button"
                  :disabled="stage === 'processing'"
                  @click="handleKeepValidRows"
                >
                  Keep Valid Rows
                </button>

                <button
                  v-if="showImportErrorDownload"
                  class="school-it-import__secondary-action"
                  type="button"
                  :disabled="stage === 'processing'"
                  @click="handleDownloadImportErrors"
                >
                  Download Failed Rows
                </button>
              </div>

              <div v-if="displayRows.length" class="school-it-import__results-list">
                <article
                  v-for="row in displayRows"
                  :key="row.id"
                  class="school-it-import__result-row"
                  :class="{ 'school-it-import__result-row--invalid': row.status !== 'valid' }"
                >
                  <div class="school-it-import__result-top">
                    <div class="school-it-import__result-identity">
                      <p class="school-it-import__result-name">{{ row.name }}</p>
                      <p class="school-it-import__result-id">{{ row.studentId || `Row ${row.row}` }}</p>
                    </div>

                    <span
                      class="school-it-import__result-status"
                      :class="{ 'school-it-import__result-status--invalid': row.status !== 'valid' }"
                    >
                      {{ row.status === 'valid' ? 'Ready' : 'Needs Review' }}
                    </span>
                  </div>

                  <div class="school-it-import__result-meta">
                    <span>{{ row.department }}</span>
                    <span>{{ row.program }}</span>
                  </div>

                  <p v-if="row.errors.length" class="school-it-import__result-error">
                    {{ row.errors[0] }}
                  </p>
                </article>
              </div>

              <p v-else class="school-it-import__empty">No students could be resolved from this file.</p>
            </div>
          </Transition>

          <input
            ref="fileInputEl"
            class="school-it-import__file-input"
            type="file"
            accept=".xlsx,.csv"
            @change="handleFileSelect"
          >
        </section>

        <div class="school-it-import__action-row dashboard-enter dashboard-enter--5">
          <button
            ref="swipePillRef"
            class="school-it-import__swipe-pill"
            :class="{
              'school-it-import__swipe-pill--busy': stage === 'processing',
              'school-it-import__swipe-pill--ready': stage === 'result',
            }"
            type="button"
            :disabled="isPrimaryActionDisabled"
            @click="handlePillClick"
            @touchstart.passive="handleSwipeStart"
            @mousedown="handleSwipeStart"
          >
            <span 
              ref="swipeThumbRef"
              class="school-it-import__swipe-thumb"
              :style="thumbStyle"
            >
              <ArrowRight :size="18" />
            </span>

            <span class="school-it-import__swipe-label" :style="{ opacity: labelOpacity }">{{ primaryActionLabel }}</span>

            <span v-if="stage === 'idle'" class="school-it-import__swipe-chevrons" aria-hidden="true" :style="{ opacity: labelOpacity }">
              <ChevronRight :size="16" />
              <ChevronRight :size="16" />
            </span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ArrowRight, ChevronRight, CloudUpload, Info, Download } from 'lucide-vue-next'
import SchoolItTopHeader from '@/components/dashboard/SchoolItTopHeader.vue'
import { useAuth } from '@/composables/useAuth.js'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { usePreviewTheme } from '@/composables/usePreviewTheme.js'
import { schoolItPreviewData } from '@/data/schoolItPreview.js'
import {
  BackendApiError,
  downloadImportErrors,
  downloadPreviewImportErrors,
  downloadPreviewRetryFile,
  downloadStudentImportTemplate,
  getStudentImportStatus,
  previewImportStudents,
  removeInvalidPreviewRows,
  startStudentImport,
} from '@/services/backendApi.js'
import {
  createMockImportPreviewSummary,
  extractStudentImportDisplayRows,
} from '@/services/studentImport.js'

const props = defineProps({
  preview: {
    type: Boolean,
    default: false,
  },
})

const POLL_INTERVAL_MS = 1200
const fileInputEl = ref(null)
const swipePillRef = ref(null)
const swipeThumbRef = ref(null)
const infoOpen = ref(false)
const isDragActive = ref(false)
const selectedFile = ref(null)
const stage = ref('idle')
const processingLabel = ref('Uploading Please Wait')
const displayProgress = ref(0)
const feedbackMessage = ref('')
const feedbackError = ref(false)
const previewSummary = ref(null)
const importSummary = ref(null)
const displayRows = ref([])

const isSwiping = ref(false)
const swipeProgress = ref(0)
let swipeStartX = 0
let swipeMaxTravel = 0

const { currentUser, schoolSettings, apiBaseUrl, token } = useDashboardSession()
const { logout } = useAuth()

const activeUser = computed(() => (props.preview ? schoolItPreviewData.user : currentUser.value))
const activeSchoolSettings = computed(() => (props.preview ? schoolItPreviewData.schoolSettings : schoolSettings.value))

usePreviewTheme(() => props.preview, activeSchoolSettings)

const displayName = computed(() => {
  const first = activeUser.value?.first_name || ''
  const middle = activeUser.value?.middle_name || ''
  const last = activeUser.value?.last_name || ''
  return [first, middle, last].filter(Boolean).join(' ') || activeUser.value?.email?.split('@')[0] || 'School IT'
})

const initials = computed(() => buildInitials(displayName.value))
const avatarUrl = computed(() => activeUser.value?.avatar_url || '')
const validPreviewRows = computed(() => displayRows.value.filter((row) => row.status === 'valid').length)
const invalidPreviewRows = computed(() => displayRows.value.filter((row) => row.status !== 'valid').length)
const canKeepValidRows = computed(() => validPreviewRows.value > 0 && invalidPreviewRows.value > 0 && Boolean(previewSummary.value?.preview_token))
const showPreviewRepairActions = computed(() =>
  stage.value === 'result'
  && !importSummary.value
  && Boolean(previewSummary.value?.preview_token)
  && invalidPreviewRows.value > 0
)
const showImportErrorDownload = computed(() =>
  stage.value === 'result'
  && Boolean(importSummary.value?.failed_count)
  && Boolean(importSummary.value?.job_id)
)
const showImportSuccessMessage = computed(() =>
  stage.value === 'result' && importSummary.value?.state === 'completed'
)
const importSuccessMessage = computed(() => {
  if (!showImportSuccessMessage.value) return ''

  const successCount = Number(importSummary.value?.success_count || 0)
  const failedCount = Number(importSummary.value?.failed_count || 0)

  if (failedCount > 0) {
    return `${successCount} student accounts were imported. ${failedCount} rows still need review.`
  }

  if (successCount === 1) {
    return '1 student account was added to the database.'
  }

  return `${successCount} student accounts were added to the database.`
})
const primaryActionLabel = computed(() => {
  if (stage.value === 'processing') return 'Processing...'
  if (stage.value === 'result' && importSummary.value?.state === 'completed') return 'Import Another'
  if (stage.value === 'result' && importSummary.value?.state === 'failed') return 'Try Another File'
  if (stage.value === 'result' && previewSummary.value && !previewSummary.value.can_commit) return 'Fix Errors to Import'
  return 'Slide to Import'
})
const isPrimaryActionDisabled = computed(() => {
  if (stage.value === 'processing') return true
  if (stage.value === 'result' && importSummary.value) return false
  if (stage.value === 'result' && previewSummary.value && !previewSummary.value.can_commit) return true
  return !selectedFile.value
})
const resultTitle = computed(() => {
  if (importSummary.value?.state === 'completed') return 'Imported Students'
  if (importSummary.value?.state === 'failed') return 'Import Results'
  return 'Import Preview'
})
const resultSummary = computed(() => {
  if (importSummary.value?.state === 'completed') {
    return `${importSummary.value.success_count} imported, ${importSummary.value.failed_count} failed`
  }
  if (importSummary.value?.state === 'failed') {
    return `${importSummary.value.success_count} imported, ${importSummary.value.failed_count} failed during this job`
  }
  if (previewSummary.value) {
    return `${validPreviewRows.value} ready, ${invalidPreviewRows.value} flagged from ${previewSummary.value.filename || 'selected file'}`
  }
  return 'Review the rows detected from the selected file.'
})

let progressAnimationFrameId = 0
let pollTimeoutId = 0

const thumbStyle = computed(() => {
  if (isSwiping.value) {
    return { left: `calc(5px + ${swipeProgress.value}px)`, transition: 'none' }
  }
  return {}
})

const labelOpacity = computed(() => {
  if (isSwiping.value && swipeMaxTravel > 0) {
    return Math.max(0, 1 - (swipeProgress.value / (swipeMaxTravel * 0.4)))
  }
  return 1
})

onMounted(() => {
  resetFlow()
  window.addEventListener('mousemove', handleSwipeMove)
  window.addEventListener('mouseup', handleSwipeEnd)
  window.addEventListener('touchmove', handleSwipeMove, { passive: false })
  window.addEventListener('touchend', handleSwipeEnd)
})

onBeforeUnmount(() => {
  stopProgressAnimation()
  clearPollTimer()
  window.removeEventListener('mousemove', handleSwipeMove)
  window.removeEventListener('mouseup', handleSwipeEnd)
  window.removeEventListener('touchmove', handleSwipeMove)
  window.removeEventListener('touchend', handleSwipeEnd)
})

function buildInitials(value) {
  const parts = String(value || '').split(' ').filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  return String(value || '').slice(0, 2).toUpperCase()
}

function openFilePicker() {
  if (stage.value === 'processing') return
  fileInputEl.value?.click()
}

function handleFileSelect(event) {
  const file = event?.target?.files?.[0] || null
  commitSelectedFile(file)
  if (event?.target) event.target.value = ''
  if (selectedFile.value) {
    runPreviewFlow()
  }
}

function handleFileDrop(event) {
  isDragActive.value = false
  const file = event?.dataTransfer?.files?.[0] || null
  commitSelectedFile(file)
  if (selectedFile.value) {
    runPreviewFlow()
  }
}

function commitSelectedFile(file) {
  feedbackMessage.value = ''
  feedbackError.value = false
  previewSummary.value = null
  importSummary.value = null
  displayRows.value = []

  if (!file) {
    selectedFile.value = null
    return
  }

  const normalizedName = String(file.name || '').toLowerCase()
  if (!normalizedName.endsWith('.xlsx') && !normalizedName.endsWith('.csv')) {
    selectedFile.value = null
    feedbackError.value = true
    feedbackMessage.value = 'Only .xlsx and .csv files are allowed.'
    return
  }

  selectedFile.value = file
}

function handlePillClick() {
  if (stage.value === 'result' && importSummary.value) {
    handlePrimaryAction()
  }
}

function handleSwipeStart(e) {
  if (isPrimaryActionDisabled.value) return
  if (stage.value === 'result' && importSummary.value) return // Allow click for "Import Another"
  
  isSwiping.value = true
  swipeStartX = e.type.includes('mouse') ? e.clientX : e.touches?.[0]?.clientX
  
  if (swipePillRef.value && swipeThumbRef.value) {
    const pillRect = swipePillRef.value.getBoundingClientRect()
    const thumbRect = swipeThumbRef.value.getBoundingClientRect()
    swipeMaxTravel = pillRect.width - thumbRect.width - 10
  }
}

function handleSwipeMove(e) {
  if (!isSwiping.value) return
  if (e.cancelable) e.preventDefault()
  
  const currentX = e.type.includes('mouse') ? e.clientX : e.touches?.[0]?.clientX
  let deltaX = currentX - swipeStartX
  
  if (deltaX < 0) deltaX = 0
  if (deltaX > swipeMaxTravel) deltaX = swipeMaxTravel
  
  swipeProgress.value = deltaX
}

function handleSwipeEnd() {
  if (!isSwiping.value) return
  isSwiping.value = false
  
  if (swipeProgress.value > swipeMaxTravel * 0.85) {
    swipeProgress.value = swipeMaxTravel
    handlePrimaryAction()
  } else {
    swipeProgress.value = 0
  }
  
  if (stage.value !== 'processing') {
    setTimeout(() => {
      swipeProgress.value = 0
    }, 300)
  }
}

async function handlePrimaryAction() {
  if (stage.value === 'result' && importSummary.value) {
    resetFlow()
    await nextTick()
    return
  }

  if (!selectedFile.value) {
    feedbackError.value = true
    feedbackMessage.value = 'Choose a CSV or Excel file first.'
    return
  }

  await runImportFlow()
}

async function runPreviewFlow() {
  stage.value = 'processing'
  feedbackMessage.value = ''
  feedbackError.value = false
  previewSummary.value = null
  importSummary.value = null
  displayRows.value = []
  displayProgress.value = 0
  processingLabel.value = 'Analyzing file structure...'
  
  try {
    smoothProgressTo(45, 400)
    
    const preview = props.preview
      ? await runMockPreview(selectedFile.value)
      : await previewImportStudents(apiBaseUrl.value, token.value, selectedFile.value)
      
    previewSummary.value = preview
    displayRows.value = extractStudentImportDisplayRows(preview)
    
    smoothProgressTo(100, 300)
    await wait(320)
    stage.value = 'result'
    
    if (!preview.can_commit) {
      feedbackError.value = true
      feedbackMessage.value = 'File has errors. Please fix highlighted rows and select an updated file.'
    } else {
      feedbackError.value = false
      feedbackMessage.value = 'File looks good! Ready to import.'
    }
  } catch (error) {
    stage.value = 'idle'
    displayProgress.value = 0
    feedbackError.value = true
    feedbackMessage.value = resolveImportErrorMessage(error)
    selectedFile.value = null
  }
}

async function runImportFlow() {
  if (!previewSummary.value || !previewSummary.value.can_commit) return
  if (!previewSummary.value.preview_token) {
    feedbackError.value = true
    feedbackMessage.value = 'Preview token is missing. Preview the file again before importing.'
    stage.value = 'result'
    return
  }

  stage.value = 'processing'
  feedbackMessage.value = ''
  feedbackError.value = false
  displayProgress.value = 0
  processingLabel.value = 'Importing students...'

  try {
    smoothProgressTo(42, 480)

    if (props.preview) {
      await runMockImport(previewSummary.value)
    } else {
      const job = await startStudentImport(apiBaseUrl.value, token.value, previewSummary.value.preview_token)
      await pollImportJob(job.job_id)
    }

    smoothProgressTo(100, 320)
    await wait(340)
    stage.value = 'result'

    if (importSummary.value?.state === 'failed') {
      feedbackError.value = true
      feedbackMessage.value = 'Import finished with errors. Review the uploaded rows.'
    } else {
      feedbackMessage.value = 'Students were imported successfully.'
      feedbackError.value = false
    }
  } catch (error) {
    stage.value = 'result'
    displayProgress.value = importSummary.value?.percentage_completed
      ? Number(importSummary.value.percentage_completed)
      : (previewSummary.value?.can_commit ? 100 : 0)
    feedbackError.value = true
    feedbackMessage.value = resolveImportErrorMessage(error)
  }
}

function triggerBlobDownload(blob, fileName) {
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', fileName)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

async function downloadTemplate() {
  if (props.preview) {
    const headers = 'Student_ID,Email,Last Name,First Name,Middle Name,Department,Course\n'
    const blob = new Blob([headers], { type: 'text/csv;charset=utf-8;' })
    triggerBlobDownload(blob, 'student_import_template.csv')
    return
  }

  try {
    const blob = await downloadStudentImportTemplate(apiBaseUrl.value, token.value)
    triggerBlobDownload(blob, 'student_import_template.xlsx')
  } catch (error) {
    feedbackError.value = true
    feedbackMessage.value = resolveImportErrorMessage(error)
  }
}

async function handleDownloadPreviewErrors() {
  if (props.preview || !previewSummary.value?.preview_token) return

  try {
    const blob = await downloadPreviewImportErrors(apiBaseUrl.value, token.value, previewSummary.value.preview_token)
    triggerBlobDownload(blob, `preview_errors_${previewSummary.value.preview_token}.xlsx`)
  } catch (error) {
    feedbackError.value = true
    feedbackMessage.value = resolveImportErrorMessage(error)
  }
}

async function handleDownloadPreviewRetryFile() {
  if (props.preview || !previewSummary.value?.preview_token) return

  try {
    const blob = await downloadPreviewRetryFile(apiBaseUrl.value, token.value, previewSummary.value.preview_token)
    triggerBlobDownload(blob, `preview_retry_${previewSummary.value.preview_token}.xlsx`)
  } catch (error) {
    feedbackError.value = true
    feedbackMessage.value = resolveImportErrorMessage(error)
  }
}

async function handleKeepValidRows() {
  if (props.preview || !previewSummary.value?.preview_token || !canKeepValidRows.value) return

  stage.value = 'processing'
  feedbackMessage.value = ''
  feedbackError.value = false
  processingLabel.value = 'Keeping valid rows from preview...'
  smoothProgressTo(56, 360)

  try {
    const cleanedPreview = await removeInvalidPreviewRows(apiBaseUrl.value, token.value, previewSummary.value.preview_token)
    previewSummary.value = cleanedPreview
    displayRows.value = extractStudentImportDisplayRows(cleanedPreview)
    smoothProgressTo(100, 220)
    await wait(260)
    stage.value = 'result'
    feedbackError.value = false
    feedbackMessage.value = 'Invalid rows were removed. The remaining rows are ready to import.'
  } catch (error) {
    stage.value = 'result'
    feedbackError.value = true
    feedbackMessage.value = resolveImportErrorMessage(error)
  }
}

async function handleDownloadImportErrors() {
  if (props.preview || !importSummary.value?.job_id) return

  try {
    const blob = await downloadImportErrors(apiBaseUrl.value, token.value, importSummary.value.job_id)
    triggerBlobDownload(blob, `import_${importSummary.value.job_id}_failed_rows.xlsx`)
  } catch (error) {
    feedbackError.value = true
    feedbackMessage.value = resolveImportErrorMessage(error)
  }
}

async function runMockPreview(file) {
  processingLabel.value = 'Reading the uploaded file'
  smoothProgressTo(36, 560)
  await wait(640)

  return createMockImportPreviewSummary({
    fileName: file?.name || 'student_import_template.xlsx',
    users: schoolItPreviewData.users,
    departments: schoolItPreviewData.departments,
    programs: schoolItPreviewData.programs,
  })
}

async function runMockImport(preview) {
  smoothProgressTo(78, 880)
  await wait(920)
  importSummary.value = {
    job_id: `preview-${Date.now()}`,
    state: 'completed',
    total_rows: preview.total_rows,
    processed_rows: preview.total_rows,
    success_count: preview.valid_rows,
    failed_count: preview.invalid_rows,
    percentage_completed: 100,
    errors: [],
  }
}

async function pollImportJob(jobId) {
  clearPollTimer()

  for (let attempt = 0; attempt < 120; attempt += 1) {
    const summary = await getStudentImportStatus(apiBaseUrl.value, token.value, jobId)
    importSummary.value = summary

    const targetProgress = summary.state === 'completed'
      ? 100
      : Math.min(96, Math.max(48, Number(summary.percentage_completed || 0)))

    smoothProgressTo(targetProgress, 420)

    if (summary.state === 'completed' || summary.state === 'failed') {
      return
    }

    await wait(POLL_INTERVAL_MS)
  }

  throw new BackendApiError('Import is taking longer than expected. Please try again in a moment.')
}

function smoothProgressTo(target, duration = 460) {
  const nextTarget = Math.max(0, Math.min(100, Number(target || 0)))
  const startValue = displayProgress.value
  const startedAt = performance.now()

  stopProgressAnimation()

  const tick = (timestamp) => {
    const elapsed = timestamp - startedAt
    const progress = Math.min(1, elapsed / duration)
    const eased = 1 - Math.pow(1 - progress, 3)
    displayProgress.value = startValue + ((nextTarget - startValue) * eased)

    if (progress < 1) {
      progressAnimationFrameId = window.requestAnimationFrame(tick)
      return
    }

    displayProgress.value = nextTarget
    progressAnimationFrameId = 0
  }

  progressAnimationFrameId = window.requestAnimationFrame(tick)
}

function stopProgressAnimation() {
  if (progressAnimationFrameId) {
    window.cancelAnimationFrame(progressAnimationFrameId)
    progressAnimationFrameId = 0
  }
}

function clearPollTimer() {
  if (pollTimeoutId) {
    window.clearTimeout(pollTimeoutId)
    pollTimeoutId = 0
  }
}

function wait(ms) {
  return new Promise((resolve) => {
    clearPollTimer()
    pollTimeoutId = window.setTimeout(() => {
      pollTimeoutId = 0
      resolve()
    }, ms)
  })
}

function resetFlow() {
  stopProgressAnimation()
  clearPollTimer()
  selectedFile.value = null
  if (fileInputEl.value) fileInputEl.value.value = ''
  stage.value = 'idle'
  processingLabel.value = 'Uploading Please Wait'
  displayProgress.value = 0
  previewSummary.value = null
  importSummary.value = null
  displayRows.value = []
  feedbackMessage.value = ''
  feedbackError.value = false
  isSwiping.value = false
  swipeProgress.value = 0
}

function resolveImportErrorMessage(error) {
  if (!(error instanceof BackendApiError)) {
    return error?.message || 'Unable to import this file right now.'
  }

  if (error.status === 400) {
    return error.message || 'Only .xlsx and .csv files are allowed.'
  }

  if (error.status === 403) {
    return 'This session is not allowed to import students right now.'
  }

  if (error.status === 413) {
    return error.message || 'The uploaded file is too large.'
  }

  if (error.status === 429) {
    return 'Too many import requests. Please wait before uploading again.'
  }

  if (error.status === 401) {
    return 'Session expired. Please log in again.'
  }

  return error.message || 'Unable to import this file right now.'
}

async function handleLogout() {
  await logout()
}
</script>

<style scoped>
.school-it-import{min-height:100vh;padding:30px 28px 120px;font-family:'Manrope',sans-serif}
.school-it-import__shell{width:100%;max-width:1120px;margin:0 auto}
.school-it-import__body{display:flex;flex-direction:column;gap:18px;max-width:460px;margin:24px auto 0}
.school-it-import__title-card,.school-it-import__panel{background:var(--color-surface);border-radius:32px;box-shadow:0 18px 40px rgba(15,23,42,.04)}
.school-it-import__title-card{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:20px 22px}
.school-it-import__title{margin:0;font-size:clamp(18px,5vw,20px);font-weight:800;line-height:1;letter-spacing:-.04em;color:var(--color-text-primary)}
.school-it-import__info-button{width:34px;height:34px;padding:0;border:1.2px solid color-mix(in srgb,var(--color-text-primary) 12%, transparent);border-radius:999px;background:transparent;color:var(--color-text-primary);display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.school-it-import__info-note{margin:0;padding:0 8px;font-size:13px;line-height:1.45;color:var(--color-text-secondary)}
.school-it-import__panel{padding:18px;overflow:hidden}
.school-it-import__stage{min-height:250px;display:flex;flex-direction:column}
.school-it-import__dropzone{width:100%;min-height:250px;padding:28px 18px 22px;border:none;border-radius:28px;background:var(--color-surface);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;transition:transform .22s ease,box-shadow .28s ease,background-color .22s ease}
.school-it-import__dropzone--active{transform:translateY(-2px);box-shadow:0 18px 34px rgba(15,23,42,.08);background:color-mix(in srgb,var(--color-surface) 86%,var(--color-primary) 14%)}
.school-it-import__dropzone--selected{background:color-mix(in srgb,var(--color-surface) 92%,var(--color-primary) 8%)}
.school-it-import__dropzone-icon{color:var(--color-text-primary)}
.school-it-import__dropzone-copy{display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center}
.school-it-import__dropzone-title,.school-it-import__dropzone-caption,.school-it-import__dropzone-file{margin:0}
.school-it-import__dropzone-title{font-size:14px;font-weight:600;line-height:1.35;color:var(--color-text-primary)}
.school-it-import__dropzone-caption{font-size:13px;color:var(--color-text-secondary)}
.school-it-import__dropzone-file{font-size:12px;font-weight:700;color:var(--color-primary)}
.school-it-import__stage--processing{align-items:center;justify-content:center;gap:30px}
.school-it-import__processing-label{margin:0;font-size:14px;font-weight:600;line-height:1.2;color:var(--color-text-primary);text-align:center}
.school-it-import__progress-shell{width:min(100%,286px);padding:0 6px}
.school-it-import__progress-track{position:relative;width:100%;height:12px;border-radius:999px;background:color-mix(in srgb,var(--color-surface) 70%, var(--color-bg));overflow:visible}
.school-it-import__progress-fill{position:absolute;inset:0 auto 0 0;min-width:18px;border-radius:999px;background:linear-gradient(90deg,var(--color-primary) 0%,color-mix(in srgb,var(--color-primary) 84%, white) 55%,var(--color-primary) 100%);box-shadow:0 8px 20px color-mix(in srgb,var(--color-primary) 24%, transparent);overflow:hidden;transition:width .34s cubic-bezier(.22,1,.36,1)}
.school-it-import__progress-fill::after{content:"";position:absolute;inset:0;transform:translateX(-100%);background:linear-gradient(105deg,rgba(255,255,255,0) 0%,rgba(255,255,255,.5) 42%,rgba(255,255,255,0) 72%);animation:school-it-import-liquid 1.15s linear infinite}
.school-it-import__progress-knob{position:absolute;top:50%;width:6px;height:38px;border-radius:999px;background:#111111;transform:translate(-50%,-50%);box-shadow:0 10px 16px rgba(15,23,42,.16);transition:left .34s cubic-bezier(.22,1,.36,1)}
.school-it-import__stage--result{gap:16px}
.school-it-import__result-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.school-it-import__result-copy{display:flex;flex-direction:column;gap:6px;min-width:0}
.school-it-import__result-title,.school-it-import__result-summary,.school-it-import__result-name,.school-it-import__result-id,.school-it-import__result-error,.school-it-import__empty{margin:0}
.school-it-import__result-title{font-size:clamp(22px,6.5vw,28px);font-weight:800;line-height:.94;letter-spacing:-.05em;color:var(--color-text-primary)}
.school-it-import__result-summary{font-size:13px;line-height:1.4;color:var(--color-text-secondary)}
.school-it-import__result-reset{min-height:38px;padding:0 14px;border:none;border-radius:999px;background:color-mix(in srgb,var(--color-surface) 84%, var(--color-bg));color:var(--color-text-primary);font-size:12px;font-weight:700;white-space:nowrap}
.school-it-import__feedback{padding:0 2px;font-size:13px;font-weight:600;line-height:1.4;color:#15803D}
.school-it-import__feedback--error{color:#D92D20}
.school-it-import__success-banner{display:flex;flex-direction:column;gap:6px;padding:14px 16px;border-radius:22px;background:color-mix(in srgb,var(--color-primary) 14%, white);border:1px solid color-mix(in srgb,var(--color-primary) 24%, transparent)}
.school-it-import__success-title,.school-it-import__success-copy{margin:0}
.school-it-import__success-title{font-size:13px;font-weight:800;line-height:1.2;color:var(--color-text-primary)}
.school-it-import__success-copy{font-size:12px;font-weight:600;line-height:1.45;color:var(--color-text-secondary)}
.school-it-import__result-actions{display:flex;flex-wrap:wrap;gap:10px}
.school-it-import__secondary-action{min-height:36px;padding:0 14px;border:none;border-radius:999px;background:color-mix(in srgb,var(--color-surface) 82%, var(--color-bg));color:var(--color-text-primary);font-size:12px;font-weight:700}
.school-it-import__secondary-action--primary{background:color-mix(in srgb,var(--color-primary) 18%, white);color:var(--color-text-primary)}
.school-it-import__secondary-action:disabled{opacity:.62;cursor:not-allowed}
.school-it-import__results-list{display:flex;flex-direction:column;gap:12px;max-height:360px;overflow:auto;padding-right:2px}
.school-it-import__result-row{display:flex;flex-direction:column;gap:10px;padding:16px;border-radius:24px;background:color-mix(in srgb,var(--color-surface) 88%, var(--color-bg))}
.school-it-import__result-row--invalid{background:color-mix(in srgb,var(--color-surface) 76%, #FDE8E8)}
.school-it-import__result-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.school-it-import__result-identity{display:flex;flex-direction:column;gap:4px;min-width:0}
.school-it-import__result-name{font-size:15px;font-weight:800;line-height:1.08;color:var(--color-text-primary)}
.school-it-import__result-id{font-size:12px;font-weight:700;line-height:1;color:var(--color-primary)}
.school-it-import__result-status{min-height:30px;padding:0 12px;border-radius:999px;background:color-mix(in srgb,var(--color-primary) 18%, white);color:var(--color-text-primary);display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;letter-spacing:.02em;white-space:nowrap}
.school-it-import__result-status--invalid{background:#FEE2E2;color:#8A1C1C}
.school-it-import__result-meta{display:flex;flex-wrap:wrap;gap:8px 14px;font-size:12px;font-weight:600;line-height:1.3;color:var(--color-text-secondary)}
.school-it-import__result-error{font-size:12px;line-height:1.35;color:#B42318}
.school-it-import__empty{padding:18px 6px 8px;font-size:14px;line-height:1.5;color:var(--color-text-secondary);text-align:center}
.school-it-import__file-input{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
.school-it-import__action-row{display:flex;justify-content:center}
.school-it-import__swipe-pill{position:relative;width:min(100%,182px);min-height:56px;padding:0 18px 0 64px;border:none;border-radius:999px;background:var(--color-primary);color:var(--color-banner-text);display:inline-flex;align-items:center;justify-content:center;gap:10px;overflow:hidden;transition:transform .18s ease,filter .2s ease,box-shadow .28s ease}
.school-it-import__swipe-pill:disabled{opacity:.62;cursor:not-allowed}
.school-it-import__swipe-pill:not(:disabled):hover{filter:brightness(1.03)}
.school-it-import__swipe-pill:not(:disabled):active{transform:scale(.985)}
.school-it-import__swipe-thumb{position:absolute;left:5px;top:50%;width:46px;height:46px;border-radius:999px;background:var(--color-nav);color:var(--color-nav-text);display:inline-flex;align-items:center;justify-content:center;transform:translateY(-50%);transition:left .34s cubic-bezier(.22,1,.36,1),transform .2s ease}
.school-it-import__swipe-pill--busy .school-it-import__swipe-thumb{left:calc(100% - 51px)}
.school-it-import__swipe-label{font-size:12px;font-weight:700;line-height:1;letter-spacing:-.02em;transition:opacity .2s ease}
.school-it-import__swipe-chevrons{position:absolute;right:14px;display:inline-flex;align-items:center;gap:0;color:var(--color-banner-text);opacity:.88;animation:school-it-import-chevrons 1.15s ease-in-out infinite}
.school-it-import__swipe-pill--busy .school-it-import__swipe-chevrons,.school-it-import__swipe-pill--ready .school-it-import__swipe-chevrons{display:none}

.school-it-import-stage-enter-active,.school-it-import-stage-leave-active{transition:opacity .28s ease,transform .34s cubic-bezier(.22,1,.36,1)}
.school-it-import-stage-enter-from,.school-it-import-stage-leave-to{opacity:0;transform:translateY(8px)}
.school-it-import-info-enter-active,.school-it-import-info-leave-active{transition:opacity .22s ease,transform .24s ease}
.school-it-import-info-enter-from,.school-it-import-info-leave-to{opacity:0;transform:translateY(-4px)}

@keyframes school-it-import-liquid{
  from{transform:translateX(-120%)}
  to{transform:translateX(140%)}
}

@keyframes school-it-import-chevrons{
  0%,100%{transform:translateX(0);opacity:.72}
  50%{transform:translateX(4px);opacity:1}
}

@media (min-width:768px){
  .school-it-import{padding:40px 36px 60px}
  .school-it-import__body{max-width:520px;margin-top:30px}
  .school-it-import__panel{padding:20px}
  .school-it-import__stage{min-height:278px}
  .school-it-import__dropzone{min-height:278px}
}

@media (max-width:420px){
  .school-it-import{padding:26px 18px 118px}
  .school-it-import__body{gap:16px}
  .school-it-import__title-card{padding:18px 18px}
  .school-it-import__panel{padding:16px}
  .school-it-import__stage{min-height:232px}
  .school-it-import__dropzone{min-height:232px;padding:22px 14px 18px}
  .school-it-import__dropzone-icon{width:82px;height:82px}
  .school-it-import__result-row{padding:14px}
}

@media (prefers-reduced-motion:reduce){
  .school-it-import__dropzone,
  .school-it-import__progress-fill,
  .school-it-import__progress-knob,
  .school-it-import__swipe-pill,
  .school-it-import__swipe-thumb,
  .school-it-import__swipe-chevrons,
  .school-it-import-stage-enter-active,
  .school-it-import-stage-leave-active,
  .school-it-import-info-enter-active,
  .school-it-import-info-leave-active{
    transition:none;
    animation:none;
  }
}

.school-it-import__download-template {
  background: color-mix(in srgb, var(--color-surface) 80%, black 20%);
  color: var(--color-text-primary);
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  transition: opacity 0.2s ease;
}

.school-it-import__download-template:hover {
  opacity: 0.8;
}
</style>
