const MANILA_TIMEZONE = "Asia/Manila";
const TIMEZONE_PATTERN = /([zZ]|[+-]\d{2}:\d{2})$/;

export const parseAttendanceDateTime = (value?: string | null) => {
  if (!value) {
    return new Date(Number.NaN);
  }

  const normalizedValue = TIMEZONE_PATTERN.test(value) ? value : `${value}Z`;
  return new Date(normalizedValue);
};

export const getAttendanceTimestamp = (value?: string | null) =>
  parseAttendanceDateTime(value).getTime();

const formatAttendanceValue = (
  value: string | null | undefined,
  options: Intl.DateTimeFormatOptions,
  fallback: string
) => {
  const parsed = parseAttendanceDateTime(value);
  if (!Number.isFinite(parsed.getTime())) {
    return fallback;
  }

  return new Intl.DateTimeFormat("en-PH", {
    timeZone: MANILA_TIMEZONE,
    ...options,
  }).format(parsed);
};

export const formatAttendanceDate = (value?: string | null, fallback = "N/A") =>
  formatAttendanceValue(
    value,
    {
      month: "short",
      day: "numeric",
      year: "numeric",
    },
    fallback
  );

export const formatAttendanceTime = (value?: string | null, fallback = "N/A") =>
  formatAttendanceValue(
    value,
    {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    },
    fallback
  );

export const formatAttendanceDateTime = (
  value?: string | null,
  fallback = "Not set"
) =>
  formatAttendanceValue(
    value,
    {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    },
    fallback
  );
