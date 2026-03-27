import React, { useState, useEffect } from "react";
import { NavbarStudentSSG } from "../components/NavbarStudentSSG";
import { NavbarStudent } from "../components/NavbarStudent";
import SsgFeatureShell from "../components/SsgFeatureShell";
import {
  fetchActiveEventAttendances,
  markAbsentWithoutTimeOut,
  recordAttendanceTimeOut,
  recordManualAttendance,
  type EventAttendanceWithStudent,
} from "../api/attendanceApi";
import { fetchAllEvents } from "../api/eventsApi";
import {
  formatAttendanceDate,
  formatAttendanceTime,
} from "../utils/attendanceDateTime";

interface ManualAttendanceProps {
  role: string;
}
// Types
interface Event {
  id: number;
  name: string; // Changed from title
  start_datetime: string; // Changed from date
  end_datetime: string;
  status: string;
}

interface Attendance {
  id: number;
  student_id: number;
  student: Student; // Add this to include student details
  event_id: number;
  time_in: string;
  time_out?: string | null;
  status: string;
  method: string;
  notes?: string | null;
}

interface Student {
  id: number;
  student_id: string | null; // The actual student ID (like "2020-1234")
  name: string;
}

export const ManualAttendance: React.FC<ManualAttendanceProps> = ({ role }) => {
  const governanceContext =
    role === "ssg" ? "SSG" : role === "sg" ? "SG" : role === "org" ? "ORG" : null;
  const isGovernanceRole = Boolean(governanceContext);
  const governanceUnitType = (governanceContext ?? "SSG") as "SSG" | "SG" | "ORG";
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const [studentId, setStudentId] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");
  const [activeAttendances, setActiveAttendances] = useState<Attendance[]>([]);
  // Add new state for mark absent functionality
  const [markingAbsent, setMarkingAbsent] = useState(false);

  // Fetch events on component mount
  useEffect(() => {
    void fetchEvents();
  }, []);

  // Fetch active attendances when event is selected
  useEffect(() => {
    if (selectedEventId) {
      void fetchActiveAttendances();
    }
  }, [selectedEventId]);

  const fetchEvents = async () => {
    try {
      const eventsData = await fetchAllEvents(
        false,
        governanceContext ?? undefined
      );
      setEvents(eventsData);
    } catch (error) {
      console.error("Error fetching events:", error);
      setMessage("Failed to fetch events");
      setMessageType("error");
    }
  };

  const fetchActiveAttendances = async () => {
    if (!selectedEventId) return;

    try {
      const attendancesWithStudents = await fetchActiveEventAttendances(
        selectedEventId,
        governanceContext ?? undefined
      );

      // Transform the data to match your frontend interface
      const formattedAttendances = attendancesWithStudents.map((item: EventAttendanceWithStudent) => ({
        ...item.attendance,
        student: {
          id: item.attendance.student_id,
          student_id: item.student_id,
          name: item.student_name,
        },
      }));

      setActiveAttendances(formattedAttendances);
    } catch (error) {
      console.error("Error fetching attendances:", error);
    }
  };

  const showMessage = (text: string, type: "success" | "error") => {
    setMessage(text);
    setMessageType(type);
    setTimeout(() => {
      setMessage("");
      setMessageType("");
    }, 5000);
  };

  const handleTimeIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEventId || !studentId.trim()) {
      showMessage("Please select an event and enter a student ID", "error");
      return;
    }

    setLoading(true);
    try {
      const payload = await recordManualAttendance({
        eventId: selectedEventId,
        studentId: studentId.trim(),
        notes: notes.trim() || null,
        governanceContext: governanceContext ?? undefined,
      });
      showMessage(
        payload?.action === "time_out"
          ? `Time out recorded successfully for ${studentId}`
          : `Time in recorded successfully for ${studentId}`,
        "success"
      );
      setStudentId("");
      setNotes("");
      fetchActiveAttendances(); // Refresh active attendances
    } catch (error) {
      showMessage(
        error instanceof Error ? error.message : "Failed to record time in",
        "error"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleTimeOut = async (
    attendanceId: number,
    studentDisplayId: string | null
  ) => {
    setLoading(true);
    try {
      await recordAttendanceTimeOut(
        attendanceId,
        governanceContext ?? undefined
      );
      showMessage(
        `Time out recorded successfully for ${studentDisplayId ?? "the selected student"}`,
        "success"
      );
      fetchActiveAttendances(); // Refresh active attendances
    } catch (error) {
      showMessage(
        error instanceof Error ? error.message : "Failed to record time out",
        "error"
      );
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (timeString: string | null) => formatAttendanceTime(timeString);
  const formatDate = (timeString: string | null) => formatAttendanceDate(timeString);

  // NEW: Handle mark absent functionality
  const handleMarkAbsent = async () => {
    if (!selectedEventId) {
      showMessage("Please select an event first", "error");
      return;
    }

    const confirmMessage = `This will mark all students who timed in but didn't time out as ABSENT for the selected event. Are you sure?`;

    if (!window.confirm(confirmMessage)) {
      return;
    }

    setMarkingAbsent(true);
    try {
      const result = await markAbsentWithoutTimeOut(
        selectedEventId,
        governanceContext ?? undefined
      );
      showMessage(
        `Successfully marked ${result.updated_count} students as absent`,
        "success"
      );
      fetchActiveAttendances(); // Refresh active attendances
    } catch (error) {
      showMessage(
        error instanceof Error
          ? error.message
          : "Failed to mark students absent",
        "error"
      );
    } finally {
      setMarkingAbsent(false);
    }
  };

  // Get selected event details for display
  const selectedEvent = events.find((event) => event.id === selectedEventId);

  if (isGovernanceRole) {
    const manualStats = [
      {
        label: "Available Events",
        value: events.length,
        hint: "Events currently available for attendance work",
      },
      {
        label: "Selected Event",
        value: selectedEvent ? selectedEvent.name : "None",
        hint: "Current event receiving manual attendance updates",
      },
      {
        label: "Active Attendances",
        value: activeAttendances.length,
        hint: "Students who have timed in but not timed out",
      },
      {
        label: "Absent Flow",
        value: markingAbsent ? "Running" : "Ready",
        hint: "Bulk absent marking status for open sessions",
      },
    ];

    return (
      <SsgFeatureShell
        eyebrow={`${governanceContext} / Manual Attendance`}
        title={
          governanceContext === "SSG"
            ? "Manual attendance workspace"
            : governanceContext === "SG"
              ? "Department attendance workspace"
              : "Organization attendance workspace"
        }
        description={
          governanceContext === "SSG"
            ? "Record student time in, time out, and handle remaining open attendance sessions for the selected event."
            : governanceContext === "SG"
              ? "Record department attendance, manage time out, and handle remaining open attendance sessions for the selected event."
              : "Record organization attendance, manage time out, and handle remaining open attendance sessions for the selected event."
        }
        stats={manualStats}
        unitType={governanceUnitType}
      >
        {message && (
          <div className={`alert ${messageType === "success" ? "alert-success" : "alert-danger"} mb-0`}>
            {message}
          </div>
        )}

        <section className="ssg-feature-form-grid">
          <article className="ssg-feature-card">
            <div className="ssg-feature-card__header">
              <div>
                <h2 className="ssg-feature-card__title">Record time in</h2>
                <p className="ssg-feature-card__subtitle">
                  Select an event and submit the student ID to add a manual attendance record.
                </p>
              </div>
            </div>

            <form onSubmit={handleTimeIn} className="ssg-feature-stack">
              <div className="ssg-feature-field">
                <label htmlFor="event-select">Select Event</label>
                <select
                  id="event-select"
                  className="ssg-feature-select"
                  value={selectedEventId || ""}
                  onChange={(e) => setSelectedEventId(Number(e.target.value) || null)}
                  required
                >
                  <option value="">Choose an event...</option>
                  {events.map((event) => (
                    <option key={event.id} value={event.id}>
                      {event.name} - {formatDate(event.start_datetime)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="ssg-feature-field">
                <label htmlFor="student-id">Student ID</label>
                <input
                  id="student-id"
                  className="ssg-feature-input"
                  type="text"
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  placeholder="Enter student ID"
                  required
                />
              </div>

              <div className="ssg-feature-field ssg-feature-field--full">
                <label htmlFor="notes">Notes</label>
                <textarea
                  id="notes"
                  className="ssg-feature-textarea"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add any notes..."
                  rows={3}
                />
              </div>

              <div className="ssg-inline-actions">
                <button type="submit" disabled={loading} className="btn btn-primary">
                  {loading ? "Recording..." : "Record Time In"}
                </button>
              </div>
            </form>
          </article>

          <article className="ssg-feature-card">
            <div className="ssg-feature-card__header">
              <div>
                <h2 className="ssg-feature-card__title">Active attendances</h2>
                <p className="ssg-feature-card__subtitle">
                  Open sessions for the selected event that still need time out or absent handling.
                </p>
              </div>
              {activeAttendances.length > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAbsent}
                  disabled={markingAbsent}
                  className="btn btn-outline-warning"
                  title="Mark all active attendances as absent"
                >
                  {markingAbsent ? "Marking Absent..." : "Mark All as Absent"}
                </button>
              )}
            </div>

            {selectedEvent && (
              <div className="ssg-feature-empty">
                Event: <strong>{selectedEvent.name}</strong> ({activeAttendances.length} active)
              </div>
            )}

            {!selectedEventId ? (
              <div className="ssg-feature-empty">Select an event first to view active attendances.</div>
            ) : activeAttendances.length === 0 ? (
              <div className="ssg-feature-empty">No active attendances found for this event.</div>
            ) : (
              <div className="ssg-feature-list">
                {activeAttendances.map((attendance) => (
                  <div key={attendance.id} className="ssg-feature-list-item">
                    <div className="ssg-feature-list-item__meta">
                      <strong>
                        {attendance.student.student_id ?? "No student ID"} - {attendance.student.name}
                      </strong>
                      <span>
                        Time In: {formatTime(attendance.time_in)} on {formatDate(attendance.time_in)}
                      </span>
                      {attendance.notes && <small>Notes: {attendance.notes}</small>}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleTimeOut(attendance.id, attendance.student.student_id)}
                      disabled={loading}
                      className="btn btn-outline-primary"
                    >
                      {loading ? "Recording..." : "Record Time Out"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </article>
        </section>
      </SsgFeatureShell>
    );
  }

  return (
    <div className="attendance-container">
      {role === "student-ssg" ? (
        <NavbarStudentSSG />
      ) : (
        <NavbarStudent />
      )}
      <div className="attendance-header">
        <h1>Manual Attendance</h1>
        <p>Record student time in and time out manually</p>
      </div>

      {message && <div className={`message ${messageType}`}>{message}</div>}

      <div className="attendance-content">
        {/* Time In Form */}
        <div className="attendance-card">
          <h2>Record Time In</h2>
          <form onSubmit={handleTimeIn} className="attendance-form">
            <div className="form-group">
              <label htmlFor="event-select">Select Event *</label>
              <select
                id="event-select"
                value={selectedEventId || ""}
                onChange={(e) =>
                  setSelectedEventId(Number(e.target.value) || null)
                }
                required
                className="form-control"
              >
                <option value="">Choose an event...</option>
                {events.map((event) => (
                  <option key={event.id} value={event.id}>
                    {event.name} - {formatDate(event.start_datetime)}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="student-id">Student ID *</label>
              <input
                id="student-id"
                type="text"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="Enter student ID"
                required
                className="form-control"
              />
            </div>

            <div className="form-group">
              <label htmlFor="notes">Notes (Optional)</label>
              <textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add any notes..."
                rows={3}
                className="form-control"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? "Recording..." : "Record Time In"}
            </button>
          </form>
        </div>

        {/* Active Attendances */}
        {selectedEventId && (
          <div className="attendance-card">
            <div className="card-header-with-action">
              <div>
                <h2>Active Attendances</h2>
                <p className="card-subtitle">
                  Students who haven't timed out yet
                </p>
              </div>
              {/* NEW: Mark Absent Button */}
              {activeAttendances.length > 0 && (
                <button
                  onClick={handleMarkAbsent}
                  disabled={markingAbsent}
                  className="btn btn-warning btn-mark-absent"
                  title="Mark all active attendances as absent (for students who didn't time out)"
                >
                  {markingAbsent ? "Marking Absent..." : "Mark All as Absent"}
                </button>
              )}
            </div>

            {selectedEvent && (
              <div className="event-info">
                <strong>Event:</strong> {selectedEvent.name} (
                {activeAttendances.length} active)
              </div>
            )}

            {activeAttendances.length === 0 ? (
              <div className="empty-state">
                <p>No active attendances found for this event.</p>
              </div>
            ) : (
              <div className="attendance-list">
                {activeAttendances.map((attendance) => (
                  <div key={attendance.id} className="attendance-item">
                    <div className="attendance-info">
                      <div className="student-info">
                        <span className="student-id">
                          Student: {attendance.student.student_id ?? "No student ID"} -{" "}
                          {attendance.student.name}
                        </span>
                        <span className="time-in">
                          Time In: {formatTime(attendance.time_in)} on{" "}
                          {formatDate(attendance.time_in)}
                        </span>
                        {attendance.notes && (
                          <span className="notes">
                            Notes: {attendance.notes}
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        handleTimeOut(
                          attendance.id,
                          attendance.student.student_id
                        )
                      }
                      disabled={loading}
                      className="btn btn-secondary"
                    >
                      {loading ? "Recording..." : "Record Time Out"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <style>{`
        .attendance-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
        }

        .attendance-header {
          text-align: center;
          margin-bottom: 30px;
        }

        .attendance-header h1 {
          color: var(--primary-color, #162F65);
          margin-bottom: 10px;
          font-size: 2.5rem;
          font-weight: 600;
        }

        .attendance-header p {
          color: var(--secondary-color, #2C5F9E);
          font-size: 1.1rem;
        }

        .message {
          padding: 12px 16px;
          border-radius: 8px;
          margin-bottom: 20px;
          font-weight: 500;
        }

        .message.success {
          background-color: #d4edda;
          border: 1px solid #c3e6cb;
          color: #155724;
        }

        .message.error {
          background-color: #f8d7da;
          border: 1px solid #f5c6cb;
          color: #721c24;
        }

        .attendance-content {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 30px;
        }

        @media (max-width: 768px) {
          .attendance-content {
            grid-template-columns: 1fr;
          }
        }

        .attendance-card {
          background: white;
          border-radius: 12px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
          padding: 25px;
          border: 1px solid #e1e5e9;
        }

        .attendance-card h2 {
          margin-top: 0;
          margin-bottom: 20px;
          color: var(--primary-color, #162F65);
          font-size: 1.5rem;
          font-weight: 600;
        }

        .card-subtitle {
          color: #666;
          margin-bottom: 20px;
          font-size: 0.9rem;
        }

        /* NEW: Card header with action button */
        .card-header-with-action {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 15px;
        }

        .card-header-with-action h2 {
          margin: 0 0 5px 0;
        }

        .card-header-with-action .card-subtitle {
          margin-bottom: 0;
        }

        .btn-mark-absent {
          flex-shrink: 0;
          margin-left: 15px;
          font-size: 0.9rem;
          padding: 8px 16px;
        }

        /* NEW: Event info section */
        .event-info {
          background-color: #f8f9fa;
          padding: 10px 15px;
          border-radius: 6px;
          margin-bottom: 15px;
          font-size: 0.9rem;
          color: #495057;
          border-left: 4px solid var(--primary-color, #162F65);
        }

        .attendance-form {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
        }

        .form-group label {
          margin-bottom: 6px;
          font-weight: 500;
          color: var(--primary-color, #162F65);
          font-size: 0.9rem;
        }

        .form-control {
          padding: 12px;
          border: 2px solid #e1e5e9;
          border-radius: 8px;
          font-size: 16px;
          transition: border-color 0.2s;
        }

        .form-control:focus {
          outline: none;
          border-color: var(--primary-color, #162F65);
          box-shadow: 0 0 0 3px rgba(22, 47, 101, 0.1);
        }

        .btn {
          padding: 12px 24px;
          border: none;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          text-align: center;
        }

        .btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .btn-primary {
          background-color: var(--primary-color, #162F65);
          color: white;
        }

        .btn-primary:hover:not(:disabled) {
          background-color: var(--secondary-color, #2C5F9E);
          transform: translateY(-1px);
        }

        .btn-secondary {
          background-color: #6c757d;
          color: white;
        }

        .btn-secondary:hover:not(:disabled) {
          background-color: #545b62;
          transform: translateY(-1px);
        }

        /* NEW: Warning button style */
        .btn-warning {
          background-color: #ffc107;
          color: #212529;
        }

        .btn-warning:hover:not(:disabled) {
          background-color: #e0a800;
          transform: translateY(-1px);
        }

        .empty-state {
          text-align: center;
          padding: 40px 20px;
          color: #666;
        }

        .attendance-list {
          display: flex;
          flex-direction: column;
          gap: 15px;
        }

        .attendance-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 15px;
          background-color: #f8f9fa;
          border-radius: 8px;
          border: 1px solid #e1e5e9;
        }

        .attendance-info {
          flex: 1;
        }

        .student-info {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .student-id {
          font-weight: 600;
          color: var(--primary-color, #162F65);
          font-size: 1rem;
        }

        .time-in {
          color: #666;
          font-size: 0.9rem;
        }

        .notes {
          color: #666;
          font-size: 0.85rem;
          font-style: italic;
        }

        @media (max-width: 768px) {
          .card-header-with-action {
            flex-direction: column;
            align-items: stretch;
            gap: 15px;
          }

          .btn-mark-absent {
            margin-left: 0;
            width: 100%;
          }
        }

        @media (max-width: 480px) {
          .attendance-item {
            flex-direction: column;
            align-items: stretch;
            gap: 10px;
          }

          .btn {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
};
