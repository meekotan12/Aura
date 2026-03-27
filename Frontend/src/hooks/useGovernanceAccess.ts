import { useEffect, useState } from "react";

import {
  fetchMyGovernanceAccess,
  GovernanceAccessResponse,
  GovernancePermissionCode,
} from "../api/governanceHierarchyApi";
import { getStoredUserId } from "../lib/auth/storedUser";

type UseGovernanceAccessOptions = {
  enabled?: boolean;
  forceRefresh?: boolean;
};

let cachedUserId: number | null = null;
let cachedAccess: GovernanceAccessResponse | null = null;
let inflightRequest: Promise<GovernanceAccessResponse> | null = null;
const GOVERNANCE_ACCESS_STORAGE_KEY = "valid8.governance.access";
const GOVERNANCE_ACCESS_UPDATED_EVENT = "valid8:governance-access-updated";

const parseStoredGovernanceAccess = (): GovernanceAccessResponse | null => {
  try {
    const raw = localStorage.getItem(GOVERNANCE_ACCESS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as GovernanceAccessResponse;
    if (
      typeof parsed?.user_id !== "number" ||
      typeof parsed?.school_id !== "number" ||
      !Array.isArray(parsed?.permission_codes) ||
      !Array.isArray(parsed?.units)
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
};

const writeStoredGovernanceAccess = (access: GovernanceAccessResponse | null) => {
  if (!access) {
    localStorage.removeItem(GOVERNANCE_ACCESS_STORAGE_KEY);
  } else {
    localStorage.setItem(GOVERNANCE_ACCESS_STORAGE_KEY, JSON.stringify(access));
  }

  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(GOVERNANCE_ACCESS_UPDATED_EVENT));
  }
};

export const getStoredGovernanceAccess = (): GovernanceAccessResponse | null => {
  const currentUserId = getStoredUserId();
  const storedAccess = parseStoredGovernanceAccess();
  if (!storedAccess || storedAccess.user_id !== currentUserId) {
    return null;
  }
  return storedAccess;
};

const syncCacheWithCurrentUser = () => {
  const currentUserId = getStoredUserId();
  if (cachedUserId !== currentUserId) {
    cachedUserId = currentUserId;
    cachedAccess = getStoredGovernanceAccess();
    inflightRequest = null;
  }
};

const loadGovernanceAccess = async (forceRefresh = false): Promise<GovernanceAccessResponse> => {
  syncCacheWithCurrentUser();

  if (!forceRefresh && cachedAccess) {
    return cachedAccess;
  }

  if (!forceRefresh && inflightRequest) {
    return inflightRequest;
  }

  inflightRequest = fetchMyGovernanceAccess()
    .then((access) => {
      cachedAccess = access;
      cachedUserId = access.user_id;
      writeStoredGovernanceAccess(access);
      return access;
    })
    .finally(() => {
      inflightRequest = null;
    });

  return inflightRequest;
};

export const clearGovernanceAccessCache = () => {
  cachedAccess = null;
  inflightRequest = null;
  cachedUserId = getStoredUserId();
  writeStoredGovernanceAccess(null);
};

export const primeGovernanceAccessCache = async (forceRefresh = true) => {
  try {
    return await loadGovernanceAccess(forceRefresh);
  } catch {
    writeStoredGovernanceAccess(null);
    return null;
  }
};

export const hasGovernancePermission = (
  access: GovernanceAccessResponse | null,
  permissionCode: GovernancePermissionCode
) => {
  return access?.permission_codes.includes(permissionCode) ?? false;
};

export const useGovernanceAccess = (
  options: UseGovernanceAccessOptions = {}
) => {
  const { enabled = true, forceRefresh = false } = options;
  const [access, setAccess] = useState<GovernanceAccessResponse | null>(
    enabled && !forceRefresh ? cachedAccess || getStoredGovernanceAccess() : null
  );
  const [loading, setLoading] = useState(enabled && (!cachedAccess || forceRefresh));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      setError(null);
      return;
    }

    let isMounted = true;
    setLoading(!cachedAccess || forceRefresh);
    setError(null);

    loadGovernanceAccess(forceRefresh)
      .then((result) => {
        if (!isMounted) return;
        setAccess(result);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load governance access");
      })
      .finally(() => {
        if (!isMounted) return;
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [enabled, forceRefresh]);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") {
      return;
    }

    const syncFromCache = () => {
      syncCacheWithCurrentUser();
      setAccess(cachedAccess || getStoredGovernanceAccess());
      setLoading(false);
      setError(null);
    };

    window.addEventListener(GOVERNANCE_ACCESS_UPDATED_EVENT, syncFromCache);
    window.addEventListener("storage", syncFromCache);

    return () => {
      window.removeEventListener(GOVERNANCE_ACCESS_UPDATED_EVENT, syncFromCache);
      window.removeEventListener("storage", syncFromCache);
    };
  }, [enabled]);

  return {
    access,
    loading,
    error,
    hasPermission: (permissionCode: GovernancePermissionCode) =>
      hasGovernancePermission(access, permissionCode),
  };
};
