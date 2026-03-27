import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import NavbarAdmin from "../components/NavbarAdmin";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import {
  fetchLoginHistory,
  fetchMfaStatus,
  fetchUserSessions,
  LoginHistoryItem,
  MfaStatus,
  revokeOtherSessions,
  revokeUserSession,
  updateMfaStatus,
  UserSessionItem,
} from "../api/platformOpsApi";
import { isStoredCampusAdmin } from "../lib/auth/storedUser";

const SecurityCenter = () => {
  const isSchoolIT = isStoredCampusAdmin();
  const NavbarComponent = isSchoolIT ? NavbarSchoolIT : NavbarAdmin;
  const facialVerificationPath = isSchoolIT
    ? "/campus_admin_face_verification"
    : "/admin_face_verification";

  const [mfa, setMfa] = useState<MfaStatus | null>(null);
  const [sessions, setSessions] = useState<UserSessionItem[]>([]);
  const [history, setHistory] = useState<LoginHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingMfa, setSavingMfa] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [mfaData, sessionsData, historyData] = await Promise.all([
        fetchMfaStatus(),
        fetchUserSessions(),
        fetchLoginHistory(100),
      ]);
      setMfa(mfaData);
      setSessions(sessionsData);
      setHistory(historyData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load security center");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggleMfa = async () => {
    if (!mfa) return;
    setSavingMfa(true);
    setError(null);
    try {
      const updated = await updateMfaStatus({ mfa_enabled: !mfa.mfa_enabled });
      setMfa(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update MFA");
    } finally {
      setSavingMfa(false);
    }
  };

  const handleRevoke = async (sessionId: string) => {
    setError(null);
    try {
      await revokeUserSession(sessionId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke session");
    }
  };

  const handleRevokeOthers = async () => {
    setError(null);
    try {
      await revokeOtherSessions();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke other sessions");
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f8f9fa" }}>
      <NavbarComponent />
      <main className="container py-4">
        <h2 className="mb-3">Security Center</h2>
        {error && <div className="alert alert-danger">{error}</div>}

        <div className="card mb-4">
          <div className="card-header">Facial Verification</div>
          <div className="card-body d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-3">
            <div>
              <div className="fw-semibold">Identity check workspace</div>
              <div className="text-muted">
                Enroll the backend reference face, run verification checks, and review the current face security status for this account.
              </div>
            </div>
            <Link to={facialVerificationPath} className="btn btn-outline-primary">
              Open Facial Verification
            </Link>
          </div>
        </div>

        <div className="card mb-4">
          <div className="card-header">Multi-Factor Authentication</div>
          <div className="card-body">
            {loading || !mfa ? (
              <p className="mb-0">Loading...</p>
            ) : (
              <div className="d-flex align-items-center justify-content-between">
                <div>
                  <div>
                    <strong>Status:</strong> {mfa.mfa_enabled ? "Enabled" : "Disabled"}
                  </div>
                  <div>
                    <strong>Trusted device days:</strong> {mfa.trusted_device_days}
                  </div>
                </div>
                <button className="btn btn-primary" onClick={toggleMfa} disabled={savingMfa}>
                  {savingMfa ? "Updating..." : mfa.mfa_enabled ? "Disable MFA" : "Enable MFA"}
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="card mb-4">
          <div className="card-header d-flex justify-content-between align-items-center">
            <span>Active Sessions</span>
            <button className="btn btn-outline-danger btn-sm" onClick={handleRevokeOthers}>
              Revoke Other Sessions
            </button>
          </div>
          <div className="table-responsive">
            <table className="table table-sm table-striped mb-0">
              <thead>
                <tr>
                  <th>Session</th>
                  <th>IP</th>
                  <th>User Agent</th>
                  <th>Created</th>
                  <th>Expires</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.id}>
                    <td>{session.id}</td>
                    <td>{session.ip_address || "-"}</td>
                    <td style={{ maxWidth: 360, wordBreak: "break-word" }}>{session.user_agent || "-"}</td>
                    <td>{new Date(session.created_at).toLocaleString()}</td>
                    <td>{new Date(session.expires_at).toLocaleString()}</td>
                    <td>{session.revoked_at ? "Revoked" : session.is_current ? "Current" : "Active"}</td>
                    <td>
                      {!session.revoked_at && !session.is_current && (
                        <button className="btn btn-sm btn-outline-danger" onClick={() => handleRevoke(session.id)}>
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {!loading && sessions.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center py-4">
                      No sessions found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-header">Login History</div>
          <div className="table-responsive">
            <table className="table table-sm table-striped mb-0">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Email</th>
                  <th>Method</th>
                  <th>Result</th>
                  <th>Reason</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {history.map((entry) => (
                  <tr key={entry.id}>
                    <td>{new Date(entry.created_at).toLocaleString()}</td>
                    <td>{entry.email_attempted}</td>
                    <td>{entry.auth_method}</td>
                    <td>{entry.success ? "Success" : "Failed"}</td>
                    <td>{entry.failure_reason || "-"}</td>
                    <td>{entry.ip_address || "-"}</td>
                  </tr>
                ))}
                {!loading && history.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-4">
                      No login history yet.
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

export default SecurityCenter;
