import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { NavbarStudent } from "../components/NavbarStudent";
import { NavbarStudentSSG } from "../components/NavbarStudentSSG";
import { FaArrowRight, FaSearch } from "react-icons/fa";
import {
  fetchAllEvents,
  fetchMyAttendanceRecords,
  type AttendanceRecord,
  type Event,
} from "../api/eventsApi";
import {
  formatManilaDateTime,
  getStudentEventActionState,
} from "../utils/eventAttendanceWindow";
import { formatEventDepartments, formatEventPrograms } from "../utils/eventScopeLabels";
import { getAttendanceTimestamp } from "../utils/attendanceDateTime";
import "../css/UpcomingEvents.css";

interface UpcomingEventsProps {
  role: string;
}

export const UpcomingEvents: React.FC<UpcomingEventsProps> = ({ role }) => {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [events, setEvents] = useState<Event[]>([]);
  const [attendanceRecords, setAttendanceRecords] = useState<AttendanceRecord[]>(
    []
  );
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const deferredSearchTerm = useDeferredValue(searchTerm);

  useEffect(() => {
    const loadEvents = async () => {
      setIsLoading(true);
      try {
        const [allEvents, myAttendanceRecords] = await Promise.all([
          fetchAllEvents(true),
          fetchMyAttendanceRecords(),
        ]);

        const mergedEvents = allEvents
          .filter((event) => event.status === "ongoing" || event.status === "upcoming")
          .sort(
          (left, right) => {
            if (left.status !== right.status) {
              return left.status === "ongoing" ? -1 : 1;
            }

            return (
              new Date(left.start_datetime).getTime() -
              new Date(right.start_datetime).getTime()
            );
          }
          );

        setEvents(mergedEvents);
        setAttendanceRecords(myAttendanceRecords);
      } catch (error) {
        console.error("Error fetching events:", error);
      } finally {
        setIsLoading(false);
      }
    };

    loadEvents();
  }, []);

  const latestAttendanceByEvent = useMemo(() => {
    const recordsByEvent = new Map<number, AttendanceRecord>();

    for (const record of attendanceRecords) {
      const existing = recordsByEvent.get(record.event_id);
      if (!existing) {
        recordsByEvent.set(record.event_id, record);
        continue;
      }

      if (getAttendanceTimestamp(record.time_in) > getAttendanceTimestamp(existing.time_in)) {
        recordsByEvent.set(record.event_id, record);
      }
    }

    return recordsByEvent;
  }, [attendanceRecords]);

  const formatDateTime = (datetime: string) => {
    return formatManilaDateTime(datetime);
  };

  const hasGeofence = (event: Event) =>
    event.geo_latitude != null &&
    event.geo_longitude != null &&
    event.geo_radius_m != null;

  const filteredEvents = events.filter(
    (event) =>
      event.name.toLowerCase().includes(deferredSearchTerm.toLowerCase())
  );

  return (
    <div className="upcoming-page">
      {role === "student-ssg" ? (
        <NavbarStudentSSG />
      ) : (
        <NavbarStudent />
      )}

      <div className="upcoming-container">
        <div className="upcoming-header">
          <h2>Upcoming Events</h2>
          <p className="subtitle">View upcoming and ongoing events</p>
        </div>

        <div className="search-filter-section">
          <div className="search-box">
            <FaSearch className="search-icon" />
            <input
              type="text"
              placeholder="Search events..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>
        </div>

        <div className="table-responsive">
          <table className="upcoming-table">
            <thead>
              <tr>
                <th>Event Name</th>
                <th>Department(s)</th>
                <th>Program(s)</th>
                <th>Date & Time</th>
                <th>Location</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7}>Loading events...</td>
                </tr>
              ) : filteredEvents.length > 0 ? (
                filteredEvents.map((event) => (
                  <tr key={event.id}>
                    <td data-label="Event Name">{event.name}</td>
                    <td data-label="Department(s)">
                      {formatEventDepartments(event.departments)}
                    </td>
                    <td data-label="Program(s)">
                      {formatEventPrograms(event.programs)}
                    </td>
                    <td data-label="Date & Time">
                      {formatDateTime(event.start_datetime)} -{" "}
                      {formatDateTime(event.end_datetime)}
                    </td>
                    <td data-label="Location">{event.location}</td>
                    <td data-label="Status">
                      <span className={`status-badge ${event.status}`}>
                        {event.status.charAt(0).toUpperCase() +
                          event.status.slice(1)}
                      </span>
                    </td>
                    <td data-label="Action">
                      {(() => {
                        const actionState = getStudentEventActionState(
                          event,
                          latestAttendanceByEvent.get(event.id)
                        );
                        const isActionable =
                          actionState === "sign_in" || actionState === "sign_out";

                        if (!hasGeofence(event) && isActionable) {
                          return (
                            <button
                              type="button"
                              className="upcoming-action-button"
                              disabled
                            >
                              <FaArrowRight />
                              Unavailable
                            </button>
                          );
                        }

                        if (isActionable) {
                          return (
                            <button
                              type="button"
                              className="upcoming-action-button"
                              onClick={() =>
                                navigate(`/student_event_checkin?eventId=${event.id}`)
                              }
                            >
                              <FaArrowRight />
                              {actionState === "sign_out" ? "Sign Out" : "Sign In"}
                            </button>
                          );
                        }

                        const placeholder =
                          actionState === "done"
                            ? "Done"
                            : actionState === "not_open"
                              ? "Opens Soon"
                              : actionState === "waiting_sign_out"
                                ? "Waiting Sign-Out"
                                : actionState === "missed_check_in"
                                  ? "Check-In Closed"
                                  : "Closed";

                        return (
                          <span className="upcoming-action-placeholder">
                            {placeholder}
                          </span>
                        );
                      })()}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="no-results">
                    No upcoming or ongoing events found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default UpcomingEvents;
