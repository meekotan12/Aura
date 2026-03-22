import { useEffect, useRef, useState } from "react";
import {
  FaCheckCircle,
  FaEdit,
  FaSearch,
  FaShieldAlt,
  FaTrashAlt,
  FaUserCog,
} from "react-icons/fa";
import Modal from "react-modal";
import { useNavigate } from "react-router-dom";

import { normalizeLogoUrl } from "../api/schoolSettingsApi";
import { NavbarAdmin } from "../components/NavbarAdmin";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import { useUser } from "../context/UserContext";
import { isCampusAdminRole, normalizeRole } from "../utils/roleUtils";
import "../css/ManageUsers.css";

// Define interfaces based on your API schemas
interface User {
  id: number;
  email: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  is_active: boolean;
  created_at: string;
  roles: UserRole[];
  student_profile?: StudentProfile;
}

interface UserRole {
  role: {
    name: string;
  };
}

interface StudentProfile {
  id: number;
  student_id?: string;
  year_level?: number;
  department?: Department;
  program?: Program;
  department_id?: number; // Add this field to match your state management
  program_id?: number; // Add this field to match your state management
}

interface Department {
  id: number;
  name: string;
}

interface Program {
  id: number;
  name: string;
  department_ids?: number[];
}

// Enum for roles
enum RoleEnum {
  ADMIN = "admin",
  CAMPUS_ADMIN = "campus_admin",
  STUDENT = "student",
}

const USERS_PAGE_SIZE = 25;

Modal.setAppElement("#root");

const getStoredRoles = (): string[] => {
  try {
    const rawUser = localStorage.getItem("user");
    if (!rawUser) return [];
    const parsed = JSON.parse(rawUser);
    return Array.isArray(parsed?.roles) ? parsed.roles : [];
  } catch {
    return [];
  }
};

const formatRoleLabel = (roleName: string) => {
  switch (roleName) {
    case RoleEnum.ADMIN:
      return "Admin";
    case RoleEnum.CAMPUS_ADMIN:
      return "Campus Admin";
    case RoleEnum.STUDENT:
      return "Student";
    default:
      return roleName;
  }
};

const getRoleTone = (roleName: string) => {
  switch (roleName) {
    case RoleEnum.ADMIN:
      return "primary";
    case RoleEnum.CAMPUS_ADMIN:
      return "info";
    case RoleEnum.STUDENT:
      return "success";
    default:
      return "secondary";
  }
};

const formatCreatedAt = (value?: string) => {
  if (!value) return "No date";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No date";

  return new Intl.DateTimeFormat("en-PH", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
};

export const ManageUsers: React.FC = () => {
  const navigate = useNavigate();
  const { branding } = useUser();
  const roles = getStoredRoles();
  const isSchoolIT = roles.some(isCampusAdminRole);
  const NavbarComponent = isSchoolIT ? NavbarSchoolIT : NavbarAdmin;
  const canManageRoles = !isSchoolIT;
  const editableRoles = canManageRoles
    ? [
        RoleEnum.ADMIN,
        RoleEnum.CAMPUS_ADMIN,
        RoleEnum.STUDENT,
      ]
    : [];
  const [searchTerm, setSearchTerm] = useState("");
  const [users, setUsers] = useState<User[]>([]);
  const [editUserId, setEditUserId] = useState<number | null>(null);
  const [deleteUserId, setDeleteUserId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUsersRefreshing, setIsUsersRefreshing] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string>
  >({});
  const [departments, setDepartments] = useState<Department[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);

  // Edit user state
  const [editedUser, setEditedUser] = useState<Partial<User>>({
    email: "",
    first_name: "",
    middle_name: "",
    last_name: "",
    roles: [],
  });
  const [editStudentProfile, setEditStudentProfile] = useState<
    Partial<StudentProfile>
  >({});
  const [editProfileImage, setEditProfileImage] = useState<File | null>(null);
  const [editPreviewImage, setEditPreviewImage] = useState<string | null>(null);
  const editFileInputRef = useRef<HTMLInputElement>(null);

  const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
  const API_URL = `${BASE_URL}/users`;
  const logoUrl = normalizeLogoUrl(branding?.logo_url);

  const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem("authToken");
    if (!token) {
      navigate("/login");
      throw new Error("No authentication token found");
    }

    const headers = {
      ...options.headers,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };

    try {
      const response = await fetch(url, { ...options, headers });

      if (response.status === 401) {
        localStorage.removeItem("authToken");
        navigate("/login");
        throw new Error("Session expired. Please login again.");
      }

      if (!response.ok) {
        const errorText = await response.text();
        let errorData;
        let errorMessage = `HTTP error! status: ${response.status}`;

        try {
          errorData = JSON.parse(errorText);
          console.error("API Error Response:", errorData);

          if (errorData.detail) {
            errorMessage =
              typeof errorData.detail === "string"
                ? errorData.detail
                : JSON.stringify(errorData.detail);
          } else if (errorData.message) {
            errorMessage = errorData.message;
          } else if (typeof errorData === "object") {
            errorMessage = JSON.stringify(errorData);
          }
        } catch {
          console.error("API Error (non-JSON):", errorText);
          errorMessage = errorText || errorMessage;
        }

        throw new Error(errorMessage);
      }

      return response;
    } catch (err) {
      console.error(`Error fetching ${url}:`, err);
      throw err;
    }
  };

  // Fetch users from API
  const fetchUsers = async (pageIndex = currentPage) => {
    const safePageIndex = Math.max(pageIndex, 0);
    if (!isLoading) {
      setIsUsersRefreshing(true);
    }

    try {
      setError(null);
      // Use canonical collection URL to avoid redirect-induced CORS failures.
      const response = await fetchWithAuth(
        `${API_URL}/?skip=${safePageIndex * USERS_PAGE_SIZE}&limit=${USERS_PAGE_SIZE}`
      );
      const data = await response.json();

      if (safePageIndex > 0 && data.length === 0) {
        setCurrentPage(safePageIndex - 1);
        return;
      }

      setUsers(data);
      setHasNextPage(data.length === USERS_PAGE_SIZE);
      setIsLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setIsLoading(false);
    } finally {
      setIsUsersRefreshing(false);
    }
  };

  // Fetch departments and programs
  const fetchDepartmentsAndPrograms = async () => {
    try {
      const [deptsResponse, progsResponse] = await Promise.all([
        fetchWithAuth(`${BASE_URL}/departments/`),
        fetchWithAuth(`${BASE_URL}/programs/`),
      ]);

      const deptsData = await deptsResponse.json();
      const progsData = await progsResponse.json();

      setDepartments(deptsData);
      setPrograms(progsData);
    } catch (err) {
      console.error("Error fetching departments or programs:", err);
    }
  };

  useEffect(() => {
    void fetchUsers(currentPage);
  }, [currentPage]);

  useEffect(() => {
    void fetchDepartmentsAndPrograms();
  }, []);

  const getFullName = (user: User) => {
    return [user.first_name || "", user.middle_name || "", user.last_name || ""]
      .filter(Boolean)
      .join(" ");
  };

  const handleEditClick = (user: User) => {
    setEditUserId(user.id);
    setEditedUser({ ...user });

    // Set student profile if exists
    if (user.student_profile) {
      setEditStudentProfile({
        student_id: user.student_profile.student_id,
        year_level: user.student_profile.year_level,
        department_id: user.student_profile.department?.id,
        program_id: user.student_profile.program?.id,
      });
    } else {
      setEditStudentProfile({});
    }

    setEditPreviewImage(null); // Reset preview image
    setValidationErrors({});
  };

  const validateFields = (user: Partial<User>) => {
    const errors: Record<string, string> = {};

    if (!user.first_name?.trim()) {
      errors.first_name = "First name is required";
    }

    if (!user.last_name?.trim()) {
      errors.last_name = "Last name is required";
    }

    if (!user.email?.trim()) {
      errors.email = "Email is required";
    } else if (!/\S+@\S+\.\S+/.test(user.email)) {
      errors.email = "Email is invalid";
    }

    if (!isSchoolIT && (!user.roles || user.roles.length === 0)) {
      errors.roles = "At least one role must be selected";
    }

    // Validate student profile if user has student role
    const hasStudentRole = user.roles?.some(
      (r) => r.role.name === RoleEnum.STUDENT
    );
    if (hasStudentRole) {
      if (!editStudentProfile?.student_id?.trim()) {
        errors.student_id = "Student ID is required";
      }
      if (!editStudentProfile?.year_level) {
        errors.year_level = "Year level is required";
      }
      if (!editStudentProfile?.program_id) {
        errors.program_id = "Program is required";
      }
      if (!editStudentProfile?.department_id) {
        errors.department_id = "Department is required";
      }
    }

    return errors;
  };

  const handleSaveChanges = async () => {
    if (editUserId === null || !editedUser.id) {
      console.error("No user selected for editing or missing ID");
      return;
    }

    const errors = validateFields(editedUser);
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    try {
      // Prepare the user update data
      const userUpdateData = {
        email: editedUser.email,
        first_name: editedUser.first_name,
        last_name: editedUser.last_name,
        middle_name: editedUser.middle_name,
      };

      // If roles are being updated
      if (canManageRoles && editedUser.roles) {
        const roleUpdate = {
          roles: editedUser.roles.map((r) => r.role.name),
        };
        await fetchWithAuth(`${API_URL}/${editedUser.id}/roles`, {
          method: "PUT",
          body: JSON.stringify(roleUpdate),
        });
      }

      // Update user basic info
      await fetchWithAuth(`${API_URL}/${editedUser.id}`, {
        method: "PATCH",
        body: JSON.stringify(userUpdateData),
      });

      // Handle student profile
      const hasStudentRole = editedUser.roles?.some(
        (r) => r.role.name === RoleEnum.STUDENT
      );
      if (hasStudentRole) {
        if (editedUser.student_profile) {
          // Update existing student profile
          await fetchWithAuth(
            `${API_URL}/student-profiles/${editedUser.student_profile.id}`,
            {
              method: "PATCH",
              body: JSON.stringify(editStudentProfile),
            }
          );
        } else {
          // Create new student profile
          const studentProfileCreate = {
            user_id: editedUser.id,
            ...editStudentProfile,
          };
          await fetchWithAuth(`${API_URL}/admin/students/`, {
            method: "POST",
            body: JSON.stringify(studentProfileCreate),
          });
        }
      } else if (editedUser.student_profile) {
        // Remove student profile if role was removed
        await fetchWithAuth(
          `${API_URL}/student-profiles/${editedUser.student_profile.id}`,
          {
            method: "DELETE",
          }
        );
      }

      // Handle profile image upload if changed
      if (editProfileImage) {
        const formData = new FormData();
        formData.append("file", editProfileImage);
        await fetchWithAuth(`${API_URL}/${editedUser.id}/upload-photo`, {
          method: "POST",
          body: formData,
          headers: {
            // Remove Content-Type header for FormData
            Authorization: `Bearer ${localStorage.getItem("authToken")}`,
          },
        });
      }

      // Refresh the user list
      await fetchUsers(currentPage);
      setEditUserId(null);
      setEditProfileImage(null);
      setEditPreviewImage(null);
      setValidationErrors({});
    } catch (err) {
      console.error("Update error:", err);
      setError(err instanceof Error ? err.message : "Failed to update user");
    }
  };

  const handleDeleteClick = (userId: number) => {
    setDeleteUserId(userId);
  };

  const handleConfirmDelete = async () => {
    if (deleteUserId === null) return;

    try {
      await fetchWithAuth(`${API_URL}/${deleteUserId}`, {
        method: "DELETE",
      });

      // Refresh the user list
      if (users.length === 1 && currentPage > 0) {
        setDeleteUserId(null);
        setCurrentPage((page) => Math.max(page - 1, 0));
      } else {
        await fetchUsers(currentPage);
        setDeleteUserId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete user");
    }
  };

  const closeEditModal = () => {
    setEditUserId(null);
    setEditProfileImage(null);
    setEditPreviewImage(null);
    setValidationErrors({});
  };

  const closeDeleteModal = () => {
    setDeleteUserId(null);
  };

  const toggleRoleSelection = (roleName: string) => {
    if (!editedUser.roles) return;

    const roleEnumValue = Object.values(RoleEnum).find(
      (r) => r.toLowerCase() === roleName.toLowerCase()
    );
    if (!roleEnumValue) return;

    const newRoles = [...editedUser.roles];
    const existingIndex = newRoles.findIndex(
      (r) => r.role.name === roleEnumValue
    );

    if (existingIndex >= 0) {
      newRoles.splice(existingIndex, 1);
    } else {
      newRoles.push({ role: { name: roleEnumValue } });
    }

    setEditedUser({ ...editedUser, roles: newRoles });
  };

  const handleEditImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setEditProfileImage(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setEditPreviewImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const triggerEditFileInput = () => {
    editFileInputRef.current?.click();
  };

  const getRoleBadge = (role: UserRole) => {
    const roleName = role.role.name;
    const badgeClass = `manage-users-role-pill manage-users-role-pill--${getRoleTone(
      roleName
    )}`;

    return <span className={badgeClass}>{formatRoleLabel(roleName)}</span>;
  };

  const filteredUsers = users.filter((user) => {
    const fullName = getFullName(user);
    const userRoles = user.roles || [];
    const roleNames = userRoles.map((r) => r.role.name).join(", ");
    const studentId = user.student_profile?.student_id || "";
    const yearLevel = user.student_profile?.year_level?.toString() || "";
    const program = user.student_profile?.program?.name || "";
    return [fullName, user.email, roleNames, studentId, yearLevel, program]
      .join(" ")
      .toLowerCase()
      .includes(searchTerm.toLowerCase());
  });

  const totalUsers = users.length;
  const activeUsers = users.filter((user) => user.is_active).length;
  const studentUsers = users.filter(
    (user) =>
      user.roles.some((role) => role.role.name === RoleEnum.STUDENT) ||
      Boolean(user.student_profile)
  ).length;
  const leadershipUsers = users.filter((user) =>
    user.roles.some((role) =>
      [RoleEnum.CAMPUS_ADMIN, RoleEnum.ADMIN].includes(
        normalizeRole(role.role.name) === "campus-admin"
          ? RoleEnum.CAMPUS_ADMIN
          : (role.role.name as RoleEnum)
      )
    )
  ).length;
  const pendingDeletionUser =
    deleteUserId === null
      ? null
      : users.find((user) => user.id === deleteUserId) || null;
  const pageEyebrow = isSchoolIT
    ? "Campus Admin User Management"
    : "Platform User Management";
  const pageTitle = isSchoolIT
    ? "Manage campus users in the same control format"
    : "Review user accounts across the platform";
  const pageCopy = isSchoolIT
    ? "Review imported student accounts, keep academic records accurate, and route SSG assignments through the dedicated Manage SSG flow."
    : "Review school accounts, platform roles, and profile details with the same organized layout used in the governance setup screens.";
  const pageStart = users.length === 0 ? 0 : currentPage * USERS_PAGE_SIZE + 1;
  const pageEnd = currentPage * USERS_PAGE_SIZE + users.length;

  if (isLoading) {
    return (
      <div className="manage-users-page">
        <NavbarComponent />
        <div className="manage-users-state">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="manage-users-page">
      <NavbarComponent />
      <main className="container py-4">
        <section className="manage-users-hero card border-0 shadow-sm mb-4">
          <div className="card-body p-4 p-lg-5">
            <div className="row g-4 align-items-center">
              <div className="col-lg-7">
                <div className="d-flex align-items-center gap-3 mb-3">
                  <div className="manage-users-hero__brand">
                    {logoUrl ? (
                      <img src={logoUrl} alt="School logo" />
                    ) : (
                      <FaUserCog />
                    )}
                  </div>
                  <div>
                    <p className="manage-users-hero__eyebrow mb-1">
                      {pageEyebrow}
                    </p>
                    <h1 className="manage-users-hero__title mb-2">
                      {pageTitle}
                    </h1>
                  </div>
                </div>

                <p className="manage-users-hero__copy mb-3">{pageCopy}</p>

                <div className="manage-users-hero__flow">
                  <span className="is-active">Imported Students</span>
                  <span>/</span>
                  <span>{isSchoolIT ? "Manage SSG" : "Role Assignment"}</span>
                  <span>/</span>
                  <span>Profile Updates</span>
                  <span>/</span>
                  <span>Access Cleanup</span>
                </div>
              </div>

              <div className="col-lg-5">
                <div className="row g-3">
                  <div className="col-sm-6">
                    <div className="manage-users-stat">
                      <span className="manage-users-stat__label">
                        Users Loaded
                      </span>
                      <strong className="manage-users-stat__value">
                        {totalUsers}
                      </strong>
                    </div>
                  </div>
                  <div className="col-sm-6">
                    <div className="manage-users-stat">
                      <span className="manage-users-stat__label">
                        Active on Page
                      </span>
                      <strong className="manage-users-stat__value">
                        {activeUsers}
                      </strong>
                    </div>
                  </div>
                  <div className="col-sm-6">
                    <div className="manage-users-stat">
                      <span className="manage-users-stat__label">
                        Students on Page
                      </span>
                      <strong className="manage-users-stat__value">
                        {studentUsers}
                      </strong>
                    </div>
                  </div>
                  <div className="col-sm-6">
                    <div className="manage-users-stat">
                      <span className="manage-users-stat__label">
                        {isSchoolIT ? "Governance on Page" : "Leadership on Page"}
                      </span>
                      <strong className="manage-users-stat__value">
                        {leadershipUsers}
                      </strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {error && (
          <div className="alert alert-danger d-flex flex-wrap align-items-center justify-content-between gap-3">
            <span>{error}</span>
            <button
              className="btn btn-sm btn-light manage-users-alert-action"
              onClick={() => {
                setError(null);
                void fetchUsers(currentPage);
              }}
              type="button"
            >
              Refresh data
            </button>
          </div>
        )}

        <div className="row g-4">
          <div className="col-xl-4">
            <div className="card border-0 shadow-sm mb-4">
              <div className="card-body p-4">
                <div className="d-flex align-items-center gap-2 mb-3">
                  <FaSearch className="text-primary" />
                  <h2 className="h5 mb-0">Search and Filter</h2>
                </div>

                <div className="manage-users-search-box mb-3">
                  <FaSearch className="manage-users-search-box__icon" />
                  <input
                    type="search"
                      placeholder="Search by name, email, student ID, role, or program"
                    className="form-control manage-users-search-box__input"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                <div className="manage-users-callout">
                  <strong>
                    Page {currentPage + 1} | {filteredUsers.length} users in view
                  </strong>
                  <p className="mb-0">
                    {searchTerm.trim()
                      ? "Your results update live as you search across academic and governance details on the current page."
                      : "Use the search field to narrow the directory by student record, role, email, or program on the current page."}
                  </p>
                </div>
              </div>
            </div>

            <div className="card border-0 shadow-sm">
              <div className="card-body p-4">
                <div className="d-flex align-items-center gap-2 mb-3">
                  <FaShieldAlt className="text-primary" />
                  <h2 className="h5 mb-0">Management Notes</h2>
                </div>

                <div className="manage-users-rule-list">
                  <div className="manage-users-rule-item">
                    <FaCheckCircle />
                    <span>
                      {isSchoolIT
                        ? "Campus Admin manages student accounts here, while SSG assignments and permissions are handled only from Manage SSG."
                        : "Admin can review and maintain all supported user roles across the platform."}
                    </span>
                  </div>
                  <div className="manage-users-rule-item">
                    <FaCheckCircle />
                    <span>
                      Student profile fields stay connected to department, program, and year level data.
                    </span>
                  </div>
                  <div className="manage-users-rule-item">
                    <FaCheckCircle />
                    <span>
                      {isSchoolIT
                        ? "Imported users stay students first. Officer access is granted only when a student is assigned from Manage SSG."
                        : "Only the base auth roles stay here now: Admin, Campus Admin, and Student."}
                    </span>
                  </div>
                  <div className="manage-users-rule-item">
                    <FaCheckCircle />
                    <span>
                      Edit and delete actions now always target the correct user even while the list is filtered.
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-xl-8">
            <div className="card border-0 shadow-sm">
              <div className="card-body p-4">
                <div className="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-3">
                  <div>
                    <h2 className="h5 mb-1">User Directory</h2>
                    <p className="text-muted mb-0">
                      {isSchoolIT
                        ? "Review profile details and maintain academic records for campus students."
                        : "Review profile details, adjust roles, and maintain academic or SSG records."}
                    </p>
                  </div>
                  <div className="manage-users-inline-meta">
                    <span className="manage-users-inline-meta__pill">
                      {isUsersRefreshing ? "Refreshing..." : `Page ${currentPage + 1}`}
                    </span>
                  </div>
                </div>

                {filteredUsers.length === 0 ? (
                  <div className="manage-users-empty-state">
                    No matching users found on this page. Try a different search term or move to another page.
                  </div>
                ) : (
                  <div className="manage-users-table-wrap">
                    <table className="manage-users-table">
                      <thead>
                        <tr>
                          <th>User</th>
                          <th>Roles</th>
                          <th>Academic / Governance</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredUsers.map((user) => (
                          <tr key={user.id}>
                            <td data-label="User">
                              <div className="manage-users-user-cell">
                                <strong>{getFullName(user)}</strong>
                                <span>{user.email}</span>
                                <small>
                                  Created {formatCreatedAt(user.created_at)}
                                </small>
                              </div>
                            </td>
                            <td data-label="Roles">
                              <div className="manage-users-role-row">
                                {user.roles.map((role, index) => (
                                  <span key={`${user.id}-${role.role.name}-${index}`}>
                                    {getRoleBadge(role)}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td data-label="Academic / Governance">
                              <div className="manage-users-detail-stack">
                                {user.student_profile?.student_id && (
                                  <span>ID: {user.student_profile.student_id}</span>
                                )}
                                {user.student_profile?.year_level && (
                                  <span>Year: {user.student_profile.year_level}</span>
                                )}
                                {user.student_profile?.program?.name && (
                                  <span>
                                    Program: {user.student_profile.program.name}
                                  </span>
                                )}
                                {user.student_profile?.department?.name && (
                                  <span>
                                    Dept: {user.student_profile.department.name}
                                  </span>
                                )}
                                {!user.student_profile && (
                                  <span>No additional profile details</span>
                                )}
                              </div>
                            </td>
                            <td data-label="Status">
                              <span
                                className={`manage-users-status-pill ${
                                  user.is_active ? "is-active" : "is-inactive"
                                }`}
                              >
                                {user.is_active ? "Active" : "Inactive"}
                              </span>
                            </td>
                            <td data-label="Actions">
                              <div className="manage-users-action-row">
                                <button
                                  className="btn btn-info"
                                  onClick={() => handleEditClick(user)}
                                  type="button"
                                >
                                  <FaEdit /> Edit
                                </button>
                                <button
                                  className="btn btn-danger"
                                  onClick={() => handleDeleteClick(user.id)}
                                  type="button"
                                >
                                  <FaTrashAlt /> Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {(users.length > 0 || currentPage > 0) && (
                  <div className="manage-users-pagination">
                    <div className="manage-users-pagination__summary">
                      {users.length === 0
                        ? `Page ${currentPage + 1} has no users.`
                        : `Showing ${pageStart}-${pageEnd} on page ${currentPage + 1}`}
                      {searchTerm.trim()
                        ? ` | ${filteredUsers.length} match${filteredUsers.length === 1 ? "" : "es"} on this page`
                        : ""}
                    </div>
                    <div className="manage-users-pagination__controls">
                      <button
                        className="btn btn-outline-secondary"
                        onClick={() => setCurrentPage((page) => Math.max(page - 1, 0))}
                        disabled={currentPage === 0 || isUsersRefreshing}
                        type="button"
                      >
                        Previous
                      </button>
                      <button
                        className="btn btn-outline-secondary"
                        onClick={() => setCurrentPage((page) => page + 1)}
                        disabled={!hasNextPage || isUsersRefreshing}
                        type="button"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Edit User Modal */}
        <Modal
          isOpen={editUserId !== null}
          onRequestClose={closeEditModal}
          className="user-modal"
          overlayClassName="modal-overlay"
        >
          <div className="modal-header">
            <h3>Edit User Account</h3>
            <button
              onClick={closeEditModal}
              className="close-button"
              type="button"
            >
              &times;
            </button>
          </div>
          <div className="modal-body">
            <div className="form-group">
              <label>Profile Image</label>
              <div className="image-upload-container">
                <div className="image-preview" onClick={triggerEditFileInput}>
                  {editPreviewImage ? (
                    <img src={editPreviewImage} alt="Preview" />
                  ) : (
                    <div className="upload-placeholder">
                      Click to upload image
                    </div>
                  )}
                </div>
                <input
                  type="file"
                  ref={editFileInputRef}
                  onChange={handleEditImageChange}
                  accept="image/*"
                  style={{ display: "none" }}
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="editFirstName">First Name</label>
              <input
                type="text"
                id="editFirstName"
                value={editedUser.first_name || ""}
                onChange={(e) =>
                  setEditedUser({ ...editedUser, first_name: e.target.value })
                }
                className={validationErrors.first_name ? "input-error" : ""}
              />
              {validationErrors.first_name && (
                <div className="error-message">
                  {validationErrors.first_name}
                </div>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="editMiddleName">Middle Name (Optional)</label>
              <input
                type="text"
                id="editMiddleName"
                value={editedUser.middle_name || ""}
                onChange={(e) =>
                  setEditedUser({ ...editedUser, middle_name: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label htmlFor="editLastName">Last Name</label>
              <input
                type="text"
                id="editLastName"
                value={editedUser.last_name || ""}
                onChange={(e) =>
                  setEditedUser({ ...editedUser, last_name: e.target.value })
                }
                className={validationErrors.last_name ? "input-error" : ""}
              />
              {validationErrors.last_name && (
                <div className="error-message">
                  {validationErrors.last_name}
                </div>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="editEmail">Email</label>
              <input
                type="email"
                id="editEmail"
                value={editedUser.email || ""}
                onChange={(e) =>
                  setEditedUser({ ...editedUser, email: e.target.value })
                }
                className={validationErrors.email ? "input-error" : ""}
              />
              {validationErrors.email && (
                <div className="error-message">{validationErrors.email}</div>
              )}
            </div>

            {/* Student Profile Fields */}
            {editedUser.roles?.some(
              (r) => r.role.name === RoleEnum.STUDENT
            ) && (
              <>
                <div className="form-group">
                  <label htmlFor="editStudentId">Student ID</label>
                  <input
                    type="text"
                    id="editStudentId"
                    placeholder="Student ID"
                    value={editStudentProfile.student_id || ""}
                    onChange={(e) =>
                      setEditStudentProfile({
                        ...editStudentProfile,
                        student_id: e.target.value,
                      })
                    }
                    className={validationErrors.student_id ? "input-error" : ""}
                  />
                  {validationErrors.student_id && (
                    <div className="error-message">
                      {validationErrors.student_id}
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="editYearLevel">Year Level</label>
                  <select
                    id="editYearLevel"
                    value={editStudentProfile.year_level || 1}
                    onChange={(e) =>
                      setEditStudentProfile({
                        ...editStudentProfile,
                        year_level: parseInt(e.target.value),
                      })
                    }
                    className={validationErrors.year_level ? "input-error" : ""}
                  >
                    {[1, 2, 3, 4, 5].map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                  {validationErrors.year_level && (
                    <div className="error-message">
                      {validationErrors.year_level}
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="editDepartment">Department</label>
                  <select
                    id="editDepartment"
                    value={editStudentProfile.department_id || ""}
                    onChange={(e) =>
                      setEditStudentProfile({
                        ...editStudentProfile,
                        department_id: parseInt(e.target.value),
                      })
                    }
                    className={
                      validationErrors.department_id ? "input-error" : ""
                    }
                  >
                    <option value="">Select Department</option>
                    {departments.map((dept) => (
                      <option key={dept.id} value={dept.id}>
                        {dept.name}
                      </option>
                    ))}
                  </select>
                  {validationErrors.department_id && (
                    <div className="error-message">
                      {validationErrors.department_id}
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="editProgram">Program</label>
                  <select
                    id="editProgram"
                    value={editStudentProfile.program_id || ""}
                    onChange={(e) =>
                      setEditStudentProfile({
                        ...editStudentProfile,
                        program_id: parseInt(e.target.value),
                      })
                    }
                    className={validationErrors.program_id ? "input-error" : ""}
                  >
                    <option value="">Select Program</option>
                    {programs
                      .filter(
                        (prog) =>
                          !editStudentProfile.department_id ||
                          prog.department_ids?.includes(
                            editStudentProfile.department_id
                          )
                      )
                      .map((prog) => (
                        <option key={prog.id} value={prog.id}>
                          {prog.name}
                        </option>
                      ))}
                  </select>
                  {validationErrors.program_id && (
                    <div className="error-message">
                      {validationErrors.program_id}
                    </div>
                  )}
                </div>
              </>
            )}

            {canManageRoles ? (
              <div className="form-group">
                <label>Roles</label>
                <div className="role-selection">
                  {editableRoles.map((role) => {
                    return (
                      <label key={role} className="role-checkbox">
                        <input
                          type="checkbox"
                          checked={
                            editedUser.roles?.some((r) => r.role.name === role) ||
                            false
                          }
                          onChange={() => toggleRoleSelection(role)}
                        />
                        <span className="checkmark"></span>
                        {formatRoleLabel(role)}
                      </label>
                    );
                  })}
                </div>
                {validationErrors.roles && (
                  <div className="error-message">{validationErrors.roles}</div>
                )}
              </div>
            ) : (
              <div className="manage-users-callout">
                <strong>Role changes are locked in Campus Admin.</strong>
                <p className="mb-0">
                  Imported users stay students here. Add or remove SSG officers from
                  {" "}
                  Manage SSG instead of editing roles in this screen.
                </p>
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button
              className="btn btn-secondary"
              onClick={closeEditModal}
              type="button"
            >
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleSaveChanges}
              type="button"
            >
              Save Changes
            </button>
          </div>
        </Modal>

        {/* Delete Confirmation Modal */}
        <Modal
          isOpen={deleteUserId !== null}
          onRequestClose={closeDeleteModal}
          className="confirmation-modal"
          overlayClassName="modal-overlay"
        >
          <div className="modal-header">
            <h3>Confirm Deletion</h3>
          </div>
          <div className="modal-body">
            <p>Are you sure you want to delete this user?</p>
            {pendingDeletionUser && (
              <div className="user-to-delete">
                <p>
                  {getFullName(pendingDeletionUser)} ({pendingDeletionUser.email})
                </p>
                <p>
                  Roles:{" "}
                  {pendingDeletionUser.roles
                    .map((r) => formatRoleLabel(r.role.name))
                    .join(", ")}
                </p>
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button
              className="btn btn-outline-secondary"
              onClick={closeDeleteModal}
              type="button"
            >
              Cancel
            </button>
            <button
              className="btn btn-danger"
              onClick={handleConfirmDelete}
              type="button"
            >
              Delete User
            </button>
          </div>
        </Modal>
      </main>
    </div>
  );
};

export default ManageUsers;
