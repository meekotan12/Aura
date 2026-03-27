import { buildApiUrl } from "./apiUrl";
import { buildAuthHeaders as buildSharedAuthHeaders } from "../lib/api/client";

export interface StudentEventLocationPayload {
  latitude: number;
  longitude: number;
  accuracyM?: number | null;
}

export interface EventLocationVerificationResponse {
  ok: boolean;
  reason?: string | null;
  distance_m: number;
  effective_distance_m?: number | null;
  radius_m: number;
  accuracy_m?: number | null;
  time_status?: {
    event_status:
      | "before_check_in"
      | "early_check_in"
      | "late_check_in"
      | "absent_check_in"
      | "sign_out_pending"
      | "sign_out_open"
      | "closed";
    current_time: string;
    check_in_opens_at: string;
    start_time: string;
    end_time: string;
    late_threshold_time: string;
    attendance_override_active: boolean;
    effective_present_until_at: string;
    effective_late_until_at: string;
    sign_out_opens_at: string;
    normal_sign_out_closes_at: string;
    effective_sign_out_closes_at: string;
    timezone_name: string;
  } | null;
  attendance_decision?: {
    action: "check_in" | "sign_out";
    event_status:
      | "before_check_in"
      | "early_check_in"
      | "late_check_in"
      | "absent_check_in"
      | "sign_out_pending"
      | "sign_out_open"
      | "closed";
    attendance_allowed: boolean;
    attendance_status?: "present" | "late" | "absent" | null;
    reason_code?: string | null;
    message: string;
    current_time: string;
    check_in_opens_at: string;
    start_time: string;
    end_time: string;
    late_threshold_time: string;
    attendance_override_active: boolean;
    effective_present_until_at: string;
    effective_late_until_at: string;
    sign_out_opens_at: string;
    normal_sign_out_closes_at: string;
    effective_sign_out_closes_at: string;
    timezone_name: string;
  } | null;
}

export interface StudentEventAttendanceScanResponse {
  action: "time_in" | "timeout";
  student_id: string;
  student_name: string;
  attendance_id: number;
  distance: number;
  confidence: number;
  threshold: number;
  liveness: {
    label?: string;
    score?: number;
    reason?: string | null;
  };
  geo?: EventLocationVerificationResponse | null;
  time_in?: string | null;
  time_out?: string | null;
  duration_minutes?: number | null;
  message?: string | null;
}

type ErrorBody = {
  detail?: unknown;
  message?: unknown;
};

export class StudentEventCheckInApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "StudentEventCheckInApiError";
    this.status = status;
    this.detail = detail;
  }
}

const buildAuthHeaders = () => {
  return buildSharedAuthHeaders(undefined, { "Content-Type": "application/json" });
};

const parseJson = async <T>(response: Response) =>
  (await response.json().catch(() => ({}))) as T;

const detailToMessage = (detail: unknown, fallback: string) => {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (detail && typeof detail === "object") {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }

    const reason = (detail as { reason?: unknown }).reason;
    if (typeof reason === "string" && reason.trim()) {
      return reason;
    }

    const code = (detail as { code?: unknown }).code;
    if (typeof code === "string" && code === "implausible_travel_speed") {
      return "Location verification failed because the travel pattern looks unrealistic.";
    }

    return JSON.stringify(detail);
  }

  return fallback;
};

const ensureOk = async <T>(response: Response, fallback: string) => {
  const body = await parseJson<T & ErrorBody>(response);

  if (!response.ok) {
    const detail = body?.detail ?? body?.message ?? body;
    throw new StudentEventCheckInApiError(
      detailToMessage(detail, fallback),
      response.status,
      detail,
    );
  }

  return body as T;
};

const blobToDataUrl = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () =>
      reject(new Error("Failed to read the live face image from the camera."));
    reader.readAsDataURL(blob);
  });

export const verifyStudentEventLocation = async (
  eventId: number,
  location: StudentEventLocationPayload,
) => {
  const response = await fetch(buildApiUrl(`/api/events/${eventId}/verify-location`), {
    method: "POST",
    headers: buildAuthHeaders(),
    body: JSON.stringify({
      latitude: location.latitude,
      longitude: location.longitude,
      accuracy_m: location.accuracyM ?? null,
    }),
  });

  return ensureOk<EventLocationVerificationResponse>(
    response,
    "Failed to verify the current location for this event.",
  );
};

export const submitStudentEventAttendanceScan = async ({
  eventId,
  imageBlob,
  location,
}: {
  eventId: number;
  imageBlob?: Blob | null;
  location: StudentEventLocationPayload;
}) => {
  const imageBase64 = imageBlob ? await blobToDataUrl(imageBlob) : null;
  const response = await fetch(buildApiUrl("/api/face/face-scan-with-recognition"), {
    method: "POST",
    headers: buildAuthHeaders(),
    body: JSON.stringify({
      event_id: eventId,
      image_base64: imageBase64,
      latitude: location.latitude,
      longitude: location.longitude,
      accuracy_m: location.accuracyM ?? null,
    }),
  });

  return ensureOk<StudentEventAttendanceScanResponse>(
    response,
    "Failed to verify the live face for this event sign-in.",
  );
};

export const describeStudentEventCheckInError = (error: unknown) => {
  if (error instanceof StudentEventCheckInApiError) {
    return detailToMessage(error.detail, error.message);
  }

  return error instanceof Error
    ? error.message
    : "The event sign-in request failed.";
};
