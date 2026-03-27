import { apiJsonRequest, apiVoidRequest } from "../lib/api/client";

export interface DepartmentSummary {
  id: number;
  name: string;
  school_id?: number | null;
}

export interface ProgramSummary {
  id: number;
  name: string;
  school_id?: number | null;
  department_ids: number[];
}

export interface AcademicCatalog {
  departments: DepartmentSummary[];
  programs: ProgramSummary[];
}

export interface DepartmentPayload {
  name: string;
}

export interface ProgramPayload {
  name: string;
  department_ids: number[];
}

const normalizeProgram = (program: Omit<ProgramSummary, "department_ids"> & {
  department_ids?: number[] | null;
}): ProgramSummary => ({
  ...program,
  department_ids: Array.isArray(program.department_ids) ? program.department_ids : [],
});

export const fetchAcademicDepartments = async (): Promise<DepartmentSummary[]> =>
  apiJsonRequest<DepartmentSummary[]>(
    "/api/departments/",
    { auth: true, method: "GET" },
    "Failed to fetch departments"
  );

export const fetchAcademicPrograms = async (): Promise<ProgramSummary[]> => {
  const programs = await apiJsonRequest<
    Array<Omit<ProgramSummary, "department_ids"> & { department_ids?: number[] | null }>
  >("/api/programs/", { auth: true, method: "GET" }, "Failed to fetch programs");
  return programs.map(normalizeProgram);
};

export const fetchAcademicCatalog = async (): Promise<AcademicCatalog> => {
  const [departments, programs] = await Promise.all([
    fetchAcademicDepartments(),
    fetchAcademicPrograms(),
  ]);

  return {
    departments,
    programs,
  };
};

export const createAcademicDepartment = async (
  payload: DepartmentPayload
): Promise<DepartmentSummary> =>
  apiJsonRequest<DepartmentSummary>(
    "/api/departments/",
    { auth: true, method: "POST", json: payload },
    "Failed to create department"
  );

export const updateAcademicDepartment = async (
  departmentId: number,
  payload: DepartmentPayload
): Promise<DepartmentSummary> =>
  apiJsonRequest<DepartmentSummary>(
    `/api/departments/${departmentId}`,
    { auth: true, method: "PATCH", json: payload },
    "Failed to update department"
  );

export const deleteAcademicDepartment = async (departmentId: number): Promise<void> =>
  apiVoidRequest(
    `/api/departments/${departmentId}`,
    { auth: true, method: "DELETE" },
    "Failed to delete department"
  );

export const createAcademicProgram = async (
  payload: ProgramPayload
): Promise<ProgramSummary> => {
  const program = await apiJsonRequest<
    Omit<ProgramSummary, "department_ids"> & { department_ids?: number[] | null }
  >(
    "/api/programs/",
    { auth: true, method: "POST", json: payload },
    "Failed to create program"
  );

  return normalizeProgram(program);
};

export const updateAcademicProgram = async (
  programId: number,
  payload: ProgramPayload
): Promise<ProgramSummary> => {
  const program = await apiJsonRequest<
    Omit<ProgramSummary, "department_ids"> & { department_ids?: number[] | null }
  >(
    `/api/programs/${programId}`,
    { auth: true, method: "PATCH", json: payload },
    "Failed to update program"
  );

  return normalizeProgram(program);
};

export const deleteAcademicProgram = async (programId: number): Promise<void> =>
  apiVoidRequest(
    `/api/programs/${programId}`,
    { auth: true, method: "DELETE" },
    "Failed to delete program"
  );
