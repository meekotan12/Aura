const REDIRECT_ALLOWLIST = new Set<string>([
  "/",
  "/login",
  "/change-password",
  "/auth/face-verification",
  "/student_face_registration",
  "/student_event_checkin",
  "/admin_dashboard",
  "/admin_home",
  "/admin_reports",
  "/admin_manage_users",
  "/admin_school_management",
  "/admin_audit_logs",
  "/admin_notifications",
  "/admin_security",
  "/admin_face_verification",
  "/admin_password_resets",
  "/admin_subscription",
  "/admin_governance",
  "/admin_profile",
  "/student_dashboard",
  "/student_home",
  "/student_upcoming_events",
  "/student_events_attended",
  "/student_profile",
  "/campus_admin_dashboard",
  "/campus_admin_home",
  "/campus_admin_events",
  "/campus_admin_reports",
  "/campus_admin_attendance",
  "/campus_admin_announcements",
  "/campus_admin_create_department_program",
  "/campus_admin_branding",
  "/campus_admin_import_users",
  "/campus_admin_password_resets",
  "/campus_admin_manage_users",
  "/campus_admin_audit_logs",
  "/campus_admin_notifications",
  "/campus_admin_security",
  "/campus_admin_face_verification",
  "/campus_admin_subscription",
  "/campus_admin_governance",
  "/campus_admin_governance_hierarchy",
  "/campus_admin_profile",
  "/ssg_dashboard",
  "/ssg_home",
  "/ssg_profile",
  "/ssg_events",
  "/ssg_records",
  "/ssg_manual_attendance",
  "/ssg_manage_sg",
  "/ssg_announcements",
  "/ssg_students",
  "/student_ssg_dashboard",
  "/studentssg_home",
  "/studentssg_upcoming_events",
  "/studentssg_events_attended",
  "/studentssg_events",
  "/studentssg_attendance",
  "/studentssg_records",
  "/studentssg_manual_attendance",
  "/studentssg_face_scan",
  "/studentssg_profile",
  "/sg_dashboard",
  "/sg_home",
  "/sg_profile",
  "/sg_events",
  "/sg_records",
  "/sg_manual_attendance",
  "/sg_manage_org",
  "/sg_announcements",
  "/sg_students",
  "/org_dashboard",
  "/org_home",
  "/org_profile",
  "/org_events",
  "/org_records",
  "/org_manual_attendance",
  "/org_announcements",
  "/org_students",
  "/unauthorized",
]);

const REDIRECT_BASE_URL = "https://valid8.local";

export const isAllowedRedirectPath = (value: string | null | undefined): boolean => {
  if (typeof value !== "string") {
    return false;
  }

  const trimmedValue = value.trim();
  if (!trimmedValue || !trimmedValue.startsWith("/") || trimmedValue.startsWith("//")) {
    return false;
  }

  try {
    const parsed = new URL(trimmedValue, REDIRECT_BASE_URL);
    if (parsed.origin !== REDIRECT_BASE_URL) {
      return false;
    }
    return REDIRECT_ALLOWLIST.has(parsed.pathname);
  } catch {
    return false;
  }
};

export const sanitizeRedirectPath = (
  value: string | null | undefined,
  fallback = "/"
): string => {
  const safeFallback = isAllowedRedirectPath(fallback) ? fallback : "/";
  if (!isAllowedRedirectPath(value)) {
    return safeFallback;
  }

  const parsed = new URL(value!.trim(), REDIRECT_BASE_URL);
  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
};

export const getRedirectAllowlist = (): string[] => Array.from(REDIRECT_ALLOWLIST);
