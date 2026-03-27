import { FormEvent, useEffect, useMemo, useState } from "react";
import Modal from "react-modal";
import {
  FaArrowLeft,
  FaEdit,
  FaPlus,
  FaProjectDiagram,
  FaSearch,
  FaTrashAlt,
  FaUsers,
} from "react-icons/fa";

import {
  assignGovernanceMember,
  createGovernanceUnit,
  deleteGovernanceMember,
  deleteGovernanceUnit,
  fetchGovernanceUnitDetails,
  fetchGovernanceUnits,
  GovernanceMemberItem,
  GovernancePermissionCode,
  GovernanceStudentCandidate,
  GovernanceUnitDetail,
  searchGovernanceStudentCandidates,
  updateGovernanceMember,
  updateGovernanceUnit,
} from "../api/governanceHierarchyApi";
import { fetchAcademicCatalog } from "../api/academicApi";
import NavbarSSG from "../components/NavbarSSG";
import "../css/GovernanceHierarchyManagement.css";
import "../css/SsgWorkspace.css";
import { useSsgWorkspace } from "../hooks/useSsgWorkspace";
import { primeGovernanceAccessCache } from "../hooks/useGovernanceAccess";
import {
  formatUserDisplayName,
  getAvatarToneClass,
  getInitials,
} from "../utils/ssgWorkspaceHelpers";

interface Department {
  id: number;
  name: string;
}

interface Program {
  id: number;
  name: string;
}

interface MemberDraftState {
  selectedCandidate: GovernanceStudentCandidate | null;
  searchTerm: string;
  positionTitle: string;
  permissionCodes: GovernancePermissionCode[];
}

interface SgCreateFormState {
  unit_code: string;
  unit_name: string;
  description: string;
  department_id: string;
}

interface SgInfoFormState {
  unit_code: string;
  unit_name: string;
  description: string;
}

type ManageSgTab = "units" | "members" | "permissions";

const permissionOptions = [
  {
    code: "create_org" as GovernancePermissionCode,
    label: "Create ORG",
    description: "Allow this SG officer to create ORG units within the department.",
  },
  {
    code: "manage_members" as GovernancePermissionCode,
    label: "Manage Members",
    description: "Allow this SG officer to manage ORG member assignments and updates.",
  },
  {
    code: "manage_events" as GovernancePermissionCode,
    label: "Manage Events",
    description: "Allow this SG officer to access SG event management.",
  },
  {
    code: "manage_attendance" as GovernancePermissionCode,
    label: "Manage Attendance",
    description: "Allow this SG officer to access records and manual attendance.",
  },
  {
    code: "manage_announcements" as GovernancePermissionCode,
    label: "Manage Announcements",
    description: "Allow this SG officer to publish SG announcements.",
  },
  {
    code: "view_students" as GovernancePermissionCode,
    label: "View Students",
    description: "Allow this SG officer to view students inside the department scope.",
  },
  {
    code: "manage_students" as GovernancePermissionCode,
    label: "Manage Students",
    description: "Allow this SG officer to manage governance notes within the department scope.",
  },
  {
    code: "assign_permissions" as GovernancePermissionCode,
    label: "Assign Permissions",
    description: "Allow this SG officer to update ORG officer permissions.",
  },
] as const;

const permissionLabelMap = new Map(
  permissionOptions.map((permission) => [permission.code, permission.label] as const)
);

const emptyMemberDraft: MemberDraftState = {
  selectedCandidate: null,
  searchTerm: "",
  positionTitle: "",
  permissionCodes: [],
};

const emptyCreateForm: SgCreateFormState = {
  unit_code: "",
  unit_name: "",
  description: "",
  department_id: "",
};

const emptyInfoForm: SgInfoFormState = {
  unit_code: "",
  unit_name: "",
  description: "",
};

Modal.setAppElement("#root");

const sortGovernanceUnits = (units: GovernanceUnitDetail[]) =>
  [...units].sort((left, right) => {
    const leftDepartment = left.department_id ?? 0;
    const rightDepartment = right.department_id ?? 0;
    if (leftDepartment !== rightDepartment) return leftDepartment - rightDepartment;
    return left.unit_name.localeCompare(right.unit_name);
  });

const ManageSg = () => {
  const { accessLoading, campusName, hasPermission, ssgAccessUnit } = useSsgWorkspace();

  const canCreateSg = hasPermission("create_sg");
  const canManageMembers = hasPermission("manage_members");
  const canAssignPermissions = hasPermission("assign_permissions");
  const canManageSg = canCreateSg || canManageMembers || canAssignPermissions;

  const [departments, setDepartments] = useState<Department[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [sgUnits, setSgUnits] = useState<GovernanceUnitDetail[]>([]);
  const [selectedSgId, setSelectedSgId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<ManageSgTab>("units");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchingStudents, setSearchingStudents] = useState(false);
  const [studentResults, setStudentResults] = useState<GovernanceStudentCandidate[]>([]);
  const [permissionDrafts, setPermissionDrafts] = useState<Record<number, GovernancePermissionCode[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [isMemberModalOpen, setIsMemberModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<GovernanceMemberItem | null>(null);
  const [memberPendingRemoval, setMemberPendingRemoval] = useState<GovernanceMemberItem | null>(null);
  const [memberDraft, setMemberDraft] = useState<MemberDraftState>(emptyMemberDraft);
  const [createForm, setCreateForm] = useState<SgCreateFormState>(emptyCreateForm);
  const [infoForm, setInfoForm] = useState<SgInfoFormState>(emptyInfoForm);

  const selectedSg = useMemo(
    () => sgUnits.find((unit) => unit.id === selectedSgId) ?? null,
    [selectedSgId, sgUnits]
  );

  useEffect(() => {
    if (!selectedSg) {
      setPermissionDrafts({});
      return;
    }

    setPermissionDrafts(
      Object.fromEntries(
        selectedSg.members.map((member) => [
          member.id,
          member.member_permissions.map((item) => item.permission.permission_code),
        ])
      )
    );
  }, [selectedSg]);

  const loadAcademicLookup = async () => {
    const { departments: nextDepartments, programs: nextPrograms } =
      await fetchAcademicCatalog();
    setDepartments(nextDepartments);
    setPrograms(nextPrograms);
  };

  const loadManageSg = async (preferredSgId?: number | null) => {
    if (!ssgAccessUnit) {
      setSgUnits([]);
      setSelectedSgId(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [sgSummaries] = await Promise.all([
        fetchGovernanceUnits({
          unit_type: "SG",
          parent_unit_id: ssgAccessUnit.governance_unit_id,
        }),
        loadAcademicLookup(),
      ]);

      const sgDetails = sortGovernanceUnits(
        await Promise.all(sgSummaries.map((unit) => fetchGovernanceUnitDetails(unit.id)))
      );

      setSgUnits(sgDetails);
      setSelectedSgId((current) => {
        if (preferredSgId && sgDetails.some((unit) => unit.id === preferredSgId)) return preferredSgId;
        if (current && sgDetails.some((unit) => unit.id === current)) return current;
        return sgDetails[0]?.id ?? null;
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load department SG units");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!accessLoading) void loadManageSg();
  }, [accessLoading, ssgAccessUnit?.governance_unit_id]);

  useEffect(() => {
    if (
      !isMemberModalOpen ||
      editingMember ||
      !canManageMembers ||
      memberDraft.selectedCandidate ||
      memberDraft.searchTerm.trim().length < 2 ||
      !selectedSg
    ) {
      setStudentResults([]);
      return;
    }

    const timeoutId = window.setTimeout(async () => {
      setSearchingStudents(true);
      try {
        const results = await searchGovernanceStudentCandidates({
          q: memberDraft.searchTerm.trim(),
          governance_unit_id: selectedSg.id,
          limit: 8,
        });
        setStudentResults(results);
      } catch (requestError) {
        setError(
          requestError instanceof Error ? requestError.message : "Failed to search imported students"
        );
      } finally {
        setSearchingStudents(false);
      }
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [
    canManageMembers,
    editingMember,
    isMemberModalOpen,
    memberDraft.searchTerm,
    memberDraft.selectedCandidate,
    selectedSg,
  ]);

  const totalMembers = sgUnits.reduce((sum, unit) => sum + unit.members.length, 0);
  const totalDepartmentsCovered = new Set(
    sgUnits
      .map((unit) => unit.department_id)
      .filter((departmentId): departmentId is number => typeof departmentId === "number")
  ).size;
  const availableDepartments = departments.filter(
    (department) => !sgUnits.some((unit) => unit.department_id === department.id)
  );

  const getDepartmentName = (departmentId?: number | null) =>
    departments.find((department) => department.id === departmentId)?.name || "No department";

  const getProgramName = (programId?: number | null) =>
    programs.find((program) => program.id === programId)?.name || "No program";

  const getStudentSummary = (candidate: GovernanceStudentCandidate | GovernanceMemberItem) => {
    const profile =
      "student_profile" in candidate ? candidate.student_profile : candidate.user.student_profile;
    return {
      studentId: profile?.student_id || "No student ID",
      programName: getProgramName(profile?.program_id),
      departmentName: getDepartmentName(profile?.department_id),
      yearLevel: profile?.year_level ? `Year ${profile.year_level}` : "No year level",
    };
  };

  const openCreateModal = () => {
    setCreateForm({
      unit_code: "",
      unit_name: "",
      description: "",
      department_id: availableDepartments[0] ? String(availableDepartments[0].id) : "",
    });
    setIsCreateModalOpen(true);
    setError(null);
  };

  const openInfoModal = (unit: GovernanceUnitDetail) => {
    setSelectedSgId(unit.id);
    setInfoForm({
      unit_code: unit.unit_code,
      unit_name: unit.unit_name,
      description: unit.description || "",
    });
    setIsInfoModalOpen(true);
    setError(null);
  };

  const openAddMemberModal = (unit: GovernanceUnitDetail) => {
    if (!canManageMembers) return;
    setSelectedSgId(unit.id);
    setEditingMember(null);
    setMemberDraft(emptyMemberDraft);
    setStudentResults([]);
    setIsMemberModalOpen(true);
    setActiveTab("members");
    setError(null);
  };

  const openEditMemberModal = (member: GovernanceMemberItem) => {
    if (!member.user.student_profile || (!canManageMembers && !canAssignPermissions)) return;
    setEditingMember(member);
    setMemberDraft({
      selectedCandidate: {
        user: member.user,
        student_profile: member.user.student_profile,
        is_current_governance_member: true,
      },
      searchTerm: "",
      positionTitle: member.position_title || "",
      permissionCodes: member.member_permissions.map((item) => item.permission.permission_code),
    });
    setStudentResults([]);
    setIsMemberModalOpen(true);
    setError(null);
  };

  const closeMemberModal = () => {
    setIsMemberModalOpen(false);
    setEditingMember(null);
    setMemberDraft(emptyMemberDraft);
    setStudentResults([]);
  };

  const handleSelectCandidate = (candidate: GovernanceStudentCandidate) => {
    setMemberDraft((current) => ({
      ...current,
      selectedCandidate: candidate,
      searchTerm: "",
    }));
    setStudentResults([]);
  };

  const toggleDraftPermission = (permissionCode: GovernancePermissionCode) => {
    if (!canAssignPermissions) return;
    setMemberDraft((current) => ({
      ...current,
      permissionCodes: current.permissionCodes.includes(permissionCode)
        ? current.permissionCodes.filter((code) => code !== permissionCode)
        : [...current.permissionCodes, permissionCode],
    }));
  };

  const toggleMemberPermissionDraft = (memberId: number, permissionCode: GovernancePermissionCode) => {
    if (!canAssignPermissions) return;
    setPermissionDrafts((current) => {
      const existing = current[memberId] ?? [];
      return {
        ...current,
        [memberId]: existing.includes(permissionCode)
          ? existing.filter((code) => code !== permissionCode)
          : [...existing, permissionCode],
      };
    });
  };

  const handleCreateSg = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!ssgAccessUnit) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const createdUnit = await createGovernanceUnit({
        unit_code: createForm.unit_code.trim(),
        unit_name: createForm.unit_name.trim(),
        description: createForm.description.trim() || null,
        unit_type: "SG",
        parent_unit_id: ssgAccessUnit.governance_unit_id,
        department_id: Number(createForm.department_id),
      });
      await loadManageSg(createdUnit.id);
      setSuccess("Department SG created successfully.");
      setIsCreateModalOpen(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to create the SG unit");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveInfo = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSg) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await updateGovernanceUnit(selectedSg.id, {
        unit_code: infoForm.unit_code.trim(),
        unit_name: infoForm.unit_name.trim(),
        description: infoForm.description.trim() || null,
      });
      await loadManageSg(selectedSg.id);
      setSuccess("Department SG details updated successfully.");
      setIsInfoModalOpen(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update the SG details");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSg || !memberDraft.selectedCandidate) return;

    const trimmedPositionTitle = memberDraft.positionTitle.trim();
    if (!editingMember && !canManageMembers) return;
    if (canManageMembers && !trimmedPositionTitle) {
      setError("Position title is required for SG members.");
      setSuccess(null);
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      if (editingMember) {
        const payload: {
          user_id?: number;
          position_title?: string;
          permission_codes?: GovernancePermissionCode[];
        } = {};
        if (canManageMembers) {
          payload.user_id = memberDraft.selectedCandidate.user.id;
          payload.position_title = trimmedPositionTitle;
        }
        if (canAssignPermissions) {
          payload.permission_codes = memberDraft.permissionCodes;
        }
        await updateGovernanceMember(editingMember.id, payload);
        setSuccess("SG member updated successfully.");
      } else {
        await assignGovernanceMember(selectedSg.id, {
          user_id: memberDraft.selectedCandidate.user.id,
          position_title: trimmedPositionTitle,
          permission_codes: canAssignPermissions ? memberDraft.permissionCodes : [],
        });
        setSuccess("Student added to the department SG successfully.");
      }
      await primeGovernanceAccessCache(true);
      await loadManageSg(selectedSg.id);
      closeMemberModal();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to save the SG member");
    } finally {
      setSaving(false);
    }
  };

  const handleSavePermissionCard = async (member: GovernanceMemberItem) => {
    if (!canAssignPermissions || !selectedSg) return;
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await updateGovernanceMember(member.id, {
        permission_codes: permissionDrafts[member.id] ?? [],
      });
      await primeGovernanceAccessCache(true);
      await loadManageSg(selectedSg.id);
      setSuccess(`Updated permissions for ${formatUserDisplayName(member.user)}.`);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Failed to update SG member permissions"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveMember = async () => {
    if (!memberPendingRemoval || !selectedSg) return;
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await deleteGovernanceMember(memberPendingRemoval.id);
      await primeGovernanceAccessCache(true);
      await loadManageSg(selectedSg.id);
      if (editingMember?.id === memberPendingRemoval.id) closeMemberModal();
      setMemberPendingRemoval(null);
      setSuccess("SG member removed successfully.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to remove the SG member");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSg = async (unit: GovernanceUnitDetail) => {
    if (!canCreateSg) return;
    const confirmed = window.confirm(
      `Deactivate ${unit.unit_name}? This SG will be hidden until recreated, and its active members will lose SG access.`
    );
    if (!confirmed) return;

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await deleteGovernanceUnit(unit.id);
      await loadManageSg(selectedSgId === unit.id ? null : selectedSgId);
      setSuccess("SG deactivated successfully.");
      if (selectedSgId === unit.id) {
        setActiveTab("units");
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to deactivate the SG unit");
    } finally {
      setSaving(false);
    }
  };

  const canOpenMemberEditor = canManageMembers || canAssignPermissions;
  const canSubmitMemberModal = editingMember
    ? Boolean(memberDraft.selectedCandidate) &&
      ((canManageMembers && memberDraft.positionTitle.trim()) || !canManageMembers) &&
      canOpenMemberEditor
    : canManageMembers && Boolean(memberDraft.selectedCandidate) && Boolean(memberDraft.positionTitle.trim());

  const renderMemberTable = () => {
    if (!selectedSg) {
      return <div className="ssg-empty-state">Select an SG unit to manage members.</div>;
    }

    return (
      <section className="ssg-panel-card">
        <div className="ssg-panel-card__header">
          <div>
            <h2 className="ssg-panel-card__title">{selectedSg.unit_name} members</h2>
            <p className="ssg-panel-card__subtitle">
              {selectedSg.members.length} active member(s) assigned inside {getDepartmentName(selectedSg.department_id)}.
            </p>
          </div>
          {canManageMembers && (
            <button type="button" className="btn btn-primary" onClick={() => openAddMemberModal(selectedSg)}>
              <FaPlus className="me-2" />
              Add Member
            </button>
          )}
        </div>

        {selectedSg.members.length === 0 ? (
          <div className="ssg-empty-state">
            No SG officers yet. Add an imported student from this department to start assigning roles.
          </div>
        ) : (
          <div className="ssg-table-wrap">
            <table className="ssg-data-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Position</th>
                  <th>Permissions</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {selectedSg.members.map((member) => {
                  const name = formatUserDisplayName(member.user);
                  const summary = getStudentSummary(member);
                  const permissionLabels = member.member_permissions.map(
                    (item) => permissionLabelMap.get(item.permission.permission_code) || item.permission.permission_code
                  );
                  const preview = permissionLabels.slice(0, 2);
                  const overflowCount = Math.max(permissionLabels.length - preview.length, 0);

                  return (
                    <tr key={member.id}>
                      <td data-label="Student">
                        <div className="ssg-table-student">
                          <div className={`ssg-avatar ${getAvatarToneClass(member.user_id)}`}>
                            {getInitials(name)}
                          </div>
                          <div>
                            <strong>{name}</strong>
                            <span>{summary.studentId}</span>
                            <small>
                              {summary.programName} - {summary.yearLevel}
                            </small>
                          </div>
                        </div>
                      </td>
                      <td data-label="Position">
                        <span className="ssg-badge ssg-badge--member">
                          {member.position_title || "No position"}
                        </span>
                      </td>
                      <td data-label="Permissions">
                        <div className="ssg-permission-pill-list">
                          {preview.length === 0 ? (
                            <span className="ssg-permission-pill is-muted">No permissions</span>
                          ) : (
                            preview.map((label) => (
                              <span className="ssg-permission-pill" key={`${member.id}-${label}`}>
                                {label}
                              </span>
                            ))
                          )}
                          {overflowCount > 0 && (
                            <span className="ssg-permission-pill is-muted">+{overflowCount}</span>
                          )}
                        </div>
                      </td>
                      <td data-label="Actions">
                        <div className="ssg-table-actions">
                          {canOpenMemberEditor && (
                            <button
                              type="button"
                              className="btn btn-outline-primary"
                              onClick={() => openEditMemberModal(member)}
                            >
                              <FaEdit className="me-2" />
                              {canManageMembers ? "Edit" : "Edit Permissions"}
                            </button>
                          )}
                          {canManageMembers && (
                            <button
                              type="button"
                              className="btn btn-outline-danger"
                              onClick={() => setMemberPendingRemoval(member)}
                            >
                              <FaTrashAlt className="me-2" />
                              Delete
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    );
  };

  const renderPermissionCards = () => {
    if (!selectedSg) {
      return <div className="ssg-empty-state">Select an SG unit to manage permissions.</div>;
    }

    if (selectedSg.members.length === 0) {
      return (
        <div className="ssg-empty-state">
          No SG members are assigned yet. Add members first before managing permissions.
        </div>
      );
    }

    return (
      <section className="ssg-member-permission-grid">
        {selectedSg.members.map((member) => {
          const name = formatUserDisplayName(member.user);
          const draftPermissions = permissionDrafts[member.id] ?? [];
          return (
            <article key={member.id} className="ssg-panel-card ssg-member-permission-card">
              <div className="ssg-member-permission-card__header">
                <div className={`ssg-avatar ${getAvatarToneClass(member.user_id)}`}>{getInitials(name)}</div>
                <div>
                  <strong>{name}</strong>
                  <div className="ssg-panel-card__subtitle">{member.position_title || "No position assigned"}</div>
                </div>
              </div>

              <div className="ssg-permission-option-grid">
                {permissionOptions.map((permission) => (
                  <label key={`${member.id}-${permission.code}`} className="ssg-permission-option">
                    <input
                      type="checkbox"
                      checked={draftPermissions.includes(permission.code)}
                      onChange={() => toggleMemberPermissionDraft(member.id, permission.code)}
                      disabled={!canAssignPermissions || saving}
                    />
                    <div>
                      <strong>{permission.label}</strong>
                      <span>{permission.description}</span>
                    </div>
                  </label>
                ))}
              </div>

              <div className="ssg-inline-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!canAssignPermissions || saving}
                  onClick={() => void handleSavePermissionCard(member)}
                >
                  Save
                </button>
              </div>
            </article>
          );
        })}
      </section>
    );
  };

  return (
    <div className="ssg-workspace-page">
      <NavbarSSG />

      <main className="container py-4 ssg-workspace-main">
        <section className="ssg-page-header">
          <div className="ssg-page-header__copy">
            <p className="ssg-page-eyebrow">SSG / Manage SG</p>
            <h1>Department student governments</h1>
            <p>
              Create one SG per department, assign officers from imported students, and control each
              officer&apos;s permissions from the SSG workspace.
            </p>
          </div>
          <div className="ssg-page-actions">
            {activeTab !== "units" && selectedSg && (
              <button type="button" className="btn btn-outline-light" onClick={() => setActiveTab("units")}>
                <FaArrowLeft className="me-2" />
                Back
              </button>
            )}
            {canCreateSg && (
              <button type="button" className="btn btn-light" onClick={openCreateModal}>
                <FaPlus className="me-2" />
                Create SG
              </button>
            )}
          </div>
        </section>

        <section className="ssg-stat-grid">
          <article className="ssg-stat-card">
            <span className="ssg-stat-card__label">SG Units</span>
            <strong className="ssg-stat-card__value">{sgUnits.length}</strong>
            <span className="ssg-stat-card__hint">Department-wide SG units in {campusName}</span>
          </article>
          <article className="ssg-stat-card">
            <span className="ssg-stat-card__label">Covered Departments</span>
            <strong className="ssg-stat-card__value">{totalDepartmentsCovered}</strong>
            <span className="ssg-stat-card__hint">Departments already assigned their SG</span>
          </article>
          <article className="ssg-stat-card">
            <span className="ssg-stat-card__label">Total SG Members</span>
            <strong className="ssg-stat-card__value">{totalMembers}</strong>
            <span className="ssg-stat-card__hint">Students currently serving inside SG units</span>
          </article>
          <article className="ssg-stat-card">
            <span className="ssg-stat-card__label">Access Level</span>
            <strong className="ssg-stat-card__value">{canManageSg ? "Enabled" : "Hidden"}</strong>
            <span className="ssg-stat-card__hint">
              SSG officers need create, member, or permission access to use this page.
            </span>
          </article>
        </section>

        {error && <div className="alert alert-danger mb-0">{error}</div>}
        {success && <div className="alert alert-success mb-0">{success}</div>}

        {selectedSg && (
          <section className="ssg-panel-card">
            <div className="ssg-panel-card__header">
              <div>
                <h2 className="ssg-panel-card__title">
                  {selectedSg.unit_code} - {selectedSg.unit_name}
                </h2>
                <p className="ssg-panel-card__subtitle">
                  Department: {getDepartmentName(selectedSg.department_id)} - SG units stay department-wide,
                  covering all programs under that department.
                </p>
              </div>
              <div className="ssg-subtabs">
                <button
                  type="button"
                  className={`ssg-subtab ${activeTab === "units" ? "is-active" : ""}`}
                  onClick={() => setActiveTab("units")}
                >
                  SG Units
                </button>
                <button
                  type="button"
                  className={`ssg-subtab ${activeTab === "members" ? "is-active" : ""}`}
                  onClick={() => setActiveTab("members")}
                >
                  Members
                </button>
                <button
                  type="button"
                  className={`ssg-subtab ${activeTab === "permissions" ? "is-active" : ""}`}
                  onClick={() => setActiveTab("permissions")}
                >
                  Permissions
                </button>
              </div>
            </div>
          </section>
        )}

        {loading ? (
          <div className="ssg-empty-state">Loading department SG workspace...</div>
        ) : activeTab === "units" ? (
          <section className="ssg-unit-grid">
            {sgUnits.length === 0 ? (
              <div className="ssg-empty-state">
                No department SG units exist yet. Create the first SG to start assigning department officers.
              </div>
            ) : (
              sgUnits.map((unit) => (
                <article key={unit.id} className="ssg-unit-card">
                  <div className="ssg-unit-card__header">
                    <div className={`ssg-avatar ${getAvatarToneClass(unit.id)}`}>
                      <FaProjectDiagram />
                    </div>
                    <span className="ssg-badge ssg-badge--member">{unit.members.length} members</span>
                  </div>

                  <div className="ssg-unit-card__meta">
                    <strong>{unit.unit_code}</strong>
                    <h3>{unit.unit_name}</h3>
                    <span>{getDepartmentName(unit.department_id)}</span>
                    <small>{unit.description || "Department-wide student government unit"}</small>
                  </div>

                  <div className="ssg-unit-card__actions">
                    {(canManageMembers || canAssignPermissions) && (
                      <button
                        type="button"
                        className="btn btn-outline-primary"
                        onClick={() => {
                          setSelectedSgId(unit.id);
                          setActiveTab("members");
                        }}
                      >
                        <FaUsers className="me-2" />
                        Members
                      </button>
                    )}
                    {canAssignPermissions && (
                      <button
                        type="button"
                        className="btn btn-outline-primary"
                        onClick={() => {
                          setSelectedSgId(unit.id);
                          setActiveTab("permissions");
                        }}
                      >
                        Permissions
                      </button>
                    )}
                    {canCreateSg && (
                      <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={() => openInfoModal(unit)}
                      >
                        <FaEdit className="me-2" />
                        Edit
                      </button>
                    )}
                    {canCreateSg && (
                      <button
                        type="button"
                        className="btn btn-outline-danger"
                        onClick={() => void handleDeleteSg(unit)}
                        disabled={saving}
                      >
                        <FaTrashAlt className="me-2" />
                        Delete
                      </button>
                    )}
                  </div>
                </article>
              ))
            )}
          </section>
        ) : activeTab === "members" ? (
          renderMemberTable()
        ) : (
          renderPermissionCards()
        )}
      </main>

      <Modal
        isOpen={isCreateModalOpen}
        onRequestClose={() => setIsCreateModalOpen(false)}
        className="ssg-setup-modal"
        overlayClassName="ssg-setup-overlay"
      >
        <form onSubmit={handleCreateSg}>
          <div className="ssg-setup-modal__header">
            <h3>Create SG</h3>
            <button type="button" className="ssg-setup-modal__close" onClick={() => setIsCreateModalOpen(false)}>
              &times;
            </button>
          </div>

          <div className="ssg-setup-modal__body">
            <div className="form-group">
              <label htmlFor="sgCode">Unit Code</label>
              <input
                id="sgCode"
                value={createForm.unit_code}
                onChange={(event) => setCreateForm((current) => ({ ...current, unit_code: event.target.value }))}
                placeholder="SG-ENGINEERING"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="sgName">Unit Name</label>
              <input
                id="sgName"
                value={createForm.unit_name}
                onChange={(event) => setCreateForm((current) => ({ ...current, unit_name: event.target.value }))}
                placeholder="College of Engineering Student Government"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="sgDepartment">Department</label>
              <select
                id="sgDepartment"
                value={createForm.department_id}
                onChange={(event) => setCreateForm((current) => ({ ...current, department_id: event.target.value }))}
                required
              >
                <option value="">Select department</option>
                {availableDepartments.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="sgDescription">Description</label>
              <textarea
                id="sgDescription"
                rows={4}
                value={createForm.description}
                onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="Describe this department SG."
              />
            </div>
            <div className="sg-inline-note">
              SG units are department-wide only. Program-level governance will be handled by ORG later.
            </div>
            {availableDepartments.length === 0 && (
              <div className="ssg-modal-empty">
                Every department already has an SG. Edit an existing unit instead of creating another one.
              </div>
            )}
          </div>

          <div className="ssg-setup-modal__footer">
            <button type="button" className="btn btn-outline-secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || availableDepartments.length === 0}>
              {saving ? "Saving..." : "Create SG"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isInfoModalOpen}
        onRequestClose={() => setIsInfoModalOpen(false)}
        className="ssg-setup-modal"
        overlayClassName="ssg-setup-overlay"
      >
        <form onSubmit={handleSaveInfo}>
          <div className="ssg-setup-modal__header">
            <h3>Edit SG</h3>
            <button type="button" className="ssg-setup-modal__close" onClick={() => setIsInfoModalOpen(false)}>
              &times;
            </button>
          </div>

          <div className="ssg-setup-modal__body">
            <div className="form-group">
              <label htmlFor="editSgCode">Unit Code</label>
              <input
                id="editSgCode"
                value={infoForm.unit_code}
                onChange={(event) => setInfoForm((current) => ({ ...current, unit_code: event.target.value }))}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="editSgName">Unit Name</label>
              <input
                id="editSgName"
                value={infoForm.unit_name}
                onChange={(event) => setInfoForm((current) => ({ ...current, unit_name: event.target.value }))}
                required
              />
            </div>
            <div className="form-group">
              <label>Department</label>
              <input value={getDepartmentName(selectedSg?.department_id)} disabled />
            </div>
            <div className="form-group">
              <label htmlFor="editSgDescription">Description</label>
              <textarea
                id="editSgDescription"
                rows={4}
                value={infoForm.description}
                onChange={(event) => setInfoForm((current) => ({ ...current, description: event.target.value }))}
              />
            </div>
          </div>

          <div className="ssg-setup-modal__footer">
            <button type="button" className="btn btn-outline-secondary" onClick={() => setIsInfoModalOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isMemberModalOpen}
        onRequestClose={closeMemberModal}
        className="ssg-setup-modal ssg-setup-modal--wide"
        overlayClassName="ssg-setup-overlay"
      >
        <form onSubmit={handleSaveMember}>
          <div className="ssg-setup-modal__header">
            <h3>{editingMember ? "Edit SG Member" : "Add SG Member"}</h3>
            <button type="button" className="ssg-setup-modal__close" onClick={closeMemberModal}>
              &times;
            </button>
          </div>

          <div className="ssg-setup-modal__body">
            {!editingMember && canManageMembers && (
              <div className="form-group">
                <label htmlFor="sgStudentSearch">Search imported students</label>
                <div className="ssg-search-input">
                  <FaSearch />
                  <input
                    id="sgStudentSearch"
                    value={memberDraft.searchTerm}
                    onChange={(event) =>
                      setMemberDraft((current) => ({
                        ...current,
                        searchTerm: event.target.value,
                        selectedCandidate: null,
                      }))
                    }
                    placeholder="Search by student ID or name"
                  />
                </div>
              </div>
            )}

            {!editingMember && canManageMembers && searchingStudents && (
              <div className="ssg-modal-empty">Searching imported students...</div>
            )}

            {!editingMember &&
              canManageMembers &&
              !searchingStudents &&
              memberDraft.searchTerm.trim().length >= 2 &&
              studentResults.length === 0 &&
              !memberDraft.selectedCandidate && (
                <div className="ssg-modal-empty">No imported students found for that search.</div>
              )}

            {!editingMember && canManageMembers && studentResults.length > 0 && !memberDraft.selectedCandidate && (
              <div className="ssg-search-results mb-3">
                {studentResults.map((candidate) => {
                  const summary = getStudentSummary(candidate);
                  return (
                    <button
                      type="button"
                      className="ssg-search-result"
                      key={candidate.user.id}
                      onClick={() => handleSelectCandidate(candidate)}
                    >
                      <strong>{formatUserDisplayName(candidate.user)}</strong>
                      <span>{summary.studentId}</span>
                      <small>
                        {summary.departmentName} - {summary.programName} - {summary.yearLevel}
                      </small>
                    </button>
                  );
                })}
              </div>
            )}

            {memberDraft.selectedCandidate && (
              <div className="ssg-selected-student mb-3">
                <div>
                  <strong>{formatUserDisplayName(memberDraft.selectedCandidate.user)}</strong>
                  <span>{getStudentSummary(memberDraft.selectedCandidate).studentId}</span>
                  <small>
                    {getStudentSummary(memberDraft.selectedCandidate).departmentName} -{" "}
                    {getStudentSummary(memberDraft.selectedCandidate).programName} -{" "}
                    {getStudentSummary(memberDraft.selectedCandidate).yearLevel}
                  </small>
                </div>
                {!editingMember && canManageMembers && (
                  <button
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={() => setMemberDraft((current) => ({ ...current, selectedCandidate: null }))}
                  >
                    Change
                  </button>
                )}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="sgPositionTitle">Position title</label>
              <input
                id="sgPositionTitle"
                value={memberDraft.positionTitle}
                onChange={(event) => setMemberDraft((current) => ({ ...current, positionTitle: event.target.value }))}
                placeholder="President, Secretary, Treasurer..."
                disabled={!canManageMembers}
              />
            </div>

            <div className="form-group">
              <label>Permissions</label>
              <div className="ssg-permission-option-grid">
                {permissionOptions.map((permission) => (
                  <label key={permission.code} className="ssg-permission-option">
                    <input
                      type="checkbox"
                      checked={memberDraft.permissionCodes.includes(permission.code)}
                      onChange={() => toggleDraftPermission(permission.code)}
                      disabled={!canAssignPermissions}
                    />
                    <div>
                      <strong>{permission.label}</strong>
                      <span>{permission.description}</span>
                    </div>
                  </label>
                ))}
              </div>
              {!canAssignPermissions && (
                <div className="sg-inline-note mt-3">
                  Your SSG access can manage SG membership, but it cannot change SG officer permissions.
                </div>
              )}
            </div>
          </div>

          <div className="ssg-setup-modal__footer">
            {editingMember && canManageMembers && (
              <button
                type="button"
                className="btn btn-outline-danger me-auto"
                onClick={() => setMemberPendingRemoval(editingMember)}
              >
                Remove Member
              </button>
            )}
            <button type="button" className="btn btn-outline-secondary" onClick={closeMemberModal}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || !canSubmitMemberModal}>
              {saving ? "Saving..." : editingMember ? "Save Changes" : "Add Member"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={memberPendingRemoval !== null}
        onRequestClose={() => setMemberPendingRemoval(null)}
        className="ssg-setup-modal ssg-setup-modal--compact"
        overlayClassName="ssg-setup-overlay"
      >
        <div className="ssg-setup-modal__header">
          <h3>Remove Member</h3>
          <button type="button" className="ssg-setup-modal__close" onClick={() => setMemberPendingRemoval(null)}>
            &times;
          </button>
        </div>
        <div className="ssg-setup-modal__body">
          <p className="mb-2">
            Remove{" "}
            <strong>
              {memberPendingRemoval ? formatUserDisplayName(memberPendingRemoval.user) : "this member"}
            </strong>{" "}
            from the selected SG?
          </p>
          <div className="ssg-remove-note">
            On removal, this user returns to a regular student role unless they still belong to another governance membership.
          </div>
        </div>
        <div className="ssg-setup-modal__footer">
          <button type="button" className="btn btn-outline-secondary" onClick={() => setMemberPendingRemoval(null)}>
            Cancel
          </button>
          <button type="button" className="btn btn-danger" onClick={() => void handleRemoveMember()} disabled={saving}>
            {saving ? "Removing..." : "Confirm Remove"}
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default ManageSg;
