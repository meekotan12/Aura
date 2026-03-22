import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  consumeAuthStatusMessage,
  clearPendingFaceAuthSession,
  login,
  persistAuthSession,
  requestForgotPassword,
  storePendingFaceAuthSession,
  verifyMfaChallenge,
  type AuthSession,
} from "../api/authApi";
import {
  buildBrandingFromAuthSession,
  getRequiredFaceVerificationRole,
  resolvePostAuthenticationPath,
  syncRememberedEmail,
} from "../authFlow";
import { primeGovernanceAccessCache } from "../hooks/useGovernanceAccess";
import { useUser } from "../context/UserContext";
import { FaUser, FaLock, FaEnvelope, FaEye, FaEyeSlash } from "react-icons/fa";

const getErrorMessage = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback;

const LoginForm = () => {
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [rememberMe, setRememberMe] = useState<boolean>(false);
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showForgotPassword, setShowForgotPassword] = useState<boolean>(false);
  const [forgotEmail, setForgotEmail] = useState<string>("");
  const [forgotSubmitting, setForgotSubmitting] = useState<boolean>(false);
  const [forgotMessage, setForgotMessage] = useState<string | null>(null);
  const [forgotError, setForgotError] = useState<string | null>(null);
  const [mfaChallengeId, setMfaChallengeId] = useState<string | null>(null);
  const [mfaEmail, setMfaEmail] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState<string>("");
  const [mfaPending, setMfaPending] = useState<boolean>(false);
  const [mfaSubmitting, setMfaSubmitting] = useState<boolean>(false);
  const [mfaExpiresAt, setMfaExpiresAt] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { setBranding } = useUser();

  useEffect(() => {
    const pendingAuthStatus = consumeAuthStatusMessage();
    if (pendingAuthStatus) {
      setAuthError(pendingAuthStatus);
    }

    const savedEmail = localStorage.getItem("rememberedEmail");
    if (savedEmail) {
      setEmail(savedEmail);
      setRememberMe(true);
    }
  }, []);

  const completeLogin = async (session: AuthSession) => {
    if (!session.token || !session.roles) {
      throw new Error("Invalid response from server.");
    }

    persistAuthSession(session);
    setBranding(buildBrandingFromAuthSession(session));
    syncRememberedEmail(session.email || email, rememberMe);
    await primeGovernanceAccessCache(true);
    const nextPath = await resolvePostAuthenticationPath({
      roles: session.roles || [],
      mustChangePassword: session.mustChangePassword,
      authToken: session.token,
      userId: session.id ?? null,
    });

    navigate(nextPath);
  };

  const continueLoginFlow = async (session: AuthSession) => {
    const faceRole = getRequiredFaceVerificationRole(session.roles || []);
    const requiresFaceVerification =
      session.faceVerificationRequired || faceRole !== null;

    if (!requiresFaceVerification || !faceRole) {
      await completeLogin(session);
      return;
    }

    storePendingFaceAuthSession({
      session,
      rememberMe,
      faceRole,
    });
    navigate("/auth/face-verification", { replace: true });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsLoading(true);
    setAuthError(null);
    clearPendingFaceAuthSession();

    try {
      const userData = await login(email, password);
      if (userData.mfaRequired) {
        setMfaPending(true);
        setMfaChallengeId(userData.mfaChallengeId || null);
        setMfaEmail(userData.email || email);
        setMfaExpiresAt(userData.mfaExpiresAt || null);
        setMfaCode("");
        return;
      }
      await continueLoginFlow(userData);
    } catch (error) {
      setAuthError(getErrorMessage(error, "Login failed! Please check your credentials."));
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyMfa = async () => {
    if (!mfaChallengeId || !mfaEmail) {
      alert("MFA challenge is missing. Please log in again.");
      setMfaPending(false);
      return;
    }
    if (!mfaCode.trim()) {
      alert("Enter your MFA code.");
      return;
    }
    setMfaSubmitting(true);
    try {
      const userData = await verifyMfaChallenge(mfaEmail, mfaChallengeId, mfaCode.trim());
      setMfaPending(false);
      setMfaChallengeId(null);
      setMfaEmail(null);
      setMfaCode("");
      await continueLoginFlow(userData);
    } catch (error) {
      alert(getErrorMessage(error, "Failed to verify MFA code."));
    } finally {
      setMfaSubmitting(false);
    }
  };

  const handleForgotPasswordSubmit = async () => {
    setForgotSubmitting(true);
    setForgotError(null);
    setForgotMessage(null);

    try {
      const targetEmail = forgotEmail.trim();
      if (!targetEmail) {
        throw new Error("Please enter your email.");
      }
      const message = await requestForgotPassword(targetEmail);
      setForgotMessage(message);
    } catch (error) {
      setForgotError(getErrorMessage(error, "Failed to submit forgot password request."));
    } finally {
      setForgotSubmitting(false);
    }
  };

  return (
    <div className="login-form-container">
      <h4 className="user-login-title">
        <FaUser className="user-icon" /> User Login
      </h4>

      {authError && <p className="forgot-password-error">{authError}</p>}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">
            <FaEnvelope className="input-icon" /> Email
          </label>
          <input
            type="email"
            className="form-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="Enter your email address"
            minLength={2}
            maxLength={50}
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            <FaLock className="input-icon" /> Password
          </label>
          <div className="password-input-container">
            <input
              type={showPassword ? "text" : "password"}
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
              minLength={8}
              maxLength={255}
            />
            <button
              type="button"
              className="toggle-password"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <FaEyeSlash /> : <FaEye />}
            </button>
          </div>
        </div>

        <div className="form-options">
          <div className="remember-me">
            <input
              type="checkbox"
              id="rememberMe"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
            />
            <label htmlFor="rememberMe">Remember me</label>
          </div>
          <button
            type="button"
            className="forgot-password"
            onClick={() => {
              setShowForgotPassword((prev) => !prev);
              setForgotEmail((prev) => (prev ? prev : email));
              setForgotError(null);
              setForgotMessage(null);
            }}
          >
            Forgot password?
          </button>
        </div>

        {showForgotPassword && (
          <div className="forgot-password-panel">
            <label className="form-label mb-2">Reset Password Request</label>
            <input
              type="email"
              className="form-input"
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
              placeholder="Enter your account email"
              required
            />
            <button
              type="button"
              className="forgot-password-submit"
              onClick={handleForgotPasswordSubmit}
              disabled={forgotSubmitting}
            >
              {forgotSubmitting ? "Submitting..." : "Submit Request"}
            </button>
            {forgotMessage && <p className="forgot-password-message">{forgotMessage}</p>}
            {forgotError && <p className="forgot-password-error">{forgotError}</p>}
          </div>
        )}

        {mfaPending && (
          <div className="forgot-password-panel">
            <label className="form-label mb-2">Multi-Factor Verification</label>
            <p style={{ marginBottom: 8 }}>
              Enter the 6-digit code sent to <strong>{mfaEmail}</strong>.
            </p>
            {mfaExpiresAt && <p style={{ marginBottom: 8 }}>Code expires at: {mfaExpiresAt}</p>}
            <input
              type="text"
              className="form-input"
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value)}
              placeholder="Enter MFA code"
              maxLength={12}
            />
            <button
              type="button"
              className="forgot-password-submit"
              onClick={handleVerifyMfa}
              disabled={mfaSubmitting}
            >
              {mfaSubmitting ? "Verifying..." : "Verify Code"}
            </button>
          </div>
        )}

        <button
          type="submit"
          className="login-button"
          disabled={isLoading}
        >
          {isLoading ? <span className="spinner"></span> : "Login"}
        </button>
      </form>
    </div>
  );
};

export default LoginForm;
