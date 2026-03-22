import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { changePassword, logout } from "../api/authApi";
import { resolvePostAuthenticationPath } from "../authFlow";
import { primeGovernanceAccessCache } from "../hooks/useGovernanceAccess";

const hasStrongPassword = (password: string): boolean =>
  /[A-Z]/.test(password) && /[a-z]/.test(password) && /[0-9]/.test(password);

const ChangePassword = () => {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const token =
    localStorage.getItem("authToken") ||
    localStorage.getItem("token") ||
    localStorage.getItem("access_token");

  const storedUser = useMemo(() => {
    const raw = localStorage.getItem("user");
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }, []);

  const resolveNextPath = async (
    roles: string[],
    authToken: string | null,
    userId: number | null
  ) => {
    await primeGovernanceAccessCache(true);
    return resolvePostAuthenticationPath({
      roles,
      mustChangePassword: false,
      authToken,
      userId,
    });
  };

  useEffect(() => {
    if (!token || !storedUser) {
      navigate("/", { replace: true });
      return;
    }
    const needsPasswordChange = Boolean(storedUser.mustChangePassword || storedUser.must_change_password);
    if (!needsPasswordChange) {
      let cancelled = false;
      const redirectToResolvedPath = async () => {
        const nextPath = await resolveNextPath(
          storedUser.roles || [],
          token,
          typeof storedUser.id === "number" ? storedUser.id : null
        );
        if (!cancelled) {
          navigate(nextPath, { replace: true });
        }
      };

      void redirectToResolvedPath();
      return () => {
        cancelled = true;
      };
    }
  }, [navigate, storedUser, token]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!currentPassword || !newPassword || !confirmPassword) {
      setError("All fields are required.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }

    if (!hasStrongPassword(newPassword)) {
      setError("New password must include uppercase, lowercase, and a number.");
      return;
    }

    if (!(storedUser?.mustChangePassword || storedUser?.must_change_password)) {
      const nextPath = await resolveNextPath(
        storedUser?.roles || [],
        token,
        typeof storedUser?.id === "number" ? storedUser.id : null
      );
      navigate(nextPath, { replace: true });
      return;
    }

    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);

      const updatedUser = {
        ...storedUser,
        mustChangePassword: false,
        must_change_password: false,
      };
      localStorage.setItem("user", JSON.stringify(updatedUser));

      setSuccess("Password changed successfully. Redirecting...");
      window.setTimeout(async () => {
        const nextPath = await resolveNextPath(
          updatedUser.roles || [],
          token,
          typeof updatedUser.id === "number" ? updatedUser.id : null
        );
        navigate(nextPath, { replace: true });
      }, 700);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="container py-5" style={{ maxWidth: 520 }}>
      <div className="card shadow-sm border-0">
        <div className="card-body">
          <h4 className="mb-3">Change Password</h4>
          <p className="text-muted mb-4">
            You must change your temporary password before accessing the dashboard.
          </p>

          {error && <div className="alert alert-danger">{error}</div>}
          {success && <div className="alert alert-success">{success}</div>}

          <form onSubmit={handleSubmit}>
            <div className="mb-3">
              <label className="form-label">Current Password</label>
              <input
                type="password"
                className="form-control"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </div>

            <div className="mb-3">
              <label className="form-label">New Password</label>
              <input
                type="password"
                className="form-control"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </div>

            <div className="mb-4">
              <label className="form-label">Confirm New Password</label>
              <input
                type="password"
                className="form-control"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>

            <div className="d-flex gap-2">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
                style={{
                  backgroundColor: "var(--primary-color, #162F65)",
                  borderColor: "var(--primary-color, #162F65)",
                }}
              >
                {loading ? "Updating..." : "Update Password"}
              </button>
              <button type="button" className="btn btn-outline-secondary" onClick={handleLogout}>
                Logout
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ChangePassword;
