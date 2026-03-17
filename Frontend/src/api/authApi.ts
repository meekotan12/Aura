import type { FacialVerificationRole } from "./facialVerificationApi";
import type { UpdateEventPayload } from "./eventsApi";
import { applyTheme, clearBranding, saveTheme } from "./schoolSettingsApi";
import { clearStudentFaceEnrollmentState } from "./studentFaceEnrollmentApi";
import { clearGovernanceAccessCache } from "../hooks/useGovernanceAccess";
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const PENDING_FACE_AUTH_KEY = "valid8.pendingFaceAuth";
const PENDING_FACE_AUTH_TTL_MS = 15 * 60 * 1000;
export const INACTIVE_SCHOOL_DETAIL = "This account's school is inactive.";
const AUTH_STATUS_MESSAGE_KEY = "valid8.authStatusMessage";

let authRedirectInProgress = false;

const normalizeRoles = (roles: unknown): string[] => {
  if (!Array.isArray(roles)) return [];
  return roles
    .map((role) => (typeof role === "string" ? role.trim() : ""))
    .filter((role) => role.length > 0);
};

const getStoredToken = () =>
  localStorage.getItem("authToken") ||
  localStorage.getItem("token") ||
  localStorage.getItem("access_token");

const extractDetailMessage = (payload: unknown): string | null => {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const detail = (payload as { detail?: unknown }).detail;
  return typeof detail === "string" && detail.trim().length > 0 ? detail : null;
};

const authHeaders = () => {
  const token = getStoredToken();
  if (!token) {
    throw new Error("No authentication token found");
  }
  return { Authorization: `Bearer ${token}` };
};

interface AuthResponseBody {
  access_token?: string | null;
  token_type?: string;
  email?: string;
  roles?: string[];
  user_id?: number;
  first_name?: string;
  last_name?: string;
  school_id?: number | null;
  school_name?: string | null;
  school_code?: string | null;
  logo_url?: string | null;
  primary_color?: string | null;
  secondary_color?: string | null;
  accent_color?: string | null;
  must_change_password?: boolean;
  mfa_required?: boolean;
  mfa_challenge_id?: string;
  mfa_expires_at?: string;
  session_id?: string;
  face_verification_required?: boolean;
  face_reference_enrolled?: boolean;
  face_verification_pending?: boolean;
}

export interface AuthSession {
  token: string | null;
  tokenType: string;
  email: string | null;
  roles: string[];
  id?: number;
  firstName?: string;
  lastName?: string;
  schoolId: number | null;
  schoolName: string | null;
  schoolCode: string | null;
  logoUrl: string | null;
  primaryColor: string | null;
  secondaryColor: string | null;
  accentColor: string | null;
  mustChangePassword: boolean;
  sessionId: string | null;
  mfaRequired: boolean;
  mfaChallengeId: string | null;
  mfaExpiresAt: string | null;
  faceVerificationRequired: boolean;
  faceReferenceEnrolled: boolean;
  faceVerificationPending: boolean;
}

export interface PendingFaceAuthSession {
  session: AuthSession;
  rememberMe: boolean;
  faceRole: FacialVerificationRole;
  savedAt: string;
}

const normalizeAuthSession = (
  data: AuthResponseBody,
  fallbackEmail?: string
): AuthSession => {
  const normalizedRoles = normalizeRoles(data.roles);
  return {
    token: data.access_token ?? null,
    tokenType: data.token_type ?? (data.mfa_required ? "mfa" : "bearer"),
    email: data.email ?? fallbackEmail ?? null,
    roles: normalizedRoles,
    id: data.user_id,
    firstName: data.first_name,
    lastName: data.last_name,
    schoolId: data.school_id ?? null,
    schoolName: data.school_name ?? null,
    schoolCode: data.school_code ?? null,
    logoUrl: data.logo_url ?? null,
    primaryColor: data.primary_color ?? null,
    secondaryColor: data.secondary_color ?? null,
    accentColor: data.accent_color ?? null,
    mustChangePassword: Boolean(data.must_change_password),
    sessionId: data.session_id ?? null,
    mfaRequired: Boolean(data.mfa_required),
    mfaChallengeId: data.mfa_challenge_id ?? null,
    mfaExpiresAt: data.mfa_expires_at ?? null,
    faceVerificationRequired: Boolean(data.face_verification_required),
    faceReferenceEnrolled: Boolean(data.face_reference_enrolled),
    faceVerificationPending: Boolean(data.face_verification_pending),
  };
};

const persistUserData = (session: AuthSession) => {
  localStorage.setItem("userData", JSON.stringify({
    email: session.email,
    roles: session.roles,
    id: session.id,
    firstName: session.firstName,
    lastName: session.lastName,
    schoolId: session.schoolId,
    schoolName: session.schoolName,
    schoolCode: session.schoolCode,
    logoUrl: session.logoUrl,
    mustChangePassword: session.mustChangePassword,
    sessionId: session.sessionId,
    faceVerificationRequired: session.faceVerificationRequired,
    faceReferenceEnrolled: session.faceReferenceEnrolled,
  }));
};

export const clearPendingFaceAuthSession = () => {
  sessionStorage.removeItem(PENDING_FACE_AUTH_KEY);
};

export const storePendingFaceAuthSession = (
  pendingSession: Omit<PendingFaceAuthSession, "savedAt">
) => {
  sessionStorage.setItem(PENDING_FACE_AUTH_KEY, JSON.stringify({
    ...pendingSession,
    savedAt: new Date().toISOString(),
  }));
};

export const getPendingFaceAuthSession = (): PendingFaceAuthSession | null => {
  const raw = sessionStorage.getItem(PENDING_FACE_AUTH_KEY);
  if (!raw) {
    return null;
  }

  try {
    const pending = JSON.parse(raw) as PendingFaceAuthSession;
    const savedAt = Date.parse(pending.savedAt);
    if (!Number.isFinite(savedAt) || Date.now() - savedAt > PENDING_FACE_AUTH_TTL_MS) {
      clearPendingFaceAuthSession();
      return null;
    }
    return pending;
  } catch {
    clearPendingFaceAuthSession();
    return null;
  }
};

export const persistAuthSession = (session: AuthSession) => {
  if (!session.token) {
    throw new Error("Authentication token was not returned.");
  }
  if (session.faceVerificationPending || session.tokenType === "face_pending") {
    throw new Error("Face verification is still pending for this session.");
  }

  localStorage.setItem("authToken", session.token);
  localStorage.setItem("token", session.token);
  localStorage.setItem("access_token", session.token);
  localStorage.setItem("user", JSON.stringify(session));
  persistUserData(session);
  clearGovernanceAccessCache();

  if (session.primaryColor) {
    const theme = {
      primary_color: session.primaryColor,
      secondary_color: session.secondaryColor ?? session.primaryColor,
    };
    applyTheme(theme);
    saveTheme(theme);
  }

  clearPendingFaceAuthSession();
  return session;
};

export const login = async (email: string, password: string) => {
  try {
    // Trim inputs
    email = email.trim();
    password = password.trim();

    const response = await fetch(`${BASE_URL}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Incorrect email or password');
      }
      const body = (await response.json().catch(() => null)) as unknown;
      throw new Error(
        extractDetailMessage(body) ?? `Network error: ${response.status}`
      );
    }

    const data = (await response.json()) as AuthResponseBody;
    return normalizeAuthSession(data, email);
  } catch (error) {
    console.error('Login error:', error);
    throw new Error(
      error instanceof Error ? error.message : 'Authentication failed'
    );
  }
};

export const verifyMfaChallenge = async (
  email: string,
  challengeId: string,
  code: string
) => {
  const response = await fetch(`${BASE_URL}/auth/mfa/verify`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: email.trim(),
      challenge_id: challengeId,
      code: code.trim(),
    }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body?.detail === "string" ? body.detail : "Failed to verify MFA code"
    );
  }

  return normalizeAuthSession(body as AuthResponseBody, email);
};

// Add this helper function to get the token
export const getAuthToken = () => {
  return getStoredToken();
};

// Add this function to clear auth data
export const logout = () => {
  localStorage.removeItem('authToken');
  localStorage.removeItem('access_token');
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  localStorage.removeItem('userData');
  clearGovernanceAccessCache();
  clearPendingFaceAuthSession();
  clearStudentFaceEnrollmentState();
  clearBranding();
};

export const handleInactiveSchoolSession = (detail: unknown): boolean => {
  if (detail !== INACTIVE_SCHOOL_DETAIL || !getStoredToken()) {
    return false;
  }

  if (authRedirectInProgress) {
    return true;
  }

  authRedirectInProgress = true;
  sessionStorage.setItem(AUTH_STATUS_MESSAGE_KEY, INACTIVE_SCHOOL_DETAIL);
  logout();
  window.location.replace("/login");
  return true;
};

export const consumeAuthStatusMessage = (): string | null => {
  const message = sessionStorage.getItem(AUTH_STATUS_MESSAGE_KEY);
  if (!message) {
    return null;
  }

  sessionStorage.removeItem(AUTH_STATUS_MESSAGE_KEY);
  authRedirectInProgress = false;
  return message;
};

export const changePassword = async (currentPassword: string, newPassword: string) => {
  const response = await fetch(`${BASE_URL}/auth/change-password`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (typeof body?.detail === "string") {
      throw new Error(body.detail);
    }
    throw new Error("Failed to change password");
  }

  try {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      const parsed = JSON.parse(storedUser);
      parsed.mustChangePassword = false;
      localStorage.setItem("user", JSON.stringify(parsed));
    }
  } catch {
    // Ignore local storage parsing errors.
  }

  try {
    const storedUserData = localStorage.getItem("userData");
    if (storedUserData) {
      const parsed = JSON.parse(storedUserData);
      parsed.mustChangePassword = false;
      localStorage.setItem("userData", JSON.stringify(parsed));
    }
  } catch {
    // Ignore local storage parsing errors.
  }

  return body;
};

export const requestForgotPassword = async (email: string): Promise<string> => {
  const response = await fetch(`${BASE_URL}/auth/forgot-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email: email.trim() }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (typeof body?.detail === "string") {
      throw new Error(body.detail);
    }
    throw new Error("Failed to submit forgot password request");
  }

  return typeof body?.message === "string"
    ? body.message
    : "If the account exists, a password reset request has been submitted.";
};

// Example of how to use the token in API calls
export const updateEvent = async (eventId: number, eventData: UpdateEventPayload) => {
  const response = await fetch(`${BASE_URL}/events/${eventId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(eventData),
  });

  if (!response.ok) {
    throw new Error(`Failed to update event: ${response.status}`);
  }

  return await response.json();
};
