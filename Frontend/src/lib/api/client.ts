import { buildApiUrl } from "../../api/apiUrl";
import {
  clearStoredAuthSession,
  consumeStoredAuthStatusMessage,
  getStoredAuthToken,
  setStoredAuthStatusMessage,
} from "../auth/sessionStore";

export const INACTIVE_SCHOOL_DETAIL = "This account's school is inactive.";

let inactiveSchoolRedirectInProgress = false;
let restoreInterceptedFetch: (() => void) | null = null;

const headersInitToObject = (headers?: HeadersInit): Record<string, string> => {
  if (!headers) {
    return {};
  }

  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }

  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }

  return { ...headers };
};

const hasHeader = (headers: Record<string, string>, headerName: string): boolean =>
  Object.keys(headers).some((key) => key.toLowerCase() === headerName.toLowerCase());

const resolveFetchInput = (input: RequestInfo | URL): RequestInfo | URL => {
  if (typeof input !== "string") {
    return input;
  }

  return buildApiUrl(input);
};

const parseResponseDetail = async (response: Response): Promise<unknown> => {
  const clonedResponse = response.clone();

  try {
    const payload = await clonedResponse.json();
    if (payload && typeof payload === "object") {
      return (payload as { detail?: unknown }).detail ?? payload;
    }
    return payload;
  } catch {
    try {
      const raw = await clonedResponse.text();
      return raw || null;
    } catch {
      return null;
    }
  }
};

const handleAuthSideEffects = async (response: Response): Promise<void> => {
  if (response.status === 401) {
    clearStoredAuthSession();
    return;
  }

  if (response.status !== 403) {
    return;
  }

  const detail = await parseResponseDetail(response);
  if (detail !== INACTIVE_SCHOOL_DETAIL || inactiveSchoolRedirectInProgress) {
    return;
  }

  inactiveSchoolRedirectInProgress = true;
  setStoredAuthStatusMessage(INACTIVE_SCHOOL_DETAIL);
  clearStoredAuthSession();

  if (typeof window !== "undefined") {
    window.location.replace("/login");
  }
};

export const installApiFetchInterceptor = (): (() => void) => {
  if (typeof window === "undefined") {
    return () => {};
  }

  if (restoreInterceptedFetch) {
    return restoreInterceptedFetch;
  }

  const originalFetch = window.fetch.bind(window);
  const interceptedFetch: typeof window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    await handleAuthSideEffects(response);
    return response;
  };

  window.fetch = interceptedFetch;

  restoreInterceptedFetch = () => {
    if (window.fetch === interceptedFetch) {
      window.fetch = originalFetch;
    }
    restoreInterceptedFetch = null;
  };

  return restoreInterceptedFetch;
};

export const apiFetch = async (
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> => {
  const response = await fetch(resolveFetchInput(input), init);
  await handleAuthSideEffects(response);
  return response;
};

export const buildAuthHeaders = (
  authToken?: string | null,
  extraHeaders?: HeadersInit
): HeadersInit => {
  const token = authToken ?? getStoredAuthToken();
  if (!token) {
    throw new Error("No authentication token found");
  }

  return {
    ...headersInitToObject(extraHeaders),
    Authorization: `Bearer ${token}`,
  };
};

export type ApiRequestInit = Omit<RequestInit, "body"> & {
  auth?: boolean;
  json?: unknown;
  body?: BodyInit | null;
};

export const apiRequest = async (
  input: RequestInfo | URL,
  init: ApiRequestInit = {}
): Promise<Response> => {
  const { auth = false, headers, json, body, ...rest } = init;
  const nextHeaders = headersInitToObject(headers);

  if (json !== undefined && !hasHeader(nextHeaders, "Content-Type")) {
    nextHeaders["Content-Type"] = "application/json";
  }

  return apiFetch(input, {
    ...rest,
    headers: auth ? buildAuthHeaders(undefined, nextHeaders) : nextHeaders,
    body: json !== undefined ? JSON.stringify(json) : body,
  });
};

export const apiJsonRequest = async <T>(
  input: RequestInfo | URL,
  init: ApiRequestInit | undefined,
  fallback: string
): Promise<T> => {
  const response = await apiRequest(input, init);
  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, fallback));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
};

export const apiVoidRequest = async (
  input: RequestInfo | URL,
  init: ApiRequestInit | undefined,
  fallback: string
): Promise<void> => {
  const response = await apiRequest(input, init);
  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, fallback));
  }
};

export const extractApiErrorMessage = async (
  response: Response,
  fallback: string
): Promise<string> => {
  const body = await response.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return fallback;
  }

  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail;
  }

  if (detail && typeof detail === "object") {
    const nestedMessage = (detail as { message?: unknown; reason?: unknown }).message;
    if (typeof nestedMessage === "string" && nestedMessage.trim().length > 0) {
      return nestedMessage;
    }

    const nestedReason = (detail as { reason?: unknown }).reason;
    if (typeof nestedReason === "string" && nestedReason.trim().length > 0) {
      return nestedReason;
    }

    return JSON.stringify(detail);
  }

  const message = (body as { message?: unknown }).message;
  if (typeof message === "string" && message.trim().length > 0) {
    return message;
  }

  const error = (body as { error?: unknown }).error;
  if (typeof error === "string" && error.trim().length > 0) {
    return error;
  }

  return fallback;
};

export const consumeAuthStatusMessage = (): string | null => {
  const message = consumeStoredAuthStatusMessage();
  if (!message) {
    return null;
  }

  inactiveSchoolRedirectInProgress = false;
  return message;
};
