import { FormEvent, useEffect, useState } from "react";
import Modal from "react-modal";
import {
  FaEdit,
  FaInfoCircle,
  FaPlus,
  FaProjectDiagram,
  FaSearch,
  FaTrashAlt,
} from "react-icons/fa";

import {
  assignGovernanceMember,
  deleteGovernanceMember,
  fetchCampusSsgSetup,
  GovernanceMemberItem,
  GovernancePermissionCode,
  GovernanceSsgSetupResponse,
  GovernanceStudentCandidate,
  searchGovernanceStudentCandidates,
  updateGovernanceMember,
  updateGovernanceUnit,
} from "../api/governanceHierarchyApi";
import { fetchAcademicCatalog } from "../api/academicApi";
import { normalizeLogoUrl } from "../api/schoolSettingsApi";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import { useUser } from "../context/UserContext";
import { primeGovernanceAccessCache } from "../hooks/useGovernanceAccess";
import "../css/GovernanceHierarchyManagement.css";

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

const permissionSections: Array<{
  key: string;
  title: string;
  description: string;
  permissions: Array<{
    code: GovernancePermissionCode;
    label: string;
    description: string;
    visibilityNote: string;
  }>;
}> = [
  {
    key: "event_management",
    title: "Event Management",
    description: "Controls event and announcement work for SSG officers.",
    permissions: [
      {
        code: "manage_events",
        label: "Manage Events",
        description: "Allow this officer to access and manage SSG event activities.",
        visibilityNote: "Shows: Events",
      },
      {
        code: "manage_announcements",
        label: "Manage Announcements",
        description: "Allow this officer to publish and maintain SSG announcements.",
        visibilityNote: "Shows: Manage Announcements",
      },
    ],
  },
  {
    key: "attendance_management",
    title: "Attendance Management",
    description: "Controls SSG attendance and event record work.",
    permissions: [
      {
        code: "manage_attendance",
        label: "Attendance Management",
        description: "Allow this officer to work on attendance records and manual attendance.",
        visibilityNote: "Shows: Records, Manual Attendance",
      },
    ],
  },
  {
    key: "student_management",
    title: "Student Management",
    description: "Controls student visibility and student management within allowed scope.",
    permissions: [
      {
        code: "view_students",
        label: "View Students",
        description: "Allow this officer to view students within the SSG's allowed scope.",
        visibilityNote: "Shows: View Students",
      },
      {
        code: "manage_students",
        label: "Manage Students",
        description: "Allow this officer to manage students within the SSG's allowed scope.",
        visibilityNote: "Shows: Manage Students",
      },
    ],
  },
  {
    key: "sg_management",
    title: "SG Management",
    description: "Controls SG setup, SG member maintenance, and SG permission assignment.",
    permissions: [
      {
        code: "create_sg",
        label: "Create SG",
        description: "Allow this officer to create SG units under the campus SSG.",
        visibilityNote: "Shows: Create SG",
      },
      {
        code: "assign_permissions",
        label: "Permission Management",
        description: "Allow this officer to assign and update governance permissions for SG work.",
        visibilityNote: "Shows: Permission Management",
      },
      {
        code: "manage_members",
        label: "Manage Members",
        description: "Allow this officer to manage SG-related member assignments and updates.",
        visibilityNote: "Shows: Manage Members",
      },
    ],
  },
];

const permissionCatalog: Array<{
  code: GovernancePermissionCode;
  label: string;
  description: string;
}> = permissionSections.flatMap((section) =>
  section.permissions.map((permission) => ({
    code: permission.code,
    label: permission.label,
    description: permission.description,
  }))
);

const permissionLabelMap = new Map(
  permissionCatalog.map((permission) => [permission.code, permission.label] as const)
);

const emptyMemberDraft: MemberDraftState = {
  selectedCandidate: null as GovernanceStudentCandidate | null,
  searchTerm: "",
  positionTitle: "",
  permissionCodes: [],
};

Modal.setAppElement("#root");

const formatUserDisplayName = (user: {
  first_name?: string | null;
  middle_name?: string | null;
  last_name?: string | null;
  email: string;
}) => {
  const parts = [user.first_name, user.middle_name, user.last_name]
    .map((value) => value?.trim())
    .filter(Boolean);
  return parts.length ? parts.join(" ") : user.email;
};

const getInitials = (name: string) =>
  name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

const getAvatarTone = (seed: number) => {
  const tones = ["tone-blue", "tone-gold", "tone-teal", "tone-coral", "tone-slate"];
  return tones[Math.abs(seed) % tones.length];
};

const GovernanceHierarchyManagement = () => {
  const { branding } = useUser();
  const logoUrl = normalizeLogoUrl(branding?.logo_url);
  const campusName = branding?.school_name || "Campus";

  const [setup, setSetup] = useState<GovernanceSsgSetupResponse | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchingStudents, setSearchingStudents] = useState(false);
  const [studentResults, setStudentResults] = useState<GovernanceStudentCandidate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [isMemberModalOpen, setIsMemberModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<GovernanceMemberItem | null>(null);
  const [memberPendingRemoval, setMemberPendingRemoval] = useState<GovernanceMemberItem | null>(null);
  const [memberDraft, setMemberDraft] = useState(emptyMemberDraft);
  const [infoForm, setInfoForm] = useState({
    unit_name: "Supreme Students Government",
    description: "",
  });

  const ssgUnit = setup?.unit ?? null;
  const totalMembers = ssgUnit?.members.length ?? 0;
  const activePositions = ssgUnit?.members.filter((member) => member.position_title?.trim()).length ?? 0;

  const loadAcademicLookup = async () => {
    const { departments: nextDepartments, programs: nextPrograms } =
      await fetchAcademicCatalog();
    setDepartments(nextDepartments);
    setPrograms(nextPrograms);
  };

  const loadSetup = async () => {
    setLoading(true);
    setError(null);

    try {
      const [setupPayload] = await Promise.all([fetchCampusSsgSetup(), loadAcademicLookup()]);
      setSetup(setupPayload);
      setInfoForm({
        unit_name: setupPayload.unit.unit_name,
        description: setupPayload.unit.description || "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the campus SSG");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSetup();
  }, []);

  useEffect(() => {
    if (!isMemberModalOpen || editingMember || memberDraft.selectedCandidate || memberDraft.searchTerm.trim().length < 2 || !ssgUnit) {
      setStudentResults([]);
      return;
    }

    const timeoutId = window.setTimeout(async () => {
      setSearchingStudents(true);
      try {
        const results = await searchGovernanceStudentCandidates({
          q: memberDraft.searchTerm.trim(),
          governance_unit_id: ssgUnit.id,
          limit: 8,
        });
        setStudentResults(results);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to search imported students");
      } finally {
        setSearchingStudents(false);
      }
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [editingMember, isMemberModalOpen, memberDraft.searchTerm, memberDraft.selectedCandidate, ssgUnit]);

  const getProgramName = (programId?: number | null) =>
    programs.find((program) => program.id === programId)?.name || "No course";

  const getDepartmentName = (departmentId?: number | null) =>
    departments.find((department) => department.id === departmentId)?.name || "No department";

  const getStudentSummary = (candidate: GovernanceStudentCandidate | GovernanceMemberItem) => {
    const profile =
      "student_profile" in candidate ? candidate.student_profile : candidate.user.student_profile;
    return {
      studentId: profile?.student_id || "No ID",
      course: getProgramName(profile?.program_id),
      yearLevel: profile?.year_level ? `Year ${profile.year_level}` : "No year level",
      department: getDepartmentName(profile?.department_id),
    };
  };

  const getPermissionLabels = (member: GovernanceMemberItem) =>
    member.member_permissions.map(
      (item) => permissionLabelMap.get(item.permission.permission_code) || item.permission.permission_code
    );

  const openInfoModal = () => {
    if (!ssgUnit) return;
    setInfoForm({
      unit_name: ssgUnit.unit_name,
      description: ssgUnit.description || "",
    });
    setIsInfoModalOpen(true);
  };

  const openAddMemberModal = () => {
    setEditingMember(null);
    setMemberDraft(emptyMemberDraft);
    setStudentResults([]);
    setIsMemberModalOpen(true);
  };

  const openEditMemberModal = (member: GovernanceMemberItem) => {
    if (!member.user.student_profile) return;
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
  };

  const closeMemberModal = () => {
    setIsMemberModalOpen(false);
    setEditingMember(null);
    setMemberDraft(emptyMemberDraft);
    setStudentResults([]);
  };

  const handleSaveInfo = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!ssgUnit) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const updatedUnit = await updateGovernanceUnit(ssgUnit.id, {
        unit_name: infoForm.unit_name.trim(),
        description: infoForm.description.trim() || null,
      });
      setSetup((current) =>
        current
          ? {
              ...current,
              unit: updatedUnit,
            }
          : current
      );
      setSuccess("Campus SSG details updated successfully.");
      setIsInfoModalOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update SSG details");
    } finally {
      setSaving(false);
    }
  };

  const handleSelectCandidate = (candidate: GovernanceStudentCandidate) => {
    setMemberDraft((current) => ({
      ...current,
      selectedCandidate: candidate,
      searchTerm: "",
    }));
    setStudentResults([]);
  };

  const togglePermission = (permissionCode: GovernancePermissionCode) => {
    setMemberDraft((current) => ({
      ...current,
      permissionCodes: current.permissionCodes.includes(permissionCode)
        ? current.permissionCodes.filter((code) => code !== permissionCode)
        : [...current.permissionCodes, permissionCode],
    }));
  };

  const handleSaveMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!ssgUnit || !memberDraft.selectedCandidate) return;

    const trimmedPositionTitle = memberDraft.positionTitle.trim();
    if (!trimmedPositionTitle) {
      setError("Position title is required for SSG members.");
      setSuccess(null);
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    const payload = {
      user_id: memberDraft.selectedCandidate.user.id,
      position_title: trimmedPositionTitle,
      permission_codes: memberDraft.permissionCodes,
    };

    try {
      if (editingMember) {
        await updateGovernanceMember(editingMember.id, payload);
        setSuccess("SSG member updated successfully.");
      } else {
        await assignGovernanceMember(ssgUnit.id, payload);
        setSuccess("Student added to the campus SSG successfully.");
      }
      await primeGovernanceAccessCache(true);
      await loadSetup();
      closeMemberModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save the SSG member");
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveMember = async () => {
    if (!memberPendingRemoval) return;
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await deleteGovernanceMember(memberPendingRemoval.id);
      await primeGovernanceAccessCache(true);
      await loadSetup();
      if (editingMember?.id === memberPendingRemoval.id) {
        closeMemberModal();
      }
      setMemberPendingRemoval(null);
      setSuccess("SSG member removed successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove the SSG member");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="ssg-setup-page">
      <NavbarSchoolIT />

      <main className="container py-4">
        <section className="ssg-setup-hero card border-0 shadow-sm mb-4">
          <div className="card-body p-4 p-lg-5">
            <div className="d-flex flex-wrap align-items-center justify-content-between gap-4">
              <div className="ssg-setup-hero__copy">
                <div className="d-flex align-items-center gap-3 mb-3">
                  <div className="ssg-setup-hero__brand">
                    {logoUrl ? <img src={logoUrl} alt="Campus logo" /> : <FaProjectDiagram />}
                  </div>
                  <div>
                    <p className="ssg-setup-hero__eyebrow mb-1">Campus Admin / Manage SSG</p>
                    <h1 className="ssg-setup-hero__title mb-2">Campus SSG setup</h1>
                  </div>
                </div>

                <p className="ssg-setup-hero__text mb-0">
                  Maintain the fixed Supreme Students Government for this campus, assign officers
                  from imported students, and keep each officer&apos;s position and permissions organized.
                </p>
              </div>

              <div className="ssg-setup-stats">
                <div className="ssg-setup-stat">
                  <span>Total members</span>
                  <strong>{totalMembers}</strong>
                </div>
                <div className="ssg-setup-stat">
                  <span>Active positions</span>
                  <strong>{activePositions}</strong>
                </div>
                <div className="ssg-setup-stat">
                  <span>Imported students</span>
                  <strong>{setup?.total_imported_students ?? 0}</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <div className="ssg-setup-banner mb-4">
          <FaInfoCircle />
          <span>This SSG is fixed. Every campus has exactly one SSG and it can only be edited here.</span>
        </div>

        {loading || !ssgUnit ? (
          <div className="ssg-setup-empty card border-0 shadow-sm">Loading campus SSG setup...</div>
        ) : (
          <>
            <section className="card border-0 shadow-sm mb-4">
              <div className="card-body p-4">
                <div className="d-flex flex-wrap align-items-start justify-content-between gap-3">
                  <div className="ssg-unit-card__content">
                    <div className="ssg-unit-card__code">{ssgUnit.unit_code}</div>
                    <h2 className="ssg-unit-card__title">{ssgUnit.unit_name}</h2>
                    <p className="ssg-unit-card__meta mb-1">{campusName}</p>
                    <p className="ssg-unit-card__description mb-0">
                      {ssgUnit.description || "No description yet."}
                    </p>
                  </div>
                  <button type="button" className="btn btn-primary" onClick={openInfoModal}>
                    <FaEdit className="me-2" />
                    Edit Info
                  </button>
                </div>
              </div>
            </section>

            <section className="card border-0 shadow-sm">
              <div className="card-body p-4">
                <div className="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-3">
                  <div>
                    <h2 className="h5 mb-1">SSG Members</h2>
                    <p className="text-muted mb-0">
                      Search imported students in this campus and assign them as SSG officers.
                    </p>
                  </div>
                  <button type="button" className="btn btn-primary" onClick={openAddMemberModal}>
                    <FaPlus className="me-2" />
                    Add Member
                  </button>
                </div>

                {ssgUnit.members.length === 0 ? (
                  <div className="ssg-setup-empty">
                    No SSG members yet. Add an imported student to start assigning officers.
                  </div>
                ) : (
                  <div className="ssg-members-table-wrap">
                    <table className="ssg-members-table">
                      <thead>
                        <tr>
                          <th>Student</th>
                          <th>Position</th>
                          <th>Permissions</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ssgUnit.members.map((member) => {
                          const name = formatUserDisplayName(member.user);
                          const summary = getStudentSummary(member);
                          const permissionLabels = getPermissionLabels(member);
                          const preview = permissionLabels.slice(0, 2);
                          const overflowCount = Math.max(permissionLabels.length - preview.length, 0);

                          return (
                            <tr key={member.id}>
                              <td data-label="Student">
                                <div className="ssg-member-student">
                                  <div className={`ssg-member-avatar ${getAvatarTone(member.user_id)}`}>
                                    {getInitials(name)}
                                  </div>
                                  <div>
                                    <strong>{name}</strong>
                                    <span>{summary.studentId}</span>
                                    <small>
                                      {summary.course} / {summary.yearLevel}
                                    </small>
                                  </div>
                                </div>
                              </td>
                              <td data-label="Position">
                                <span className="ssg-position-badge">
                                  {member.position_title || "No position"}
                                </span>
                              </td>
                              <td data-label="Permissions">
                                <div className="ssg-permission-preview">
                                  {preview.length === 0 ? (
                                    <span className="ssg-permission-chip is-muted">No permissions</span>
                                  ) : (
                                    preview.map((label) => (
                                      <span className="ssg-permission-chip" key={`${member.id}-${label}`}>
                                        {label}
                                      </span>
                                    ))
                                  )}
                                  {overflowCount > 0 && (
                                    <span className="ssg-permission-chip is-muted">+{overflowCount}</span>
                                  )}
                                </div>
                              </td>
                              <td data-label="Actions">
                                <div className="ssg-member-actions">
                                  <button
                                    type="button"
                                    className="btn btn-outline-primary"
                                    onClick={() => openEditMemberModal(member)}
                                  >
                                    <FaEdit className="me-2" />
                                    Edit
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-outline-danger"
                                    onClick={() => setMemberPendingRemoval(member)}
                                  >
                                    <FaTrashAlt className="me-2" />
                                    Delete
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </main>

      <Modal isOpen={isInfoModalOpen} onRequestClose={() => setIsInfoModalOpen(false)} className="ssg-setup-modal" overlayClassName="ssg-setup-overlay">
        <form onSubmit={handleSaveInfo}>
          <div className="ssg-setup-modal__header">
            <h3>Edit SSG Info</h3>
            <button type="button" className="ssg-setup-modal__close" onClick={() => setIsInfoModalOpen(false)}>
              &times;
            </button>
          </div>
          <div className="ssg-setup-modal__body">
            <div className="form-group">
              <label>Abbreviation</label>
              <input value={ssgUnit?.unit_code || "SSG"} disabled />
            </div>
            <div className="form-group">
              <label htmlFor="ssgName">Full Name</label>
              <input id="ssgName" value={infoForm.unit_name} onChange={(event) => setInfoForm((current) => ({ ...current, unit_name: event.target.value }))} required />
            </div>
            <div className="form-group">
              <label htmlFor="ssgDescription">Description</label>
              <textarea id="ssgDescription" value={infoForm.description} onChange={(event) => setInfoForm((current) => ({ ...current, description: event.target.value }))} rows={4} />
            </div>
          </div>
          <div className="ssg-setup-modal__footer">
            <button type="button" className="btn btn-outline-secondary" onClick={() => setIsInfoModalOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Save Info"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal isOpen={isMemberModalOpen} onRequestClose={closeMemberModal} className="ssg-setup-modal ssg-setup-modal--wide" overlayClassName="ssg-setup-overlay">
        <form onSubmit={handleSaveMember}>
          <div className="ssg-setup-modal__header">
            <h3>{editingMember ? "Edit Member" : "Add Member"}</h3>
            <button type="button" className="ssg-setup-modal__close" onClick={closeMemberModal}>
              &times;
            </button>
          </div>

          <div className="ssg-setup-modal__body">
            {!editingMember && (
              <div className="form-group">
                <label htmlFor="studentSearch">Search Imported Students</label>
                <div className="ssg-search-input">
                  <FaSearch />
                  <input
                    id="studentSearch"
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

            {!editingMember && searchingStudents && <div className="ssg-modal-empty">Searching imported students...</div>}

            {!editingMember && !searchingStudents && memberDraft.searchTerm.trim().length >= 2 && studentResults.length === 0 && !memberDraft.selectedCandidate && (
              <div className="ssg-modal-empty">No imported students found for that search.</div>
            )}

            {!editingMember && studentResults.length > 0 && !memberDraft.selectedCandidate && (
              <div className="ssg-search-results mb-3">
                {studentResults.map((candidate) => {
                  const summary = getStudentSummary(candidate);
                  return (
                    <button type="button" className="ssg-search-result" key={candidate.user.id} onClick={() => handleSelectCandidate(candidate)}>
                      <strong>{formatUserDisplayName(candidate.user)}</strong>
                      <span>{summary.studentId}</span>
                      <small>
                        {summary.course} / {summary.yearLevel}
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
                    {getStudentSummary(memberDraft.selectedCandidate).course} / {getStudentSummary(memberDraft.selectedCandidate).yearLevel}
                  </small>
                </div>
                {!editingMember && (
                  <button type="button" className="btn btn-outline-secondary" onClick={() => setMemberDraft((current) => ({ ...current, selectedCandidate: null }))}>
                    Change
                  </button>
                )}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="positionTitle">Position Title</label>
              <input id="positionTitle" value={memberDraft.positionTitle} onChange={(event) => setMemberDraft((current) => ({ ...current, positionTitle: event.target.value }))} placeholder="President, Secretary, Treasurer..." />
            </div>

            <div className="form-group">
              <label>Permissions</label>
              <div className="ssg-permission-sections">
                {permissionSections.map((section) => (
                  <section key={section.key} className="ssg-permission-section">
                    <div className="ssg-permission-section__header">
                      <strong>{section.title}</strong>
                      <span>{section.description}</span>
                    </div>
                    <div className="ssg-permission-grid">
                      {section.permissions.map((permission) => (
                        <label key={permission.code} className="ssg-permission-option">
                          <input
                            type="checkbox"
                            checked={memberDraft.permissionCodes.includes(permission.code)}
                            onChange={() => togglePermission(permission.code)}
                          />
                          <div>
                            <strong>{permission.label}</strong>
                            <span>{permission.description}</span>
                            <small className="ssg-permission-option__note">
                              {permission.visibilityNote}
                            </small>
                          </div>
                        </label>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          </div>

          <div className="ssg-setup-modal__footer">
            {editingMember && (
              <button type="button" className="btn btn-outline-danger me-auto" onClick={() => setMemberPendingRemoval(editingMember)}>
                Remove Member
              </button>
            )}
            <button type="button" className="btn btn-outline-secondary" onClick={closeMemberModal}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || !memberDraft.selectedCandidate || !memberDraft.positionTitle.trim()}>
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
            Remove <strong>{memberPendingRemoval ? formatUserDisplayName(memberPendingRemoval.user) : "this member"}</strong> from the campus SSG?
          </p>
          <div className="ssg-remove-note">
            On removal, this user will return to a regular student role unless they still belong to another governance membership.
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

export default GovernanceHierarchyManagement;
