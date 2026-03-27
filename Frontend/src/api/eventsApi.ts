import { buildApiUrl } from "./apiUrl";
import { buildAuthHeaders } from "../lib/api/client";

const EVENTS_CACHE_TTL_MS = 60_000;

export type GovernanceContext = "SSG" | "SG" | "ORG";
export type EventStatus = "upcoming" | "ongoing" | "completed" | "cancelled";

export interface Event {
  id: number;
  name: string;
  location: string;
  geo_latitude?: number | null;
  geo_longitude?: number | null;
  geo_radius_m?: number | null;
  geo_required?: boolean;
  geo_max_accuracy_m?: number | null;
  early_check_in_minutes?: number;
  late_threshold_minutes?: number;
  sign_out_grace_minutes?: number;
  sign_out_open_delay_minutes?: number;
  sign_out_override_until?: string | null;
  present_until_override_at?: string | null;
  late_until_override_at?: string | null;
  start_datetime: string;
  end_datetime: string;
  status: EventStatus;
  departments?: Department[];
  programs?: Program[];
}

export interface CreateEventPayload {
  name: string;
  location: string;
  geo_latitude?: number | null;
  geo_longitude?: number | null;
  geo_radius_m?: number | null;
  geo_required?: boolean;
  geo_max_accuracy_m?: number | null;
  early_check_in_minutes?: number;
  late_threshold_minutes?: number;
  sign_out_grace_minutes?: number;
  sign_out_open_delay_minutes?: number;
  start_datetime: string;
  end_datetime: string;
  status?: EventStatus;
  department_ids?: number[];
  program_ids?: number[];
}

export interface AttendanceRecord {
  id: number;
  event_id: number;
  event_name: string;
  time_in: string;
  time_out: string | null;
  check_in_status?: "present" | "late" | "absent" | null;
  check_out_status?: "present" | "absent" | null;
  status: "present" | "late" | "absent" | "excused";
  display_status?: "present" | "late" | "absent" | "excused" | "incomplete";
  completion_state?: "completed" | "incomplete";
  is_valid_attendance?: boolean;
  method: "face_scan" | "manual";
  duration_minutes: number | null;
  notes?: string | null;
}

export interface EventAttendanceWithStudent {
  attendance: {
    id: number;
    event_id: number;
    student_id: number;
    time_in: string;
    time_out?: string | null;
    check_in_status?: "present" | "late" | "absent" | null;
    check_out_status?: "present" | "absent" | null;
    method: "face_scan" | "manual";
    status: "present" | "late" | "absent" | "excused";
    display_status?: "present" | "late" | "absent" | "excused" | "incomplete";
    completion_state?: "completed" | "incomplete";
    is_valid_attendance?: boolean;
    notes?: string | null;
  };
  student_id: string | null;
  student_name: string;
}

export interface EventStatsResponse {
  total: number;
  statuses: Partial<
    Record<
      "present" | "late" | "absent" | "excused",
      {
        count: number;
        percentage: number;
      }
    >
  > & Partial<
    Record<
      "incomplete",
      {
        count: number;
        percentage: number;
      }
    >
  >;
}

interface Department {
  id: number;
  name: string;
}

interface Program {
  id: number;
  name: string;
}

export interface UpdateEventPayload {
  name?: string;
  location?: string;
  geo_latitude?: number | null;
  geo_longitude?: number | null;
  geo_radius_m?: number | null;
  geo_required?: boolean;
  geo_max_accuracy_m?: number | null;
  early_check_in_minutes?: number;
  late_threshold_minutes?: number;
  sign_out_grace_minutes?: number;
  sign_out_open_delay_minutes?: number;
  start_datetime?: string;
  end_datetime?: string;
  status?: EventStatus;
  department_ids?: number[];
  program_ids?: number[];
}

export interface OpenSignOutEarlyPayload {
  use_sign_out_grace_minutes: boolean;
  close_after_minutes?: number;
}

type EventCacheEntry = {
  data: Event[];
  expiresAt: number;
};

const eventsCache = new Map<string, EventCacheEntry>();

const parseError = async (response: Response, fallback: string): Promise<string> => {
  const raw = await response.text().catch(() => "");
  if (!raw.trim()) {
    return fallback;
  }

  try {
    const body = JSON.parse(raw) as { detail?: unknown; message?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
    if (typeof body.message === "string" && body.message.trim()) {
      return body.message;
    }
  } catch {
    return raw.trim() || fallback;
  }

  return raw.trim() || fallback;
};

const getAuthHeaders = (): HeadersInit => {
  return buildAuthHeaders();
};

const getCachedEvents = (key: string): Event[] | null => {
  const entry = eventsCache.get(key);
  if (!entry) {
    return null;
  }

  if (Date.now() > entry.expiresAt) {
    eventsCache.delete(key);
    return null;
  }

  return entry.data;
};

const setCachedEvents = (key: string, data: Event[]) => {
  eventsCache.set(key, {
    data,
    expiresAt: Date.now() + EVENTS_CACHE_TTL_MS,
  });
};

const clearEventsCache = () => {
  eventsCache.clear();
};

const buildGovernanceContextQuery = (governanceContext?: GovernanceContext) =>
  governanceContext ? `?governance_context=${encodeURIComponent(governanceContext)}` : "";

const hydrateStatusCache = (events: Event[], governanceContext?: GovernanceContext) => {
  const statuses: EventStatus[] = [
    "upcoming",
    "ongoing",
    "completed",
    "cancelled",
  ];

  for (const status of statuses) {
    setCachedEvents(
      governanceContext ? `status:${status}:${governanceContext}` : `status:${status}`,
      events.filter((event) => event.status === status)
    );
  }
};

export const fetchAllEvents = async (
  forceRefresh = false,
  governanceContext?: GovernanceContext
): Promise<Event[]> => {
  const cacheKey = governanceContext ? `all:${governanceContext}` : "all";
  const cachedEvents = forceRefresh ? null : getCachedEvents(cacheKey);
  if (cachedEvents) {
    return cachedEvents;
  }

  const query = buildGovernanceContextQuery(governanceContext);
  const response = await fetch(buildApiUrl(`/api/events/${query}`), {
    headers: getAuthHeaders(),
  });
  if (!response.ok) throw new Error("Network error");

  const data = (await response.json()) as Event[];
  setCachedEvents(cacheKey, data);
  hydrateStatusCache(data, governanceContext);
  return data;
};

export const fetchUpcomingEvents = async (): Promise<Event[]> => {
  return fetchEventsByStatus("upcoming");
};

export const createEvent = async (
  payload: CreateEventPayload,
  governanceContext?: GovernanceContext
): Promise<Event> => {
  const query = buildGovernanceContextQuery(governanceContext);
  const response = await fetch(buildApiUrl(`/api/events/${query}`), {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      status: "upcoming",
      geo_required: false,
      department_ids: [],
      program_ids: [],
      ...payload,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to create event"));
  }

  clearEventsCache();
  return (await response.json()) as Event;
};

export const updateEvent = async (
  eventId: number,
  payload: UpdateEventPayload,
  governanceContext?: GovernanceContext
): Promise<Event> => {
  const query = buildGovernanceContextQuery(governanceContext);
  const response = await fetch(buildApiUrl(`/api/events/${eventId}${query}`), {
    method: "PATCH",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to update event"));
  }

  clearEventsCache();
  return (await response.json()) as Event;
};

export const updateEventStatus = async (
  eventId: number,
  status: EventStatus,
  governanceContext?: GovernanceContext
): Promise<Event> => {
  const query = new URLSearchParams({ status });
  if (governanceContext) {
    query.set("governance_context", governanceContext);
  }

  const response = await fetch(buildApiUrl(`/api/events/${eventId}/status?${query.toString()}`), {
    method: "PATCH",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to update event status"));
  }

  clearEventsCache();
  return (await response.json()) as Event;
};

export const deleteEvent = async (
  eventId: number,
  governanceContext?: GovernanceContext
): Promise<void> => {
  const query = buildGovernanceContextQuery(governanceContext);
  const response = await fetch(buildApiUrl(`/api/events/${eventId}${query}`), {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to delete event"));
  }

  clearEventsCache();
};

export const openSignOutEarly = async (
  eventId: number,
  payload: OpenSignOutEarlyPayload,
  governanceContext?: GovernanceContext
): Promise<Event> => {
  const query = buildGovernanceContextQuery(governanceContext);
  const response = await fetch(buildApiUrl(`/api/events/${eventId}/sign-out/open-early${query}`), {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to open sign-out early"));
  }

  clearEventsCache();
  return (await response.json()) as Event;
};

export const fetchEventById = async (
  eventId: number,
  governanceContext?: GovernanceContext
): Promise<Event> => {
  const query = buildGovernanceContextQuery(governanceContext);
  const response = await fetch(buildApiUrl(`/api/events/${eventId}${query}`), {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to fetch event details"));
  }

  return (await response.json()) as Event;
};

export const fetchEventStats = async (
  eventId: number,
  governanceContext?: GovernanceContext
): Promise<EventStatsResponse> => {
  const query = buildGovernanceContextQuery(governanceContext);
  const response = await fetch(buildApiUrl(`/api/events/${eventId}/stats${query}`), {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to fetch event statistics"));
  }

  return (await response.json()) as EventStatsResponse;
};

export const fetchEventAttendancesWithStudents = async (
  eventId: number,
  governanceContext?: GovernanceContext
): Promise<EventAttendanceWithStudent[]> => {
  const query = buildGovernanceContextQuery(governanceContext);
  const response = await fetch(
    buildApiUrl(`/api/attendance/events/${eventId}/attendances-with-students${query}`),
    {
      headers: getAuthHeaders(),
    }
  );

  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to fetch event attendee records"));
  }

  return (await response.json()) as EventAttendanceWithStudent[];
};

export const fetchEventsByStatus = async (
  status: EventStatus,
  forceRefresh = false,
  governanceContext?: GovernanceContext
): Promise<Event[]> => {
  const cacheKey = governanceContext ? `status:${status}:${governanceContext}` : `status:${status}`;
  const cachedEvents = forceRefresh ? null : getCachedEvents(cacheKey);
  if (cachedEvents) {
    return cachedEvents;
  }

  const allEvents = forceRefresh ? null : getCachedEvents(governanceContext ? `all:${governanceContext}` : "all");
  if (allEvents) {
    const filteredEvents = allEvents.filter((event) => event.status === status);
    setCachedEvents(cacheKey, filteredEvents);
    return filteredEvents;
  }

  const query = new URLSearchParams({ status });
  if (governanceContext) {
    query.set("governance_context", governanceContext);
  }
  const response = await fetch(buildApiUrl(`/api/events/?${query.toString()}`), {
    headers: getAuthHeaders(),
  });
  if (!response.ok) throw new Error("Network error");

  const data = (await response.json()) as Event[];
  setCachedEvents(cacheKey, data);
  return data;
};

export const fetchEventsAttended = async (): Promise<Event[]> => {
  const records = await fetchMyAttendanceRecords();

  const latestByEvent = new Map<number, Event>();
  for (const record of records) {
    const eventId = Number(record.event_id);
    if (!Number.isFinite(eventId)) continue;

    latestByEvent.set(eventId, {
      id: eventId,
      name: record.event_name || `Event #${eventId}`,
      location: "N/A",
      start_datetime: record.time_in || "",
      end_datetime: record.time_out || record.time_in || "",
      status: "completed",
    });
  }

  return Array.from(latestByEvent.values());
};

export const fetchMyAttendanceRecords = async (): Promise<AttendanceRecord[]> => {
  const response = await fetch(buildApiUrl("/api/attendance/me/records"), {
    headers: getAuthHeaders(),
  });
  if (!response.ok) throw new Error(`Failed to fetch attendance history: ${response.status}`);

  const rows = (await response.json()) as Array<{
    attendances?: Array<{
      event_id: number;
      event_name?: string;
      time_in?: string;
      time_out?: string | null;
    }>;
  }>;

  if (!Array.isArray(rows) || rows.length === 0 || !Array.isArray(rows[0].attendances)) {
    return [];
  }

  return rows[0].attendances as AttendanceRecord[];
};
