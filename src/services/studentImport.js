function toOptionalString(value, fallback = '') {
  if (value == null) return fallback
  const normalized = String(value).trim()
  return normalized.length ? normalized : fallback
}

function toOptionalNumber(value, fallback = 0) {
  const normalized = Number(value)
  return Number.isFinite(normalized) ? normalized : fallback
}

function normalizeStringList(values) {
  return Array.isArray(values)
    ? values.map((value) => toOptionalString(value, '')).filter(Boolean)
    : []
}

function normalizeRowData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return { ...value }
}

function readCaseInsensitive(rowData = {}, candidateKeys = []) {
  const direct = candidateKeys.find((key) => toOptionalString(rowData[key], ''))
  if (direct) return toOptionalString(rowData[direct], '')

  const normalizedEntries = Object.entries(rowData).map(([key, value]) => [
    String(key).trim().toLowerCase(),
    value,
  ])

  for (const candidateKey of candidateKeys) {
    const normalizedCandidate = String(candidateKey).trim().toLowerCase()
    const matched = normalizedEntries.find(([key]) => key === normalizedCandidate)
    if (matched && toOptionalString(matched[1], '')) {
      return toOptionalString(matched[1], '')
    }
  }

  return ''
}

function buildFullName(rowData = {}) {
  const firstName = readCaseInsensitive(rowData, ['First Name', 'first_name'])
  const middleName = readCaseInsensitive(rowData, ['Middle Name', 'middle_name'])
  const lastName = readCaseInsensitive(rowData, ['Last Name', 'last_name'])
  const directName = readCaseInsensitive(rowData, ['Full Name', 'full_name', 'Student Name', 'student_name'])

  const combined = [firstName, middleName, lastName].filter(Boolean).join(' ').trim()
  return combined || directName || 'Unnamed Student'
}

function buildStudentId(rowData = {}) {
  return readCaseInsensitive(rowData, ['Student_ID', 'Student ID', 'student_id'])
}

function buildDepartmentName(rowData = {}) {
  return readCaseInsensitive(rowData, ['Department', 'department', 'department_name']) || 'Unassigned Department'
}

function buildProgramName(rowData = {}) {
  return readCaseInsensitive(rowData, ['Course', 'Program', 'course', 'program', 'program_name']) || 'Unassigned Program'
}

function normalizePreviewRow(row = {}, index = 0) {
  const rowData = normalizeRowData(row.row_data)
  return {
    row: toOptionalNumber(row.row, index + 1),
    status: toOptionalString(row.status, 'unknown'),
    errors: normalizeStringList(row.errors),
    suggestions: normalizeStringList(row.suggestions),
    row_data: rowData,
  }
}

function normalizeImportErrorRow(row = {}, index = 0) {
  return {
    row: toOptionalNumber(row.row, index + 1),
    error: toOptionalString(row.error, 'Unknown import error'),
  }
}

export function normalizeImportPreviewSummary(payload = {}) {
  const rows = Array.isArray(payload?.rows) ? payload.rows.map(normalizePreviewRow) : []

  return {
    filename: toOptionalString(payload?.filename, ''),
    preview_token: toOptionalString(payload?.preview_token, ''),
    total_rows: toOptionalNumber(payload?.total_rows, rows.length),
    valid_rows: toOptionalNumber(payload?.valid_rows, rows.filter((row) => row.status === 'valid').length),
    invalid_rows: toOptionalNumber(payload?.invalid_rows, rows.filter((row) => row.status !== 'valid').length),
    can_commit: Boolean(payload?.can_commit),
    rows,
  }
}

export function normalizeImportJobCreateResponse(payload = {}) {
  return {
    job_id: toOptionalString(payload?.job_id, ''),
    status: toOptionalString(payload?.status, 'queued'),
    retried_from_job_id: toOptionalString(payload?.retried_from_job_id, ''),
  }
}

export function normalizeImportJobStatus(payload = {}) {
  return {
    job_id: toOptionalString(payload?.job_id, ''),
    state: toOptionalString(payload?.state, 'queued'),
    total_rows: toOptionalNumber(payload?.total_rows, 0),
    processed_rows: toOptionalNumber(payload?.processed_rows, 0),
    success_count: toOptionalNumber(payload?.success_count, 0),
    failed_count: toOptionalNumber(payload?.failed_count, 0),
    percentage_completed: Math.max(0, Math.min(100, toOptionalNumber(payload?.percentage_completed, 0))),
    estimated_time_remaining_seconds: payload?.estimated_time_remaining_seconds == null
      ? null
      : toOptionalNumber(payload?.estimated_time_remaining_seconds, null),
    errors: Array.isArray(payload?.errors) ? payload.errors.map(normalizeImportErrorRow) : [],
    failed_report_download_url: toOptionalString(payload?.failed_report_download_url, ''),
  }
}

export function extractStudentImportDisplayRows(summary = {}) {
  return (Array.isArray(summary?.rows) ? summary.rows : [])
    .map((row, index) => {
      const rowData = normalizeRowData(row?.row_data) || {}

      return {
        id: `${toOptionalNumber(row?.row, index + 1)}-${buildStudentId(rowData) || index + 1}`,
        row: toOptionalNumber(row?.row, index + 1),
        studentId: buildStudentId(rowData),
        name: buildFullName(rowData),
        department: buildDepartmentName(rowData),
        program: buildProgramName(rowData),
        status: toOptionalString(row?.status, 'unknown'),
        errors: normalizeStringList(row?.errors),
        suggestions: normalizeStringList(row?.suggestions),
      }
    })
}

export function createMockImportPreviewSummary({
  fileName = 'student_import_template.xlsx',
  users = [],
  departments = [],
  programs = [],
} = {}) {
  const departmentById = new Map(
    (Array.isArray(departments) ? departments : []).map((department) => [
      Number(department?.id),
      toOptionalString(department?.name, 'Unassigned Department'),
    ])
  )
  const programById = new Map(
    (Array.isArray(programs) ? programs : []).map((program) => [
      Number(program?.id),
      toOptionalString(program?.name, 'Unassigned Program'),
    ])
  )

  const rows = (Array.isArray(users) ? users : [])
    .filter((user) => user?.student_profile)
    .map((user, index) => ({
      row: index + 2,
      status: 'valid',
      errors: [],
      suggestions: [],
      row_data: {
        Student_ID: toOptionalString(user?.student_profile?.student_id, ''),
        Email: toOptionalString(user?.email, ''),
        'Last Name': toOptionalString(user?.last_name, ''),
        'First Name': toOptionalString(user?.first_name, ''),
        'Middle Name': toOptionalString(user?.middle_name, ''),
        Department: departmentById.get(Number(user?.student_profile?.department_id)) || 'Unassigned Department',
        Course: programById.get(Number(user?.student_profile?.program_id)) || 'Unassigned Program',
      },
    }))

  return normalizeImportPreviewSummary({
    filename: fileName,
    total_rows: rows.length,
    valid_rows: rows.length,
    invalid_rows: 0,
    can_commit: rows.length > 0,
    rows,
  })
}
