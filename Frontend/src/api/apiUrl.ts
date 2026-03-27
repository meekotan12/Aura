const DEFAULT_LOCAL_API_BASE_URL = "http://localhost:8000";

const trimTrailingSlashes = (value: string): string => value.replace(/\/+$/, "");
const normalizeConfiguredApiBaseUrl = (value: string): string => {
  if (!value || value === "/api") {
    return value;
  }

  return value.replace(/\/api$/, "");
};

const isLocalHostname = (hostname: string): boolean =>
  hostname === "localhost" || hostname === "127.0.0.1";

const resolveApiBaseUrl = (): string => {
  const configuredApiBaseUrl = normalizeConfiguredApiBaseUrl(trimTrailingSlashes(
    (import.meta.env.VITE_API_URL || "").trim()
  ));

  if (configuredApiBaseUrl) {
    return configuredApiBaseUrl;
  }

  if (typeof window !== "undefined" && isLocalHostname(window.location.hostname)) {
    return DEFAULT_LOCAL_API_BASE_URL;
  }

  return "";
};

const API_BASE_URL = resolveApiBaseUrl();

const normalizePath = (path: string): string => {
  if (!path) {
    return "/";
  }

  return path.startsWith("/") ? path : `/${path}`;
};

export const buildApiUrl = (path: string): string => {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  const normalizedPath = normalizePath(path);

  if (!API_BASE_URL || API_BASE_URL === "/api") {
    return normalizedPath;
  }

  return `${API_BASE_URL}${normalizedPath}`;
};

export const buildAssetUrl = (path: string): string => {
  if (!path) {
    return path;
  }

  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  return buildApiUrl(path);
};

export const apiBaseUrl = API_BASE_URL;
