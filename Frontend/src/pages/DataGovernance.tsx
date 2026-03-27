import { FormEvent, useEffect, useState } from "react";

import NavbarAdmin from "../components/NavbarAdmin";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import {
  createConsent,
  createDataRequest,
  DataRequestItem,
  fetchDataRequests,
  fetchGovernanceSettings,
  fetchMyConsents,
  GovernanceSettings,
  runRetentionCleanup,
  updateDataRequestStatus,
  updateGovernanceSettings,
} from "../api/platformOpsApi";
import { isStoredCampusAdmin, readStoredUserSession } from "../lib/auth/storedUser";
import { hasAnyRole } from "../utils/roleUtils";

const DataGovernance = () => {
  const roles = readStoredUserSession()?.roles ?? [];
  const isSchoolIT = isStoredCampusAdmin();
  const isPrivileged = hasAnyRole(roles, "admin", "campus_admin");
  const NavbarComponent = isSchoolIT ? NavbarSchoolIT : NavbarAdmin;

  const [settings, setSettings] = useState<GovernanceSettings | null>(null);
  const [requests, setRequests] = useState<DataRequestItem[]>([]);
  const [consentsCount, setConsentsCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState(true);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsData, requestsData, consentsData] = await Promise.all([
        fetchGovernanceSettings(),
        fetchDataRequests({ limit: 100 }),
        fetchMyConsents(),
      ]);
      setSettings(settingsData);
      setRequests(requestsData);
      setConsentsCount(consentsData.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load governance data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const saveSettings = async (event: FormEvent) => {
    event.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await updateGovernanceSettings({
        attendance_retention_days: settings.attendance_retention_days,
        audit_log_retention_days: settings.audit_log_retention_days,
        import_file_retention_days: settings.import_file_retention_days,
        auto_delete_enabled: settings.auto_delete_enabled,
      });
      setSettings(updated);
      setSuccess("Governance settings updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update governance settings");
    } finally {
      setSaving(false);
    }
  };

  const submitDataRequest = async (type: "export" | "delete") => {
    setError(null);
    setSuccess(null);
    try {
      await createDataRequest({
        request_type: type,
        reason: type === "export" ? "User requested data export" : "User requested account deletion",
      });
      setSuccess(`${type.toUpperCase()} request created.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create request");
    }
  };

  const addConsent = async () => {
    setError(null);
    try {
      await createConsent({
        consent_type: "facial_recognition",
        consent_granted: true,
        consent_version: "v1",
        source: "web",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add consent");
    }
  };

  const runRetention = async () => {
    setError(null);
    setSuccess(null);
    try {
      const result = await runRetentionCleanup({ dry_run: dryRun });
      setSuccess(result.summary);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run retention");
    }
  };

  const updateRequestStatus = async (requestId: number, status: "approved" | "rejected" | "completed") => {
    setError(null);
    try {
      await updateDataRequestStatus(requestId, { status });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update request");
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f8f9fa" }}>
      <NavbarComponent />
      <main className="container py-4">
        <h2 className="mb-3">Data Governance</h2>
        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <div className="card mb-3">
          <div className="card-header">Privacy & Data Requests</div>
          <div className="card-body d-flex flex-wrap gap-2">
            <button className="btn btn-outline-primary" onClick={() => submitDataRequest("export")}>
              Request My Data Export
            </button>
            <button className="btn btn-outline-danger" onClick={() => submitDataRequest("delete")}>
              Request My Data Deletion
            </button>
            <button className="btn btn-outline-secondary" onClick={addConsent}>
              Add Consent Record
            </button>
            <span className="badge bg-light text-dark align-self-center">My consents: {consentsCount}</span>
          </div>
        </div>

        {!settings || loading ? (
          <div className="card mb-3">
            <div className="card-body">Loading governance settings...</div>
          </div>
        ) : (
          <form className="card mb-3" onSubmit={saveSettings}>
            <div className="card-header">Retention Settings</div>
            <div className="card-body row g-3">
              <div className="col-md-4">
                <label className="form-label">Attendance Retention (days)</label>
                <input
                  type="number"
                  className="form-control"
                  value={settings.attendance_retention_days}
                  onChange={(e) =>
                    setSettings((prev) =>
                      prev ? { ...prev, attendance_retention_days: Number(e.target.value) || 30 } : prev
                    )
                  }
                />
              </div>
              <div className="col-md-4">
                <label className="form-label">Audit Log Retention (days)</label>
                <input
                  type="number"
                  className="form-control"
                  value={settings.audit_log_retention_days}
                  onChange={(e) =>
                    setSettings((prev) =>
                      prev ? { ...prev, audit_log_retention_days: Number(e.target.value) || 90 } : prev
                    )
                  }
                />
              </div>
              <div className="col-md-4">
                <label className="form-label">Import File Retention (days)</label>
                <input
                  type="number"
                  className="form-control"
                  value={settings.import_file_retention_days}
                  onChange={(e) =>
                    setSettings((prev) =>
                      prev ? { ...prev, import_file_retention_days: Number(e.target.value) || 7 } : prev
                    )
                  }
                />
              </div>
              <div className="col-12">
                <div className="form-check">
                  <input
                    type="checkbox"
                    className="form-check-input"
                    id="autoDeleteEnabled"
                    checked={settings.auto_delete_enabled}
                    onChange={(e) =>
                      setSettings((prev) => (prev ? { ...prev, auto_delete_enabled: e.target.checked } : prev))
                    }
                  />
                  <label className="form-check-label" htmlFor="autoDeleteEnabled">
                    Enable non-dry-run auto cleanup
                  </label>
                </div>
              </div>
            </div>
            <div className="card-footer d-flex gap-2">
              <button className="btn btn-primary" type="submit" disabled={saving}>
                {saving ? "Saving..." : "Save Settings"}
              </button>
              <div className="form-check align-self-center ms-2">
                <input
                  id="dryRun"
                  type="checkbox"
                  className="form-check-input"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                />
                <label className="form-check-label" htmlFor="dryRun">
                  Dry run
                </label>
              </div>
              <button type="button" className="btn btn-outline-warning" onClick={runRetention}>
                Run Retention
              </button>
            </div>
          </form>
        )}

        <div className="card">
          <div className="card-header">Data Requests</div>
          <div className="table-responsive">
            <table className="table table-sm table-striped mb-0">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Requested By</th>
                  <th>Target User</th>
                  <th>Created</th>
                  <th>Output</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {requests.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.request_type}</td>
                    <td>{item.status}</td>
                    <td>{item.requested_by_user_id ?? "-"}</td>
                    <td>{item.target_user_id ?? "-"}</td>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                    <td>{item.output_path || "-"}</td>
                    <td>
                      {isPrivileged && item.status === "pending" && (
                        <div className="d-flex gap-1">
                          <button
                            className="btn btn-sm btn-outline-success"
                            onClick={() => updateRequestStatus(item.id, "approved")}
                          >
                            Approve
                          </button>
                          <button
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => updateRequestStatus(item.id, "rejected")}
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {!loading && requests.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center py-4">
                      No data requests.
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

export default DataGovernance;
