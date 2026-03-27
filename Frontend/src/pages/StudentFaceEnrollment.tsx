import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { FaCamera, FaCheckCircle, FaUserGraduate } from "react-icons/fa";

import CameraFeed from "../components/CameraFeed";
import { logout } from "../api/authApi";
import {
  clearStudentFaceEnrollmentState,
  fetchStudentFaceEnrollmentStatus,
  registerCurrentStudentFace,
  setStudentFaceEnrollmentRequired,
} from "../api/studentFaceEnrollmentApi";
import { resolveDashboardPath } from "../authFlow";
import { readStoredUserSession } from "../lib/auth/storedUser";
import { sanitizeRedirectPath } from "../utils/redirects";
import "../css/FacialVerification.css";
import "../css/StudentFaceEnrollment.css";

const toErrorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Failed to register the student face.";

const StudentFaceEnrollment = () => {
  const navigate = useNavigate();
  const redirectTimerRef = useRef<number | null>(null);
  const captureLockRef = useRef(false);
  const storedUser = useMemo(() => readStoredUserSession(), []);

  const [loadingStatus, setLoadingStatus] = useState(true);
  const [streamEnabled, setStreamEnabled] = useState(false);
  const [captureRequested, setCaptureRequested] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [studentLabel, setStudentLabel] = useState<string>("Student");

  const fallbackRoles = useMemo(() => storedUser?.roles || [], [storedUser]);
  const dashboardPath = sanitizeRedirectPath(resolveDashboardPath(fallbackRoles), "/student_dashboard");
  const displayName =
    `${storedUser?.firstName || ""} ${storedUser?.lastName || ""}`.trim() || "Student";

  useEffect(
    () => () => {
      if (redirectTimerRef.current) {
        window.clearTimeout(redirectTimerRef.current);
      }
    },
    []
  );

  useEffect(() => {
    if (!storedUser?.roles?.length) {
      navigate("/", { replace: true });
      return;
    }

    const loadStatus = async () => {
      setLoadingStatus(true);
      setStatusError(null);

      try {
        const status = await fetchStudentFaceEnrollmentStatus();
        const nextDashboardPath = resolveDashboardPath(
          status.roles.length > 0 ? status.roles : fallbackRoles
        );
        const safeNextDashboardPath = sanitizeRedirectPath(nextDashboardPath, "/student_dashboard");

        if (!status.hasStudentRole || !status.hasStudentProfile) {
          clearStudentFaceEnrollmentState(status.userId ?? storedUser.id ?? null);
          navigate(safeNextDashboardPath, { replace: true });
          return;
        }

        if (status.faceScanBypassEnabled) {
          clearStudentFaceEnrollmentState(status.userId ?? storedUser.id ?? null);
          navigate(safeNextDashboardPath, { replace: true });
          return;
        }

        if (status.faceRegistered) {
          clearStudentFaceEnrollmentState(status.userId ?? storedUser.id ?? null);
          navigate(safeNextDashboardPath, { replace: true });
          return;
        }

        if (status.userId != null) {
          setStudentFaceEnrollmentRequired(status.userId, true);
        }

        setStudentLabel(status.studentId || displayName);
        setStreamEnabled(true);
      } catch (error) {
        setStatusError(toErrorMessage(error));
      } finally {
        setLoadingStatus(false);
      }
    };

    void loadStatus();
  }, [displayName, fallbackRoles, navigate, storedUser]);

  const handleRegisterRequest = () => {
    if (submitting) {
      return;
    }

    setStatusError(null);
    setSuccessMessage(null);
    setCaptureRequested(true);
    setStreamEnabled(true);
  };

  const handleFrame = async (blob: Blob) => {
    if (!captureRequested || captureLockRef.current) {
      return;
    }

    captureLockRef.current = true;
    setCaptureRequested(false);
    setSubmitting(true);
    setStatusError(null);

    try {
      const result = await registerCurrentStudentFace(blob);
      clearStudentFaceEnrollmentState(storedUser?.id ?? null);
      setStreamEnabled(false);
      setSuccessMessage(
        result.studentId
          ? `Face registered for ${result.studentId}. Redirecting...`
          : "Face registered successfully. Redirecting..."
      );

      redirectTimerRef.current = window.setTimeout(() => {
        navigate(sanitizeRedirectPath(dashboardPath, "/student_dashboard"), { replace: true });
      }, 900);
    } catch (error) {
      setStatusError(toErrorMessage(error));
      setStreamEnabled(true);
    } finally {
      setSubmitting(false);
      captureLockRef.current = false;
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/", { replace: true });
  };

  if (!storedUser) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="student-face-enrollment-page">
      <main className="student-face-enrollment-shell">
        <section className="student-face-enrollment-card">
          <div className="student-face-enrollment-header">
            <span className="student-face-enrollment-badge">
              <FaUserGraduate />
              Student Face Setup
            </span>
            <h1>Register your face before continuing</h1>
            <p>{studentLabel}</p>
          </div>

          {loadingStatus ? (
            <div className="student-face-enrollment-state">
              <div className="student-face-enrollment-spinner" />
              <p>Checking your face registration...</p>
            </div>
          ) : (
            <div className="student-face-enrollment-body">
              <div className="student-face-enrollment-camera">
                <CameraFeed
                  streamEnabled={streamEnabled}
                  scanEnabled={captureRequested && !submitting}
                  showControls
                  circleMask
                  placeholderText="Allow camera access to register your face."
                  onFrame={handleFrame}
                  onCameraStateChange={() => undefined}
                  onScanError={(error) => {
                    if (captureRequested || submitting) {
                      setStatusError(toErrorMessage(error));
                    }
                  }}
                />
              </div>

              <div className="student-face-enrollment-actions">
                <button
                  type="button"
                  className="verification-button verification-button--primary"
                  onClick={handleRegisterRequest}
                  disabled={submitting}
                >
                  <FaCamera />
                  {submitting ? "Registering..." : "Register Face"}
                </button>
                <button
                  type="button"
                  className="verification-button verification-button--neutral"
                  onClick={handleLogout}
                  disabled={submitting}
                >
                  Logout
                </button>
              </div>

              <div className="student-face-enrollment-note">
                Live camera capture is required. If your face is already registered,
                this page will redirect automatically.
              </div>

              {statusError ? (
                <div className="status-message status-message--error">
                  <span>{statusError}</span>
                </div>
              ) : null}

              {successMessage ? (
                <div className="status-message status-message--success">
                  <FaCheckCircle />
                  <span>{successMessage}</span>
                </div>
              ) : null}
            </div>
          )}
        </section>
      </main>
    </div>
  );
};

export default StudentFaceEnrollment;
