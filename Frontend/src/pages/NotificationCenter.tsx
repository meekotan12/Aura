import { useEffect, useMemo, useState } from "react";

import NavbarAdmin from "../components/NavbarAdmin";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import { NavbarStudent } from "../components/NavbarStudent";
import {
  dispatchEventReminderNotifications,
  dispatchLowAttendanceNotifications,
  dispatchMissedEventsNotifications,
  fetchMyNotificationInbox,
  fetchNotificationLogs,
  fetchNotificationPreferences,
  NotificationDispatchSummary,
  NotificationLogItem,
  NotificationPreference,
  sendTestNotification,
  updateNotificationPreferences,
} from "../api/platformOpsApi";
import {
  isStoredCampusAdmin,
  readStoredUserSession,
} from "../lib/auth/storedUser";

const NotificationCenter = () => {
  const storedUser = useMemo(() => readStoredUserSession(), []);
  const normalizedRoles = useMemo(
    () => (storedUser?.roles ?? []).map((role) => role.trim().toLowerCase()),
    [storedUser]
  );
  const isStudentView =
    normalizedRoles.includes("student") &&
    !normalizedRoles.includes("admin") &&
    !normalizedRoles.includes("campus_admin");
  const isSchoolIT = !isStudentView && isStoredCampusAdmin();
  const NavbarComponent = isStudentView
    ? NavbarStudent
    : isSchoolIT
      ? NavbarSchoolIT
      : NavbarAdmin;

  const [preferences, setPreferences] = useState<NotificationPreference | null>(null);
  const [logs, setLogs] = useState<NotificationLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<NotificationDispatchSummary | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [prefData, logsData] = await Promise.all([
        fetchNotificationPreferences(),
        isStudentView ? fetchMyNotificationInbox(100) : fetchNotificationLogs({ limit: 100 }),
      ]);
      setPreferences(prefData);
      setLogs(logsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notification center");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [isStudentView]);

  const savePreferences = async () => {
    if (!preferences) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateNotificationPreferences(preferences);
      setPreferences(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences");
    } finally {
      setSaving(false);
    }
  };

  const runAction = async (action: () => Promise<NotificationDispatchSummary>) => {
    setError(null);
    try {
      const data = await action();
      setSummary(data);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dispatch notifications");
    }
  };

  const pageTitle = isStudentView ? "My Notifications" : "Notification Center";
  const pageDescription = isStudentView
    ? "Review attendance alerts, sign-in confirmations, sign-out confirmations, and reminders."
    : "Manage notification channels, review the latest delivery logs, and dispatch reminders.";

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(180deg, #f4f7fb 0%, #e7eef8 100%)" }}>
      <NavbarComponent />
      <main className="container py-4">
        <div className="mb-4">
          <h2 className="mb-2">{pageTitle}</h2>
          <p className="text-muted mb-0">{pageDescription}</p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}
        {summary && !isStudentView && (
          <div className="alert alert-info">
            <strong>{summary.category}</strong>: processed {summary.processed_users}, sent {summary.sent},
            failed {summary.failed}, skipped {summary.skipped}
          </div>
        )}

        <div className="card mb-4 shadow-sm border-0">
          <div className="card-header bg-white">Notification Preferences</div>
          <div className="card-body">
            {loading || !preferences ? (
              <p className="mb-0">Loading...</p>
            ) : (
              <>
                <div className="form-check mb-2">
                  <input
                    id="pref-email"
                    type="checkbox"
                    className="form-check-input"
                    checked={preferences.email_enabled}
                    onChange={(e) =>
                      setPreferences((prev) => (prev ? { ...prev, email_enabled: e.target.checked } : prev))
                    }
                  />
                  <label className="form-check-label" htmlFor="pref-email">
                    Email notifications
                  </label>
                </div>
                <div className="form-check mb-2">
                  <input
                    id="pref-missed"
                    type="checkbox"
                    className="form-check-input"
                    checked={preferences.notify_missed_events}
                    onChange={(e) =>
                      setPreferences((prev) =>
                        prev ? { ...prev, notify_missed_events: e.target.checked } : prev
                      )
                    }
                  />
                  <label className="form-check-label" htmlFor="pref-missed">
                    Missed event alerts
                  </label>
                </div>
                <div className="form-check mb-2">
                  <input
                    id="pref-low"
                    type="checkbox"
                    className="form-check-input"
                    checked={preferences.notify_low_attendance}
                    onChange={(e) =>
                      setPreferences((prev) =>
                        prev ? { ...prev, notify_low_attendance: e.target.checked } : prev
                      )
                    }
                  />
                  <label className="form-check-label" htmlFor="pref-low">
                    Low attendance alerts
                  </label>
                </div>
                <div className="form-check mb-3">
                  <input
                    id="pref-security"
                    type="checkbox"
                    className="form-check-input"
                    checked={preferences.notify_account_security}
                    onChange={(e) =>
                      setPreferences((prev) =>
                        prev ? { ...prev, notify_account_security: e.target.checked } : prev
                      )
                    }
                  />
                  <label className="form-check-label" htmlFor="pref-security">
                    Security alerts
                  </label>
                </div>
                <button className="btn btn-primary" onClick={savePreferences} disabled={saving}>
                  {saving ? "Saving..." : "Save Preferences"}
                </button>
              </>
            )}
          </div>
        </div>

        {!isStudentView ? (
          <div className="card mb-4 shadow-sm border-0">
            <div className="card-header bg-white">Dispatch Actions</div>
            <div className="card-body d-flex flex-wrap gap-2">
              <button className="btn btn-outline-primary" onClick={() => runAction(() => sendTestNotification())}>
                Send Test
              </button>
              <button
                className="btn btn-outline-secondary"
                onClick={() => runAction(() => dispatchEventReminderNotifications({ lead_hours: 24 }))}
              >
                Run Event Reminders
              </button>
              <button
                className="btn btn-outline-warning"
                onClick={() => runAction(() => dispatchMissedEventsNotifications({ lookback_days: 14 }))}
              >
                Run Missed Events
              </button>
              <button
                className="btn btn-outline-danger"
                onClick={() => runAction(() => dispatchLowAttendanceNotifications({ threshold_percent: 75 }))}
              >
                Run Low Attendance
              </button>
            </div>
          </div>
        ) : null}

        <div className="card shadow-sm border-0">
          <div className="card-header bg-white">
            {isStudentView ? "Recent Activity" : "Recent Notification Logs"}
          </div>
          <div className="table-responsive">
            <table className="table table-sm table-striped mb-0">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Channel</th>
                  <th>Status</th>
                  {!isStudentView ? <th>User</th> : null}
                  <th>Created</th>
                  <th>Subject</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.category}</td>
                    <td>{log.channel}</td>
                    <td>{log.status}</td>
                    {!isStudentView ? <td>{log.user_id ?? "-"}</td> : null}
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td>
                      <div>{log.subject}</div>
                      <small className="text-muted">{log.message}</small>
                    </td>
                  </tr>
                ))}
                {!loading && logs.length === 0 && (
                  <tr>
                    <td colSpan={isStudentView ? 5 : 6} className="text-center py-4">
                      No notifications yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
};

export default NotificationCenter;
