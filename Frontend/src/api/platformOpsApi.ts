import { apiJsonRequest, apiVoidRequest } from "../lib/api/client";

const toQuery = (params: Record<string, string | number | boolean | null | undefined>) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}`.trim() !== "") {
      query.set(key, String(value));
    }
  });
  return query.toString();
};

const getJson = <T>(path: string, fallback: string) =>
  apiJsonRequest<T>(path, { method: "GET", auth: true }, fallback);

const sendJson = <T>(
  path: string,
  method: "POST" | "PUT" | "PATCH",
  fallback: string,
  payload?: unknown
) =>
  apiJsonRequest<T>(
    path,
    {
      method,
      auth: true,
      ...(payload !== undefined ? { json: payload } : {}),
    },
    fallback
  );

const sendVoid = (
  path: string,
  method: "POST" | "DELETE",
  fallback: string
) => apiVoidRequest(path, { method, auth: true }, fallback);

export interface AuditLogItem {
  id: number;
  school_id: number;
  actor_user_id?: number | null;
  action: string;
  status: string;
  details?: string | null;
  details_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogSearchResponse {
  total: number;
  items: AuditLogItem[];
}

export const fetchAuditLogs = async (params: {
  q?: string;
  action?: string;
  status?: string;
  actor_user_id?: number;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditLogSearchResponse> => {
  const query = toQuery(params);
  return getJson<AuditLogSearchResponse>(
    `/api/audit-logs${query ? `?${query}` : ""}`,
    "Failed to fetch audit logs"
  );
};

export interface NotificationPreference {
  user_id: number;
  email_enabled: boolean;
  sms_enabled: boolean;
  sms_number?: string | null;
  notify_missed_events: boolean;
  notify_low_attendance: boolean;
  notify_account_security: boolean;
  notify_subscription: boolean;
  updated_at: string;
}

export interface NotificationLogItem {
  id: number;
  school_id?: number | null;
  user_id?: number | null;
  category: string;
  channel: string;
  status: string;
  subject: string;
  message: string;
  error_message?: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface NotificationDispatchSummary {
  processed_users: number;
  sent: number;
  failed: number;
  skipped: number;
  category: string;
}

export const fetchNotificationPreferences = async (): Promise<NotificationPreference> => {
  return getJson<NotificationPreference>(
    "/api/notifications/preferences/me",
    "Failed to fetch preferences"
  );
};

export const updateNotificationPreferences = async (
  payload: Partial<NotificationPreference>
): Promise<NotificationPreference> => {
  return sendJson<NotificationPreference>(
    "/api/notifications/preferences/me",
    "PUT",
    "Failed to update preferences",
    payload
  );
};

export const fetchNotificationLogs = async (params: {
  school_id?: number;
  category?: string;
  status?: string;
  user_id?: number;
  limit?: number;
}): Promise<NotificationLogItem[]> => {
  const query = toQuery(params);
  return getJson<NotificationLogItem[]>(
    `/api/notifications/logs${query ? `?${query}` : ""}`,
    "Failed to fetch notification logs"
  );
};

export const fetchMyNotificationInbox = async (limit = 50): Promise<NotificationLogItem[]> => {
  return getJson<NotificationLogItem[]>(
    `/api/notifications/inbox/me?limit=${limit}`,
    "Failed to fetch your notifications"
  );
};

export const sendTestNotification = async (message?: string): Promise<NotificationDispatchSummary> => {
  return sendJson<NotificationDispatchSummary>(
    "/api/notifications/test",
    "POST",
    "Failed to send test notification",
    { channel: "email", message }
  );
};

export const dispatchMissedEventsNotifications = async (
  params: { school_id?: number; lookback_days?: number } = {}
): Promise<NotificationDispatchSummary> => {
  const query = toQuery(params);
  return sendJson<NotificationDispatchSummary>(
    `/api/notifications/dispatch/missed-events${query ? `?${query}` : ""}`,
    "POST",
    "Failed to dispatch missed event alerts"
  );
};

export const dispatchLowAttendanceNotifications = async (
  params: { school_id?: number; threshold_percent?: number; min_records?: number } = {}
): Promise<NotificationDispatchSummary> => {
  const query = toQuery(params);
  return sendJson<NotificationDispatchSummary>(
    `/api/notifications/dispatch/low-attendance${query ? `?${query}` : ""}`,
    "POST",
    "Failed to dispatch low attendance alerts"
  );
};

export const dispatchEventReminderNotifications = async (
  params: { school_id?: number; lead_hours?: number } = {}
): Promise<NotificationDispatchSummary> => {
  const query = toQuery(params);
  return sendJson<NotificationDispatchSummary>(
    `/api/notifications/dispatch/event-reminders${query ? `?${query}` : ""}`,
    "POST",
    "Failed to dispatch event reminders"
  );
};

export interface MfaStatus {
  user_id: number;
  mfa_enabled: boolean;
  trusted_device_days: number;
  updated_at: string;
}

export interface UserSessionItem {
  id: string;
  token_jti: string;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
  last_seen_at: string;
  revoked_at?: string | null;
  expires_at: string;
  is_current: boolean;
}

export interface LoginHistoryItem {
  id: number;
  user_id?: number | null;
  school_id?: number | null;
  email_attempted: string;
  success: boolean;
  auth_method: string;
  failure_reason?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
}

export const fetchMfaStatus = async (): Promise<MfaStatus> => {
  return getJson<MfaStatus>("/api/auth/security/mfa-status", "Failed to fetch MFA status");
};

export const updateMfaStatus = async (
  payload: { mfa_enabled: boolean; trusted_device_days?: number }
): Promise<MfaStatus> => {
  return sendJson<MfaStatus>(
    "/api/auth/security/mfa-status",
    "PUT",
    "Failed to update MFA status",
    payload
  );
};

export const fetchUserSessions = async (): Promise<UserSessionItem[]> => {
  return getJson<UserSessionItem[]>("/api/auth/security/sessions", "Failed to fetch sessions");
};

export const revokeUserSession = async (sessionId: string): Promise<void> => {
  return sendVoid(
    `/api/auth/security/sessions/${sessionId}/revoke`,
    "POST",
    "Failed to revoke session"
  );
};

export const revokeOtherSessions = async (): Promise<number> => {
  const body = await sendJson<{ revoked_count: number }>(
    "/api/auth/security/sessions/revoke-others",
    "POST",
    "Failed to revoke sessions"
  );
  return body.revoked_count;
};

export const fetchLoginHistory = async (limit = 100): Promise<LoginHistoryItem[]> => {
  return getJson<LoginHistoryItem[]>(
    `/api/auth/security/login-history?limit=${limit}`,
    "Failed to fetch login history"
  );
};

export interface SubscriptionMetrics {
  user_count: number;
  event_count_current_month: number;
  import_count_current_month: number;
  user_limit: number;
  event_limit_monthly: number;
  import_limit_monthly: number;
  user_usage_percent: number;
  event_usage_percent: number;
  import_usage_percent: number;
}

export interface SubscriptionSettings {
  school_id: number;
  plan_name: string;
  user_limit: number;
  event_limit_monthly: number;
  import_limit_monthly: number;
  renewal_date?: string | null;
  auto_renew: boolean;
  reminder_days_before: number;
  updated_at: string;
  metrics: SubscriptionMetrics;
}

export const fetchSubscription = async (schoolId?: number): Promise<SubscriptionSettings> => {
  const query = toQuery({ school_id: schoolId });
  return getJson<SubscriptionSettings>(
    `/api/subscription/me${query ? `?${query}` : ""}`,
    "Failed to fetch subscription"
  );
};

export const updateSubscription = async (
  payload: Partial<SubscriptionSettings>,
  schoolId?: number
): Promise<SubscriptionSettings> => {
  const query = toQuery({ school_id: schoolId });
  return sendJson<SubscriptionSettings>(
    `/api/subscription/me${query ? `?${query}` : ""}`,
    "PUT",
    "Failed to update subscription",
    payload
  );
};

export const runSubscriptionReminders = async (schoolId?: number): Promise<{
  schools_checked: number;
  reminders_created: number;
  reminders_sent: number;
  reminders_failed: number;
}> => {
  const query = toQuery({ school_id: schoolId });
  return sendJson<{
    schools_checked: number;
    reminders_created: number;
    reminders_sent: number;
    reminders_failed: number;
  }>(
    `/api/subscription/run-reminders${query ? `?${query}` : ""}`,
    "POST",
    "Failed to run reminders"
  );
};

export interface GovernanceSettings {
  school_id: number;
  attendance_retention_days: number;
  audit_log_retention_days: number;
  import_file_retention_days: number;
  auto_delete_enabled: boolean;
  updated_at: string;
}

export interface ConsentItem {
  id: number;
  user_id: number;
  school_id: number;
  consent_type: string;
  consent_granted: boolean;
  consent_version: string;
  source: string;
  created_at: string;
}

export interface DataRequestItem {
  id: number;
  school_id: number;
  requested_by_user_id?: number | null;
  target_user_id?: number | null;
  request_type: string;
  scope: string;
  status: string;
  reason?: string | null;
  details_json?: Record<string, unknown> | null;
  output_path?: string | null;
  handled_by_user_id?: number | null;
  created_at: string;
  resolved_at?: string | null;
}

export const fetchGovernanceSettings = async (schoolId?: number): Promise<GovernanceSettings> => {
  const query = toQuery({ school_id: schoolId });
  return getJson<GovernanceSettings>(
    `/api/governance/settings/me${query ? `?${query}` : ""}`,
    "Failed to fetch governance settings"
  );
};

export const updateGovernanceSettings = async (
  payload: Partial<GovernanceSettings>,
  schoolId?: number
): Promise<GovernanceSettings> => {
  const query = toQuery({ school_id: schoolId });
  return sendJson<GovernanceSettings>(
    `/api/governance/settings/me${query ? `?${query}` : ""}`,
    "PUT",
    "Failed to update governance settings",
    payload
  );
};

export const createConsent = async (payload: {
  consent_type: string;
  consent_granted: boolean;
  consent_version?: string;
  source?: string;
}): Promise<ConsentItem> => {
  return sendJson<ConsentItem>(
    "/api/governance/consents/me",
    "POST",
    "Failed to save consent",
    payload
  );
};

export const fetchMyConsents = async (): Promise<ConsentItem[]> => {
  return getJson<ConsentItem[]>("/api/governance/consents/me", "Failed to fetch consents");
};

export const createDataRequest = async (payload: {
  request_type: "export" | "delete";
  reason?: string;
  target_user_id?: number;
  details_json?: Record<string, unknown>;
}): Promise<DataRequestItem> => {
  return sendJson<DataRequestItem>(
    "/api/governance/requests",
    "POST",
    "Failed to create data request",
    payload
  );
};

export const fetchDataRequests = async (params: {
  school_id?: number;
  status?: string;
  request_type?: string;
  limit?: number;
} = {}): Promise<DataRequestItem[]> => {
  const query = toQuery(params);
  return getJson<DataRequestItem[]>(
    `/api/governance/requests${query ? `?${query}` : ""}`,
    "Failed to fetch data requests"
  );
};

export const updateDataRequestStatus = async (
  requestId: number,
  payload: { status: "approved" | "rejected" | "completed"; note?: string }
): Promise<DataRequestItem> => {
  return sendJson<DataRequestItem>(
    `/api/governance/requests/${requestId}`,
    "PATCH",
    "Failed to update data request",
    payload
  );
};

export const runRetentionCleanup = async (
  payload: { dry_run: boolean },
  schoolId?: number
): Promise<{
  school_id: number;
  dry_run: boolean;
  deleted_audit_logs: number;
  deleted_import_logs: number;
  deleted_notifications: number;
  summary: string;
}> => {
  const query = toQuery({ school_id: schoolId });
  return sendJson<{
    school_id: number;
    dry_run: boolean;
    deleted_audit_logs: number;
    deleted_import_logs: number;
    deleted_notifications: number;
    summary: string;
  }>(
    `/api/governance/run-retention${query ? `?${query}` : ""}`,
    "POST",
    "Failed to run retention cleanup",
    payload
  );
};
