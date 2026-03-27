const AUTH_TOKEN_KEY = "authToken";
const LEGACY_AUTH_TOKEN_KEYS = ["token", "access_token"] as const;
const USER_KEY = "user";
const USER_DATA_KEY = "userData";
const AUTH_STATUS_MESSAGE_KEY = "valid8.authStatusMessage";

const hasStorage = (): boolean => typeof window !== "undefined";

export const getStoredAuthToken = (): string | null => {
  if (!hasStorage()) {
    return null;
  }

  return (
    localStorage.getItem(AUTH_TOKEN_KEY) ||
    LEGACY_AUTH_TOKEN_KEYS.map((key) => localStorage.getItem(key)).find(Boolean) ||
    null
  );
};

export const persistStoredAuthToken = (token: string): void => {
  if (!hasStorage()) {
    return;
  }

  localStorage.setItem(AUTH_TOKEN_KEY, token);
  LEGACY_AUTH_TOKEN_KEYS.forEach((key) => localStorage.removeItem(key));
};

export const migrateLegacyAuthStorage = (): void => {
  if (!hasStorage()) {
    return;
  }

  const canonicalToken = localStorage.getItem(AUTH_TOKEN_KEY);
  if (canonicalToken) {
    LEGACY_AUTH_TOKEN_KEYS.forEach((key) => localStorage.removeItem(key));
    return;
  }

  const legacyToken = LEGACY_AUTH_TOKEN_KEYS.map((key) => localStorage.getItem(key)).find(Boolean);
  if (!legacyToken) {
    return;
  }

  localStorage.setItem(AUTH_TOKEN_KEY, legacyToken);
  LEGACY_AUTH_TOKEN_KEYS.forEach((key) => localStorage.removeItem(key));
};

export const clearStoredAuthSession = (): void => {
  if (!hasStorage()) {
    return;
  }

  localStorage.removeItem(AUTH_TOKEN_KEY);
  LEGACY_AUTH_TOKEN_KEYS.forEach((key) => localStorage.removeItem(key));
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(USER_DATA_KEY);
};

export const setStoredUser = (value: string): void => {
  if (!hasStorage()) {
    return;
  }

  localStorage.setItem(USER_KEY, value);
};

export const getStoredUser = (): string | null => {
  if (!hasStorage()) {
    return null;
  }

  return localStorage.getItem(USER_KEY);
};

export const setStoredUserData = (value: string): void => {
  if (!hasStorage()) {
    return;
  }

  localStorage.setItem(USER_DATA_KEY, value);
};

export const getStoredUserData = (): string | null => {
  if (!hasStorage()) {
    return null;
  }

  return localStorage.getItem(USER_DATA_KEY);
};

export const setStoredAuthStatusMessage = (message: string): void => {
  if (!hasStorage()) {
    return;
  }

  sessionStorage.setItem(AUTH_STATUS_MESSAGE_KEY, message);
};

export const consumeStoredAuthStatusMessage = (): string | null => {
  if (!hasStorage()) {
    return null;
  }

  const message = sessionStorage.getItem(AUTH_STATUS_MESSAGE_KEY);
  if (!message) {
    return null;
  }

  sessionStorage.removeItem(AUTH_STATUS_MESSAGE_KEY);
  return message;
};

