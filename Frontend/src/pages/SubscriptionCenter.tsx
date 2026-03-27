import { FormEvent, useEffect, useState } from "react";

import NavbarAdmin from "../components/NavbarAdmin";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import {
  fetchSubscription,
  runSubscriptionReminders,
  SubscriptionSettings,
  updateSubscription,
} from "../api/platformOpsApi";
import {
  isStoredCampusAdmin,
  isStoredPlatformAdmin,
  readStoredUserSession,
} from "../lib/auth/storedUser";

const SubscriptionCenter = () => {
  const stored = readStoredUserSession();
  const isSchoolIT = isStoredCampusAdmin();
  const isPlatformAdmin = isStoredPlatformAdmin();
  const NavbarComponent = isSchoolIT ? NavbarSchoolIT : NavbarAdmin;

  const [schoolId, setSchoolId] = useState<string>(stored?.schoolId ? String(stored.schoolId) : "");
  const [data, setData] = useState<SubscriptionSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const parsedSchoolId = schoolId ? Number(schoolId) : undefined;
      const result = await fetchSubscription(parsedSchoolId);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load subscription");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!data) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const parsedSchoolId = schoolId ? Number(schoolId) : undefined;
      const updated = await updateSubscription(
        {
          plan_name: data.plan_name,
          user_limit: data.user_limit,
          event_limit_monthly: data.event_limit_monthly,
          import_limit_monthly: data.import_limit_monthly,
          renewal_date: data.renewal_date || null,
          auto_renew: data.auto_renew,
          reminder_days_before: data.reminder_days_before,
        },
        parsedSchoolId
      );
      setData(updated);
      setSuccess("Subscription settings updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update subscription");
    } finally {
      setSaving(false);
    }
  };

  const runReminders = async () => {
    setError(null);
    setSuccess(null);
    try {
      const parsedSchoolId = schoolId ? Number(schoolId) : undefined;
      const result = await runSubscriptionReminders(parsedSchoolId);
      setSuccess(
        `Checked ${result.schools_checked}, created ${result.reminders_created}, sent ${result.reminders_sent}.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run reminders");
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f8f9fa" }}>
      <NavbarComponent />
      <main className="container py-4">
        <h2 className="mb-3">Subscription & Usage</h2>
        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {isPlatformAdmin && (
          <div className="card mb-3">
            <div className="card-body d-flex gap-2 align-items-center">
              <label className="form-label mb-0">School ID</label>
              <input
                className="form-control"
                style={{ maxWidth: 180 }}
                value={schoolId}
                onChange={(e) => setSchoolId(e.target.value)}
              />
              <button className="btn btn-outline-primary" onClick={load}>
                Load
              </button>
            </div>
          </div>
        )}

        {!data || loading ? (
          <div className="card">
            <div className="card-body">Loading...</div>
          </div>
        ) : (
          <>
            <div className="row g-3 mb-3">
              <div className="col-md-4">
                <div className="card h-100">
                  <div className="card-body">
                    <h6 className="card-title">Users</h6>
                    <p className="mb-1">
                      {data.metrics.user_count} / {data.metrics.user_limit}
                    </p>
                    <div className="progress">
                      <div
                        className="progress-bar"
                        style={{ width: `${Math.min(data.metrics.user_usage_percent, 100)}%` }}
                      >
                        {data.metrics.user_usage_percent}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="col-md-4">
                <div className="card h-100">
                  <div className="card-body">
                    <h6 className="card-title">Events (This Month)</h6>
                    <p className="mb-1">
                      {data.metrics.event_count_current_month} / {data.metrics.event_limit_monthly}
                    </p>
                    <div className="progress">
                      <div
                        className="progress-bar bg-warning"
                        style={{ width: `${Math.min(data.metrics.event_usage_percent, 100)}%` }}
                      >
                        {data.metrics.event_usage_percent}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="col-md-4">
                <div className="card h-100">
                  <div className="card-body">
                    <h6 className="card-title">Imports (This Month)</h6>
                    <p className="mb-1">
                      {data.metrics.import_count_current_month} / {data.metrics.import_limit_monthly}
                    </p>
                    <div className="progress">
                      <div
                        className="progress-bar bg-info"
                        style={{ width: `${Math.min(data.metrics.import_usage_percent, 100)}%` }}
                      >
                        {data.metrics.import_usage_percent}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <form className="card" onSubmit={onSubmit}>
              <div className="card-header">Subscription Settings</div>
              <div className="card-body row g-3">
                <div className="col-md-4">
                  <label className="form-label">Plan Name</label>
                  <input
                    className="form-control"
                    value={data.plan_name}
                    onChange={(e) => setData((prev) => (prev ? { ...prev, plan_name: e.target.value } : prev))}
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label">User Limit</label>
                  <input
                    type="number"
                    className="form-control"
                    value={data.user_limit}
                    onChange={(e) =>
                      setData((prev) => (prev ? { ...prev, user_limit: Number(e.target.value) || 1 } : prev))
                    }
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label">Event Limit / Month</label>
                  <input
                    type="number"
                    className="form-control"
                    value={data.event_limit_monthly}
                    onChange={(e) =>
                      setData((prev) =>
                        prev ? { ...prev, event_limit_monthly: Number(e.target.value) || 1 } : prev
                      )
                    }
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label">Import Limit / Month</label>
                  <input
                    type="number"
                    className="form-control"
                    value={data.import_limit_monthly}
                    onChange={(e) =>
                      setData((prev) =>
                        prev ? { ...prev, import_limit_monthly: Number(e.target.value) || 1 } : prev
                      )
                    }
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label">Renewal Date</label>
                  <input
                    type="date"
                    className="form-control"
                    value={data.renewal_date ? data.renewal_date.substring(0, 10) : ""}
                    onChange={(e) =>
                      setData((prev) => (prev ? { ...prev, renewal_date: e.target.value || null } : prev))
                    }
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label">Reminder Days Before</label>
                  <input
                    type="number"
                    className="form-control"
                    value={data.reminder_days_before}
                    onChange={(e) =>
                      setData((prev) =>
                        prev ? { ...prev, reminder_days_before: Number(e.target.value) || 1 } : prev
                      )
                    }
                  />
                </div>
                <div className="col-12">
                  <div className="form-check">
                    <input
                      id="auto-renew"
                      type="checkbox"
                      className="form-check-input"
                      checked={data.auto_renew}
                      onChange={(e) => setData((prev) => (prev ? { ...prev, auto_renew: e.target.checked } : prev))}
                    />
                    <label htmlFor="auto-renew" className="form-check-label">
                      Auto renew
                    </label>
                  </div>
                </div>
              </div>
              <div className="card-footer d-flex gap-2">
                <button className="btn btn-primary" type="submit" disabled={saving}>
                  {saving ? "Saving..." : "Save Settings"}
                </button>
                <button className="btn btn-outline-warning" type="button" onClick={runReminders}>
                  Run Renewal Reminders
                </button>
              </div>
            </form>
          </>
        )}
      </main>
    </div>
  );
};

export default SubscriptionCenter;
