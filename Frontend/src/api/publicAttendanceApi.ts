import { buildApiUrl } from "./apiUrl";

import type { EventLocationVerificationResponse } from "./studentEventCheckInApi";

export interface PublicAttendanceLocationPayload {
  latitude: number;
  longitude: number;
  accuracyM?: number | null;
}

export interface PublicAttendanceEventSummary {
  id: number;
  school_id: number;
  school_name: string;
  name: string;
  location: string;
  start_datetime: string;
  end_datetime: string;
  geo_radius_m: number;
  distance_m: number;
  effective_distance_m?: number | null;
  accuracy_m?: number | null;
  attendance_phase: "sign_in" | "sign_out";
  phase_message: string;
  scope_label: string;
  departments: string[];
  programs: string[];
}

export interface PublicAttendanceNearbyEventsResponse {
  events: PublicAttendanceEventSummary[];
  scan_cooldown_seconds: number;
}

export interface PublicAttendanceFaceOutcome {
  action:
    | "time_in"
    | "time_out"
    | "already_signed_in"
    | "already_signed_out"
    | "rejected"
    | "out_of_scope"
    | "no_match"
    | "liveness_failed"
    | "duplicate_face"
    | "cooldown_skipped";
  reason_code?: string | null;
  message: string;
  student_id?: string | null;
  student_name?: string | null;
  attendance_id?: number | null;
  distance?: number | null;
  confidence?: number | null;
  threshold?: number | null;
  liveness?: {
    label?: string;
    score?: number;
    reason?: string | null;
  } | null;
  time_in?: string | null;
  time_out?: string | null;
  duration_minutes?: number | null;
}

export interface PublicAttendanceScanResponse {
  event_id: number;
  event_phase: "sign_in" | "sign_out";
  message: string;
  scan_cooldown_seconds: number;
  geo?: EventLocationVerificationResponse | null;
  outcomes: PublicAttendanceFaceOutcome[];
}

type ErrorBody = {
  detail?: unknown;
  message?: unknown;
};

export class PublicAttendanceApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "PublicAttendanceApiError";
    this.status = status;
    this.detail = detail;
  }
}

const parseJson = async <T>(response: Response) =>
  (await response.json().catch(() => ({}))) as T;

const blobToDataUrl = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () =>
      reject(new Error("Failed to read the public kiosk camera frame."));
    reader.readAsDataURL(blob);
  });

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

    return JSON.stringify(detail);
  }

  return fallback;
};

const ensureOk = async <T>(response: Response, fallback: string) => {
  const body = await parseJson<T & ErrorBody>(response);

  if (!response.ok) {
    const detail = body?.detail ?? body?.message ?? body;
    throw new PublicAttendanceApiError(
      detailToMessage(detail, fallback),
      response.status,
      detail,
    );
  }

  return body as T;
};

export const fetchNearbyPublicAttendanceEvents = async (
  location: PublicAttendanceLocationPayload,
) => {
  const response = await fetch(buildApiUrl("/public-attendance/events/nearby"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      latitude: location.latitude,
      longitude: location.longitude,
      accuracy_m: location.accuracyM ?? null,
    }),
  });

  return ensureOk<PublicAttendanceNearbyEventsResponse>(
    response,
    "Failed to load nearby public attendance events.",
  );
};

export const submitPublicAttendanceScan = async ({
  eventId,
  imageBlob,
  location,
  cooldownStudentIds,
  threshold,
}: {
  eventId: number;
  imageBlob: Blob;
  location: PublicAttendanceLocationPayload;
  cooldownStudentIds?: string[];
  threshold?: number | null;
}) => {
  const imageBase64 = await blobToDataUrl(imageBlob);
  const response = await fetch(
    buildApiUrl(`/public-attendance/events/${eventId}/multi-face-scan`),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        image_base64: imageBase64,
        latitude: location.latitude,
        longitude: location.longitude,
        accuracy_m: location.accuracyM ?? null,
        threshold: threshold ?? null,
        cooldown_student_ids: cooldownStudentIds ?? [],
      }),
    },
  );

  return ensureOk<PublicAttendanceScanResponse>(
    response,
    "Failed to process the public face attendance scan.",
  );
};

export const describePublicAttendanceError = (error: unknown) => {
  if (error instanceof PublicAttendanceApiError) {
    return detailToMessage(error.detail, error.message);
  }

  return error instanceof Error
    ? error.message
    : "The public attendance kiosk request failed.";
};
