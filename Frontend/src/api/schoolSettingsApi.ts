import { buildApiUrl, buildAssetUrl } from "./apiUrl";
const SCHOOL_THEME_KEY = "schoolTheme";
const SCHOOL_BRANDING_KEY = "schoolBranding";

export interface SchoolSettings {
  school_id: number;
  school_name: string;
  school_code?: string | null;
  logo_url: string | null;
  primary_color: string;
  secondary_color: string | null;
  event_default_early_check_in_minutes: number;
  event_default_late_threshold_minutes: number;
  event_default_sign_out_grace_minutes: number;
  subscription_status?: string;
  active_status?: boolean;
}

export interface SchoolSettingsUpdatePayload {
  school_name?: string;
  primary_color?: string;
  secondary_color?: string | null;
  school_code?: string | null;
  event_default_early_check_in_minutes?: number;
  event_default_late_threshold_minutes?: number;
  event_default_sign_out_grace_minutes?: number;
}

export interface UserImportErrorItem {
  row: number;
  error: string;
}

export interface UserImportSummary {
  job_id: string;
  state: string;
  total_rows: number;
  processed_rows: number;
  success_count: number;
  failed_count: number;
  percentage_completed: number;
  estimated_time_remaining_seconds?: number | null;
  errors: UserImportErrorItem[];
  failed_report_download_url?: string | null;
}

export interface ImportPreviewRow {
  row: number;
  status: string;
  errors: string[];
  suggestions: string[];
  row_data?: Record<string, string> | null;
}

export interface ImportPreviewSummary {
  filename: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  can_commit: boolean;
  preview_token?: string | null;
  rows: ImportPreviewRow[];
}

export interface AdminSchoolItCreatePayload {
  school_name: string;
  primary_color: string;
  secondary_color?: string | null;
  school_code?: string | null;
  school_it_email: string;
  school_it_first_name: string;
  school_it_middle_name?: string | null;
  school_it_last_name: string;
  school_it_password?: string | null;
}

export interface AdminSchoolItCreateResponse {
  school: SchoolSettings;
  school_it_user_id: number;
  school_it_email: string;
  generated_temporary_password?: string | null;
}

export interface SchoolSummary {
  school_id: number;
  school_name: string;
  school_code?: string | null;
  subscription_status: string;
  active_status: boolean;
  created_at: string;
  updated_at: string;
}

export interface SchoolITAccountSummary {
  user_id: number;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  school_id?: number | null;
  school_name?: string | null;
  is_active: boolean;
}

interface ImportJobCreateResponse {
  job_id: string;
  status: string;
}

const getAuthToken = () =>
  localStorage.getItem("authToken") ||
  localStorage.getItem("token") ||
  localStorage.getItem("access_token");

const clearAuthState = () => {
  localStorage.removeItem("authToken");
  localStorage.removeItem("token");
  localStorage.removeItem("access_token");
  localStorage.removeItem("user");
  localStorage.removeItem("userData");
};

const withAuthHeaders = () => {
  const token = getAuthToken();
  if (!token) {
    throw new Error("No authentication token found");
  }

  return {
    Authorization: `Bearer ${token}`,
  };
};

const extractApiErrorMessage = async (response: Response, fallback: string): Promise<string> => {
  if (response.status === 401) {
    clearAuthState();
    return "Session expired. Please log in again.";
  }

  const body = await response.json().catch(() => null);
  if (!body) return fallback;
  if (typeof body.detail === "string" && body.detail.trim().length > 0) return body.detail;
  if (typeof body.message === "string" && body.message.trim().length > 0) return body.message;
  if (typeof body.error === "string" && body.error.trim().length > 0) return body.error;
  return fallback;
};

export const normalizeLogoUrl = (logoUrl?: string | null): string | null => {
  if (!logoUrl) return null;
  return buildAssetUrl(logoUrl);
};

export const applyTheme = (settings: Pick<SchoolSettings, "primary_color" | "secondary_color">) => {
  const primary = settings.primary_color || "#162F65";
  const secondary = settings.secondary_color || "#2C5F9E";
  const root = document.documentElement;
  root.style.setProperty("--primary-color", primary);
  root.style.setProperty("--secondary-color", secondary);
  root.style.setProperty("--accent-color", secondary);
  root.style.setProperty("--hover-color", secondary);
};

export const saveTheme = (settings: Pick<SchoolSettings, "primary_color" | "secondary_color">) => {
  localStorage.setItem(SCHOOL_THEME_KEY, JSON.stringify(settings));
};

export const saveBranding = (settings: SchoolSettings) => {
  localStorage.setItem(SCHOOL_BRANDING_KEY, JSON.stringify(settings));
  applyTheme(settings);
  saveTheme(settings);
};

export const getStoredBranding = (): SchoolSettings | null => {
  const raw = localStorage.getItem(SCHOOL_BRANDING_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as SchoolSettings;
  } catch {
    localStorage.removeItem(SCHOOL_BRANDING_KEY);
    return null;
  }
};

export const clearBranding = () => {
  localStorage.removeItem(SCHOOL_BRANDING_KEY);
  localStorage.removeItem(SCHOOL_THEME_KEY);
};

export const applyStoredTheme = () => {
  const branding = getStoredBranding();
  if (branding) {
    applyTheme(branding);
    return;
  }

  const stored = localStorage.getItem(SCHOOL_THEME_KEY);
  if (!stored) return;

  try {
    const parsed = JSON.parse(stored) as Pick<SchoolSettings, "primary_color" | "secondary_color">;
    applyTheme(parsed);
  } catch {
    localStorage.removeItem(SCHOOL_THEME_KEY);
  }
};

export const fetchSchoolSettings = async (): Promise<SchoolSettings> => {
  const response = await fetch(buildApiUrl("/api/school/me"), {
    method: "GET",
    headers: withAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, "Failed to fetch school branding"));
  }

  const data = (await response.json()) as SchoolSettings;
  saveBranding(data);
  return data;
};

const buildSchoolFormData = (
  payload: SchoolSettingsUpdatePayload,
  logoFile?: File | null
): FormData => {
  const formData = new FormData();
  if (payload.school_name !== undefined) formData.append("school_name", payload.school_name);
  if (payload.primary_color !== undefined) formData.append("primary_color", payload.primary_color);
  if (payload.secondary_color !== undefined) formData.append("secondary_color", payload.secondary_color || "");
  if (payload.school_code !== undefined) formData.append("school_code", payload.school_code || "");
  if (payload.event_default_early_check_in_minutes !== undefined) {
    formData.append(
      "event_default_early_check_in_minutes",
      `${payload.event_default_early_check_in_minutes}`
    );
  }
  if (payload.event_default_late_threshold_minutes !== undefined) {
    formData.append(
      "event_default_late_threshold_minutes",
      `${payload.event_default_late_threshold_minutes}`
    );
  }
  if (payload.event_default_sign_out_grace_minutes !== undefined) {
    formData.append(
      "event_default_sign_out_grace_minutes",
      `${payload.event_default_sign_out_grace_minutes}`
    );
  }
  if (logoFile) formData.append("logo", logoFile);
  return formData;
};

export const createSchool = async (
  payload: SchoolSettingsUpdatePayload,
  logoFile?: File | null
): Promise<SchoolSettings> => {
  const formData = buildSchoolFormData(payload, logoFile);
  const response = await fetch(buildApiUrl("/api/school/create"), {
    method: "POST",
    headers: withAuthHeaders(),
    body: formData,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to create school");
  }

  const data = body as SchoolSettings;
  saveBranding(data);
  return data;
};

export const updateSchoolSettings = async (
  payload: SchoolSettingsUpdatePayload,
  logoFile?: File | null
): Promise<SchoolSettings> => {
  const formData = buildSchoolFormData(payload, logoFile);
  const response = await fetch(buildApiUrl("/api/school/update"), {
    method: "PUT",
    headers: withAuthHeaders(),
    body: formData,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to update school branding");
  }

  const data = body as SchoolSettings;
  saveBranding(data);
  return data;
};

export const downloadUserImportTemplate = async (): Promise<void> => {
  const response = await fetch(buildApiUrl("/api/admin/import-students/template"), {
    method: "GET",
    headers: withAuthHeaders(),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to download import template");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "student_import_template.xlsx";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
};

export const importUsersFromExcel = async (previewToken: string): Promise<ImportJobCreateResponse> => {
  const formData = new FormData();
  formData.append("preview_token", previewToken);

  const response = await fetch(buildApiUrl("/api/admin/import-students"), {
    method: "POST",
    headers: withAuthHeaders(),
    body: formData,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to import users");
  }

  return body as ImportJobCreateResponse;
};

export const previewImportUsersFromExcel = async (file: File): Promise<ImportPreviewSummary> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(buildApiUrl("/api/admin/import-students/preview"), {
    method: "POST",
    headers: withAuthHeaders(),
    body: formData,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to preview import file");
  }

  return body as ImportPreviewSummary;
};

export const getImportStatus = async (jobId: string): Promise<UserImportSummary> => {
  const response = await fetch(buildApiUrl(`/api/admin/import-status/${jobId}`), {
    method: "GET",
    headers: withAuthHeaders(),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to fetch import status");
  }

  return body as UserImportSummary;
};

export const downloadPreviewImportErrors = async (previewToken: string): Promise<void> => {
  const response = await fetch(buildApiUrl(`/api/admin/import-preview-errors/${previewToken}/download`), {
    method: "GET",
    headers: withAuthHeaders(),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to download preview errors");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `preview_errors_${previewToken}.xlsx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
};

export const downloadPreviewRetryFile = async (previewToken: string): Promise<void> => {
  const response = await fetch(buildApiUrl(`/api/admin/import-preview-errors/${previewToken}/retry-download`), {
    method: "GET",
    headers: withAuthHeaders(),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to download preview retry file");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `preview_retry_${previewToken}.xlsx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
};

export const removeInvalidPreviewRows = async (
  previewToken: string
): Promise<ImportPreviewSummary> => {
  const response = await fetch(buildApiUrl(`/api/admin/import-preview-errors/${previewToken}/remove-invalid`), {
    method: "POST",
    headers: withAuthHeaders(),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to remove invalid preview rows");
  }

  return body as ImportPreviewSummary;
};

export const downloadImportErrors = async (jobId: string): Promise<void> => {
  const response = await fetch(buildApiUrl(`/api/admin/import-errors/${jobId}/download`), {
    method: "GET",
    headers: withAuthHeaders(),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to download failed rows report");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `import_${jobId}_failed_rows.xlsx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
};

export const retryFailedImportRows = async (
  jobId: string,
  rowNumbers?: number[]
): Promise<ImportJobCreateResponse> => {
  const response = await fetch(buildApiUrl(`/api/admin/import-students/retry-failed/${jobId}`), {
    method: "POST",
    headers: {
      ...withAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ row_numbers: rowNumbers && rowNumbers.length ? rowNumbers : null }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to retry failed rows");
  }
  return body as ImportJobCreateResponse;
};

const buildAdminSchoolItCreateFormData = (
  payload: AdminSchoolItCreatePayload,
  logoFile?: File | null
): FormData => {
  const formData = new FormData();
  formData.append("school_name", payload.school_name);
  formData.append("primary_color", payload.primary_color);
  if (payload.secondary_color !== undefined) {
    formData.append("secondary_color", payload.secondary_color || "");
  }
  if (payload.school_code !== undefined) {
    formData.append("school_code", payload.school_code || "");
  }
  formData.append("school_it_email", payload.school_it_email);
  formData.append("school_it_first_name", payload.school_it_first_name);
  if (payload.school_it_middle_name !== undefined) {
    formData.append("school_it_middle_name", payload.school_it_middle_name || "");
  }
  formData.append("school_it_last_name", payload.school_it_last_name);
  if (payload.school_it_password !== undefined) {
    formData.append("school_it_password", payload.school_it_password || "");
  }
  if (logoFile) {
    formData.append("logo", logoFile);
  }
  return formData;
};

export const adminCreateSchoolWithSchoolIT = async (
  payload: AdminSchoolItCreatePayload,
  logoFile?: File | null
): Promise<AdminSchoolItCreateResponse> => {
  const formData = buildAdminSchoolItCreateFormData(payload, logoFile);
  const response = await fetch(buildApiUrl("/api/school/admin/create-school-it"), {
    method: "POST",
    headers: withAuthHeaders(),
    body: formData,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to create school and Campus Admin account");
  }
  return body as AdminSchoolItCreateResponse;
};

export const adminListSchools = async (): Promise<SchoolSummary[]> => {
  const response = await fetch(buildApiUrl("/api/school/admin/list"), {
    method: "GET",
    headers: withAuthHeaders(),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to fetch schools");
  }
  return body as SchoolSummary[];
};

export const adminListSchoolItAccounts = async (): Promise<SchoolITAccountSummary[]> => {
  const response = await fetch(buildApiUrl("/api/school/admin/school-it-accounts"), {
    method: "GET",
    headers: withAuthHeaders(),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to fetch Campus Admin accounts");
  }
  return body as SchoolITAccountSummary[];
};

export const adminSetSchoolItActiveStatus = async (
  userId: number,
  isActive: boolean
): Promise<SchoolITAccountSummary> => {
  const response = await fetch(buildApiUrl(`/api/school/admin/school-it-accounts/${userId}/status`), {
    method: "PATCH",
    headers: {
      ...withAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ is_active: isActive }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to update Campus Admin status");
  }
  return body as SchoolITAccountSummary;
};

export const adminResetSchoolItPassword = async (
  userId: number
): Promise<{ user_id: number; email: string; temporary_password: string; must_change_password: boolean }> => {
  const response = await fetch(buildApiUrl(`/api/school/admin/school-it-accounts/${userId}/reset-password`), {
    method: "POST",
    headers: withAuthHeaders(),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to reset Campus Admin password");
  }
  return body as { user_id: number; email: string; temporary_password: string; must_change_password: boolean };
};


