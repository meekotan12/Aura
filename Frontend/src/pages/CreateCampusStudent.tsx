import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FaEnvelope, FaGraduationCap, FaUserPlus } from "react-icons/fa";

import NavbarSchoolIT from "../components/NavbarSchoolIT";
import {
  createStudentAccount,
  fetchSchoolDepartments,
  fetchSchoolPrograms,
  type DepartmentSummary,
  type ProgramSummary,
} from "../api/userApi";
import "../css/CreateCampusStudent.css";

interface StudentFormState {
  first_name: string;
  middle_name: string;
  last_name: string;
  email: string;
  department_id: string;
  program_id: string;
}

const initialFormState: StudentFormState = {
  first_name: "",
  middle_name: "",
  last_name: "",
  email: "",
  department_id: "",
  program_id: "",
};

const CreateCampusStudent = () => {
  const [form, setForm] = useState<StudentFormState>(initialFormState);
  const [departments, setDepartments] = useState<DepartmentSummary[]>([]);
  const [programs, setPrograms] = useState<ProgramSummary[]>([]);
  const [isCatalogLoading, setIsCatalogLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const loadCatalog = async () => {
      setIsCatalogLoading(true);
      setError(null);
      try {
        const [departmentItems, programItems] = await Promise.all([
          fetchSchoolDepartments(),
          fetchSchoolPrograms(),
        ]);
        setDepartments(departmentItems);
        setPrograms(programItems);
      } catch (catalogError) {
        setError(
          catalogError instanceof Error
            ? catalogError.message
            : "Failed to load departments and programs."
        );
      } finally {
        setIsCatalogLoading(false);
      }
    };

    void loadCatalog();
  }, []);

  const filteredPrograms = useMemo(() => {
    if (!form.department_id) {
      return [];
    }

    const selectedDepartmentId = Number(form.department_id);
    return programs.filter((program) =>
      (program.department_ids ?? []).includes(selectedDepartmentId)
    );
  }, [form.department_id, programs]);

  useEffect(() => {
    if (!form.program_id) {
      return;
    }

    const isProgramStillValid = filteredPrograms.some(
      (program) => program.id === Number(form.program_id)
    );
    if (!isProgramStillValid) {
      setForm((current) => ({ ...current, program_id: "" }));
    }
  }, [filteredPrograms, form.program_id]);

  const handleChange = (field: keyof StudentFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setValidationErrors((current) => {
      if (!current[field]) {
        return current;
      }

      const next = { ...current };
      delete next[field];
      return next;
    });
    setError(null);
    setSuccessMessage(null);
  };

  const validateForm = () => {
    const nextErrors: Record<string, string> = {};

    if (!form.first_name.trim()) {
      nextErrors.first_name = "First name is required.";
    }
    if (!form.last_name.trim()) {
      nextErrors.last_name = "Last name is required.";
    }
    if (!form.email.trim()) {
      nextErrors.email = "Email is required.";
    } else if (!/\S+@\S+\.\S+/.test(form.email)) {
      nextErrors.email = "Email must be valid.";
    }
    if (!form.department_id) {
      nextErrors.department_id = "Department is required.";
    }
    if (!form.program_id) {
      nextErrors.program_id = "Program is required.";
    }

    return nextErrors;
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const nextErrors = validateForm();
    if (Object.keys(nextErrors).length > 0) {
      setValidationErrors(nextErrors);
      setSuccessMessage(null);
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const createdStudent = await createStudentAccount({
        email: form.email.trim(),
        first_name: form.first_name.trim(),
        middle_name: form.middle_name.trim() || null,
        last_name: form.last_name.trim(),
        department_id: Number(form.department_id),
        program_id: Number(form.program_id),
      });

      setForm(initialFormState);
      setValidationErrors({});
      setSuccessMessage(
        `Student account created for ${createdStudent.email}. A random password was generated and sent to the student's email address.`
      );
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to create the student account."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="create-campus-student-page">
      <NavbarSchoolIT />

      <main className="container py-4">
        <section className="create-campus-student-hero card border-0 shadow-sm mb-4">
          <div className="card-body p-4 p-lg-5">
            <div className="row g-4 align-items-center">
              <div className="col-lg-8">
                <p className="create-campus-student-eyebrow mb-2">
                  Campus Admin Student Onboarding
                </p>
                <h1 className="create-campus-student-title mb-3">
                  Create a student account and email the generated password
                </h1>
                <p className="create-campus-student-copy mb-0">
                  This flow creates the student inside the same school scope as the
                  signed-in Campus Admin, assigns the student role, creates the
                  student profile, and sends the temporary password by email.
                </p>
              </div>

              <div className="col-lg-4">
                <div className="create-campus-student-summary">
                  <div className="create-campus-student-summary__item">
                    <FaUserPlus />
                    <span>Student role only</span>
                  </div>
                  <div className="create-campus-student-summary__item">
                    <FaGraduationCap />
                    <span>Department and program linked</span>
                  </div>
                  <div className="create-campus-student-summary__item">
                    <FaEnvelope />
                    <span>Password sent by email</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="card border-0 shadow-sm">
          <div className="card-body p-4 p-lg-5">
            <div className="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-4">
              <div>
                <h2 className="h4 mb-1">Student Details</h2>
                <p className="text-muted mb-0">
                  No manual password is required here. The backend generates it.
                </p>
              </div>

              <div className="d-flex gap-2">
                <Link to="/campus_admin_manage_users" className="btn btn-outline-secondary">
                  Manage Users
                </Link>
                <Link to="/campus_admin_dashboard" className="btn btn-outline-primary">
                  Dashboard
                </Link>
              </div>
            </div>

            {error && (
              <div className="alert alert-danger" role="alert">
                {error}
              </div>
            )}

            {successMessage && (
              <div className="alert alert-success" role="alert">
                {successMessage}
              </div>
            )}

            {isCatalogLoading ? (
              <div className="create-campus-student-state">
                <div className="spinner-border text-primary" role="status">
                  <span className="visually-hidden">Loading...</span>
                </div>
              </div>
            ) : (
              <form className="row g-4" onSubmit={handleSubmit}>
                <div className="col-md-6">
                  <label className="form-label" htmlFor="student-first-name">
                    First Name
                  </label>
                  <input
                    id="student-first-name"
                    type="text"
                    className={`form-control ${validationErrors.first_name ? "is-invalid" : ""}`}
                    value={form.first_name}
                    onChange={(event) => handleChange("first_name", event.target.value)}
                  />
                  {validationErrors.first_name && (
                    <div className="invalid-feedback">{validationErrors.first_name}</div>
                  )}
                </div>

                <div className="col-md-6">
                  <label className="form-label" htmlFor="student-middle-name">
                    Middle Name
                  </label>
                  <input
                    id="student-middle-name"
                    type="text"
                    className="form-control"
                    value={form.middle_name}
                    onChange={(event) => handleChange("middle_name", event.target.value)}
                  />
                </div>

                <div className="col-md-6">
                  <label className="form-label" htmlFor="student-last-name">
                    Last Name
                  </label>
                  <input
                    id="student-last-name"
                    type="text"
                    className={`form-control ${validationErrors.last_name ? "is-invalid" : ""}`}
                    value={form.last_name}
                    onChange={(event) => handleChange("last_name", event.target.value)}
                  />
                  {validationErrors.last_name && (
                    <div className="invalid-feedback">{validationErrors.last_name}</div>
                  )}
                </div>

                <div className="col-md-6">
                  <label className="form-label" htmlFor="student-email">
                    Email
                  </label>
                  <input
                    id="student-email"
                    type="email"
                    className={`form-control ${validationErrors.email ? "is-invalid" : ""}`}
                    value={form.email}
                    onChange={(event) => handleChange("email", event.target.value)}
                  />
                  {validationErrors.email && (
                    <div className="invalid-feedback">{validationErrors.email}</div>
                  )}
                </div>

                <div className="col-md-6">
                  <label className="form-label" htmlFor="student-department">
                    Department
                  </label>
                  <select
                    id="student-department"
                    className={`form-select ${validationErrors.department_id ? "is-invalid" : ""}`}
                    value={form.department_id}
                    onChange={(event) => handleChange("department_id", event.target.value)}
                  >
                    <option value="">Select department</option>
                    {departments.map((department) => (
                      <option key={department.id} value={department.id}>
                        {department.name}
                      </option>
                    ))}
                  </select>
                  {validationErrors.department_id && (
                    <div className="invalid-feedback">{validationErrors.department_id}</div>
                  )}
                </div>

                <div className="col-md-6">
                  <label className="form-label" htmlFor="student-program">
                    Program
                  </label>
                  <select
                    id="student-program"
                    className={`form-select ${validationErrors.program_id ? "is-invalid" : ""}`}
                    value={form.program_id}
                    onChange={(event) => handleChange("program_id", event.target.value)}
                    disabled={!form.department_id}
                  >
                    <option value="">
                      {form.department_id ? "Select program" : "Select department first"}
                    </option>
                    {filteredPrograms.map((program) => (
                      <option key={program.id} value={program.id}>
                        {program.name}
                      </option>
                    ))}
                  </select>
                  {validationErrors.program_id && (
                    <div className="invalid-feedback">{validationErrors.program_id}</div>
                  )}
                </div>

                <div className="col-12">
                  <div className="create-campus-student-note">
                    The student will be created in your current school scope. If the
                    email cannot be delivered, the account will not be created.
                  </div>
                </div>

                <div className="col-12 d-flex flex-wrap justify-content-end gap-2">
                  <Link to="/campus_admin_manage_users" className="btn btn-outline-secondary">
                    Cancel
                  </Link>
                  <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                    {isSubmitting ? "Creating student..." : "Create Student"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};

export default CreateCampusStudent;
