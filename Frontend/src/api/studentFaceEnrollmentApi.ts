import { buildApiUrl } from "./apiUrl";
import { buildAuthHeaders as buildSharedAuthHeaders } from "../lib/api/client";

const STUDENT_FACE_ENROLLMENT_KEY = "valid8.studentFaceEnrollment";

type CurrentUserProfileResponse = {
  id?: number;
  face_scan_bypass_enabled?: boolean;
  roles?: Array<{
    role?: {
      name?: string;
    };
  }>;
  student_profile?: {
    id?: number;
    student_id?: string | null;
    is_face_registered?: boolean;
    registration_complete?: boolean;
  } | null;
};

type FaceRegistrationResponse = {
  message?: string;
  student_id?: string | null;
};

type StoredEnrollmentState = {
  userId: number;
  required: boolean;
};

export interface StudentFaceEnrollmentStatus {
  userId: number | null;
  roles: string[];
  hasStudentRole: boolean;
  hasStudentProfile: boolean;
  faceRegistered: boolean;
  registrationComplete: boolean;
  studentId: string | null;
  faceScanBypassEnabled: boolean;
}

const normalizeRole = (role: string) =>
  role.trim().toLowerCase().replace(/_/g, "-");

export const hasStudentRole = (roles: string[]) =>
  roles.some((role) => normalizeRole(role) === "student");

const buildAuthHeaders = (authToken?: string | null) => {
  return buildSharedAuthHeaders(authToken, { "Content-Type": "application/json" });
};

const parseJson = async <T>(response: Response) =>
  (await response.json().catch(() => ({}))) as T;

const toErrorMessage = (body: unknown, fallback: string) => {
  if (!body || typeof body !== "object") {
    return fallback;
  }

  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (detail && typeof detail === "object") {
    return JSON.stringify(detail);
  }

  const message = (body as { message?: unknown }).message;
  if (typeof message === "string" && message.trim()) {
    return message;
  }

  return fallback;
};

const blobToDataUrl = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Failed to read the captured face image."));
    reader.readAsDataURL(blob);
  });

export const setStudentFaceEnrollmentRequired = (
  userId: number,
  required: boolean
) => {
  const payload: StoredEnrollmentState = { userId, required };
  localStorage.setItem(STUDENT_FACE_ENROLLMENT_KEY, JSON.stringify(payload));
};

export const clearStudentFaceEnrollmentState = (userId?: number | null) => {
  const raw = localStorage.getItem(STUDENT_FACE_ENROLLMENT_KEY);
  if (!raw) {
    return;
  }

  if (userId == null) {
    localStorage.removeItem(STUDENT_FACE_ENROLLMENT_KEY);
    return;
  }

  try {
    const parsed = JSON.parse(raw) as StoredEnrollmentState;
    if (parsed.userId === userId) {
      localStorage.removeItem(STUDENT_FACE_ENROLLMENT_KEY);
    }
  } catch {
    localStorage.removeItem(STUDENT_FACE_ENROLLMENT_KEY);
  }
};

export const isStudentFaceEnrollmentRequired = (userId?: number | null) => {
  const raw = localStorage.getItem(STUDENT_FACE_ENROLLMENT_KEY);
  if (!raw) {
    return false;
  }

  try {
    const parsed = JSON.parse(raw) as StoredEnrollmentState;
    return Boolean(parsed.required) && (userId == null || parsed.userId === userId);
  } catch {
    localStorage.removeItem(STUDENT_FACE_ENROLLMENT_KEY);
    return false;
  }
};

export const fetchStudentFaceEnrollmentStatus = async (
  authToken?: string | null
): Promise<StudentFaceEnrollmentStatus> => {
  const response = await fetch(buildApiUrl("/api/users/me/"), {
    method: "GET",
    headers: buildAuthHeaders(authToken),
  });
  const body = await parseJson<CurrentUserProfileResponse>(response);

  if (!response.ok) {
    throw new Error(
      toErrorMessage(body, "Failed to load the current user profile.")
    );
  }

  const roles = Array.isArray(body.roles)
    ? body.roles
        .map((item) => item?.role?.name)
        .filter((role): role is string => typeof role === "string" && role.length > 0)
    : [];
  const hasStudent = hasStudentRole(roles);
  const studentProfile = body.student_profile ?? null;

  return {
    userId: typeof body.id === "number" ? body.id : null,
    roles,
    hasStudentRole: hasStudent,
    hasStudentProfile: Boolean(studentProfile),
    faceRegistered: Boolean(studentProfile?.is_face_registered) || Boolean(body.face_scan_bypass_enabled),
    registrationComplete: Boolean(studentProfile?.registration_complete),
    studentId: studentProfile?.student_id ?? null,
    faceScanBypassEnabled: Boolean(body.face_scan_bypass_enabled),
  };
};

export const registerCurrentStudentFace = async (
  imageBlob: Blob,
  authToken?: string | null
) => {
  const imageBase64 = await blobToDataUrl(imageBlob);
  const response = await fetch(buildApiUrl("/api/face/register"), {
    method: "POST",
    headers: buildAuthHeaders(authToken),
    body: JSON.stringify({ image_base64: imageBase64 }),
  });
  const body = await parseJson<FaceRegistrationResponse>(response);

  if (!response.ok) {
    throw new Error(
      toErrorMessage(body, "Failed to register the student face.")
    );
  }

  return {
    message: body.message || "Face registered successfully.",
    studentId: body.student_id ?? null,
  };
};
