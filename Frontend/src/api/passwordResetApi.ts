import { apiFetch, buildAuthHeaders, extractApiErrorMessage } from "../lib/api/client";

export interface PasswordResetRequestItem {
  id: number;
  user_id: number;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  roles: string[];
  status: string;
  requested_at: string;
}

export interface PasswordResetApprovalResponse {
  id: number;
  user_id: number;
  status: string;
  resolved_at: string;
  message: string;
}

const withAuthHeaders = () => {
  return buildAuthHeaders();
};

export const fetchPasswordResetRequests = async (): Promise<PasswordResetRequestItem[]> => {
  const response = await apiFetch("/auth/password-reset-requests", {
    method: "GET",
    headers: withAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, "Failed to load password reset requests"));
  }

  return (await response.json()) as PasswordResetRequestItem[];
};

export const approvePasswordResetRequest = async (
  requestId: number
): Promise<PasswordResetApprovalResponse> => {
  const response = await apiFetch(`/auth/password-reset-requests/${requestId}/approve`, {
    method: "POST",
    headers: withAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, "Failed to approve password reset request"));
  }

  return (await response.json()) as PasswordResetApprovalResponse;
};
