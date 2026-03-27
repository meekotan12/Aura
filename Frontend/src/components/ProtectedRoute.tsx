import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { isStudentFaceEnrollmentRequired } from "../api/studentFaceEnrollmentApi";
import {
  GovernancePermissionCode,
  GovernanceUnitType,
} from "../api/governanceHierarchyApi";
import { useGovernanceAccess } from "../hooks/useGovernanceAccess";
import { readStoredUserSession } from "../lib/auth/storedUser";
import { sanitizeRedirectPath } from "../utils/redirects";
import { normalizeRole } from "../utils/roleUtils";

const ProtectedRoute = ({
  allowedRoles,
  requiredGovernanceUnitTypes,
  requiredGovernancePermissions,
  redirectTo = "/unauthorized",
}: {
  allowedRoles: string[];
  requiredGovernanceUnitTypes?: GovernanceUnitType[];
  requiredGovernancePermissions?: GovernancePermissionCode[];
  redirectTo?: string;
}) => {
  const location = useLocation();
  const [storedUser, setStoredUser] = useState(() => readStoredUserSession());

  useEffect(() => {
    const syncStoredUser = () => {
      setStoredUser(readStoredUserSession());
    };

    window.addEventListener("storage", syncStoredUser);
    window.addEventListener("focus", syncStoredUser);
    document.addEventListener("visibilitychange", syncStoredUser);

    return () => {
      window.removeEventListener("storage", syncStoredUser);
      window.removeEventListener("focus", syncStoredUser);
      document.removeEventListener("visibilitychange", syncStoredUser);
    };
  }, []);

  const userRoles = useMemo(
    () => storedUser?.roles.map(normalizeRole) ?? [],
    [storedUser]
  );
  const allowed = useMemo(() => allowedRoles.map(normalizeRole), [allowedRoles]);
  const safeRedirectTo = useMemo(
    () => sanitizeRedirectPath(redirectTo, "/unauthorized"),
    [redirectTo]
  );
  const requiresGovernanceAccess = Boolean(
    requiredGovernanceUnitTypes?.length || requiredGovernancePermissions?.length
  );
  const governanceAccess = useGovernanceAccess({
    enabled: requiresGovernanceAccess && Boolean(storedUser) && userRoles.length > 0,
  });
  const mustChangePassword = Boolean(storedUser?.mustChangePassword);

  const requiresStudentFaceEnrollment =
    userRoles.includes("student") &&
    isStudentFaceEnrollmentRequired(storedUser?.id ?? null);

  if (!storedUser) {
    return <Navigate to="/" replace />;
  }

  if (!Array.isArray(storedUser.roles)) {
    return <Navigate to="/" replace />;
  }

  if (mustChangePassword && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }

  if (
    requiresStudentFaceEnrollment &&
    location.pathname !== "/student_face_registration" &&
    location.pathname !== "/change-password"
  ) {
    return <Navigate to="/student_face_registration" replace />;
  }

  // Check if the user has at least one allowed role
  const hasAccess = allowed.some((role) => userRoles.includes(role));

  if (!hasAccess) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (requiresGovernanceAccess) {
    if (governanceAccess.loading) {
      return (
        <div className="route-loader" role="status" aria-live="polite">
          <div className="route-loader__spinner" />
          <p>Checking governance access...</p>
        </div>
      );
    }

    if (governanceAccess.error) {
      return <Navigate to={safeRedirectTo} replace />;
    }

    if (requiredGovernanceUnitTypes?.length) {
      const scopedUnits =
        governanceAccess.access?.units.filter((unit) =>
          requiredGovernanceUnitTypes.includes(unit.unit_type)
        ) ?? [];
      const hasRequiredUnitType = scopedUnits.length > 0;
      if (!hasRequiredUnitType) {
        return <Navigate to={safeRedirectTo} replace />;
      }

      if (requiredGovernancePermissions?.length) {
        const hasScopedPermission = scopedUnits.some((unit) =>
          requiredGovernancePermissions.some((permissionCode) =>
            unit.permission_codes.includes(permissionCode)
          )
        );
        if (!hasScopedPermission) {
          return <Navigate to={safeRedirectTo} replace />;
        }
      }
    }

    if (requiredGovernancePermissions?.length && !requiredGovernanceUnitTypes?.length) {
      const hasRequiredPermission = requiredGovernancePermissions.some((permissionCode) =>
        governanceAccess.hasPermission(permissionCode)
      );
      if (!hasRequiredPermission) {
        return <Navigate to={safeRedirectTo} replace />;
      }
    }
  }

  return <Outlet />;
};

export default ProtectedRoute;
