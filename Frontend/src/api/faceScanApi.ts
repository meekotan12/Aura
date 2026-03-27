import {
  apiJsonRequest,
  apiRequest,
  extractApiErrorMessage,
} from "../lib/api/client";

export interface FaceRegistrationResponse {
  message?: string;
  student_id?: string;
}

export interface FaceVerificationResponse {
  match_found: boolean;
  student_name?: string;
  student_id?: string;
}

export interface FaceAttendanceScanResponse {
  action: "time_in" | "timeout";
  student_id: string;
  student_name: string;
  attendance_id: number;
  duration_minutes?: number | null;
  geo?: {
    distance_m?: number | null;
  } | null;
}

export interface FaceAttendanceScanPayload {
  eventId: number;
  imageBase64: string;
  latitude?: number;
  longitude?: number;
  accuracyM?: number;
}

export const registerFaceFromImage = async (
  imageBase64: string
): Promise<FaceRegistrationResponse> =>
  apiJsonRequest<FaceRegistrationResponse>(
    "/api/face/register",
    {
      auth: true,
      method: "POST",
      json: { image_base64: imageBase64 },
    },
    "Failed to register face"
  );

export const uploadFaceRegistration = async (
  file: File
): Promise<FaceRegistrationResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiRequest("/api/face/register-upload", {
    auth: true,
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, "Failed to upload face registration"));
  }

  return (await response.json()) as FaceRegistrationResponse;
};

export const verifyFaceFromImage = async (
  imageBase64: string
): Promise<FaceVerificationResponse> =>
  apiJsonRequest<FaceVerificationResponse>(
    "/api/face/verify",
    {
      auth: true,
      method: "POST",
      json: { image_base64: imageBase64 },
    },
    "Failed to verify face"
  );

export const submitFaceAttendanceScan = async ({
  eventId,
  imageBase64,
  latitude,
  longitude,
  accuracyM,
}: FaceAttendanceScanPayload): Promise<FaceAttendanceScanResponse> =>
  apiJsonRequest<FaceAttendanceScanResponse>(
    "/api/face/face-scan-with-recognition",
    {
      auth: true,
      method: "POST",
      json: {
        event_id: eventId,
        image_base64: imageBase64,
        latitude,
        longitude,
        accuracy_m: accuracyM,
      },
    },
    "Failed to scan attendance"
  );
