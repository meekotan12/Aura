import { resolveBackendMediaUrl } from '@/services/backendMedia.js'

const DEFAULT_PRIMARY_COLOR = '#0057B8'
const DEFAULT_SECONDARY_COLOR = '#FFD400'
const DEFAULT_ACCENT_COLOR = '#000000'

function nowIso() {
    return new Date().toISOString()
}

function toOptionalString(value, fallback = null) {
    if (value == null) return fallback
    const normalized = String(value).trim()
    return normalized.length ? normalized : fallback
}

function toOptionalNumber(value, fallback = null) {
    const normalized = Number(value)
    return Number.isFinite(normalized) ? normalized : fallback
}

function toIntegerOrOriginal(value, fallback = null) {
    const normalized = toOptionalNumber(value, null)
    if (normalized != null) return normalized
    return toOptionalString(value, fallback)
}

export function normalizeRoleName(role) {
    if (typeof role === 'string') return role.trim()
    return String(role?.role?.name || role?.name || '').trim()
}

function normalizeRoleNames(roles) {
    if (!Array.isArray(roles)) return []

    const seen = new Set()
    return roles
        .map(normalizeRoleName)
        .filter(Boolean)
        .filter((roleName) => {
            const normalizedKey = roleName.toLowerCase()
            if (seen.has(normalizedKey)) return false
            seen.add(normalizedKey)
            return true
        })
}

function normalizeRoleRelations(roles) {
    return normalizeRoleNames(roles).map((roleName, index) => {
        const existing = Array.isArray(roles)
            ? roles.find((entry) => normalizeRoleName(entry).toLowerCase() === roleName.toLowerCase())
            : null

        return {
            id: toOptionalNumber(existing?.id, index + 1),
            role: {
                id: toOptionalNumber(existing?.role?.id ?? existing?.role_id, index + 1),
                name: roleName,
            },
        }
    })
}

function normalizeLiveness(value) {
    if (!value || typeof value !== 'object') return null

    return {
        label: toOptionalString(value.label, 'Unknown'),
        score: typeof value.score === 'number' ? value.score : Number(value.score || 0),
        reason: toOptionalString(value.reason, null),
    }
}

export function normalizeTokenPayload(payload = {}) {
    const roles = normalizeRoleNames(payload.roles)

    return {
        ...payload,
        access_token: toOptionalString(payload.access_token, null),
        token_type: toOptionalString(payload.token_type, 'bearer') || 'bearer',
        email: toOptionalString(payload.email, null),
        roles,
        user_id: toOptionalNumber(payload.user_id, null),
        first_name: toOptionalString(payload.first_name, null),
        last_name: toOptionalString(payload.last_name, null),
        school_id: toOptionalNumber(payload.school_id, null),
        school_name: toOptionalString(payload.school_name, null),
        school_code: toOptionalString(payload.school_code, null),
        logo_url: resolveBackendMediaUrl(toOptionalString(payload.logo_url, null)),
        primary_color: toOptionalString(payload.primary_color, null),
        secondary_color: toOptionalString(payload.secondary_color, null),
        accent_color: toOptionalString(payload.accent_color, null),
        must_change_password: Boolean(payload.must_change_password),
        session_id: toOptionalString(payload.session_id, null),
        mfa_required: Boolean(payload.mfa_required),
        mfa_challenge_id: toOptionalString(payload.mfa_challenge_id, null),
        mfa_expires_at: toOptionalString(payload.mfa_expires_at, null),
        face_verification_required: Boolean(payload.face_verification_required),
        face_reference_enrolled: Boolean(payload.face_reference_enrolled),
        face_verification_pending: Boolean(payload.face_verification_pending),
        change_password_endpoint: toOptionalString(payload.change_password_endpoint, null),
        is_admin: typeof payload.is_admin === 'boolean' ? payload.is_admin : roles.includes('admin'),
    }
}

export function normalizeDepartment(department = {}) {
    return {
        ...department,
        id: toOptionalNumber(department.id, 0),
        name: toOptionalString(department.name, 'Unnamed Department'),
    }
}

export function normalizeProgram(program = {}) {
    const departmentIds = Array.isArray(program.department_ids)
        ? program.department_ids.map((value) => toOptionalNumber(value, null)).filter((value) => value != null)
        : []

    return {
        ...program,
        id: toOptionalNumber(program.id, 0),
        name: toOptionalString(program.name, 'Unnamed Program'),
        department_ids: departmentIds,
    }
}

export function normalizeSchoolSettings(settings = null) {
    if (!settings || typeof settings !== 'object') return null

    const primaryColor = toOptionalString(settings.primary_color, DEFAULT_PRIMARY_COLOR)
    const secondaryColor = toOptionalString(settings.secondary_color, DEFAULT_SECONDARY_COLOR)

    return {
        ...settings,
        school_id: toOptionalNumber(settings.school_id ?? settings.id, 0),
        school_name: toOptionalString(settings.school_name, 'School'),
        school_code: toOptionalString(settings.school_code, null),
        logo_url: resolveBackendMediaUrl(toOptionalString(settings.logo_url, null)),
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        accent_color: toOptionalString(settings.accent_color, DEFAULT_ACCENT_COLOR),
        subscription_status: toOptionalString(settings.subscription_status, 'trial'),
        active_status: typeof settings.active_status === 'boolean' ? settings.active_status : true,
    }
}

export function normalizeEvent(event = {}) {
    return {
        ...event,
        id: toOptionalNumber(event.id, 0),
        school_id: toOptionalNumber(event.school_id, null),
        name: toOptionalString(event.name, 'Untitled Event'),
        location: toOptionalString(event.location, 'TBA'),
        start_datetime: toOptionalString(event.start_datetime, null),
        end_datetime: toOptionalString(event.end_datetime, null),
        status: toOptionalString(event.status, 'upcoming'),
        geo_required: Boolean(event.geo_required),
        geo_latitude: typeof event.geo_latitude === 'number' ? event.geo_latitude : toOptionalNumber(event.geo_latitude, null),
        geo_longitude: typeof event.geo_longitude === 'number' ? event.geo_longitude : toOptionalNumber(event.geo_longitude, null),
        geo_radius_m: toOptionalNumber(event.geo_radius_m, null),
        geo_max_accuracy_m: toOptionalNumber(event.geo_max_accuracy_m, null),
        early_check_in_minutes: toOptionalNumber(event.early_check_in_minutes, 0),
        late_threshold_minutes: toOptionalNumber(event.late_threshold_minutes, 0),
        sign_out_grace_minutes: toOptionalNumber(event.sign_out_grace_minutes, 0),
        sign_out_open_delay_minutes: toOptionalNumber(event.sign_out_open_delay_minutes, 0),
        sign_out_override_until: toOptionalString(event.sign_out_override_until, null),
        present_until_override_at: toOptionalString(event.present_until_override_at, null),
        late_until_override_at: toOptionalString(event.late_until_override_at, null),
    }
}

export function normalizeAttendanceRecord(attendance = {}) {
    return {
        ...attendance,
        id: toOptionalNumber(attendance.id, 0),
        event_id: toOptionalNumber(attendance.event_id, 0),
        event_name: toOptionalString(attendance.event_name, null),
        student_id: toIntegerOrOriginal(attendance.student_id, null),
        method: toOptionalString(attendance.method, 'manual'),
        status: toOptionalString(attendance.status, 'present'),
        display_status: toOptionalString(attendance.display_status, null),
        notes: toOptionalString(attendance.notes, null),
        time_in: toOptionalString(attendance.time_in, null),
        time_out: toOptionalString(attendance.time_out, null),
        completion_state: toOptionalString(attendance.completion_state, null),
        check_in_status: toOptionalString(attendance.check_in_status, null),
        check_out_status: toOptionalString(attendance.check_out_status, null),
        duration_minutes: toOptionalNumber(attendance.duration_minutes, null),
        is_valid_attendance: typeof attendance.is_valid_attendance === 'boolean'
            ? attendance.is_valid_attendance
            : null,
        verified_by: toOptionalNumber(attendance.verified_by, null),
    }
}

export function normalizeEventAttendanceWithStudent(payload = {}) {
    const attendance = normalizeAttendanceRecord(payload.attendance ?? payload)

    return {
        ...payload,
        attendance,
        student_id: toOptionalString(payload.student_id, null),
        student_name: toOptionalString(payload.student_name, 'Unknown Student'),
    }
}

export function normalizeEventAttendanceReport(payload = {}) {
    const normalizedPrograms = Array.isArray(payload.programs)
        ? payload.programs.map((program) => ({
            id: toOptionalNumber(program?.id, 0),
            name: toOptionalString(program?.name, 'Unknown Program'),
        }))
        : []

    const normalizedProgramBreakdown = Array.isArray(payload.program_breakdown)
        ? payload.program_breakdown.map((item) => ({
            program: toOptionalString(item?.program, 'Unknown Program'),
            total: toOptionalNumber(item?.total, 0),
            present: toOptionalNumber(item?.present, 0),
            late: toOptionalNumber(item?.late, 0),
            incomplete: toOptionalNumber(item?.incomplete, 0),
            absent: toOptionalNumber(item?.absent, 0),
        }))
        : []

    return {
        ...payload,
        event_name: toOptionalString(payload.event_name, 'Untitled Event'),
        event_date: toOptionalString(payload.event_date, null),
        event_location: toOptionalString(payload.event_location, 'N/A'),
        total_participants: toOptionalNumber(payload.total_participants, 0),
        attendees: toOptionalNumber(payload.attendees, 0),
        late_attendees: toOptionalNumber(payload.late_attendees, 0),
        incomplete_attendees: toOptionalNumber(payload.incomplete_attendees, 0),
        absentees: toOptionalNumber(payload.absentees, 0),
        attendance_rate: typeof payload.attendance_rate === 'number'
            ? payload.attendance_rate
            : toOptionalNumber(payload.attendance_rate, 0),
        programs: normalizedPrograms,
        program_breakdown: normalizedProgramBreakdown,
    }
}

export function normalizeStudentProfile(profile = null) {
    if (!profile || typeof profile !== 'object') return null

    return {
        ...profile,
        id: toOptionalNumber(profile.id, 0),
        user_id: toOptionalNumber(profile.user_id, null),
        school_id: toOptionalNumber(profile.school_id, null),
        student_id: toOptionalString(profile.student_id, null),
        department_id: toOptionalNumber(profile.department_id, null),
        program_id: toOptionalNumber(profile.program_id, null),
        year_level: toOptionalNumber(profile.year_level, null),
        attendances: Array.isArray(profile.attendances)
            ? profile.attendances.map(normalizeAttendanceRecord)
            : [],
        is_face_registered: Boolean(profile.is_face_registered),
        registration_complete: Boolean(profile.registration_complete),
        photo_url: resolveBackendMediaUrl(toOptionalString(profile.photo_url, null)),
        avatar_url: resolveBackendMediaUrl(toOptionalString(profile.avatar_url, null)),
    }
}

export function normalizeUserWithRelations(user = null) {
    if (!user || typeof user !== 'object') return null

    return {
        ...user,
        id: toOptionalNumber(user.id, 0),
        email: toOptionalString(user.email, ''),
        first_name: toOptionalString(user.first_name, ''),
        middle_name: toOptionalString(user.middle_name, null),
        last_name: toOptionalString(user.last_name, ''),
        is_active: typeof user.is_active === 'boolean' ? user.is_active : true,
        created_at: toOptionalString(user.created_at, nowIso()),
        school_id: toOptionalNumber(user.school_id, null),
        school_name: toOptionalString(user.school_name, null),
        school_code: toOptionalString(user.school_code, null),
        roles: normalizeRoleRelations(user.roles),
        ssg_profile: user.ssg_profile ?? null,
        student_profile: normalizeStudentProfile(user.student_profile),
        avatar_url: resolveBackendMediaUrl(toOptionalString(user.avatar_url ?? user.profile_photo_url, null)),
        must_change_password: Boolean(user.must_change_password),
    }
}

export function normalizeUserCreateResponse(payload = {}) {
    const user = normalizeUserWithRelations(payload)
    if (!user) return null

    return {
        ...user,
        generated_temporary_password: toOptionalString(payload.generated_temporary_password, null),
    }
}

export function normalizeFaceStatus(payload = {}) {
    return {
        ...payload,
        face_verification_required: Boolean(payload.face_verification_required),
        face_reference_enrolled: Boolean(payload.face_reference_enrolled),
        provider: toOptionalString(payload.provider, 'face_recognition'),
        updated_at: toOptionalString(payload.updated_at, null),
        last_verified_at: toOptionalString(payload.last_verified_at, null),
        liveness_enabled: payload.liveness_enabled !== false,
        anti_spoof_ready: Boolean(payload.anti_spoof_ready),
        anti_spoof_reason: toOptionalString(payload.anti_spoof_reason, null),
        live_capture_required: Boolean(payload.live_capture_required),
    }
}

export function normalizeFaceReferenceResponse(payload = {}) {
    return {
        ...payload,
        user_id: toOptionalNumber(payload.user_id, null),
        face_reference_enrolled: Boolean(payload.face_reference_enrolled),
        provider: toOptionalString(payload.provider, 'face_recognition'),
        updated_at: toOptionalString(payload.updated_at, null),
        liveness: normalizeLiveness(payload.liveness),
    }
}

export function normalizeFaceVerificationResponse(payload = {}) {
    return {
        ...payload,
        matched: Boolean(payload.matched),
        distance: typeof payload.distance === 'number' ? payload.distance : toOptionalNumber(payload.distance, null),
        confidence: typeof payload.confidence === 'number' ? payload.confidence : toOptionalNumber(payload.confidence, null),
        threshold: typeof payload.threshold === 'number' ? payload.threshold : toOptionalNumber(payload.threshold, null),
        verified_at: toOptionalString(payload.verified_at, null),
        access_token: toOptionalString(payload.access_token, null),
        token_type: toOptionalString(payload.token_type, 'bearer'),
        session_id: toOptionalString(payload.session_id, null),
        face_verification_pending: Boolean(payload.face_verification_pending),
        liveness: normalizeLiveness(payload.liveness),
    }
}

export function normalizeStudentFaceRegistrationResponse(payload = {}) {
    return {
        ...payload,
        message: toOptionalString(payload.message, 'Face registered successfully.'),
        student_id: toOptionalString(payload.student_id, null),
        liveness: normalizeLiveness(payload.liveness),
    }
}

export function normalizeCreateSchoolWithSchoolItResponse(payload = {}) {
    const school = normalizeSchoolSettings(payload.school)

    return {
        ...payload,
        school,
        school_it_user_id: toOptionalNumber(payload.school_it_user_id, null),
        school_it_email: toOptionalString(payload.school_it_email, null),
        generated_temporary_password: toOptionalString(payload.generated_temporary_password, null),
    }
}

export function normalizeSchoolSummary(summary = null) {
    if (!summary || typeof summary !== 'object') return null

    return {
        ...summary,
        school_id: toOptionalNumber(summary.school_id ?? summary.id, 0),
        school_name: toOptionalString(summary.school_name, 'School'),
        school_code: toOptionalString(summary.school_code, null),
        subscription_status: toOptionalString(summary.subscription_status, 'trial'),
        active_status: typeof summary.active_status === 'boolean' ? summary.active_status : true,
        created_at: toOptionalString(summary.created_at, nowIso()),
        updated_at: toOptionalString(summary.updated_at, nowIso()),
    }
}

export function normalizeSchoolItAccount(account = null) {
    if (!account || typeof account !== 'object') return null

    return {
        ...account,
        user_id: toOptionalNumber(account.user_id ?? account.id, 0),
        email: toOptionalString(account.email, ''),
        first_name: toOptionalString(account.first_name, null),
        last_name: toOptionalString(account.last_name, null),
        school_id: toOptionalNumber(account.school_id, null),
        school_name: toOptionalString(account.school_name, null),
        is_active: typeof account.is_active === 'boolean' ? account.is_active : true,
    }
}

export function normalizeAuditLogItem(item = null) {
    if (!item || typeof item !== 'object') return null

    return {
        ...item,
        id: toOptionalNumber(item.id, 0),
        school_id: toOptionalNumber(item.school_id, null),
        actor_user_id: toOptionalNumber(item.actor_user_id, null),
        action: toOptionalString(item.action, 'unknown_action'),
        status: toOptionalString(item.status, 'unknown'),
        details: toOptionalString(item.details, null),
        details_json: item.details_json && typeof item.details_json === 'object'
            ? item.details_json
            : null,
        created_at: toOptionalString(item.created_at, nowIso()),
    }
}

export function normalizeAuditLogResponse(payload = {}) {
    return {
        total: toOptionalNumber(payload.total, 0),
        items: Array.isArray(payload.items)
            ? payload.items.map(normalizeAuditLogItem).filter(Boolean)
            : [],
    }
}

export function normalizeNotificationLogItem(item = null) {
    if (!item || typeof item !== 'object') return null

    return {
        ...item,
        id: toOptionalNumber(item.id, 0),
        school_id: toOptionalNumber(item.school_id, null),
        user_id: toOptionalNumber(item.user_id, null),
        category: toOptionalString(item.category, 'system'),
        channel: toOptionalString(item.channel, 'email'),
        status: toOptionalString(item.status, 'unknown'),
        subject: toOptionalString(item.subject, ''),
        message: toOptionalString(item.message, ''),
        error_message: toOptionalString(item.error_message, null),
        metadata_json: item.metadata_json && typeof item.metadata_json === 'object'
            ? item.metadata_json
            : null,
        created_at: toOptionalString(item.created_at, nowIso()),
    }
}

export function normalizeNotificationDispatchSummary(payload = {}) {
    return {
        ...payload,
        processed_users: toOptionalNumber(payload.processed_users, 0),
        sent: toOptionalNumber(payload.sent, 0),
        failed: toOptionalNumber(payload.failed, 0),
        skipped: toOptionalNumber(payload.skipped, 0),
        category: toOptionalString(payload.category, 'system'),
    }
}

export function normalizeGovernanceSetting(setting = null) {
    if (!setting || typeof setting !== 'object') return null

    return {
        ...setting,
        school_id: toOptionalNumber(setting.school_id, null),
        attendance_retention_days: toOptionalNumber(setting.attendance_retention_days, 365),
        audit_log_retention_days: toOptionalNumber(setting.audit_log_retention_days, 365),
        import_file_retention_days: toOptionalNumber(setting.import_file_retention_days, 30),
        auto_delete_enabled: Boolean(setting.auto_delete_enabled),
        updated_at: toOptionalString(setting.updated_at, nowIso()),
    }
}

export function normalizeGovernanceRequest(item = null) {
    if (!item || typeof item !== 'object') return null

    return {
        ...item,
        id: toOptionalNumber(item.id, 0),
        school_id: toOptionalNumber(item.school_id, null),
        requested_by_user_id: toOptionalNumber(item.requested_by_user_id, null),
        target_user_id: toOptionalNumber(item.target_user_id, null),
        request_type: toOptionalString(item.request_type, 'export'),
        scope: toOptionalString(item.scope, 'user_data'),
        status: toOptionalString(item.status, 'pending'),
        reason: toOptionalString(item.reason, null),
        details_json: item.details_json && typeof item.details_json === 'object'
            ? item.details_json
            : null,
        output_path: toOptionalString(item.output_path, null),
        handled_by_user_id: toOptionalNumber(item.handled_by_user_id, null),
        created_at: toOptionalString(item.created_at, nowIso()),
        resolved_at: toOptionalString(item.resolved_at, null),
    }
}

export function normalizeRetentionRunResult(payload = {}) {
    return {
        ...payload,
        school_id: toOptionalNumber(payload.school_id, null),
        dry_run: Boolean(payload.dry_run),
        deleted_audit_logs: toOptionalNumber(payload.deleted_audit_logs, 0),
        deleted_import_logs: toOptionalNumber(payload.deleted_import_logs, 0),
        deleted_notifications: toOptionalNumber(payload.deleted_notifications, 0),
        summary: toOptionalString(payload.summary, ''),
    }
}

export function normalizePasswordChangeResponse(payload = {}) {
    return {
        ...payload,
        message: toOptionalString(payload.message, 'Password updated successfully'),
    }
}

export function normalizePasswordResetResponse(payload = {}) {
    if (payload == null) {
        return {
            user_id: null,
            email: null,
            temporary_password: null,
            must_change_password: false,
        }
    }

    return {
        ...payload,
        user_id: toOptionalNumber(payload.user_id, null),
        email: toOptionalString(payload.email, null),
        temporary_password: toOptionalString(payload.temporary_password, null),
        must_change_password: Boolean(payload.must_change_password),
    }
}

function normalizeEventTimeStatusInfo(payload = null) {
    if (!payload || typeof payload !== 'object') return null

    return {
        ...payload,
        event_status: toOptionalString(payload.event_status ?? payload.status, 'unknown'),
        status: toOptionalString(payload.event_status ?? payload.status, 'unknown'),
        current_time: toOptionalString(payload.current_time, nowIso()),
        check_in_opens_at: toOptionalString(payload.check_in_opens_at, null),
        start_time: toOptionalString(payload.start_time, null),
        end_time: toOptionalString(payload.end_time, null),
        late_threshold_time: toOptionalString(payload.late_threshold_time, null),
        attendance_override_active: Boolean(payload.attendance_override_active),
        effective_present_until_at: toOptionalString(payload.effective_present_until_at, null),
        effective_late_until_at: toOptionalString(payload.effective_late_until_at, null),
        sign_out_opens_at: toOptionalString(payload.sign_out_opens_at, null),
        normal_sign_out_closes_at: toOptionalString(payload.normal_sign_out_closes_at, null),
        effective_sign_out_closes_at: toOptionalString(payload.effective_sign_out_closes_at, null),
        timezone_name: toOptionalString(payload.timezone_name, null),
    }
}

function normalizeEventAttendanceDecisionInfo(payload = null) {
    if (!payload || typeof payload !== 'object') return null

    return {
        ...payload,
        action: toOptionalString(payload.action, 'check_in'),
        event_status: toOptionalString(payload.event_status ?? payload.status, 'unknown'),
        status: toOptionalString(payload.event_status ?? payload.status, 'unknown'),
        attendance_allowed: Boolean(payload.attendance_allowed),
        attendance_status: toOptionalString(payload.attendance_status, null),
        reason_code: toOptionalString(payload.reason_code, null),
        message: toOptionalString(payload.message, ''),
        current_time: toOptionalString(payload.current_time, nowIso()),
        check_in_opens_at: toOptionalString(payload.check_in_opens_at, null),
        start_time: toOptionalString(payload.start_time, null),
        end_time: toOptionalString(payload.end_time, null),
        late_threshold_time: toOptionalString(payload.late_threshold_time, null),
        attendance_override_active: Boolean(payload.attendance_override_active),
        effective_present_until_at: toOptionalString(payload.effective_present_until_at, null),
        effective_late_until_at: toOptionalString(payload.effective_late_until_at, null),
        sign_out_opens_at: toOptionalString(payload.sign_out_opens_at, null),
        normal_sign_out_closes_at: toOptionalString(payload.normal_sign_out_closes_at, null),
        effective_sign_out_closes_at: toOptionalString(payload.effective_sign_out_closes_at, null),
        timezone_name: toOptionalString(payload.timezone_name, null),
    }
}

export function normalizeEventLocationResponse(payload = {}) {
    return {
        ...payload,
        ok: payload.ok !== false,
        reason: toOptionalString(payload.reason, null),
        distance_m: typeof payload.distance_m === 'number' ? payload.distance_m : toOptionalNumber(payload.distance_m, null),
        effective_distance_m: typeof payload.effective_distance_m === 'number' ? payload.effective_distance_m : toOptionalNumber(payload.effective_distance_m, null),
        radius_m: typeof payload.radius_m === 'number' ? payload.radius_m : toOptionalNumber(payload.radius_m, null),
        accuracy_m: typeof payload.accuracy_m === 'number' ? payload.accuracy_m : toOptionalNumber(payload.accuracy_m, null),
        time_status: normalizeEventTimeStatusInfo(payload.time_status),
        attendance_decision: normalizeEventAttendanceDecisionInfo(payload.attendance_decision),
    }
}

export function normalizeGovernanceStudentProfileSummary(profile = null) {
    if (!profile || typeof profile !== 'object') return null

    return {
        ...profile,
        id: toOptionalNumber(profile.id, 0),
        student_id: toOptionalString(profile.student_id, null),
        department_id: toOptionalNumber(profile.department_id, null),
        program_id: toOptionalNumber(profile.program_id, null),
        department_name: toOptionalString(profile.department_name, null),
        program_name: toOptionalString(profile.program_name, null),
        year_level: toOptionalNumber(profile.year_level, null),
    }
}

export function normalizeGovernanceUserSummary(user = null) {
    if (!user || typeof user !== 'object') return null

    return {
        ...user,
        id: toOptionalNumber(user.id, 0),
        email: toOptionalString(user.email, ''),
        first_name: toOptionalString(user.first_name, ''),
        middle_name: toOptionalString(user.middle_name, null),
        last_name: toOptionalString(user.last_name, ''),
        school_id: toOptionalNumber(user.school_id, null),
        is_active: typeof user.is_active === 'boolean' ? user.is_active : true,
        student_profile: normalizeGovernanceStudentProfileSummary(user.student_profile),
    }
}

export function normalizeGovernanceStudentCandidate(candidate = {}) {
    return {
        ...candidate,
        user: normalizeGovernanceUserSummary(candidate.user),
        student_profile: normalizeGovernanceStudentProfileSummary(candidate.student_profile),
        is_current_governance_member: Boolean(candidate.is_current_governance_member),
    }
}

export function normalizeGovernancePermission(permission = null) {
    if (!permission || typeof permission !== 'object') return null

    return {
        ...permission,
        id: toOptionalNumber(permission.id, 0),
        permission_code: toOptionalString(permission.permission_code, null),
        permission_name: toOptionalString(permission.permission_name, null),
        description: toOptionalString(permission.description, null),
    }
}

export function normalizeGovernanceMemberPermission(permission = {}) {
    const permissionRecord = normalizeGovernancePermission(permission.permission)

    return {
        ...permission,
        id: toOptionalNumber(permission.id, 0),
        permission_id: toOptionalNumber(permission.permission_id, null),
        granted_by_user_id: toOptionalNumber(permission.granted_by_user_id, null),
        created_at: toOptionalString(permission.created_at, null),
        permission: permissionRecord,
        permission_code: toOptionalString(permission.permission_code ?? permissionRecord?.permission_code, null),
        permission_name: toOptionalString(permission.permission_name ?? permissionRecord?.permission_name, null),
        description: toOptionalString(permission.description ?? permissionRecord?.description, null),
    }
}

export function normalizeGovernanceMember(member = {}) {
    return {
        ...member,
        id: toOptionalNumber(member.id, 0),
        governance_unit_id: toOptionalNumber(member.governance_unit_id, null),
        user_id: toOptionalNumber(member.user_id, null),
        position_title: toOptionalString(member.position_title, null),
        assigned_by_user_id: toOptionalNumber(member.assigned_by_user_id, null),
        assigned_at: toOptionalString(member.assigned_at, null),
        is_active: typeof member.is_active === 'boolean' ? member.is_active : true,
        user: normalizeGovernanceUserSummary(member.user),
        member_permissions: Array.isArray(member.member_permissions)
            ? member.member_permissions.map(normalizeGovernanceMemberPermission)
            : [],
    }
}

export function normalizeGovernanceUnitPermission(permission = {}) {
    const permissionRecord = normalizeGovernancePermission(permission.permission)

    return {
        ...permission,
        id: toOptionalNumber(permission.id, 0),
        governance_unit_id: toOptionalNumber(permission.governance_unit_id, null),
        permission_id: toOptionalNumber(permission.permission_id, null),
        granted_by_user_id: toOptionalNumber(permission.granted_by_user_id, null),
        created_at: toOptionalString(permission.created_at, null),
        permission: permissionRecord,
        permission_code: toOptionalString(permission.permission_code ?? permissionRecord?.permission_code, null),
        permission_name: toOptionalString(permission.permission_name ?? permissionRecord?.permission_name, null),
        description: toOptionalString(permission.description ?? permissionRecord?.description, null),
    }
}

export function normalizeGovernanceUnitDetail(unit = null) {
    if (!unit || typeof unit !== 'object') return null

    return {
        ...unit,
        id: toOptionalNumber(unit.id, 0),
        unit_code: toOptionalString(unit.unit_code, ''),
        unit_name: toOptionalString(unit.unit_name, ''),
        description: toOptionalString(unit.description, null),
        unit_type: toOptionalString(unit.unit_type, null),
        parent_unit_id: toOptionalNumber(unit.parent_unit_id, null),
        school_id: toOptionalNumber(unit.school_id, null),
        department_id: toOptionalNumber(unit.department_id, null),
        program_id: toOptionalNumber(unit.program_id, null),
        created_by_user_id: toOptionalNumber(unit.created_by_user_id, null),
        is_active: typeof unit.is_active === 'boolean' ? unit.is_active : true,
        created_at: toOptionalString(unit.created_at, null),
        updated_at: toOptionalString(unit.updated_at, null),
        members: Array.isArray(unit.members)
            ? unit.members.map(normalizeGovernanceMember)
            : [],
        unit_permissions: Array.isArray(unit.unit_permissions)
            ? unit.unit_permissions.map(normalizeGovernanceUnitPermission)
            : [],
    }
}

export function normalizeGovernanceSsgSetup(payload = null) {
    if (!payload || typeof payload !== 'object') return null

    const unitPayload = payload.unit
        || payload.governance_unit
        || payload.ssg_unit
        || (
            payload.id != null ||
            payload.unit_code != null ||
            payload.unit_name != null
                ? payload
                : null
        )

    return {
        ...payload,
        unit: normalizeGovernanceUnitDetail(unitPayload),
        total_imported_students: toOptionalNumber(payload.total_imported_students, 0),
    }
}

export function normalizeEventTimeStatus(payload = {}) {
    return {
        ...normalizeEventTimeStatusInfo(payload),
        event_id: toOptionalNumber(payload.event_id, null),
    }
}
