import { getAuthToken } from "./authApi";
import { buildApiUrl } from "./apiUrl";

const authHeaders = () => {
  const token = getAuthToken();
  if (!token) {
    throw new Error("No authentication token found");
  }
  return { Authorization: `Bearer ${token}` };
};

export type NotificationItem = {
  id: number;
  user_id: number;
  school_id: number;
  title: string;
  message: string;
  type: string;
  related_id?: number | null;
  is_read: boolean;
  created_at: string;
};

export type NotificationListResponse = {
  unread_count: number;
  items: NotificationItem[];
};

export const fetchMyNotifications = async (): Promise<NotificationListResponse> => {
  const response = await fetch(buildApiUrl("/api/notifications-center/me"), {
    headers: {
      ...authHeaders(),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Failed to load notifications");
  }
  return body as NotificationListResponse;
};

export const markNotificationsRead = async (ids: number[]): Promise<void> => {
  const response = await fetch(buildApiUrl("/api/notifications-center/me/read"), {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ids }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to mark notifications read");
  }
};
