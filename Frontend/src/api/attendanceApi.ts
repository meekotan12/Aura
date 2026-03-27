import { apiJsonRequest } from "../lib/api/client";

export type GovernanceContext = "SSG" | "SG" | "ORG";

export type AttendanceStatusResponse = {
  has_signed_in: boolean;
  has_signed_out: boolean;
  attendance_status: "present" | "late" | "absent" | null;
  can_sign_in: boolean;
  can_sign_out: boolean;
  sign_in_time: string | null;
  sign_out_time: string | null;
};

export type AttendanceActionResponse = {
  attendance_status: "present" | "late" | "absent";
  sign_in_time: string | null;
  sign_out_time: string | null;
};

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
    notes?: string | null;
  };
  student_id: string | null;
  student_name: string;
}

export interface StudentAttendanceRecord {
  id: number;
  student_id: string | null;
  full_name: string;
  department_name: string | null;
  program_name: string | null;
  year_level: string;
  total_events: number;
  attendance_rate: number;
  last_attendance: string | null;
}

export interface AttendanceDetail {
  id: number;
  event_id: number;
  event_name: string;
  event_location: string;
  event_date: string;
  time_in: string | null;
  time_out: string | null;
  status: "present" | "late" | "absent" | "excused";
  method: string;
  notes: string | null;
  duration_minutes: number | null;
}

export interface StudentAttendanceReport {
  student: {
    student_id: string | null;
    student_name: string;
    total_events: number;
    attended_events: number;
    late_events: number;
    absent_events: number;
    excused_events: number;
    attendance_rate: number;
    last_attendance: string | null;
  };
  attendance_records: AttendanceDetail[];
  monthly_stats: Record<
    string,
    { present: number; late: number; absent: number; excused: number }
  >;
  event_type_stats: Record<string, number>;
}

export interface EventAttendanceReport {
  event_name: string;
  event_date: string;
  event_location: string;
  total_participants: number;
  attendees: number;
  late_attendees: number;
  absentees: number;
  attendance_rate: number;
  programs: Array<{ id: number; name: string }>;
  program_breakdown: Array<{
    program: string;
    total: number;
    present: number;
    late: number;
    absent: number;
  }>;
}

export interface ManualAttendanceActionResponse {
  action?: "time_in" | "time_out";
  updated_count?: number;
}

const buildQueryPath = (
  path: string,
  params: Record<string, string | number | boolean | null | undefined> = {}
) => {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    query.set(key, String(value));
  });

  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
};

const withGovernanceContext = (
  path: string,
  governanceContext?: GovernanceContext,
  params: Record<string, string | number | boolean | null | undefined> = {}
) =>
  buildQueryPath(path, {
    ...params,
    governance_context: governanceContext,
  });

export interface StudentAttendanceOverviewParams {
  governanceContext?: GovernanceContext;
  startDate?: string;
  endDate?: string;
}

export interface StudentAttendanceReportParams extends StudentAttendanceOverviewParams {
  status?: "all" | "present" | "late" | "absent" | "excused";
}

export interface ManualAttendancePayload {
  eventId: number;
  studentId: string;
  notes?: string | null;
  governanceContext?: GovernanceContext;
}

const requestAttendanceJson = <T>(
  path: string,
  init: Parameters<typeof apiJsonRequest<T>>[1],
  fallback: string
) => apiJsonRequest<T>(path, { auth: true, ...init }, fallback);

export const fetchAttendanceStatus = async (
  eventId: number
): Promise<AttendanceStatusResponse> =>
  requestAttendanceJson<AttendanceStatusResponse>(
    `/api/events/${eventId}/attendance-status`,
    { method: "GET" },
    "Failed to fetch attendance status"
  );

export const signInToEvent = async (eventId: number): Promise<AttendanceActionResponse> =>
  requestAttendanceJson<AttendanceActionResponse>(
    `/api/events/${eventId}/sign-in`,
    { method: "POST", json: {} },
    "Failed to sign in to the event"
  );

export const signOutOfEvent = async (eventId: number): Promise<AttendanceActionResponse> =>
  requestAttendanceJson<AttendanceActionResponse>(
    `/api/events/${eventId}/sign-out`,
    { method: "POST", json: {} },
    "Failed to sign out of the event"
  );

export const fetchStudentAttendanceOverview = async ({
  governanceContext,
  startDate,
  endDate,
}: StudentAttendanceOverviewParams = {}): Promise<StudentAttendanceRecord[]> =>
  requestAttendanceJson<StudentAttendanceRecord[]>(
    withGovernanceContext("/api/attendance/students/overview", governanceContext, {
      start_date: startDate,
      end_date: endDate,
    }),
    { method: "GET" },
    "Failed to fetch attendance records"
  );

export const fetchStudentAttendanceReport = async (
  studentId: string,
  { governanceContext, startDate, endDate, status }: StudentAttendanceReportParams = {}
): Promise<StudentAttendanceReport> =>
  requestAttendanceJson<StudentAttendanceReport>(
    withGovernanceContext(`/api/attendance/students/${studentId}/report`, governanceContext, {
      start_date: startDate,
      end_date: endDate,
      status: status && status !== "all" ? status : undefined,
    }),
    { method: "GET" },
    "Failed to fetch student attendance report"
  );

export const fetchEventAttendanceReport = async (
  eventId: number
): Promise<EventAttendanceReport> =>
  requestAttendanceJson<EventAttendanceReport>(
    `/api/attendance/events/${eventId}/report`,
    { method: "GET" },
    "Failed to fetch attendance report"
  );

export const fetchActiveEventAttendances = async (
  eventId: number,
  governanceContext?: GovernanceContext
): Promise<EventAttendanceWithStudent[]> =>
  requestAttendanceJson<EventAttendanceWithStudent[]>(
    withGovernanceContext(`/api/attendance/events/${eventId}/attendances`, governanceContext, {
      active_only: true,
    }),
    { method: "GET" },
    "Failed to fetch active attendances"
  );

export const recordManualAttendance = async ({
  eventId,
  studentId,
  notes,
  governanceContext,
}: ManualAttendancePayload): Promise<ManualAttendanceActionResponse> =>
  requestAttendanceJson<ManualAttendanceActionResponse>(
    withGovernanceContext("/api/attendance/manual", governanceContext),
    {
      method: "POST",
      json: {
        event_id: eventId,
        student_id: studentId,
        notes: notes ?? null,
      },
    },
    "Failed to record manual attendance"
  );

export const recordAttendanceTimeOut = async (
  attendanceId: number,
  governanceContext?: GovernanceContext
): Promise<ManualAttendanceActionResponse> =>
  requestAttendanceJson<ManualAttendanceActionResponse>(
    withGovernanceContext(`/api/attendance/${attendanceId}/time-out`, governanceContext),
    { method: "POST", json: {} },
    "Failed to record time out"
  );

export const markAbsentWithoutTimeOut = async (
  eventId: number,
  governanceContext?: GovernanceContext
): Promise<ManualAttendanceActionResponse> =>
  requestAttendanceJson<ManualAttendanceActionResponse>(
    withGovernanceContext("/api/attendance/mark-absent-no-timeout", governanceContext, {
      event_id: eventId,
    }),
    { method: "POST", json: {} },
    "Failed to mark students absent"
  );
