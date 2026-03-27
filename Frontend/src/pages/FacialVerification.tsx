import { useMemo } from "react";
import { FaUserShield } from "react-icons/fa";

import NavbarAdmin from "../components/NavbarAdmin";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import PrivilegedFaceWorkspace from "../components/PrivilegedFaceWorkspace";
import type { FacialVerificationRole } from "../api/facialVerificationApi";
import { readStoredUserSession } from "../lib/auth/storedUser";
import "../css/FacialVerification.css";

interface FacialVerificationPageProps {
  role: FacialVerificationRole;
}

const FacialVerification = ({ role }: FacialVerificationPageProps) => {
  const storedUser = useMemo(() => readStoredUserSession(), []);
  const roleLabel = role === "campus_admin" ? "Campus Admin" : "Admin";
  const NavbarComponent = role === "campus_admin" ? NavbarSchoolIT : NavbarAdmin;
  const subjectId = storedUser?.email || role;
  const subjectLabel =
    storedUser?.firstName ||
    storedUser?.lastName
      ? `${storedUser?.firstName ?? ""} ${
          storedUser?.lastName ?? ""
        }`.trim()
      : subjectId;

  return (
    <div className="facial-verification-page">
      <NavbarComponent />
      <main className="facial-verification-shell">
        <section className="facial-verification-hero">
          <span className="facial-verification-badge">
            <FaUserShield />
            Backend Security
          </span>
          <h1>{roleLabel} Live Facial Verification</h1>
          <p>{subjectLabel}</p>
        </section>

        <PrivilegedFaceWorkspace
          role={role}
          subjectId={subjectId}
          subjectLabel={subjectLabel}
          variant="manage"
        />
      </main>
    </div>
  );
};

export default FacialVerification;
