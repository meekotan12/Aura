import { resolveBackendMediaUrl } from '@/services/backendMedia.js'

const AUTH_META_KEY = 'aura_auth_meta'
export const AUTH_META_CHANGED_EVENT = 'aura-auth-meta-changed'

/**
 * Sanitize a token string: trim whitespace, reject obvious non-JWT values.
 */
export function sanitizeToken(token) {
    const trimmed = String(token || '').trim()
    if (!trimmed) return ''
    // Basic JWT format check: three dot-separated base64 segments
    if (trimmed.split('.').length === 3) return trimmed
    // If it doesn't look like a JWT, still accept it (some APIs use opaque tokens)
    // but strip any embedded HTML/script tags as a safety measure
    return trimmed.replace(/<[^>]*>/g, '')
}

function notifyAuthMetaChanged() {
    if (typeof window === 'undefined') return
    window.dispatchEvent(new CustomEvent(AUTH_META_CHANGED_EVENT))
}

function normalizeRoleName(role) {
    const normalized = String(role || '')
        .trim()
        .toLowerCase()
        .replace(/_/g, '-')

    if (normalized === 'campus-admin') return 'school-it'
    return normalized
}

function normalizeRoles(roles) {
    if (!Array.isArray(roles)) return []

    return roles
        .map((role) => {
            if (typeof role === 'string') return role
            return role?.role?.name || role?.name || ''
        })
        .map((role) => String(role || '').trim())
        .filter(Boolean)
}

export function getStoredAuthMeta() {
    try {
        const raw = localStorage.getItem(AUTH_META_KEY)
        if (!raw) return null
        return JSON.parse(raw)
    } catch {
        localStorage.removeItem(AUTH_META_KEY)
        return null
    }
}

export function storeAuthMeta(tokenPayload = {}) {
    const authMeta = {
        email: tokenPayload?.email || null,
        roles: normalizeRoles(tokenPayload?.roles),
        tokenType: tokenPayload?.token_type || 'bearer',
        userId: Number.isFinite(Number(tokenPayload?.user_id)) ? Number(tokenPayload.user_id) : null,
        firstName: tokenPayload?.first_name || null,
        lastName: tokenPayload?.last_name || null,
        mustChangePassword: Boolean(tokenPayload?.must_change_password),
        faceVerificationRequired: Boolean(tokenPayload?.face_verification_required),
        faceVerificationPending: Boolean(tokenPayload?.face_verification_pending),
        faceReferenceEnrolled: Boolean(tokenPayload?.face_reference_enrolled),
        schoolId: Number.isFinite(Number(tokenPayload?.school_id)) ? Number(tokenPayload.school_id) : null,
        schoolName: tokenPayload?.school_name || null,
        schoolCode: tokenPayload?.school_code || null,
        logoUrl: resolveBackendMediaUrl(tokenPayload?.logo_url || null),
        primaryColor: tokenPayload?.primary_color || null,
        secondaryColor: tokenPayload?.secondary_color || null,
        accentColor: tokenPayload?.accent_color || null,
        sessionId: tokenPayload?.session_id || null,
    }

    localStorage.setItem(AUTH_META_KEY, JSON.stringify(authMeta))
    notifyAuthMetaChanged()
    return authMeta
}

export function patchStoredAuthMeta(patch = {}) {
    const current = getStoredAuthMeta() || {
        email: null,
        roles: [],
        tokenType: 'bearer',
        userId: null,
        firstName: null,
        lastName: null,
        mustChangePassword: false,
        faceVerificationRequired: false,
        faceVerificationPending: false,
        faceReferenceEnrolled: false,
        schoolId: null,
        schoolName: null,
        schoolCode: null,
        logoUrl: null,
        primaryColor: null,
        secondaryColor: null,
        accentColor: null,
        sessionId: null,
    }

    const nextValue = {
        ...current,
        ...patch,
    }

    if (patch.roles) {
        nextValue.roles = normalizeRoles(patch.roles)
    }

    if (Object.prototype.hasOwnProperty.call(patch, 'logoUrl')) {
        nextValue.logoUrl = resolveBackendMediaUrl(patch.logoUrl)
    }

    localStorage.setItem(AUTH_META_KEY, JSON.stringify(nextValue))
    notifyAuthMetaChanged()
    return nextValue
}

export function clearStoredAuthMeta() {
    localStorage.removeItem(AUTH_META_KEY)
    notifyAuthMetaChanged()
}

export function needsStoredPasswordChange() {
    return Boolean(getStoredAuthMeta()?.mustChangePassword)
}

export function hasPrivilegedPendingFace(meta = getStoredAuthMeta()) {
    const roles = normalizeRoles(meta?.roles).map(normalizeRoleName)
    const hasPrivilegedRole = roles.includes('admin') || roles.includes('school-it')

    return Boolean(
        hasPrivilegedRole &&
        (
            meta?.tokenType === 'face_pending' ||
            meta?.faceVerificationPending ||
            meta?.faceVerificationRequired
        )
    )
}
