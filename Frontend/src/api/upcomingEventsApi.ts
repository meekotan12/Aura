import { getAuthToken } from "./authApi";
import { buildApiUrl } from "./apiUrl";

const authHeaders = () => {
  const token = getAuthToken();
  if (!token) {
    throw new Error("No authentication token found");
  }
  return { Authorization: `Bearer ${token}` };
};

export type SchoolEventStatus = "upcoming" | "ongoing" | "completed" | "cancelled";

export type UpcomingEvent = {
  id: number;
  school_id: number;
  name: string;
  location?: string | null;
  start_datetime: string;
  end_datetime: string;
  late_threshold_minutes?: number;
  status: SchoolEventStatus;
};

export const fetchUpcomingEvents = async (
  status: SchoolEventStatus = "upcoming"
): Promise<UpcomingEvent[]> => {
  const response = await fetch(buildApiUrl(`/api/events?status=${status}`), {
    headers: {
      ...authHeaders(),
    },
  });
  const body = await response.json().catch(() => []);
  if (!response.ok) {
    throw new Error(body.detail || "Failed to load upcoming events");
  }
  return body as UpcomingEvent[];
};
