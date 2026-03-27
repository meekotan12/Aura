import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import SsgFeatureShell from "../components/SsgFeatureShell";
import {
  type Event as EventRecord,
  type EventAttendanceWithStudent,
  type EventStatsResponse,
  fetchEventAttendancesWithStudents,
  fetchEventById,
  fetchEventStats,
  GovernanceContext,
  openSignOutEarly,
} from "../api/eventsApi";
import { useGovernanceWorkspace } from "../hooks/useGovernanceWorkspace";
import {
  formatManilaDateTime,
  getEffectiveLateCutoff,
  getEffectivePresentCutoff,
  getDerivedAbsenceCutoff,
  hasAttendanceOverrideWindow,
  getSignOutCloseTime,
} from "../utils/eventAttendanceWindow";
import { formatAttendanceDateTime } from "../utils/attendanceDateTime";
import { getGovernanceEventsPath } from "../utils/governanceEventPaths";
import { formatEventDepartments, formatEventPrograms } from "../utils/eventScopeLabels";
import "../css/SsgWorkspace.css";
import "../css/SsgFeatureShell.css";

interface GovernanceEventDetailsPageProps {
  unitType: GovernanceContext;
}

const formatEventDateTime = (datetime: string) => formatManilaDateTime(datetime);

const formatOptionalNumber = (value?: number | null, suffix = "") =>
  value == null ? "Not set" : `${value}${suffix}`;

const GovernanceEventDetailsPage = ({ unitType }: GovernanceEventDetailsPageProps) => {
  const { eventId } = useParams<{ eventId: string }>();
  const parsedEventId = Number(eventId);
  const { hasPermission } = useGovernanceWorkspace(unitType);
  const canViewAttendances = hasPermission("manage_attendance");
  const [signOutActionLoading, setSignOutActionLoading] = useState(false);
  const [signOutMessage, setSignOutMessage] = useState<string | null>(null);
  const [showSignOutEarlyForm, setShowSignOutEarlyForm] = useState(false);
  const [useCurrentGraceMinutes, setUseCurrentGraceMinutes] = useState(true);
  const [customCloseMinutes, setCustomCloseMinutes] = useState("");
  const [eventRecord, setEventRecord] = useState<EventRecord | null>(null);
  const [stats, setStats] = useState<EventStatsResponse | null>(null);
  const [attendees, setAttendees] = useState<EventAttendanceWithStudent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(parsedEventId) || parsedEventId <= 0) {
      setError("Invalid event ID.");
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      fetchEventById(parsedEventId, unitType),
      fetchEventStats(parsedEventId, unitType),
      canViewAttendances
        ? fetchEventAttendancesWithStudents(parsedEventId, unitType)
        : Promise.resolve<EventAttendanceWithStudent[]>([]),
    ])
      .then(([eventDetails, eventStats, attendanceRows]) => {
        if (!isMounted) {
          return;
        }
        setEventRecord(eventDetails);
        setStats(eventStats);
        setAttendees(attendanceRows);
        setSignOutMessage(null);
        setShowSignOutEarlyForm(false);
        setUseCurrentGraceMinutes(true);
        setCustomCloseMinutes(
          eventDetails.sign_out_grace_minutes != null ? `${eventDetails.sign_out_grace_minutes}` : ""
        );
      })
      .catch((requestError) => {
        if (!isMounted) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to load the event details."
        );
      })
      .finally(() => {
        if (!isMounted) {
          return;
        }
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [canViewAttendances, parsedEventId, unitType]);

  const selectedCloseMinutes = useMemo(() => {
    if (useCurrentGraceMinutes) {
      return Math.max(0, Number(eventRecord?.sign_out_grace_minutes ?? 0));
    }

    const parsedMinutes = Number(customCloseMinutes.trim());
    return Number.isFinite(parsedMinutes) ? parsedMinutes : Number.NaN;
  }, [customCloseMinutes, eventRecord?.sign_out_grace_minutes, useCurrentGraceMinutes]);

  const projectedCloseTimeLabel = useMemo(() => {
    if (!eventRecord || !Number.isFinite(selectedCloseMinutes) || selectedCloseMinutes < 0) {
      return "Enter a valid number of minutes to preview the close time.";
    }

    const closeTime = new Date(Date.now() + selectedCloseMinutes * 60_000);
    return formatEventDateTime(closeTime.toISOString());
  }, [eventRecord, selectedCloseMinutes]);

  const currentSignOutCloseLabel = useMemo(() => {
    if (!eventRecord) {
      return "Not set";
    }

    return formatEventDateTime(getSignOutCloseTime(eventRecord).toISOString());
  }, [eventRecord]);
  const attendanceOverrideActive = useMemo(
    () => (eventRecord ? hasAttendanceOverrideWindow(eventRecord) : false),
    [eventRecord]
  );
  const effectivePresentUntilLabel = useMemo(() => {
    if (!eventRecord) {
      return "Not set";
    }

    return formatEventDateTime(getEffectivePresentCutoff(eventRecord).toISOString());
  }, [eventRecord]);
  const effectiveLateUntilLabel = useMemo(() => {
    if (!eventRecord) {
      return "Not set";
    }

    return formatEventDateTime(getEffectiveLateCutoff(eventRecord).toISOString());
  }, [eventRecord]);

  const statCards = useMemo(() => {
    const presentCount = stats?.statuses.present?.count ?? 0;
    const lateCount = stats?.statuses.late?.count ?? 0;
    const incompleteCount = stats?.statuses.incomplete?.count ?? 0;
    const absentCount = stats?.statuses.absent?.count ?? 0;

    return [
      {
        label: "Status",
        value: eventRecord?.status ? eventRecord.status.toUpperCase() : "--",
        hint: "Current workflow status for this event",
      },
      {
        label: "Attendance",
        value: stats?.total ?? 0,
        hint: "Recorded attendance entries for this event",
      },
      {
        label: "Present / Late",
        value: `${presentCount} / ${lateCount}`,
        hint: "Current attendance breakdown",
      },
      {
        label: "Incomplete",
        value: incompleteCount,
        hint: "Signed in but missing a completed sign-out",
      },
      {
        label: "Absent",
        value: absentCount,
        hint: "Students marked absent for this event",
      },
    ];
  }, [eventRecord?.status, stats]);

  const handleOpenSignOutEarly = async () => {
    if (!eventRecord) {
      return;
    }

    if (useCurrentGraceMinutes && Number(eventRecord.sign_out_grace_minutes ?? 0) <= 0) {
      setSignOutMessage(
        "This event currently has 0 sign-out grace minutes. Choose custom minutes to keep sign-out open."
      );
      return;
    }

    if (
      !useCurrentGraceMinutes &&
      (!Number.isFinite(selectedCloseMinutes) ||
        !Number.isInteger(selectedCloseMinutes) ||
        selectedCloseMinutes < 1 ||
        selectedCloseMinutes > 1440)
    ) {
      setSignOutMessage("Enter a whole number between 1 and 1440 minutes.");
      return;
    }

    try {
      setSignOutActionLoading(true);
      setSignOutMessage(null);
      const updatedEvent = await openSignOutEarly(
        eventRecord.id,
        useCurrentGraceMinutes
          ? { use_sign_out_grace_minutes: true }
          : {
              use_sign_out_grace_minutes: false,
              close_after_minutes: selectedCloseMinutes,
            },
        unitType
      );
      setEventRecord(updatedEvent);
      setCustomCloseMinutes(
        updatedEvent.sign_out_grace_minutes != null ? `${updatedEvent.sign_out_grace_minutes}` : ""
      );
      setShowSignOutEarlyForm(false);
      setSignOutMessage(
        useCurrentGraceMinutes
            ? `Sign-out is open now and will close at ${formatEventDateTime(
              getSignOutCloseTime(updatedEvent).toISOString()
            )} using the current grace minutes.`
            : `Sign-out is open now and will close at ${formatEventDateTime(
              getSignOutCloseTime(updatedEvent).toISOString()
            )} using your custom ${updatedEvent.sign_out_grace_minutes ?? selectedCloseMinutes} minute window.`
      );
    } catch (requestError) {
      setSignOutMessage(
        requestError instanceof Error
          ? requestError.message
          : "Failed to open sign-out early."
      );
    } finally {
      setSignOutActionLoading(false);
    }
  };

  return (
    <SsgFeatureShell
      eyebrow={`${unitType} / Events / Details`}
      title={eventRecord?.name || "Event details"}
      description="Review the full event scope, schedule, location settings, and attendance snapshot for this governance event."
      stats={statCards}
      unitType={unitType}
      actions={
        <Link to={getGovernanceEventsPath(unitType)} className="btn btn-light">
          Back to Events
        </Link>
      }
    >
      {error ? <div className="alert alert-danger mb-0">{error}</div> : null}
      {signOutMessage ? <div className="alert alert-info mb-0">{signOutMessage}</div> : null}

      {loading ? (
        <div className="ssg-feature-empty">Loading event details...</div>
      ) : eventRecord ? (
        <div className="ssg-feature-stack">
          <section className="ssg-feature-card">
            <div className="ssg-feature-card__header">
              <div>
                <h2 className="ssg-feature-card__title">Schedule and venue</h2>
                <p className="ssg-feature-card__subtitle">
                  Core event timing and venue information for this {unitType} event.
                </p>
              </div>
              {canViewAttendances ? (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setShowSignOutEarlyForm((currentValue) => !currentValue);
                    setSignOutMessage(null);
                  }}
                  disabled={signOutActionLoading}
                >
                  {showSignOutEarlyForm ? "Cancel Early Sign-Out" : "Open Sign-Out Early"}
                </button>
              ) : null}
            </div>

            {canViewAttendances && showSignOutEarlyForm ? (
              <div className="ssg-feature-card mb-3">
                <div className="ssg-feature-card__header">
                  <div>
                    <h3 className="ssg-feature-card__title">Open Sign-Out Early</h3>
                    <p className="ssg-feature-card__subtitle">
                      This will end the event now and open sign-out immediately. Then the sign-out
                      window will close using either the current grace minutes or your custom minutes.
                    </p>
                  </div>
                </div>

                <div className="ssg-feature-stack">
                  <div className="form-check">
                    <input
                      id="use-current-grace"
                      className="form-check-input"
                      type="radio"
                      name="signOutEarlyMode"
                      checked={useCurrentGraceMinutes}
                      onChange={() => setUseCurrentGraceMinutes(true)}
                    />
                    <label className="form-check-label" htmlFor="use-current-grace">
                      Use current sign-out grace minutes ({eventRecord?.sign_out_grace_minutes ?? 0} minute(s))
                    </label>
                  </div>

                  <div className="form-check">
                    <input
                      id="use-custom-minutes"
                      className="form-check-input"
                      type="radio"
                      name="signOutEarlyMode"
                      checked={!useCurrentGraceMinutes}
                      onChange={() => setUseCurrentGraceMinutes(false)}
                    />
                    <label className="form-check-label" htmlFor="use-custom-minutes">
                      Use custom close minutes
                    </label>
                  </div>

                  {!useCurrentGraceMinutes ? (
                    <div className="ssg-feature-field">
                      <label htmlFor="custom-close-minutes">Close sign-out after</label>
                      <input
                        id="custom-close-minutes"
                        type="number"
                        min={1}
                        max={1440}
                        className="form-control"
                        value={customCloseMinutes}
                        onChange={(changeEvent) => setCustomCloseMinutes(changeEvent.target.value)}
                        placeholder="Enter minutes"
                      />
                    </div>
                  ) : null}

                  <div className="ssg-feature-form-grid">
                    <div className="ssg-feature-field">
                      <label>What will happen</label>
                      <div className="ssg-muted-note">
                        The event end time will be changed to now, and sign-out will open right away.
                      </div>
                    </div>
                    <div className="ssg-feature-field">
                      <label>Projected close time</label>
                      <div className="ssg-muted-note">{projectedCloseTimeLabel}</div>
                    </div>
                  </div>

                  <div className="d-flex gap-2 flex-wrap">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => void handleOpenSignOutEarly()}
                      disabled={signOutActionLoading}
                    >
                      {signOutActionLoading ? "Opening..." : "Open Sign-Out Now"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-light"
                      onClick={() => setShowSignOutEarlyForm(false)}
                      disabled={signOutActionLoading}
                    >
                      Keep Scheduled End
                    </button>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="ssg-feature-form-grid">
              <div className="ssg-feature-field">
                <label>Location</label>
                <div className="ssg-muted-note">{eventRecord.location}</div>
              </div>
              <div className="ssg-feature-field">
                <label>Status</label>
                <div className="ssg-muted-note">{eventRecord.status}</div>
              </div>
              <div className="ssg-feature-field">
                <label>Start</label>
                  <div className="ssg-muted-note">{formatEventDateTime(eventRecord.start_datetime)}</div>
              </div>
              <div className="ssg-feature-field">
                <label>End</label>
                  <div className="ssg-muted-note">{formatEventDateTime(eventRecord.end_datetime)}</div>
              </div>
              <div className="ssg-feature-field">
                <label>Early Check-In Window</label>
                <div className="ssg-muted-note">
                  {eventRecord.early_check_in_minutes ?? 0} minute(s)
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Late Threshold</label>
                <div className="ssg-muted-note">
                  {eventRecord.late_threshold_minutes ?? 0} minute(s)
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Attendance Override</label>
                <div className="ssg-muted-note">
                  {attendanceOverrideActive
                    ? "Active. Students keep the full present and late windows from the time this event was saved."
                    : "Not active. Attendance follows the scheduled start time."}
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Effective Present Until</label>
                <div className="ssg-muted-note">{effectivePresentUntilLabel}</div>
              </div>
              <div className="ssg-feature-field">
                <label>Effective Late Until</label>
                <div className="ssg-muted-note">{effectiveLateUntilLabel}</div>
              </div>
              <div className="ssg-feature-field">
                <label>Derived Absence Cutoff</label>
                <div className="ssg-muted-note">
                        {formatEventDateTime(getDerivedAbsenceCutoff(eventRecord).toISOString())}
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Sign-Out Window</label>
                <div className="ssg-muted-note">
                  {eventRecord.sign_out_grace_minutes ?? 0} minute(s) after the current event end
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Current Sign-Out Close</label>
                <div className="ssg-muted-note">
                  {currentSignOutCloseLabel}
                </div>
              </div>
            </div>
          </section>

          <section className="ssg-feature-card">
            <div className="ssg-feature-card__header">
              <div>
                <h2 className="ssg-feature-card__title">Scope</h2>
                <p className="ssg-feature-card__subtitle">
                  Departments and programs included in the event visibility scope.
                </p>
              </div>
            </div>

            <div className="ssg-feature-form-grid">
              <div className="ssg-feature-field">
                <label>Departments</label>
                {eventRecord.departments?.length ? (
                  <div className="ssg-feature-pill-list">
                    {eventRecord.departments.map((department) => (
                      <span key={department.id} className="ssg-feature-pill">
                        {department.name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="ssg-muted-note">{formatEventDepartments(eventRecord.departments)}</div>
                )}
              </div>
              <div className="ssg-feature-field">
                <label>Programs</label>
                {eventRecord.programs?.length ? (
                  <div className="ssg-feature-pill-list">
                    {eventRecord.programs.map((program) => (
                      <span key={program.id} className="ssg-feature-pill">
                        {program.name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="ssg-muted-note">{formatEventPrograms(eventRecord.programs)}</div>
                )}
              </div>
            </div>
          </section>

          <section className="ssg-feature-card">
            <div className="ssg-feature-card__header">
              <div>
                <h2 className="ssg-feature-card__title">Location verification</h2>
                <p className="ssg-feature-card__subtitle">
                  Geofence settings used when students sign in to this event.
                </p>
              </div>
            </div>

            <div className="ssg-feature-form-grid">
              <div className="ssg-feature-field">
                <label>Geofence Required</label>
                <div className="ssg-muted-note">
                  {eventRecord.geo_required ? "Yes, students must be inside the geofence." : "No"}
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Latitude</label>
                <div className="ssg-muted-note">
                  {formatOptionalNumber(eventRecord.geo_latitude)}
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Longitude</label>
                <div className="ssg-muted-note">
                  {formatOptionalNumber(eventRecord.geo_longitude)}
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Radius</label>
                <div className="ssg-muted-note">
                  {formatOptionalNumber(eventRecord.geo_radius_m, " m")}
                </div>
              </div>
              <div className="ssg-feature-field">
                <label>Max Accuracy</label>
                <div className="ssg-muted-note">
                  {formatOptionalNumber(eventRecord.geo_max_accuracy_m, " m")}
                </div>
              </div>
            </div>
          </section>

          <section className="ssg-feature-card">
            <div className="ssg-feature-card__header">
              <div>
                <h2 className="ssg-feature-card__title">Attendance snapshot</h2>
                <p className="ssg-feature-card__subtitle">
                  Current attendance counts recorded for this event.
                </p>
              </div>
            </div>

            <div className="ssg-feature-summary-grid">
              <article className="ssg-feature-summary-card">
                <strong>{stats?.total ?? 0}</strong>
                <span>Total</span>
              </article>
              <article className="ssg-feature-summary-card">
                <strong>{stats?.statuses.present?.count ?? 0}</strong>
                <span>Present</span>
              </article>
              <article className="ssg-feature-summary-card">
                <strong>{stats?.statuses.late?.count ?? 0}</strong>
                <span>Late</span>
              </article>
              <article className="ssg-feature-summary-card">
                <strong>{stats?.statuses.absent?.count ?? 0}</strong>
                <span>Absent</span>
              </article>
              <article className="ssg-feature-summary-card">
                <strong>{stats?.statuses.excused?.count ?? 0}</strong>
                <span>Excused</span>
              </article>
            </div>
          </section>

          <section className="ssg-feature-card">
            <div className="ssg-feature-card__header">
              <div>
                <h2 className="ssg-feature-card__title">Attendance roster</h2>
                <p className="ssg-feature-card__subtitle">
                  Recent attendee records for this event.
                </p>
              </div>
            </div>

            {!canViewAttendances ? (
              <div className="ssg-muted-note">
                Attendance roster access appears when the current officer has
                <strong> manage_attendance</strong>.
              </div>
            ) : attendees.length === 0 ? (
              <div className="ssg-feature-empty">No attendance records are available yet.</div>
            ) : (
              <div className="ssg-feature-table-card">
                <table>
                  <thead>
                    <tr>
                      <th>Student</th>
                      <th>Status</th>
                      <th>Method</th>
                      <th>Time In</th>
                      <th>Time Out</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attendees.map((item) => (
                      <tr key={item.attendance.id}>
                        <td data-label="Student">
                          <strong>{item.student_name}</strong>
                          <div>{item.student_id}</div>
                        </td>
                        <td data-label="Status">
                          <span className="ssg-feature-pill">{item.attendance.status}</span>
                        </td>
                        <td data-label="Method">{item.attendance.method}</td>
                        <td data-label="Time In">{formatAttendanceDateTime(item.attendance.time_in)}</td>
                        <td data-label="Time Out">
                          {item.attendance.time_out
                            ? formatAttendanceDateTime(item.attendance.time_out)
                            : "Active / no time out"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      ) : (
        <div className="ssg-feature-empty">Event details are not available.</div>
      )}
    </SsgFeatureShell>
  );
};

export default GovernanceEventDetailsPage;
