const GOVERNANCE_CONTEXTS = new Set(['SSG', 'SG', 'ORG'])

function normalizePermissionCode(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_')
}

function normalizePermissionCodeList(values = []) {
  if (!Array.isArray(values)) return []

  return [...new Set(
    values
      .map((value) => normalizePermissionCode(value))
      .filter(Boolean)
  )]
}

export function normalizeGovernanceContext(value) {
  const normalized = String(value || '').trim().toUpperCase()
  return GOVERNANCE_CONTEXTS.has(normalized) ? normalized : ''
}

export function getGovernanceAccessUnits(access = null) {
  return (Array.isArray(access?.units) ? access.units : [])
    .filter((unit) => unit && normalizeGovernanceContext(unit?.unit_type))
    .filter((unit) => unit?.is_active !== false)
}

export function hasGovernanceUnitPermission(access = null, unit = null, permissionCode = '') {
  const normalizedPermissionCode = normalizePermissionCode(permissionCode)
  if (!normalizedPermissionCode) return true

  const unitPermissionCodes = normalizePermissionCodeList(unit?.permission_codes)
  if (unitPermissionCodes.length) {
    return unitPermissionCodes.includes(normalizedPermissionCode)
  }

  const accessPermissionCodes = normalizePermissionCodeList(access?.permission_codes)
  if (accessPermissionCodes.length) {
    return accessPermissionCodes.includes(normalizedPermissionCode)
  }

  return true
}

function matchesPreferredUnit(unit = null, preferredUnitId = null, preferredContext = '') {
  const normalizedPreferredUnitId = Number(preferredUnitId)
  if (Number.isFinite(normalizedPreferredUnitId)) {
    return Number(unit?.governance_unit_id) === normalizedPreferredUnitId
  }

  const normalizedPreferredContext = normalizeGovernanceContext(preferredContext)
  if (normalizedPreferredContext) {
    return normalizeGovernanceContext(unit?.unit_type) === normalizedPreferredContext
  }

  return false
}

export function getGovernanceUnitsForAction(access = null, options = {}) {
  const {
    requiredPermissionCode = '',
    preferredUnitId = null,
    preferredContext = '',
  } = options

  const matchingUnits = getGovernanceAccessUnits(access)
    .filter((unit) => hasGovernanceUnitPermission(access, unit, requiredPermissionCode))

  const preferredUnits = matchingUnits.filter((unit) =>
    matchesPreferredUnit(unit, preferredUnitId, preferredContext)
  )
  const remainingUnits = matchingUnits.filter((unit) => !preferredUnits.includes(unit))

  return [...preferredUnits, ...remainingUnits]
}

export function resolvePreferredGovernanceUnit(access = null, options = {}) {
  return getGovernanceUnitsForAction(access, options)[0] || null
}

export function listGovernanceContextsForAction(access = null, options = {}) {
  const contexts = []

  getGovernanceUnitsForAction(access, options).forEach((unit) => {
    const context = normalizeGovernanceContext(unit?.unit_type)
    if (context && !contexts.includes(context)) {
      contexts.push(context)
    }
  })

  return contexts
}

export function collectGovernancePermissionCodes(access = null) {
  const collected = normalizePermissionCodeList(access?.permission_codes)

  getGovernanceAccessUnits(access).forEach((unit) => {
    normalizePermissionCodeList(unit?.permission_codes).forEach((permissionCode) => {
      if (!collected.includes(permissionCode)) {
        collected.push(permissionCode)
      }
    })
  })

  return collected
}
