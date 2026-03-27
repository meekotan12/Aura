import { hasAnyRole } from "../../utils/roleUtils";
import { getStoredUser } from "./sessionStore";

type RawStoredUser = {
  email?: unknown;
  roles?: unknown;
  id?: unknown;
  user_id?: unknown;
  firstName?: unknown;
  first_name?: unknown;
  lastName?: unknown;
  last_name?: unknown;
  schoolId?: unknown;
  school_id?: unknown;
  schoolName?: unknown;
  school_name?: unknown;
  schoolCode?: unknown;
  school_code?: unknown;
  mustChangePassword?: unknown;
  must_change_password?: unknown;
};

export interface StoredUserSession {
  email: string | null;
  roles: string[];
  id: number | null;
  firstName: string | null;
  lastName: string | null;
  schoolId: number | null;
  schoolName: string | null;
  schoolCode: string | null;
  mustChangePassword: boolean;
}

const asString = (value: unknown): string | null => {
  if (typeof value !== "string") {
    return null;
  }

  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
};

const asNumber = (value: unknown): number | null => {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
};

const asRoleList = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((role) => asString(role))
    .filter((role): role is string => role !== null);
};

export const readStoredUserSession = (): StoredUserSession | null => {
  const raw = getStoredUser();
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as RawStoredUser;
    return {
      email: asString(parsed.email),
      roles: asRoleList(parsed.roles),
      id: asNumber(parsed.id) ?? asNumber(parsed.user_id),
      firstName: asString(parsed.firstName) ?? asString(parsed.first_name),
      lastName: asString(parsed.lastName) ?? asString(parsed.last_name),
      schoolId: asNumber(parsed.schoolId) ?? asNumber(parsed.school_id),
      schoolName: asString(parsed.schoolName) ?? asString(parsed.school_name),
      schoolCode: asString(parsed.schoolCode) ?? asString(parsed.school_code),
      mustChangePassword: Boolean(
        parsed.mustChangePassword ?? parsed.must_change_password
      ),
    };
  } catch {
    return null;
  }
};

export const getStoredUserId = (): number | null =>
  readStoredUserSession()?.id ?? null;

export const getStoredUserRoles = (): string[] =>
  readStoredUserSession()?.roles ?? [];

export const hasStoredUserRole = (...roleNames: string[]): boolean =>
  hasAnyRole(getStoredUserRoles(), ...roleNames);

export const isStoredCampusAdmin = (): boolean =>
  hasStoredUserRole("campus_admin");

export const isStoredPlatformAdmin = (): boolean => {
  const session = readStoredUserSession();
  if (!session) {
    return false;
  }

  return hasAnyRole(session.roles, "admin") && session.schoolId == null;
};

export const getStoredUserDisplayName = (): string | null => {
  const session = readStoredUserSession();
  if (!session) {
    return null;
  }

  const fullName = [session.firstName, session.lastName]
    .filter(Boolean)
    .join(" ")
    .trim();

  return fullName || session.email || null;
};
