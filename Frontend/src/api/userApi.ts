import {
  apiJsonRequest,
  apiRequest,
  apiVoidRequest,
  extractApiErrorMessage,
} from "../lib/api/client";

export interface UserRoleAssignment {
  role: {
    name: string;
  };
}

export interface SchoolScopedUser {
  id: number;
  email: string;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  school_id?: number | null;
  is_active: boolean;
  created_at: string;
  roles: UserRoleAssignment[];
}

export interface DepartmentSummary {
  id: number;
  name: string;
  school_id?: number | null;
}

export interface ProgramSummary {
  id: number;
  name: string;
  school_id?: number | null;
  department_ids?: number[];
}

export interface StudentProfileSummary {
  id: number;
  student_id?: string | null;
  year_level?: number | null;
  department?: DepartmentSummary | null;
  program?: ProgramSummary | null;
  department_id?: number | null;
  program_id?: number | null;
}

export interface SchoolScopedUserWithRelations extends SchoolScopedUser {
  student_profile?: StudentProfileSummary | null;
}

export interface StudentAccountCreatePayload {
  email: string;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  department_id: number;
  program_id: number;
}

export interface UserCreatePayload {
  email: string;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  password: string;
  roles: string[];
}

export interface StudentProfileCreatePayload {
  user_id: number;
  student_id: string;
  department_id: number;
  program_id: number;
  year_level: number;
}

export interface UserUpdatePayload {
  email?: string;
  first_name?: string;
  middle_name?: string | null;
  last_name?: string;
}

export interface StudentProfileUpdatePayload {
  student_id?: string;
  year_level?: number;
  department_id?: number;
  program_id?: number;
}

export const fetchUsersByRole = async (roleName: string): Promise<SchoolScopedUser[]> => {
  return apiJsonRequest<SchoolScopedUser[]>(
    `/api/users/by-role/${encodeURIComponent(roleName)}`,
    { auth: true, method: "GET" },
    `Failed to fetch users for role '${roleName}'`
  );
};

export const fetchSchoolScopedUsers = async ({
  skip = 0,
  limit = 300,
}: {
  skip?: number;
  limit?: number;
} = {}): Promise<SchoolScopedUserWithRelations[]> =>
  apiJsonRequest<SchoolScopedUserWithRelations[]>(
    `/api/users/?skip=${skip}&limit=${limit}`,
    { auth: true, method: "GET" },
    "Failed to fetch campus users"
  );

export const fetchSchoolDepartments = async (): Promise<DepartmentSummary[]> =>
  apiJsonRequest<DepartmentSummary[]>(
    "/api/departments/",
    { auth: true, method: "GET" },
    "Failed to fetch departments"
  );

export const fetchSchoolPrograms = async (): Promise<ProgramSummary[]> =>
  apiJsonRequest<ProgramSummary[]>(
    "/api/programs/",
    { auth: true, method: "GET" },
    "Failed to fetch programs"
  );

export const createStudentAccount = async (
  payload: StudentAccountCreatePayload
): Promise<SchoolScopedUserWithRelations> =>
  apiJsonRequest<SchoolScopedUserWithRelations>(
    "/api/users/students/",
    { auth: true, method: "POST", json: payload },
    "Failed to create student account"
  );

export const createSchoolScopedUser = async (
  payload: UserCreatePayload
): Promise<SchoolScopedUserWithRelations> =>
  apiJsonRequest<SchoolScopedUserWithRelations>(
    "/api/users/",
    { auth: true, method: "POST", json: payload },
    "Failed to create user"
  );

export const createStudentProfile = async (
  payload: StudentProfileCreatePayload
): Promise<void> =>
  apiVoidRequest(
    "/api/users/admin/students/",
    { auth: true, method: "POST", json: payload },
    "Failed to create student profile"
  );

export const updateSchoolScopedUser = async (
  userId: number,
  payload: UserUpdatePayload
): Promise<void> =>
  apiVoidRequest(
    `/api/users/${userId}`,
    { auth: true, method: "PATCH", json: payload },
    "Failed to update user"
  );

export const updateSchoolScopedUserRoles = async (
  userId: number,
  roles: string[]
): Promise<void> =>
  apiVoidRequest(
    `/api/users/${userId}/roles`,
    { auth: true, method: "PUT", json: { roles } },
    "Failed to update user roles"
  );

export const updateStudentProfile = async (
  profileId: number,
  payload: StudentProfileUpdatePayload
): Promise<void> =>
  apiVoidRequest(
    `/api/users/student-profiles/${profileId}`,
    { auth: true, method: "PATCH", json: payload },
    "Failed to update student profile"
  );

export const deleteStudentProfile = async (profileId: number): Promise<void> =>
  apiVoidRequest(
    `/api/users/student-profiles/${profileId}`,
    { auth: true, method: "DELETE" },
    "Failed to delete student profile"
  );

export const uploadUserPhoto = async (userId: number, file: File): Promise<void> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiRequest(`/api/users/${userId}/upload-photo`, {
    auth: true,
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, "Failed to upload user photo"));
  }
};

export const deleteSchoolScopedUser = async (userId: number): Promise<void> =>
  apiVoidRequest(
    `/api/users/${userId}`,
    { auth: true, method: "DELETE" },
    "Failed to delete user"
  );

export const fetchCurrentUserProfile = async (): Promise<SchoolScopedUserWithRelations> =>
  apiJsonRequest<SchoolScopedUserWithRelations>(
    "/api/users/me/",
    { auth: true, method: "GET" },
    "Failed to fetch current user profile"
  );
