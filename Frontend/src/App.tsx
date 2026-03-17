import { Suspense, lazy, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import ErrorBoundary from "./components/ErrorBoundary";
import { handleInactiveSchoolSession } from "./api/authApi";

const Home = lazy(() => import("./components/Home"));
const Unauthorized = lazy(() => import("./components/Unauthorized"));
const ChangePassword = lazy(() => import("./pages/ChangePassword"));
const FaceLoginChallenge = lazy(() => import("./pages/FaceLoginChallenge"));
const StudentFaceEnrollment = lazy(
  () => import("./pages/StudentFaceEnrollment")
);
const StudentEventCheckIn = lazy(() => import("./pages/StudentEventCheckIn"));
const HomeUser = lazy(() => import("./pages/HomeUser"));
const UpcomingEvents = lazy(() => import("./pages/UpcomingEvents"));
const EventsAttended = lazy(() => import("./pages/EventsAttended"));
const Events = lazy(() => import("./pages/Events"));
const Records = lazy(() => import("./pages/Records"));
const Profile = lazy(() => import("./pages/Profile"));
const Reports = lazy(() => import("./pages/Reports"));
const FaceScan = lazy(() => import("./pages/FaceScan"));
const ManualAttendance = lazy(() =>
  import("./pages/ManualAttendance").then((module) => ({
    default: module.ManualAttendance,
  }))
);
const AcademicManagement = lazy(() => import("./pages/AcademicManagement"));
const SchoolBrandingSettings = lazy(
  () => import("./pages/SchoolBrandingSettings")
);
const SchoolImportUsers = lazy(() => import("./pages/SchoolImportUsers"));
const SchoolPasswordResetRequests = lazy(
  () => import("./pages/SchoolPasswordResetRequests")
);
const AdminSchoolManagement = lazy(
  () => import("./pages/AdminSchoolManagement")
);
const ManageUsers = lazy(() => import("./pages/ManageUsers"));
const AuditLogs = lazy(() => import("./pages/AuditLogs"));
const NotificationCenter = lazy(() => import("./pages/NotificationCenter"));
const SecurityCenter = lazy(() => import("./pages/SecurityCenter"));
const FacialVerification = lazy(() => import("./pages/FacialVerification"));
const SubscriptionCenter = lazy(() => import("./pages/SubscriptionCenter"));
const DataGovernance = lazy(() => import("./pages/DataGovernance"));
const GovernanceHierarchyManagement = lazy(
  () => import("./pages/GovernanceHierarchyManagement")
);
const CampusAnnouncementsMonitor = lazy(
  () => import("./pages/CampusAnnouncementsMonitor")
);
const ManageSg = lazy(() => import("./pages/ManageSg"));
const ManageOrg = lazy(() => import("./pages/ManageOrg"));
const SsgAnnouncements = lazy(() => import("./pages/SsgAnnouncements"));
const SgAnnouncements = lazy(() => import("./pages/SgAnnouncements"));
const OrgAnnouncements = lazy(() => import("./pages/OrgAnnouncements"));
const SsgStudents = lazy(() => import("./pages/SsgStudents"));
const SgStudents = lazy(() => import("./pages/SgStudents"));
const OrgStudents = lazy(() => import("./pages/OrgStudents"));
const GovernanceEventDetailsPage = lazy(
  () => import("./pages/GovernanceEventDetailsPage")
);
const AdminDashboard = lazy(() => import("./dashboard/AdminDashboard"));
const StudentDashboard = lazy(() => import("./dashboard/StudentDashboard"));
const SSGDashboard = lazy(() => import("./dashboard/SSGDashboard"));
const SgDashboard = lazy(() => import("./dashboard/SgDashboard"));
const OrgDashboard = lazy(() => import("./dashboard/OrgDashboard"));
const SchoolITDashboard = lazy(() => import("./dashboard/SchoolITDashboard"));

const RouteLoader = () => (
  <div className="route-loader" role="status" aria-live="polite">
    <div className="route-loader__spinner" />
    <p>Loading page...</p>
  </div>
);

const App = () => {
  useEffect(() => {
    const originalFetch = window.fetch.bind(window);

    window.fetch = async (...args: Parameters<typeof window.fetch>) => {
      const response = await originalFetch(...args);

      if (response.status === 403) {
        const clonedResponse = response.clone();
        let detail: unknown = null;

        try {
          const payload = await clonedResponse.json();
          detail =
            payload && typeof payload === "object"
              ? (payload as { detail?: unknown }).detail ?? null
              : null;
        } catch {
          try {
            detail = await clonedResponse.text();
          } catch {
            detail = null;
          }
        }

        handleInactiveSchoolSession(detail);
      }

      return response;
    };

    return () => {
      window.fetch = originalFetch;
    };
  }, []);

  return (
    <ErrorBoundary>
      <Suspense fallback={<RouteLoader />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Home />} />
          <Route path="/change-password" element={<ChangePassword />} />
          <Route
            path="/auth/face-verification"
            element={<FaceLoginChallenge />}
          />

          <Route element={<ProtectedRoute allowedRoles={["student"]} />}>
            <Route
              path="/student_face_registration"
              element={<StudentFaceEnrollment />}
            />
            <Route
              path="/student_event_checkin"
              element={<StudentEventCheckIn />}
            />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
            <Route path="/admin_dashboard" element={<AdminDashboard />} />
            <Route path="/admin_home" element={<HomeUser role="admin" />} />
            <Route path="/admin_reports" element={<Reports />} />
            <Route
              path="/admin_manage_users"
              element={
                <ErrorBoundary>
                  <AdminSchoolManagement />
                </ErrorBoundary>
              }
            />
            <Route
              path="/admin_school_management"
              element={<Navigate to="/admin_manage_users" replace />}
            />
            <Route path="/admin_audit_logs" element={<AuditLogs />} />
            <Route
              path="/admin_notifications"
              element={<NotificationCenter />}
            />
            <Route path="/admin_security" element={<SecurityCenter />} />
            <Route
              path="/admin_face_verification"
              element={<FacialVerification role="admin" />}
            />
            <Route
              path="/admin_subscription"
              element={<SubscriptionCenter />}
            />
            <Route path="/admin_governance" element={<DataGovernance />} />
            <Route path="/admin_profile" element={<Profile role="admin" />} />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={["student"]} />}>
            <Route path="/student_dashboard" element={<StudentDashboard />} />
            <Route path="/student_home" element={<HomeUser role="student" />} />
            <Route
              path="/student_upcoming_events"
              element={<UpcomingEvents role="student" />}
            />
            <Route
              path="/student_events_attended"
              element={<EventsAttended role="student" />}
            />
            <Route
              path="/student_profile"
              element={<Profile role="student" />}
            />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={["campus_admin"]} />}>
            <Route path="/campus_admin_dashboard" element={<SchoolITDashboard />} />
            <Route path="/campus_admin_home" element={<SchoolITDashboard />} />
            <Route path="/campus_admin_events" element={<Events role="campus_admin" />} />
            <Route path="/campus_admin_reports" element={<Reports />} />
            <Route path="/campus_admin_attendance" element={<Records role="campus_admin" />} />
            <Route path="/campus_admin_announcements" element={<CampusAnnouncementsMonitor />} />
            <Route
              path="/campus_admin_create_department_program"
              element={
                <ErrorBoundary>
                  <AcademicManagement role="campus_admin" />
                </ErrorBoundary>
              }
            />
            <Route
              path="/campus_admin_branding"
              element={<SchoolBrandingSettings />}
            />
            <Route
              path="/campus_admin_import_users"
              element={<SchoolImportUsers />}
            />
            <Route
              path="/campus_admin_password_resets"
              element={<SchoolPasswordResetRequests />}
            />
            <Route path="/campus_admin_manage_users" element={<ManageUsers />} />
            <Route path="/campus_admin_audit_logs" element={<AuditLogs />} />
            <Route
              path="/campus_admin_notifications"
              element={<NotificationCenter />}
            />
            <Route path="/campus_admin_security" element={<SecurityCenter />} />
            <Route
              path="/campus_admin_face_verification"
              element={<FacialVerification role="campus_admin" />}
            />
            <Route
              path="/campus_admin_subscription"
              element={<SubscriptionCenter />}
            />
            <Route path="/campus_admin_governance" element={<DataGovernance />} />
            <Route
              path="/campus_admin_governance_hierarchy"
              element={<GovernanceHierarchyManagement />}
            />
            <Route
              path="/campus_admin_profile"
              element={<Profile role="campus_admin" />}
            />

            <Route
              path="/school_it_dashboard"
              element={<Navigate to="/campus_admin_dashboard" replace />}
            />
            <Route
              path="/school_it_home"
              element={<Navigate to="/campus_admin_home" replace />}
            />
            <Route
              path="/school_it_events"
              element={<Navigate to="/campus_admin_events" replace />}
            />
            <Route
              path="/school_it_reports"
              element={<Navigate to="/campus_admin_reports" replace />}
            />
            <Route
              path="/school_it_attendance"
              element={<Navigate to="/campus_admin_attendance" replace />}
            />
            <Route
              path="/school_it_announcements"
              element={<Navigate to="/campus_admin_announcements" replace />}
            />
            <Route
              path="/school_it_create_department_program"
              element={<Navigate to="/campus_admin_create_department_program" replace />}
            />
            <Route
              path="/school_it_branding"
              element={<Navigate to="/campus_admin_branding" replace />}
            />
            <Route
              path="/school_it_import_users"
              element={<Navigate to="/campus_admin_import_users" replace />}
            />
            <Route
              path="/school_it_password_resets"
              element={<Navigate to="/campus_admin_password_resets" replace />}
            />
            <Route
              path="/school_it_manage_users"
              element={<Navigate to="/campus_admin_manage_users" replace />}
            />
            <Route
              path="/school_it_audit_logs"
              element={<Navigate to="/campus_admin_audit_logs" replace />}
            />
            <Route
              path="/school_it_notifications"
              element={<Navigate to="/campus_admin_notifications" replace />}
            />
            <Route
              path="/school_it_security"
              element={<Navigate to="/campus_admin_security" replace />}
            />
            <Route
              path="/school_it_face_verification"
              element={<Navigate to="/campus_admin_face_verification" replace />}
            />
            <Route
              path="/school_it_subscription"
              element={<Navigate to="/campus_admin_subscription" replace />}
            />
            <Route
              path="/school_it_governance"
              element={<Navigate to="/campus_admin_governance" replace />}
            />
            <Route
              path="/school_it_governance_hierarchy"
              element={<Navigate to="/campus_admin_governance_hierarchy" replace />}
            />
            <Route
              path="/school_it_profile"
              element={<Navigate to="/campus_admin_profile" replace />}
            />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SSG"]}
                redirectTo="/student_dashboard"
              />
            }
          >
            <Route path="/ssg_dashboard" element={<SSGDashboard />} />
            <Route path="/ssg_home" element={<Navigate to="/ssg_dashboard" replace />} />
            <Route path="/ssg_profile" element={<Profile role="ssg" />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SSG"]}
                requiredGovernancePermissions={["manage_events"]}
                redirectTo="/ssg_dashboard"
              />
            }
          >
            <Route path="/ssg_events" element={<Events role="ssg" />} />
            <Route
              path="/ssg_events/:eventId"
              element={<GovernanceEventDetailsPage unitType="SSG" />}
            />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SSG"]}
                requiredGovernancePermissions={["manage_attendance"]}
                redirectTo="/ssg_dashboard"
              />
            }
          >
            <Route path="/ssg_records" element={<Records role="ssg" />} />
            <Route
              path="/ssg_manual_attendance"
              element={<ManualAttendance role="ssg" />}
            />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SSG"]}
                requiredGovernancePermissions={["create_sg", "manage_members", "assign_permissions"]}
                redirectTo="/ssg_dashboard"
              />
            }
          >
            <Route path="/ssg_manage_sg" element={<ManageSg />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SSG"]}
                requiredGovernancePermissions={["manage_announcements"]}
                redirectTo="/ssg_dashboard"
              />
            }
          >
            <Route path="/ssg_announcements" element={<SsgAnnouncements />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SSG"]}
                requiredGovernancePermissions={["view_students", "manage_students"]}
                redirectTo="/ssg_dashboard"
              />
            }
          >
            <Route path="/ssg_students" element={<SsgStudents />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SSG"]}
                redirectTo="/student_dashboard"
              />
            }
          >
            <Route
              path="/student_ssg_dashboard"
              element={<Navigate to="/ssg_dashboard" replace />}
            />
            <Route
              path="/studentssg_home"
              element={<Navigate to="/ssg_dashboard" replace />}
            />
            <Route
              path="/studentssg_upcoming_events"
              element={<UpcomingEvents role="student" />}
            />
            <Route
              path="/studentssg_events_attended"
              element={<EventsAttended role="student" />}
            />
            <Route
              element={
                <ProtectedRoute
                  allowedRoles={["student"]}
                  requiredGovernanceUnitTypes={["SSG"]}
                  requiredGovernancePermissions={["manage_events"]}
                  redirectTo="/studentssg_home"
                />
              }
            >
              <Route
                path="/studentssg_events"
                element={<Navigate to="/ssg_events" replace />}
              />
            </Route>
            <Route
              element={
                <ProtectedRoute
                  allowedRoles={["student"]}
                  requiredGovernanceUnitTypes={["SSG"]}
                  requiredGovernancePermissions={["manage_attendance"]}
                  redirectTo="/studentssg_home"
                />
              }
            >
              <Route
                path="/studentssg_attendance"
                element={<Navigate to="/ssg_manual_attendance" replace />}
              />
              <Route
                path="/studentssg_records"
                element={<Navigate to="/ssg_records" replace />}
              />
              <Route
                path="/studentssg_manual_attendance"
                element={<Navigate to="/ssg_manual_attendance" replace />}
              />
            </Route>
            <Route
              path="/studentssg_face_scan"
              element={<FaceScan role="student" />}
            />
            <Route
              path="/studentssg_profile"
              element={<Profile role="student" />}
            />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SG"]}
                redirectTo="/student_dashboard"
              />
            }
          >
            <Route path="/sg_dashboard" element={<SgDashboard />} />
            <Route path="/sg_home" element={<Navigate to="/sg_dashboard" replace />} />
            <Route path="/sg_profile" element={<Profile role="sg" />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SG"]}
                requiredGovernancePermissions={["manage_events"]}
                redirectTo="/sg_dashboard"
              />
            }
          >
            <Route path="/sg_events" element={<Events role="sg" />} />
            <Route
              path="/sg_events/:eventId"
              element={<GovernanceEventDetailsPage unitType="SG" />}
            />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SG"]}
                requiredGovernancePermissions={["manage_attendance"]}
                redirectTo="/sg_dashboard"
              />
            }
          >
            <Route path="/sg_records" element={<Records role="sg" />} />
            <Route path="/sg_manual_attendance" element={<ManualAttendance role="sg" />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SG"]}
                requiredGovernancePermissions={["create_org", "manage_members", "assign_permissions"]}
                redirectTo="/sg_dashboard"
              />
            }
          >
            <Route path="/sg_manage_org" element={<ManageOrg />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SG"]}
                requiredGovernancePermissions={["manage_announcements"]}
                redirectTo="/sg_dashboard"
              />
            }
          >
            <Route path="/sg_announcements" element={<SgAnnouncements />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["SG"]}
                requiredGovernancePermissions={["view_students", "manage_students"]}
                redirectTo="/sg_dashboard"
              />
            }
          >
            <Route path="/sg_students" element={<SgStudents />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["ORG"]}
                redirectTo="/student_dashboard"
              />
            }
          >
            <Route path="/org_dashboard" element={<OrgDashboard />} />
            <Route path="/org_home" element={<Navigate to="/org_dashboard" replace />} />
            <Route path="/org_profile" element={<Profile role="org" />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["ORG"]}
                requiredGovernancePermissions={["manage_events"]}
                redirectTo="/org_dashboard"
              />
            }
          >
            <Route path="/org_events" element={<Events role="org" />} />
            <Route
              path="/org_events/:eventId"
              element={<GovernanceEventDetailsPage unitType="ORG" />}
            />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["ORG"]}
                requiredGovernancePermissions={["manage_attendance"]}
                redirectTo="/org_dashboard"
              />
            }
          >
            <Route path="/org_records" element={<Records role="org" />} />
            <Route path="/org_manual_attendance" element={<ManualAttendance role="org" />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["ORG"]}
                requiredGovernancePermissions={["manage_announcements"]}
                redirectTo="/org_dashboard"
              />
            }
          >
            <Route path="/org_announcements" element={<OrgAnnouncements />} />
          </Route>

          <Route
            element={
              <ProtectedRoute
                allowedRoles={["student"]}
                requiredGovernanceUnitTypes={["ORG"]}
                requiredGovernancePermissions={["view_students", "manage_students"]}
                redirectTo="/org_dashboard"
              />
            }
          >
            <Route path="/org_students" element={<OrgStudents />} />
          </Route>

          <Route path="/unauthorized" element={<Unauthorized />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
};

export default App;
