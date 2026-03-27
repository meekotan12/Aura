import { buildApiUrl } from "./apiUrl";
import { buildAuthHeaders as buildSharedAuthHeaders } from "../lib/api/client";
import { getStoredAuthToken } from "../lib/auth/sessionStore";

const HISTORY_LIMIT = 8;
const PROFILE_PREFIX = "valid8.face.reference";
const HISTORY_PREFIX = "valid8.face.history";

export type FacialVerificationRole = "admin" | "campus_admin";
export type PersistAttemptMode = "always" | "matched" | "never";
type ImageSource = string | Blob;

type LivenessPayload = {
  label?: string;
  score?: number;
  reason?: string;
};

type FacialVerificationRequestOptions = {
  authToken?: string | null;
};

type BackendFaceStatusResponse = {
  face_verification_required?: boolean;
  face_reference_enrolled?: boolean;
  provider?: string;
  updated_at?: string | null;
  last_verified_at?: string | null;
  liveness_enabled?: boolean;
  anti_spoof_ready?: boolean;
  anti_spoof_reason?: string | null;
  live_capture_required?: boolean;
};

type BackendFaceReferenceResponse = {
  provider?: string;
  updated_at?: string;
  liveness?: LivenessPayload;
};

type BackendFaceVerificationResponse = {
  matched?: boolean;
  distance?: number;
  confidence?: number;
  threshold?: number;
  liveness?: LivenessPayload;
  verified_at?: string | null;
  access_token?: string | null;
  token_type?: string | null;
  session_id?: string | null;
  face_verification_pending?: boolean;
};

type BackendFaceLivenessResponse = {
  label?: string;
  score?: number;
  reason?: string;
};

export class FacialVerificationApiError extends Error {
  status: number;
  detail: string;
  data: unknown;

  constructor(message: string, status: number, detail: string, data: unknown) {
    super(message);
    this.name = "FacialVerificationApiError";
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

export interface FacialVerificationStatus {
  faceVerificationRequired: boolean;
  faceReferenceEnrolled: boolean;
  provider: string;
  updatedAt: string | null;
  lastVerifiedAt: string | null;
  livenessEnabled: boolean;
  antiSpoofReady: boolean;
  antiSpoofReason: string | null;
  liveCaptureRequired: boolean;
}

export interface FacialReferenceProfile {
  role: FacialVerificationRole;
  subjectId: string;
  imageDataUrl: string;
  imageHash: string;
  createdAt: string;
  provider: string;
}

export interface FacialVerificationAttempt {
  id: string;
  role: FacialVerificationRole;
  subjectId: string;
  matched: boolean;
  similarity: number;
  distance: number | null;
  threshold: number;
  createdAt: string;
  verifiedAt: string | null;
  message: string;
  provider: string;
  liveness?: LivenessPayload;
}

export interface FacialLivenessResult {
  label: string;
  score: number;
  reason?: string;
}

export interface SaveFacialReferenceResult {
  profile: FacialReferenceProfile;
  liveness?: FacialLivenessResult;
}

interface SaveReferenceInput extends FacialVerificationRequestOptions {
  role: FacialVerificationRole;
  subjectId: string;
  imageSource: ImageSource;
}

interface ClearReferenceInput extends FacialVerificationRequestOptions {
  role: FacialVerificationRole;
  subjectId: string;
}

interface VerifyFaceInput extends FacialVerificationRequestOptions {
  role: FacialVerificationRole;
  subjectId: string;
  probeImageSource: ImageSource;
  persistAttemptMode?: PersistAttemptMode;
}

interface CheckLivenessInput extends FacialVerificationRequestOptions {
  imageSource: ImageSource;
}

export interface VerificationResult {
  attempt: FacialVerificationAttempt;
  normalizedProbeImage: string;
  authSessionPatch?: {
    accessToken: string;
    tokenType: string;
    sessionId: string | null;
    faceVerificationPending: boolean;
  };
}

const buildProfileStorageKey = (
  role: FacialVerificationRole,
  subjectId: string
) => `${PROFILE_PREFIX}:${role}:${subjectId}`;

const buildHistoryStorageKey = (
  role: FacialVerificationRole,
  subjectId: string
) => `${HISTORY_PREFIX}:${role}:${subjectId}`;

const getStoredToken = () => getStoredAuthToken();

const resolveAuthToken = (authToken?: string | null) => authToken ?? getStoredToken();

const buildAuthHeaders = (authToken?: string | null) => {
  return buildSharedAuthHeaders(resolveAuthToken(authToken), {
    "Content-Type": "application/json",
  });
};

const blobToDataUrl = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Failed to read captured camera frame."));
    reader.readAsDataURL(blob);
  });

const loadImage = (source: string) =>
  new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Failed to load image"));
    image.src = source;
  });

const normalizeImage = async (imageSource: ImageSource) => {
  const dataUrl =
    typeof imageSource === "string" ? imageSource : await blobToDataUrl(imageSource);
  const image = await loadImage(dataUrl);
  const longestSide = Math.max(image.width, image.height);
  const scale = longestSide > 640 ? 640 / longestSide : 1;
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(image.width * scale));
  canvas.height = Math.max(1, Math.round(image.height * scale));

  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Failed to prepare image canvas");
  }

  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.82);
};

const createAverageHash = async (imageDataUrl: string) => {
  const image = await loadImage(imageDataUrl);
  const canvas = document.createElement("canvas");
  canvas.width = 16;
  canvas.height = 16;

  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Failed to prepare hashing canvas");
  }

  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height).data;

  const grayscaleValues: number[] = [];
  for (let index = 0; index < imageData.length; index += 4) {
    const red = imageData[index];
    const green = imageData[index + 1];
    const blue = imageData[index + 2];
    grayscaleValues.push(red * 0.299 + green * 0.587 + blue * 0.114);
  }

  const average =
    grayscaleValues.reduce((total, value) => total + value, 0) /
    grayscaleValues.length;

  return grayscaleValues.map((value) => (value >= average ? "1" : "0")).join("");
};

const readJson = <T>(storageKey: string): T | null => {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
};

const writeJson = (storageKey: string, value: unknown) => {
  localStorage.setItem(storageKey, JSON.stringify(value));
};

const parseJson = async (response: Response) => response.json().catch(() => ({}));

const toErrorMessage = (body: unknown, fallback: string) => {
  if (!body || typeof body !== "object") {
    return fallback;
  }

  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (detail && typeof detail === "object") {
    const nestedMessage = (detail as { message?: unknown; reason?: unknown }).message;
    if (typeof nestedMessage === "string" && nestedMessage.trim()) {
      return nestedMessage;
    }

    const nestedReason = (detail as { reason?: unknown }).reason;
    if (typeof nestedReason === "string" && nestedReason.trim()) {
      return nestedReason;
    }

    return JSON.stringify(detail);
  }

  const message = (body as { message?: unknown }).message;
  if (typeof message === "string" && message.trim()) {
    return message;
  }

  return fallback;
};

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

const saveVerificationHistory = (
  role: FacialVerificationRole,
  subjectId: string,
  attempt: FacialVerificationAttempt
) => {
  const existing = listFacialVerificationHistory(role, subjectId);
  writeJson(buildHistoryStorageKey(role, subjectId), [
    attempt,
    ...existing,
  ].slice(0, HISTORY_LIMIT));
};

const shouldPersistAttempt = (
  mode: PersistAttemptMode,
  attempt: FacialVerificationAttempt
) => {
  if (mode === "never") {
    return false;
  }
  if (mode === "matched") {
    return attempt.matched;
  }
  return true;
};

const toApiError = (
  status: number,
  body: unknown,
  fallback: string
) =>
  new FacialVerificationApiError(
    toErrorMessage(body, fallback),
    status,
    toErrorMessage(body, fallback),
    body
  );

export const getFacialReferenceProfile = (
  role: FacialVerificationRole,
  subjectId: string
) => readJson<FacialReferenceProfile>(buildProfileStorageKey(role, subjectId));

export const listFacialVerificationHistory = (
  role: FacialVerificationRole,
  subjectId: string
) =>
  readJson<FacialVerificationAttempt[]>(buildHistoryStorageKey(role, subjectId)) ?? [];

export const fetchFacialVerificationStatus = async (
  options: FacialVerificationRequestOptions = {}
): Promise<FacialVerificationStatus> => {
  const response = await fetch(buildApiUrl("/api/auth/security/face-status"), {
    method: "GET",
    headers: buildAuthHeaders(options.authToken),
  });
  const body = (await parseJson(response)) as BackendFaceStatusResponse;

  if (!response.ok) {
    throw toApiError(
      response.status,
      body,
      "Failed to load face verification status."
    );
  }

  return {
    faceVerificationRequired: Boolean(body.face_verification_required),
    faceReferenceEnrolled: Boolean(body.face_reference_enrolled),
    provider: body.provider || "face_recognition",
    updatedAt: body.updated_at ?? null,
    lastVerifiedAt: body.last_verified_at ?? null,
    livenessEnabled: Boolean(body.liveness_enabled ?? true),
    antiSpoofReady: Boolean(body.anti_spoof_ready),
    antiSpoofReason: body.anti_spoof_reason ?? null,
    liveCaptureRequired: Boolean(body.live_capture_required ?? true),
  };
};

export const checkFacialLiveness = async ({
  imageSource,
  authToken,
}: CheckLivenessInput): Promise<FacialLivenessResult> => {
  const normalizedImage = await normalizeImage(imageSource);
  const response = await fetch(buildApiUrl("/api/auth/security/face-liveness"), {
    method: "POST",
    headers: buildAuthHeaders(authToken),
    body: JSON.stringify({ image_base64: normalizedImage }),
  });
  const body = (await parseJson(response)) as BackendFaceLivenessResponse;

  if (!response.ok) {
    throw toApiError(
      response.status,
      body,
      "Failed to run live liveness detection."
    );
  }

  return {
    label: body.label || "Unknown",
    score: typeof body.score === "number" ? body.score : 0,
    reason: body.reason,
  };
};

export const clearFacialReferenceProfile = async ({
  role,
  subjectId,
  authToken,
}: ClearReferenceInput) => {
  const token = resolveAuthToken(authToken);
  if (!token) {
    localStorage.removeItem(buildProfileStorageKey(role, subjectId));
    return;
  }

  const response = await fetch(buildApiUrl("/api/auth/security/face-reference"), {
    method: "DELETE",
    headers: buildAuthHeaders(token),
  });
  const body = await parseJson(response);

  if (!response.ok) {
    throw toApiError(
      response.status,
      body,
      "Failed to clear the enrolled reference face."
    );
  }

  localStorage.removeItem(buildProfileStorageKey(role, subjectId));
};

export const saveFacialReferenceProfile = async ({
  role,
  subjectId,
  imageSource,
  authToken,
}: SaveReferenceInput): Promise<SaveFacialReferenceResult> => {
  const normalizedImage = await normalizeImage(imageSource);
  const response = await fetch(buildApiUrl("/api/auth/security/face-reference"), {
    method: "POST",
    headers: buildAuthHeaders(authToken),
    body: JSON.stringify({ image_base64: normalizedImage }),
  });
  const body = (await parseJson(response)) as BackendFaceReferenceResponse;

  if (!response.ok) {
    throw toApiError(
      response.status,
      body,
      "Failed to save the enrolled reference face."
    );
  }

  const profile: FacialReferenceProfile = {
    role,
    subjectId,
    imageDataUrl: normalizedImage,
    imageHash: await createAverageHash(normalizedImage),
    createdAt: body.updated_at || new Date().toISOString(),
    provider: body.provider || "face_recognition",
  };

  writeJson(buildProfileStorageKey(role, subjectId), profile);
  return {
    profile,
    liveness:
      body.liveness && typeof body.liveness === "object"
        ? {
            label: body.liveness.label || "Unknown",
            score:
              typeof body.liveness.score === "number" ? body.liveness.score : 0,
            reason: body.liveness.reason,
          }
        : undefined,
  };
};

export const verifyFacialIdentity = async ({
  role,
  subjectId,
  probeImageSource,
  authToken,
  persistAttemptMode = "always",
}: VerifyFaceInput): Promise<VerificationResult> => {
  const normalizedProbeImage = await normalizeImage(probeImageSource);
  const response = await fetch(buildApiUrl("/api/auth/security/face-verify"), {
    method: "POST",
    headers: buildAuthHeaders(authToken),
    body: JSON.stringify({ image_base64: normalizedProbeImage }),
  });
  const body = (await parseJson(response)) as BackendFaceVerificationResponse;

  if (!response.ok) {
    throw toApiError(response.status, body, "Face verification failed.");
  }

  const matched = Boolean(body.matched);
  const confidence = clamp01(
    typeof body.confidence === "number" ? body.confidence : 0
  );
  const liveness = body.liveness;
  const attempt: FacialVerificationAttempt = {
    id: crypto.randomUUID(),
    role,
    subjectId,
    matched,
    similarity: confidence,
    distance: typeof body.distance === "number" ? body.distance : null,
    threshold: typeof body.threshold === "number" ? body.threshold : 0,
    createdAt: new Date().toISOString(),
    verifiedAt: body.verified_at ?? null,
    message: matched
      ? "Live face matched the enrolled backend reference."
      : liveness?.label === "Fake"
        ? "Liveness detection rejected the live frame."
        : "Live face did not match the enrolled backend reference.",
    provider: "face_recognition",
    liveness,
  };

  if (shouldPersistAttempt(persistAttemptMode, attempt)) {
    saveVerificationHistory(role, subjectId, attempt);
  }

  return {
    attempt,
    normalizedProbeImage,
    authSessionPatch:
      typeof body.access_token === "string" && body.access_token
        ? {
            accessToken: body.access_token,
            tokenType: body.token_type || "bearer",
            sessionId: body.session_id ?? null,
            faceVerificationPending: Boolean(body.face_verification_pending),
          }
        : undefined,
  };
};
