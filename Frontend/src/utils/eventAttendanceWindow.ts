import type { AttendanceRecord, Event } from "../api/eventsApi";

export type EventWindowStage =
  | "before_check_in"
  | "early_check_in"
  | "late_check_in"
  | "absent_check_in"
  | "sign_out_pending"
  | "sign_out_open"
  | "closed";

export type StudentEventActionState =
  | "not_open"
  | "sign_in"
  | "waiting_sign_out"
  | "sign_out"
  | "missed_check_in"
  | "done"
  | "closed";

const MANILA_TIMEZONE = "Asia/Manila";
const MANILA_OFFSET_SUFFIX = "+08:00";
const TIMEZONE_PATTERN = /([zZ]|[+-]\d{2}:\d{2})$/;

const clampMinutes = (value: number | null | undefined) =>
  Math.max(0, Number.isFinite(value) ? Number(value) : 0);

const hasValidAttendanceOverride = (
  event: Pick<
    Event,
    "start_datetime" | "present_until_override_at" | "late_until_override_at"
  >
) => {
  if (!event.present_until_override_at || !event.late_until_override_at) {
    return false;
  }

  const start = parseEventDateTime(event.start_datetime);
  const presentUntil = parseEventDateTime(event.present_until_override_at);
  const lateUntil = parseEventDateTime(event.late_until_override_at);

  if (
    !Number.isFinite(start.getTime()) ||
    !Number.isFinite(presentUntil.getTime()) ||
    !Number.isFinite(lateUntil.getTime())
  ) {
    return false;
  }

  return (
    presentUntil.getTime() > start.getTime() &&
    lateUntil.getTime() >= presentUntil.getTime()
  );
};

export const parseEventDateTime = (value?: string | null) => {
  if (!value) {
    return new Date(Number.NaN);
  }

  const normalizedValue = TIMEZONE_PATTERN.test(value)
    ? value
    : `${value}${MANILA_OFFSET_SUFFIX}`;
  return new Date(normalizedValue);
};

export const formatManilaDateTime = (value?: string | null) => {
  const parsed = parseEventDateTime(value);
  if (!Number.isFinite(parsed.getTime())) {
    return "Not set";
  }

  return parsed.toLocaleString("en-PH", {
    timeZone: MANILA_TIMEZONE,
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

export const getDerivedAbsenceCutoff = (
  event: Pick<
    Event,
    | "start_datetime"
    | "late_threshold_minutes"
    | "present_until_override_at"
    | "late_until_override_at"
  >
) => {
  return getEffectiveLateCutoff(event);
};

export const hasAttendanceOverrideWindow = (
  event: Pick<
    Event,
    "start_datetime" | "present_until_override_at" | "late_until_override_at"
  >
) => hasValidAttendanceOverride(event);

export const getEffectivePresentCutoff = (
  event: Pick<
    Event,
    "start_datetime" | "present_until_override_at" | "late_until_override_at"
  >
) => {
  if (hasValidAttendanceOverride(event) && event.present_until_override_at) {
    return parseEventDateTime(event.present_until_override_at);
  }

  return parseEventDateTime(event.start_datetime);
};

export const getEffectiveLateCutoff = (
  event: Pick<
    Event,
    | "start_datetime"
    | "late_threshold_minutes"
    | "present_until_override_at"
    | "late_until_override_at"
  >
) => {
  if (hasValidAttendanceOverride(event) && event.late_until_override_at) {
    return parseEventDateTime(event.late_until_override_at);
  }

  const start = parseEventDateTime(event.start_datetime);
  return new Date(start.getTime() + clampMinutes(event.late_threshold_minutes) * 60_000);
};

export const getSignOutCloseTime = (
  event: Pick<Event, "end_datetime" | "sign_out_grace_minutes" | "sign_out_override_until">
) => {
  const end = parseEventDateTime(event.end_datetime);
  const defaultClose = new Date(
    end.getTime() + clampMinutes(event.sign_out_grace_minutes) * 60_000
  );
  const overrideClose = parseEventDateTime(event.sign_out_override_until);

  if (Number.isFinite(overrideClose.getTime())) {
    return overrideClose.getTime() < defaultClose.getTime()
      ? overrideClose
      : defaultClose;
  }

  return defaultClose;
};

export const getSignOutOpenTime = (
  event: Pick<Event, "end_datetime" | "sign_out_open_delay_minutes">
) => {
  const end = parseEventDateTime(event.end_datetime);
  return new Date(
    end.getTime() + clampMinutes(event.sign_out_open_delay_minutes) * 60_000
  );
};

export const getEventWindowStage = (
  event: Pick<
    Event,
    | "start_datetime"
    | "end_datetime"
    | "early_check_in_minutes"
    | "late_threshold_minutes"
    | "sign_out_grace_minutes"
    | "sign_out_open_delay_minutes"
    | "sign_out_override_until"
    | "present_until_override_at"
    | "late_until_override_at"
  >,
  now = new Date()
): EventWindowStage => {
  const start = parseEventDateTime(event.start_datetime);
  const end = parseEventDateTime(event.end_datetime);
  const earlyCheckInOpensAt = new Date(
    start.getTime() - clampMinutes(event.early_check_in_minutes) * 60_000
  );
  const effectivePresentCutoff = getEffectivePresentCutoff(event);
  const effectiveLateCutoff = getEffectiveLateCutoff(event);
  const signOutOpenTime = getSignOutOpenTime(event);
  const effectiveSignOutClose = getSignOutCloseTime(event);

  if (now.getTime() < earlyCheckInOpensAt.getTime()) {
    return "before_check_in";
  }
  if (now.getTime() < effectivePresentCutoff.getTime()) {
    return "early_check_in";
  }
  if (now.getTime() >= signOutOpenTime.getTime()) {
    return now.getTime() <= effectiveSignOutClose.getTime() ? "sign_out_open" : "closed";
  }
  if (now.getTime() >= end.getTime()) {
    return "sign_out_pending";
  }
  if (now.getTime() <= effectiveLateCutoff.getTime()) {
    return "late_check_in";
  }
  return "absent_check_in";
};

export const getStudentEventActionState = (
  event: Pick<
    Event,
    | "start_datetime"
    | "end_datetime"
    | "early_check_in_minutes"
    | "late_threshold_minutes"
    | "sign_out_grace_minutes"
    | "sign_out_open_delay_minutes"
    | "sign_out_override_until"
    | "present_until_override_at"
    | "late_until_override_at"
  >,
  latestRecord?: Pick<AttendanceRecord, "time_out" | "completion_state"> | null,
  now = new Date()
): StudentEventActionState => {
  if (latestRecord?.completion_state === "completed" || latestRecord?.time_out) {
    return "done";
  }

  const stage = getEventWindowStage(event, now);
  if (latestRecord) {
    if (stage === "sign_out_open") {
      return "sign_out";
    }
    if (stage === "sign_out_pending") {
      return "waiting_sign_out";
    }
    if (stage === "closed") {
      return "closed";
    }
    return "waiting_sign_out";
  }

  if (stage === "before_check_in") {
    return "not_open";
  }
  if (stage === "early_check_in" || stage === "late_check_in" || stage === "absent_check_in") {
    return "sign_in";
  }
  if (stage === "sign_out_open") {
    return "missed_check_in";
  }
  return "closed";
};
