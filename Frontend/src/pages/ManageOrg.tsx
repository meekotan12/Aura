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
import NavbarSG from "../components/NavbarSG";
import "../css/GovernanceHierarchyManagement.css";
import "../css/SsgWorkspace.css";
import { primeGovernanceAccessCache } from "../hooks/useGovernanceAccess";
import { useGovernanceWorkspace } from "../hooks/useGovernanceWorkspace";
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
  department_ids: number[];
}

interface MemberDraftState {
  selectedCandidate: GovernanceStudentCandidate | null;
  searchTerm: string;
  positionTitle: string;
  permissionCodes: GovernancePermissionCode[];
}

type ManageOrgTab = "units" | "members" | "permissions";

const permissionOptions = [
  { code: "manage_members" as GovernancePermissionCode, label: "Manage Members", description: "Manage ORG member assignments and updates." },
  { code: "manage_events" as GovernancePermissionCode, label: "Manage Events", description: "Access organization event management." },
  { code: "manage_attendance" as GovernancePermissionCode, label: "Manage Attendance", description: "Access records and manual attendance." },
  { code: "manage_announcements" as GovernancePermissionCode, label: "Manage Announcements", description: "Publish organization announcements." },
  { code: "view_students" as GovernancePermissionCode, label: "View Students", description: "View students inside the program scope." },
  { code: "manage_students" as GovernancePermissionCode, label: "Manage Students", description: "Manage governance notes inside the program scope." },
  { code: "assign_permissions" as GovernancePermissionCode, label: "Assign Permissions", description: "Manage permissions for ORG officers." },
] as const;

const permissionLabelMap = new Map(permissionOptions.map((permission) => [permission.code, permission.label] as const));

const emptyMemberDraft: MemberDraftState = {
  selectedCandidate: null,
  searchTerm: "",
  positionTitle: "",
  permissionCodes: [],
};

Modal.setAppElement("#root");

const sortUnits = (units: GovernanceUnitDetail[]) =>
  [...units].sort((left, right) => left.unit_name.localeCompare(right.unit_name));

const ManageOrg = () => {
  const { accessLoading, campusName, hasPermission, accessUnit, governanceUnit } = useGovernanceWorkspace("SG");
  const canCreateOrg = hasPermission("create_org");
  const canManageMembers = hasPermission("manage_members");
  const canAssignPermissions = hasPermission("assign_permissions");
  const canManageOrg = canCreateOrg || canManageMembers || canAssignPermissions;
  const parentDepartmentId = governanceUnit?.department_id ?? null;
  const [departments, setDepartments] = useState<Department[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [orgUnits, setOrgUnits] = useState<GovernanceUnitDetail[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<ManageOrgTab>("units");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [searchingStudents, setSearchingStudents] = useState(false);
  const [studentResults, setStudentResults] = useState<GovernanceStudentCandidate[]>([]);
  const [permissionDrafts, setPermissionDrafts] = useState<Record<number, GovernancePermissionCode[]>>({});
  const [memberDraft, setMemberDraft] = useState<MemberDraftState>(emptyMemberDraft);
  const [editingMember, setEditingMember] = useState<GovernanceMemberItem | null>(null);
  const [memberPendingRemoval, setMemberPendingRemoval] = useState<GovernanceMemberItem | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [isMemberModalOpen, setIsMemberModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ unit_code: "", unit_name: "", description: "", program_id: "" });
  const [infoForm, setInfoForm] = useState({ unit_code: "", unit_name: "", description: "" });

  const selectedOrg = useMemo(() => orgUnits.find((unit) => unit.id === selectedOrgId) ?? null, [orgUnits, selectedOrgId]);
  const getDepartmentName = (departmentId?: number | null) => departments.find((department) => department.id === departmentId)?.name || "No department";
  const getProgramName = (programId?: number | null) => programs.find((program) => program.id === programId)?.name || "No program";
  const availablePrograms = programs.filter(
    (program) =>
      parentDepartmentId !== null &&
      program.department_ids.includes(parentDepartmentId) &&
      !orgUnits.some((unit) => unit.program_id === program.id)
  );

  const getStudentSummary = (candidate: GovernanceStudentCandidate | GovernanceMemberItem) => {
    const profile = "student_profile" in candidate ? candidate.student_profile : candidate.user.student_profile;
    return {
      studentId: profile?.student_id || "No student ID",
      programName: getProgramName(profile?.program_id),
      departmentName: getDepartmentName(profile?.department_id),
      yearLevel: profile?.year_level ? `Year ${profile.year_level}` : "No year level",
    };
  };

  useEffect(() => {
    if (!selectedOrg) {
      setPermissionDrafts({});
      return;
    }
    setPermissionDrafts(
      Object.fromEntries(
        selectedOrg.members.map((member) => [
          member.id,
          member.member_permissions.map((item) => item.permission.permission_code),
        ])
      )
    );
  }, [selectedOrg]);

  const loadLookup = async () => {
    const { departments: nextDepartments, programs: nextPrograms } =
      await fetchAcademicCatalog();
    setDepartments(nextDepartments);
    setPrograms(nextPrograms);
  };

  const loadManageOrg = async (preferredOrgId?: number | null) => {
    if (!accessUnit) {
      setOrgUnits([]);
      setSelectedOrgId(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [summaries] = await Promise.all([
        fetchGovernanceUnits({ unit_type: "ORG", parent_unit_id: accessUnit.governance_unit_id }),
        loadLookup(),
      ]);
      const details = sortUnits(await Promise.all(summaries.map((unit) => fetchGovernanceUnitDetails(unit.id))));
      setOrgUnits(details);
      setSelectedOrgId((current) => {
        if (preferredOrgId && details.some((unit) => unit.id === preferredOrgId)) return preferredOrgId;
        if (current && details.some((unit) => unit.id === current)) return current;
        return details[0]?.id ?? null;
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load ORG units");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!accessLoading) void loadManageOrg();
  }, [accessLoading, accessUnit?.governance_unit_id]);

  useEffect(() => {
    if (
      !isMemberModalOpen ||
      editingMember ||
      !canManageMembers ||
      !selectedOrg ||
      memberDraft.selectedCandidate ||
      memberDraft.searchTerm.trim().length < 2
    ) {
      setStudentResults([]);
      return;
    }

    const timeoutId = window.setTimeout(async () => {
      setSearchingStudents(true);
      try {
        setStudentResults(
          await searchGovernanceStudentCandidates({
            q: memberDraft.searchTerm.trim(),
            governance_unit_id: selectedOrg.id,
            limit: 8,
          })
        );
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Failed to search imported students");
      } finally {
        setSearchingStudents(false);
      }
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [canManageMembers, editingMember, isMemberModalOpen, memberDraft.searchTerm, memberDraft.selectedCandidate, selectedOrg]);

  const totalMembers = orgUnits.reduce((sum, unit) => sum + unit.members.length, 0);
  const totalProgramsCovered = new Set(
    orgUnits.map((unit) => unit.program_id).filter((programId): programId is number => typeof programId === "number")
  ).size;
  const canOpenMemberEditor = canManageMembers || canAssignPermissions;
  const canSubmitMemberModal = editingMember
    ? Boolean(memberDraft.selectedCandidate) && ((canManageMembers && memberDraft.positionTitle.trim()) || !canManageMembers) && canOpenMemberEditor
    : canManageMembers && Boolean(memberDraft.selectedCandidate) && Boolean(memberDraft.positionTitle.trim());

  const closeMemberModal = () => {
    setIsMemberModalOpen(false);
    setEditingMember(null);
    setMemberDraft(emptyMemberDraft);
    setStudentResults([]);
  };

  const openAddMemberModal = (unit: GovernanceUnitDetail) => {
    if (!canManageMembers) return;
    setSelectedOrgId(unit.id);
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

  const handleSelectCandidate = (candidate: GovernanceStudentCandidate) => {
    setMemberDraft((current) => ({ ...current, selectedCandidate: candidate, searchTerm: "" }));
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

  const saveMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedOrg || !memberDraft.selectedCandidate) return;
    const trimmedPositionTitle = memberDraft.positionTitle.trim();
    if (!editingMember && !canManageMembers) return;
    if (canManageMembers && !trimmedPositionTitle) {
      setError("Position title is required for ORG members.");
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
        if (canAssignPermissions) payload.permission_codes = memberDraft.permissionCodes;
        await updateGovernanceMember(editingMember.id, payload);
        setSuccess("ORG member updated successfully.");
      } else {
        await assignGovernanceMember(selectedOrg.id, {
          user_id: memberDraft.selectedCandidate.user.id,
          position_title: trimmedPositionTitle,
          permission_codes: canAssignPermissions ? memberDraft.permissionCodes : [],
        });
        setSuccess("Student added to the organization successfully.");
      }
      await primeGovernanceAccessCache(true);
      await loadManageOrg(selectedOrg.id);
      closeMemberModal();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to save the ORG member");
    } finally {
      setSaving(false);
    }
  };

  const handleCreateOrg = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!accessUnit) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const createdUnit = await createGovernanceUnit({
        unit_code: createForm.unit_code.trim(),
        unit_name: createForm.unit_name.trim(),
        description: createForm.description.trim() || null,
        unit_type: "ORG",
        parent_unit_id: accessUnit.governance_unit_id,
        program_id: Number(createForm.program_id),
      });
      await loadManageOrg(createdUnit.id);
      setSuccess("Program organization created successfully.");
      setIsCreateModalOpen(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to create the ORG unit");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveInfo = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedOrg) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await updateGovernanceUnit(selectedOrg.id, {
        unit_code: infoForm.unit_code.trim(),
        unit_name: infoForm.unit_name.trim(),
        description: infoForm.description.trim() || null,
      });
      await loadManageOrg(selectedOrg.id);
      setSuccess("Program organization details updated successfully.");
      setIsInfoModalOpen(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update the ORG details");
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveMember = async () => {
    if (!memberPendingRemoval || !selectedOrg) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await deleteGovernanceMember(memberPendingRemoval.id);
      await primeGovernanceAccessCache(true);
      await loadManageOrg(selectedOrg.id);
      if (editingMember?.id === memberPendingRemoval.id) closeMemberModal();
      setMemberPendingRemoval(null);
      setSuccess("ORG member removed successfully.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to remove the ORG member");
    } finally {
      setSaving(false);
    }
  };

  const handleSavePermissionCard = async (member: GovernanceMemberItem) => {
    if (!canAssignPermissions || !selectedOrg) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await updateGovernanceMember(member.id, { permission_codes: permissionDrafts[member.id] ?? [] });
      await primeGovernanceAccessCache(true);
      await loadManageOrg(selectedOrg.id);
      setSuccess(`Updated permissions for ${formatUserDisplayName(member.user)}.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update ORG member permissions");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteOrg = async (unit: GovernanceUnitDetail) => {
    if (!canCreateOrg) return;
    const confirmed = window.confirm(
      `Deactivate ${unit.unit_name}? This ORG will be hidden until recreated, and its active members will lose ORG access.`
    );
    if (!confirmed) return;

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await deleteGovernanceUnit(unit.id);
      await loadManageOrg(selectedOrgId === unit.id ? null : selectedOrgId);
      setSuccess("ORG deactivated successfully.");
      if (selectedOrgId === unit.id) {
        setActiveTab("units");
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to deactivate the ORG unit");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="ssg-workspace-page">
      <NavbarSG />

      <main className="container py-4 ssg-workspace-main">
        <section className="ssg-page-header">
          <div className="ssg-page-header__copy">
            <p className="ssg-page-eyebrow">SG / Manage ORG</p>
            <h1>Program organizations</h1>
            <p>Create one ORG per program, assign officers from imported students, and manage permissions from the SG workspace.</p>
          </div>
          <div className="ssg-page-actions">
            {activeTab !== "units" && selectedOrg && (
              <button type="button" className="btn btn-outline-light" onClick={() => setActiveTab("units")}>
                <FaArrowLeft className="me-2" />
                Back
              </button>
            )}
            {canCreateOrg && (
              <button
                type="button"
                className="btn btn-light"
                onClick={() => {
                  setCreateForm({
                    unit_code: "",
                    unit_name: "",
                    description: "",
                    program_id: availablePrograms[0] ? String(availablePrograms[0].id) : "",
                  });
                  setIsCreateModalOpen(true);
                  setError(null);
                }}
              >
                <FaPlus className="me-2" />
                Create ORG
              </button>
            )}
          </div>
        </section>

        <section className="ssg-stat-grid">
          <article className="ssg-stat-card">
            <span className="ssg-stat-card__label">ORG Units</span>
            <strong className="ssg-stat-card__value">{orgUnits.length}</strong>
            <span className="ssg-stat-card__hint">Program organizations in {campusName}</span>
          </article>
          <article className="ssg-stat-card">
            <span className="ssg-stat-card__label">Covered Programs</span>
            <strong className="ssg-stat-card__value">{totalProgramsCovered}</strong>
            <span className="ssg-stat-card__hint">Programs already assigned their ORG</span>
          </article>
          <article className="ssg-stat-card">
            <span className="ssg-stat-card__label">Total ORG Members</span>
            <strong className="ssg-stat-card__value">{totalMembers}</strong>
            <span className="ssg-stat-card__hint">Students currently serving inside ORG units</span>
          </article>
          <article className="ssg-stat-card">
            <span className="ssg-stat-card__label">Access Level</span>
            <strong className="ssg-stat-card__value">{canManageOrg ? "Enabled" : "Hidden"}</strong>
            <span className="ssg-stat-card__hint">SG officers need create, member, or permission access to use this page.</span>
          </article>
        </section>

        {error && <div className="alert alert-danger mb-0">{error}</div>}
        {success && <div className="alert alert-success mb-0">{success}</div>}

        {selectedOrg && (
          <section className="ssg-panel-card">
            <div className="ssg-panel-card__header">
              <div>
                <h2 className="ssg-panel-card__title">{selectedOrg.unit_code} - {selectedOrg.unit_name}</h2>
                <p className="ssg-panel-card__subtitle">
                  Department: {getDepartmentName(selectedOrg.department_id)} - Program: {getProgramName(selectedOrg.program_id)}
                </p>
              </div>
              <div className="ssg-subtabs">
                {(["units", "members", "permissions"] as ManageOrgTab[]).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    className={`ssg-subtab ${activeTab === tab ? "is-active" : ""}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === "units" ? "ORG Units" : tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

        {loading ? (
          <div className="ssg-empty-state">Loading program organization workspace...</div>
        ) : activeTab === "units" ? (
          <section className="ssg-unit-grid">
            {orgUnits.length === 0 ? (
              <div className="ssg-empty-state">No ORG units exist yet. Create the first ORG to start assigning officers.</div>
            ) : (
              orgUnits.map((unit) => (
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
                    <span>{getProgramName(unit.program_id)}</span>
                    <small>{unit.description || "Program-level student organization"}</small>
                  </div>
                  <div className="ssg-unit-card__actions">
                    {(canManageMembers || canAssignPermissions) && (
                      <button type="button" className="btn btn-outline-primary" onClick={() => { setSelectedOrgId(unit.id); setActiveTab("members"); }}>
                        <FaUsers className="me-2" />
                        Members
                      </button>
                    )}
                    {canAssignPermissions && (
                      <button type="button" className="btn btn-outline-primary" onClick={() => { setSelectedOrgId(unit.id); setActiveTab("permissions"); }}>
                        Permissions
                      </button>
                    )}
                    {canCreateOrg && (
                      <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={() => {
                          setSelectedOrgId(unit.id);
                          setInfoForm({ unit_code: unit.unit_code, unit_name: unit.unit_name, description: unit.description || "" });
                          setIsInfoModalOpen(true);
                          setError(null);
                        }}
                      >
                        <FaEdit className="me-2" />
                        Edit
                      </button>
                    )}
                    {canCreateOrg && (
                      <button
                        type="button"
                        className="btn btn-outline-danger"
                        onClick={() => void handleDeleteOrg(unit)}
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
          !selectedOrg ? (
            <div className="ssg-empty-state">Select an ORG unit to manage members.</div>
          ) : (
            <section className="ssg-panel-card">
              <div className="ssg-panel-card__header">
                <div>
                  <h2 className="ssg-panel-card__title">{selectedOrg.unit_name} members</h2>
                  <p className="ssg-panel-card__subtitle">
                    {selectedOrg.members.length} active member(s) assigned inside {getProgramName(selectedOrg.program_id)}.
                  </p>
                </div>
                {canManageMembers && (
                  <button type="button" className="btn btn-primary" onClick={() => openAddMemberModal(selectedOrg)}>
                    <FaPlus className="me-2" />
                    Add Member
                  </button>
                )}
              </div>

              {selectedOrg.members.length === 0 ? (
                <div className="ssg-empty-state">No ORG officers yet. Add an imported student from this program.</div>
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
                      {selectedOrg.members.map((member) => {
                        const name = formatUserDisplayName(member.user);
                        const summary = getStudentSummary(member);
                        const labels = member.member_permissions.map(
                          (item) => permissionLabelMap.get(item.permission.permission_code) || item.permission.permission_code
                        );
                        const preview = labels.slice(0, 2);
                        const overflowCount = Math.max(labels.length - preview.length, 0);
                        return (
                          <tr key={member.id}>
                            <td data-label="Student">
                              <div className="ssg-table-student">
                                <div className={`ssg-avatar ${getAvatarToneClass(member.user_id)}`}>{getInitials(name)}</div>
                                <div>
                                  <strong>{name}</strong>
                                  <span>{summary.studentId}</span>
                                  <small>{summary.programName} - {summary.yearLevel}</small>
                                </div>
                              </div>
                            </td>
                            <td data-label="Position">
                              <span className="ssg-badge ssg-badge--member">{member.position_title || "No position"}</span>
                            </td>
                            <td data-label="Permissions">
                              <div className="ssg-permission-pill-list">
                                {preview.length === 0 ? (
                                  <span className="ssg-permission-pill is-muted">No permissions</span>
                                ) : (
                                  preview.map((label) => <span className="ssg-permission-pill" key={`${member.id}-${label}`}>{label}</span>)
                                )}
                                {overflowCount > 0 && <span className="ssg-permission-pill is-muted">+{overflowCount}</span>}
                              </div>
                            </td>
                            <td data-label="Actions">
                              <div className="ssg-table-actions">
                                {canOpenMemberEditor && (
                                  <button type="button" className="btn btn-outline-primary" onClick={() => openEditMemberModal(member)}>
                                    <FaEdit className="me-2" />
                                    {canManageMembers ? "Edit" : "Edit Permissions"}
                                  </button>
                                )}
                                {canManageMembers && (
                                  <button type="button" className="btn btn-outline-danger" onClick={() => setMemberPendingRemoval(member)}>
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
          )
        ) : !selectedOrg ? (
          <div className="ssg-empty-state">Select an ORG unit to manage permissions.</div>
        ) : selectedOrg.members.length === 0 ? (
          <div className="ssg-empty-state">No ORG members are assigned yet. Add members first.</div>
        ) : (
          <section className="ssg-member-permission-grid">
            {selectedOrg.members.map((member) => {
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
                    <button type="button" className="btn btn-primary" disabled={!canAssignPermissions || saving} onClick={() => void handleSavePermissionCard(member)}>
                      Save
                    </button>
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </main>

      <Modal
        isOpen={isCreateModalOpen}
        onRequestClose={() => setIsCreateModalOpen(false)}
        className="ssg-setup-modal"
        overlayClassName="ssg-setup-overlay"
      >
        <form onSubmit={handleCreateOrg}>
          <div className="ssg-setup-modal__header">
            <h3>Create ORG</h3>
            <button type="button" className="ssg-setup-modal__close" onClick={() => setIsCreateModalOpen(false)}>
              &times;
            </button>
          </div>
          <div className="ssg-setup-modal__body">
            <div className="form-group">
              <label htmlFor="orgCode">Unit Code</label>
              <input id="orgCode" value={createForm.unit_code} onChange={(event) => setCreateForm((current) => ({ ...current, unit_code: event.target.value }))} placeholder="ORG-CPE" required />
            </div>
            <div className="form-group">
              <label htmlFor="orgName">Unit Name</label>
              <input id="orgName" value={createForm.unit_name} onChange={(event) => setCreateForm((current) => ({ ...current, unit_name: event.target.value }))} placeholder="Computer Engineering Organization" required />
            </div>
            <div className="form-group">
              <label>Department</label>
              <input value={getDepartmentName(parentDepartmentId)} disabled />
            </div>
            <div className="form-group">
              <label htmlFor="orgProgram">Program</label>
              <select id="orgProgram" value={createForm.program_id} onChange={(event) => setCreateForm((current) => ({ ...current, program_id: event.target.value }))} required>
                <option value="">Select program</option>
                {availablePrograms.map((program) => (
                  <option key={program.id} value={program.id}>
                    {program.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="orgDescription">Description</label>
              <textarea id="orgDescription" rows={4} value={createForm.description} onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))} placeholder="Describe this organization." />
            </div>
            <div className="sg-inline-note">ORG units are program-level only. One ORG is allowed per program inside this department.</div>
            {availablePrograms.length === 0 && (
              <div className="ssg-modal-empty">Every program under this department already has an ORG. Edit an existing unit instead.</div>
            )}
          </div>
          <div className="ssg-setup-modal__footer">
            <button type="button" className="btn btn-outline-secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || availablePrograms.length === 0}>
              {saving ? "Saving..." : "Create ORG"}
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
            <h3>Edit ORG</h3>
            <button type="button" className="ssg-setup-modal__close" onClick={() => setIsInfoModalOpen(false)}>
              &times;
            </button>
          </div>
          <div className="ssg-setup-modal__body">
            <div className="form-group">
              <label htmlFor="editOrgCode">Unit Code</label>
              <input id="editOrgCode" value={infoForm.unit_code} onChange={(event) => setInfoForm((current) => ({ ...current, unit_code: event.target.value }))} required />
            </div>
            <div className="form-group">
              <label htmlFor="editOrgName">Unit Name</label>
              <input id="editOrgName" value={infoForm.unit_name} onChange={(event) => setInfoForm((current) => ({ ...current, unit_name: event.target.value }))} required />
            </div>
            <div className="form-group">
              <label>Program</label>
              <input value={getProgramName(selectedOrg?.program_id)} disabled />
            </div>
            <div className="form-group">
              <label htmlFor="editOrgDescription">Description</label>
              <textarea id="editOrgDescription" rows={4} value={infoForm.description} onChange={(event) => setInfoForm((current) => ({ ...current, description: event.target.value }))} />
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
        <form onSubmit={saveMember}>
          <div className="ssg-setup-modal__header">
            <h3>{editingMember ? "Edit ORG Member" : "Add ORG Member"}</h3>
            <button type="button" className="ssg-setup-modal__close" onClick={closeMemberModal}>
              &times;
            </button>
          </div>
          <div className="ssg-setup-modal__body">
            {!editingMember && canManageMembers && (
              <div className="form-group">
                <label htmlFor="orgStudentSearch">Search imported students</label>
                <div className="ssg-search-input">
                  <FaSearch />
                  <input
                    id="orgStudentSearch"
                    value={memberDraft.searchTerm}
                    onChange={(event) => setMemberDraft((current) => ({ ...current, searchTerm: event.target.value, selectedCandidate: null }))}
                    placeholder="Search by student ID or name"
                  />
                </div>
              </div>
            )}
            {!editingMember && canManageMembers && searchingStudents && <div className="ssg-modal-empty">Searching imported students...</div>}
            {!editingMember && canManageMembers && !searchingStudents && memberDraft.searchTerm.trim().length >= 2 && studentResults.length === 0 && !memberDraft.selectedCandidate && (
              <div className="ssg-modal-empty">No imported students found for that search.</div>
            )}
            {!editingMember && canManageMembers && studentResults.length > 0 && !memberDraft.selectedCandidate && (
              <div className="ssg-search-results mb-3">
                {studentResults.map((candidate) => {
                  const summary = getStudentSummary(candidate);
                  return (
                    <button type="button" className="ssg-search-result" key={candidate.user.id} onClick={() => handleSelectCandidate(candidate)}>
                      <strong>{formatUserDisplayName(candidate.user)}</strong>
                      <span>{summary.studentId}</span>
                      <small>{summary.departmentName} - {summary.programName} - {summary.yearLevel}</small>
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
                  <small>{getStudentSummary(memberDraft.selectedCandidate).departmentName} - {getStudentSummary(memberDraft.selectedCandidate).programName} - {getStudentSummary(memberDraft.selectedCandidate).yearLevel}</small>
                </div>
                {!editingMember && canManageMembers && (
                  <button type="button" className="btn btn-outline-secondary" onClick={() => setMemberDraft((current) => ({ ...current, selectedCandidate: null }))}>
                    Change
                  </button>
                )}
              </div>
            )}
            <div className="form-group">
              <label htmlFor="orgPositionTitle">Position title</label>
              <input id="orgPositionTitle" value={memberDraft.positionTitle} onChange={(event) => setMemberDraft((current) => ({ ...current, positionTitle: event.target.value }))} placeholder="President, Secretary, Treasurer..." disabled={!canManageMembers} />
            </div>
            <div className="form-group">
              <label>Permissions</label>
              <div className="ssg-permission-option-grid">
                {permissionOptions.map((permission) => (
                  <label key={permission.code} className="ssg-permission-option">
                    <input type="checkbox" checked={memberDraft.permissionCodes.includes(permission.code)} onChange={() => toggleDraftPermission(permission.code)} disabled={!canAssignPermissions} />
                    <div>
                      <strong>{permission.label}</strong>
                      <span>{permission.description}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <div className="ssg-setup-modal__footer">
            {editingMember && canManageMembers && (
              <button type="button" className="btn btn-outline-danger me-auto" onClick={() => setMemberPendingRemoval(editingMember)}>
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

      <Modal isOpen={memberPendingRemoval !== null} onRequestClose={() => setMemberPendingRemoval(null)} className="ssg-setup-modal ssg-setup-modal--compact" overlayClassName="ssg-setup-overlay">
        <div className="ssg-setup-modal__header">
          <h3>Remove Member</h3>
          <button type="button" className="ssg-setup-modal__close" onClick={() => setMemberPendingRemoval(null)}>
            &times;
          </button>
        </div>
        <div className="ssg-setup-modal__body">
          <p className="mb-2">
            Remove <strong>{memberPendingRemoval ? formatUserDisplayName(memberPendingRemoval.user) : "this member"}</strong> from the selected ORG?
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

export default ManageOrg;
