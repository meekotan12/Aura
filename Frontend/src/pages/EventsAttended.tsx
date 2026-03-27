import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FaArrowRight, FaCalendarAlt, FaCheckCircle, FaClock, FaSearch } from "react-icons/fa";
import { fetchMyAttendanceRecords, type AttendanceRecord } from "../api/eventsApi";
import { NavbarStudent } from "../components/NavbarStudent";
import { NavbarStudentSSG } from "../components/NavbarStudentSSG";
import {
  formatAttendanceDate,
  formatAttendanceTime,
  getAttendanceTimestamp,
} from "../utils/attendanceDateTime";

interface EventsAttendedProps {
  role: string;
}

const getStatusLabel = (
  status: AttendanceRecord["display_status"] | AttendanceRecord["status"] | undefined
) => {
  switch (status) {
    case "present":
      return "Present";
    case "late":
      return "Late";
    case "incomplete":
      return "Incomplete";
    case "absent":
      return "Absent";
    case "excused":
      return "Excused";
    default:
      return status;
  }
};

const resolveRolePaths = (role: string) => {
  if (role === "student-ssg") {
    return {
      upcoming: "/studentssg_upcoming_events",
      checkIn: "/student_event_checkin",
    };
  }

  return {
    upcoming: "/student_upcoming_events",
    checkIn: "/student_event_checkin",
  };
};

export const EventsAttended: React.FC<EventsAttendedProps> = ({ role }) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const rolePaths = useMemo(() => resolveRolePaths(role), [role]);

  useEffect(() => {
    const fetchMyAttendance = async () => {
      setIsLoading(true);
      try {
        const data = await fetchMyAttendanceRecords();
        setRecords(data);
      } catch (error) {
        console.error("Error fetching attendance records:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchMyAttendance();
  }, []);

  const filteredRecords = useMemo(
    () =>
      records
        .filter((record) =>
          record.event_name.toLowerCase().includes(searchTerm.toLowerCase())
        )
        .sort(
          (left, right) =>
            getAttendanceTimestamp(right.time_in) - getAttendanceTimestamp(left.time_in)
        ),
    [records, searchTerm]
  );

  const summaryCards = useMemo(() => {
    const attendedStatuses = new Set(["present", "late", "excused"]);

    return [
      {
        label: "Recorded Events",
        value: records.length,
        icon: <FaCalendarAlt />,
      },
      {
        label: "Attended",
        value: records.filter((record) =>
          attendedStatuses.has(record.display_status ?? record.status)
        ).length,
        icon: <FaCheckCircle />,
      },
      {
        label: "Late Arrivals",
        value: records.filter((record) => (record.display_status ?? record.status) === "late")
          .length,
        icon: <FaClock />,
      },
      {
        label: "Incomplete",
        value: records.filter((record) => (record.display_status ?? record.status) === "incomplete")
          .length,
        icon: <FaClock />,
      },
    ];
  }, [records]);

  return (
    <div className="events-attended">
      {role === "student-ssg" ? (
        <NavbarStudentSSG />
      ) : (
        <NavbarStudent />
      )}

      <div className="container">
        <div className="hero">
          <div className="header">
            <span className="eyebrow">Student Attendance</span>
            <h2>Events Attended</h2>
            <p>Review your check-ins, time-outs, and attendance status across school events.</p>
          </div>

          <div className="hero-actions">
            <Link to={rolePaths.upcoming} className="hero-link hero-link--secondary">
              Upcoming Events
              <FaArrowRight />
            </Link>
            <Link to={rolePaths.checkIn} className="hero-link">
              Face Attendance
              <FaArrowRight />
            </Link>
          </div>
        </div>

        <div className="summary-grid">
          {summaryCards.map((card) => (
            <div key={card.label} className="summary-card">
              <span className="summary-card__icon">{card.icon}</span>
              <strong>{card.value}</strong>
              <span>{card.label}</span>
            </div>
          ))}
        </div>

        <div className="search-box">
          <FaSearch className="search-icon" />
          <input
            type="text"
            placeholder="Search events..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="records-table">
          <table>
            <thead>
              <tr>
                <th>Event</th>
                <th>Date</th>
                <th>Time In</th>
                <th>Time Out</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="loading">
                    Loading your attendance records...
                  </td>
                </tr>
              ) : filteredRecords.length > 0 ? (
                filteredRecords.map((record) => (
                  <tr key={record.id}>
                    <td>{record.event_name}</td>
                    <td>{formatAttendanceDate(record.time_in, "-")}</td>
                    <td>{formatAttendanceTime(record.time_in, "-")}</td>
                    <td>{record.time_out ? formatAttendanceTime(record.time_out, "-") : "-"}</td>
                    <td>
                      <span className={`status ${record.status}`}>
                        {getStatusLabel(record.display_status ?? record.status)}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="no-results">
                    {searchTerm
                      ? "No matching records found"
                      : "No attendance records available yet. Use Face Attendance when an event is ongoing."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <style>{`
        .events-attended {
          font-family: Arial, sans-serif;
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
        }

        .container {
          margin-top: 20px;
        }

        .hero {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          gap: 1rem;
          flex-wrap: wrap;
          margin-bottom: 1.5rem;
        }

        .header {
          display: grid;
          gap: 0.4rem;
        }

        .eyebrow {
          color: var(--secondary-color, #2C5F9E);
          font-size: 0.8rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .header h2 {
          margin: 0;
          font-size: 28px;
          color: var(--primary-color, #162F65);
        }

        .header p {
          margin: 0;
          max-width: 42rem;
          color: #526377;
        }

        .hero-actions {
          display: flex;
          gap: 0.75rem;
          flex-wrap: wrap;
        }

        .hero-link {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.8rem 1rem;
          border-radius: 999px;
          background: var(--primary-color, #162F65);
          color: #fff;
          font-weight: 600;
          text-decoration: none;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .hero-link:hover {
          transform: translateY(-1px);
          box-shadow: 0 12px 24px rgba(22, 47, 101, 0.12);
        }

        .hero-link--secondary {
          background: #eef4fb;
          color: var(--primary-color, #162F65);
        }

        .summary-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 1rem;
          margin-bottom: 1.5rem;
        }

        .summary-card {
          display: grid;
          gap: 0.35rem;
          padding: 1rem 1.1rem;
          border: 1px solid #dbe6f2;
          border-radius: 18px;
          background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
          box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }

        .summary-card__icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 2.25rem;
          height: 2.25rem;
          border-radius: 999px;
          background: rgba(22, 47, 101, 0.08);
          color: var(--primary-color, #162F65);
        }

        .summary-card strong {
          font-size: 1.6rem;
          color: #173152;
        }

        .summary-card span:last-child {
          color: #5f7388;
        }

        .search-box {
          position: relative;
          margin-bottom: 20px;
          max-width: 400px;
        }

        .search-icon {
          position: absolute;
          left: 10px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--secondary-color, #2C5F9E);
        }

        .search-box input {
          width: 100%;
          padding: 10px 15px 10px 35px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 16px;
        }

        .records-table {
          overflow-x: auto;
        }

        table {
          width: 100%;
          border-collapse: collapse;
          margin-top: 10px;
        }

        th,
        td {
          padding: 12px 15px;
          text-align: left;
          border-bottom: 1px solid #eee;
        }

        th {
          background-color: #f8f9fa;
          font-weight: 600;
        }

        tr:hover {
          background-color: #f5f5f5;
        }

        .status {
          padding: 5px 10px;
          border-radius: 4px;
          font-weight: 500;
        }

        .status.present {
          background-color: #eef6ff;
          color: var(--primary-color, #162F65);
        }

        .status.late {
          background-color: #fff4e5;
          color: #9a6700;
        }

        .status.absent {
          background-color: #ffebee;
          color: #c62828;
        }

        .status.excused {
          background-color: #f0f8ff;
          color: var(--secondary-color, #2C5F9E);
        }

        .loading,
        .no-results {
          text-align: center;
          padding: 20px;
          color: #666;
        }

        @media (max-width: 768px) {
          .hero {
            align-items: stretch;
          }

          .hero-actions {
            width: 100%;
          }

          .hero-link {
            justify-content: center;
            width: 100%;
          }

          th,
          td {
            padding: 8px 10px;
            font-size: 14px;
          }
        }
      `}</style>
    </div>
  );
};

export default EventsAttended;
