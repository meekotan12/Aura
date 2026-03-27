import { useEffect, useMemo, useState } from "react";

import {
  fetchGovernanceUnitDetails,
  GovernanceUnitDetail,
  GovernancePermissionCode,
  GovernanceUnitType,
} from "../api/governanceHierarchyApi";
import { normalizeLogoUrl } from "../api/schoolSettingsApi";
import { useUser } from "../context/UserContext";
import { readStoredUserSession } from "../lib/auth/storedUser";
import { useGovernanceAccess } from "./useGovernanceAccess";

const WORKSPACE_FALLBACKS: Record<
  GovernanceUnitType,
  {
    officerLabel: string;
    unitLabel: string;
  }
> = {
  SSG: {
    officerLabel: "SSG Officer",
    unitLabel: "Supreme Students Government",
  },
  SG: {
    officerLabel: "SG Officer",
    unitLabel: "Student Government",
  },
  ORG: {
    officerLabel: "ORG Officer",
    unitLabel: "Student Organization",
  },
};

export const useGovernanceWorkspace = (unitType: GovernanceUnitType) => {
  const session = useMemo(() => readStoredUserSession(), []);
  const { branding } = useUser();
  const governance = useGovernanceAccess();
  const accessUnit = useMemo(
    () => governance.access?.units.find((unit) => unit.unit_type === unitType) ?? null,
    [governance.access, unitType]
  );
  const scopedPermissionCodes = useMemo(
    () => new Set(accessUnit?.permission_codes ?? []),
    [accessUnit]
  );
  const [governanceUnit, setGovernanceUnit] = useState<GovernanceUnitDetail | null>(null);
  const [workspaceLoading, setWorkspaceLoading] = useState(Boolean(accessUnit));
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  useEffect(() => {
    if (governance.loading) return;
    if (!accessUnit) {
      setGovernanceUnit(null);
      setWorkspaceLoading(false);
      return;
    }

    let isMounted = true;
    setWorkspaceLoading(true);
    setWorkspaceError(null);

    fetchGovernanceUnitDetails(accessUnit.governance_unit_id)
      .then((result) => {
        if (!isMounted) return;
        setGovernanceUnit(result);
      })
      .catch((error) => {
        if (!isMounted) return;
        setWorkspaceError(
          error instanceof Error ? error.message : `Failed to load the ${unitType} workspace`
        );
      })
      .finally(() => {
        if (!isMounted) return;
        setWorkspaceLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [accessUnit?.governance_unit_id, governance.loading, unitType]);

  const currentOfficer = useMemo(() => {
    if (!governanceUnit || typeof session?.id !== "number") return null;
    return governanceUnit.members.find((member) => member.user_id === session.id) ?? null;
  }, [governanceUnit, session?.id]);

  const fallback = WORKSPACE_FALLBACKS[unitType];

  return {
    access: governance.access,
    accessLoading: governance.loading,
    accessError: governance.error,
    hasPermission: (permissionCode: GovernancePermissionCode) =>
      scopedPermissionCodes.has(permissionCode),
    accessUnit,
    governanceUnit,
    workspaceLoading,
    workspaceError,
    schoolId: branding?.school_id ?? session?.schoolId ?? null,
    campusName: branding?.school_name || session?.schoolName || "Campus",
    logoUrl: normalizeLogoUrl(branding?.logo_url),
    officerName:
      [session?.firstName, session?.lastName].filter(Boolean).join(" ").trim() || fallback.officerLabel,
    officerPosition: currentOfficer?.position_title || fallback.officerLabel,
    officerMembership: currentOfficer,
    fallbackUnitLabel: fallback.unitLabel,
    unitType,
  };
};

export default useGovernanceWorkspace;
