import { useDeferredValue, useEffect, useState } from "react";
import { NavbarAdmin } from "../components/NavbarAdmin";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import search_logo from "../assets/images/search_logo.png";
import { FaDownload } from "react-icons/fa";
import {
  PieChart,
  Pie,
  Tooltip,
  Legend,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import Modal from "react-modal";
import { fetchAllEvents } from "../api/eventsApi";
import {
  fetchEventAttendanceReport,
  type EventAttendanceReport as AttendanceReport,
} from "../api/attendanceApi";
import { readStoredUserSession } from "../lib/auth/storedUser";
import { isCampusAdminRole } from "../utils/roleUtils";

interface Event {
  id: number;
  name: string;
  start_datetime?: string;
  date?: string;
  location: string;
}

const PRIMARY_COLOR = "var(--primary-color, #162F65)";
const SECONDARY_COLOR = "var(--secondary-color, #2C5F9E)";
const ACCENT_COLOR = "var(--accent-color, #4A90E2)";

export const Reports: React.FC = () => {
  const storedRoles = readStoredUserSession()?.roles ?? [];
  const isCampusAdmin = storedRoles.some(isCampusAdminRole);
  const [searchTerm, setSearchTerm] = useState("");
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [attendanceReport, setAttendanceReport] =
    useState<AttendanceReport | null>(null);
  const [selectedProgram, setSelectedProgram] = useState<number | "all">("all");
  const [isLoading, setIsLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const deferredSearchTerm = useDeferredValue(searchTerm);

  const selectedProgramName =
    selectedProgram === "all"
      ? null
      : attendanceReport?.programs.find((p) => p.id === selectedProgram)?.name ?? null;

  const selectedProgramBreakdown =
    selectedProgramName && attendanceReport
      ? attendanceReport.program_breakdown.find((p) => p.program === selectedProgramName) ?? null
      : null;
  const selectedProgramAttendees = selectedProgramBreakdown
    ? selectedProgramBreakdown.present + selectedProgramBreakdown.late
    : 0;
  const overallPresentCount = attendanceReport
    ? Math.max(0, attendanceReport.attendees - attendanceReport.late_attendees)
    : 0;

  useEffect(() => {
    const fetchEvents = async () => {
      setIsLoading(true);
      try {
        const data = await fetchAllEvents();
        setEvents(data);
      } catch (error) {
        console.error("Error fetching events:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchEvents();

    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const filteredEvents = events.filter((event) =>
    event.name.toLowerCase().includes(deferredSearchTerm.toLowerCase())
  );

  const fetchEventReport = async (event: Event): Promise<AttendanceReport> =>
    fetchEventAttendanceReport(event.id);

  const handleViewReport = async (event: Event): Promise<AttendanceReport | null> => {
    setIsLoading(true);
    try {
      const data = await fetchEventReport(event);
      setAttendanceReport(data);
      setSelectedEvent(event);
      setSelectedProgram("all");
      return data;
    } catch (error) {
      console.error("Error fetching attendance report:", error);
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadCSVReport = (report: AttendanceReport | null = attendanceReport) => {
    if (!report) return;

    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += `${report.event_name} - Attendance Report\r\n`;
    csvContent += `Date: ${report.event_date}\r\n`;
    csvContent += `Location: ${report.event_location}\r\n\r\n`;

    csvContent += `Overall Summary:\r\n`;
    csvContent += `Total Participants: ${report.total_participants}\r\n`;
    csvContent += `Attendees: ${report.attendees}\r\n`;
    csvContent += `Late Attendees: ${report.late_attendees}\r\n`;
    csvContent += `Absentees: ${report.absentees}\r\n`;
    csvContent += `Attendance Rate: ${report.attendance_rate}%\r\n\r\n`;

    csvContent += `Program Breakdown:\r\n`;
    csvContent += `Program,Total,Present,Late,Absent,Rate\r\n`;
    report.program_breakdown.forEach((program) => {
      const programAttendees = program.present + program.late;
      csvContent += `${program.program},${program.total},${program.present},${
        program.late
      },${program.absent},${Math.round(
        (programAttendees / Math.max(program.total, 1)) * 100
      )}%\r\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `${report.event_name.replace(/\s+/g, "_")}_Report.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDownloadPDFReport = (report: AttendanceReport | null = attendanceReport) => {
    if (!report) return;

    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      alert("Please allow pop-ups to download the PDF report");
      return;
    }

    let htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>${report.event_name} - Attendance Report</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 40px; }
          .header { margin-bottom: 30px; }
          h1 { color: #333; margin-bottom: 5px; }
          .event-details { color: #666; margin-bottom: 20px; }
          .summary-section { margin-bottom: 30px; }
          .summary-cards { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; }
          .summary-card { border: 1px solid #ddd; border-radius: 8px; padding: 15px; width: 200px; }
          .card-title { display: block; font-size: 14px; color: #666; }
          .card-value { display: block; font-size: 24px; font-weight: bold; margin-top: 5px; }
          .total .card-value { color: #2196F3; }
          .present .card-value { color: #4CAF50; }
          .late .card-value { color: #F57C00; }
          .absent .card-value { color: #F44336; }
          .rate .card-value { color: #FF9800; }
          table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
          th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
          th { background-color: #f2f2f2; }
          @media print {
            .no-print { display: none; }
          }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>${report.event_name} - Attendance Report</h1>
          <p class="event-details">Date: ${report.event_date} • Location: ${report.event_location}</p>
        </div>
        
        <div class="summary-section">
          <h2>Attendance Summary</h2>
          <div class="summary-cards">
            <div class="summary-card total">
              <span class="card-title">Total Participants</span>
              <span class="card-value">${report.total_participants}</span>
            </div>
            <div class="summary-card present">
              <span class="card-title">Attendees</span>
              <span class="card-value">${report.attendees}</span>
            </div>
            <div class="summary-card late">
              <span class="card-title">Late Attendees</span>
              <span class="card-value">${report.late_attendees}</span>
            </div>
            <div class="summary-card absent">
              <span class="card-title">Absentees</span>
              <span class="card-value">${report.absentees}</span>
            </div>
            <div class="summary-card rate">
              <span class="card-title">Attendance Rate</span>
              <span class="card-value">${report.attendance_rate}%</span>
            </div>
          </div>
        </div>
        
        <h2>Program Breakdown</h2>
        <table>
          <thead>
            <tr>
              <th>Program</th>
              <th>Total</th>
              <th>Present</th>
              <th>Late</th>
              <th>Absent</th>
              <th>Rate</th>
            </tr>
          </thead>
          <tbody>
    `;

    report.program_breakdown.forEach((program) => {
      const programAttendees = program.present + program.late;
      htmlContent += `
        <tr>
          <td>${program.program}</td>
          <td>${program.total}</td>
          <td>${program.present}</td>
          <td>${program.late}</td>
          <td>${program.absent}</td>
          <td>${Math.round((programAttendees / Math.max(program.total, 1)) * 100)}%</td>
        </tr>
      `;
    });

    htmlContent += `
          </tbody>
        </table>
        <div class="no-print" style="margin-top: 40px; text-align: center;">
          <button onclick="window.print();" style="padding: 10px 20px; background-color: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;">Print Report</button>
          <button onclick="window.close();" style="padding: 10px 20px; background-color: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-left: 10px;">Close</button>
        </div>
      </body>
      </html>
    `;

    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.focus();
  };

  const getChartData = () => {
    if (!attendanceReport) return [];

    if (selectedProgram === "all") {
      return [
        { name: "Present", value: overallPresentCount },
        { name: "Late", value: attendanceReport.late_attendees },
        { name: "Absent", value: attendanceReport.absentees },
      ];
    } else {
      if (!selectedProgramBreakdown) return [];
      return [
        { name: "Present", value: selectedProgramBreakdown.present },
        { name: "Late", value: selectedProgramBreakdown.late },
        { name: "Absent", value: selectedProgramBreakdown.absent },
      ];
    }
  };

  const getProgramChartData = () => {
    if (!attendanceReport || selectedProgram !== "all") return [];
    return attendanceReport.program_breakdown.map((program) => ({
      name: program.program,
      present: program.present,
      late: program.late,
      absent: program.absent,
    }));
  };

  const formatEventDate = (event: Event) => {
    const rawDate = event.start_datetime ?? event.date;
    if (!rawDate) return "N/A";

    const parsed = new Date(rawDate);
    if (Number.isNaN(parsed.getTime())) return rawDate;

    return parsed.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  const contentPadding = isMobile ? "1rem" : "1.5rem";
  const tableCellPadding = isMobile ? "10px 12px" : "12px 15px";
  const actionButtonStyle = {
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "5px",
    padding: "8px 15px",
    width: isMobile ? "100%" : "auto",
  } as const;

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "var(--page-background, #f5f5f5)",
        fontFamily: "Arial, sans-serif",
      }}
    >
      {isCampusAdmin ? <NavbarSchoolIT /> : <NavbarAdmin />}
      <div
        style={{
          width: "min(100%, var(--app-shell-max-width))",
          maxWidth: "1200px",
          margin: "0 auto",
          padding: contentPadding,
        }}
      >
        <header
          style={{
            marginBottom: "30px",
          }}
        >
          <h2
            style={{
              marginBottom: "5px",
              color: PRIMARY_COLOR,
            }}
          >
            {isCampusAdmin ? "Campus Attendance Reports" : "Event Attendance Reports"}
          </h2>
          <p
            style={{
              color: SECONDARY_COLOR,
              marginTop: "0",
            }}
          >
            {isCampusAdmin
              ? "View and download school-scoped attendance reports for events across your campus"
              : "View and download detailed attendance records for university events"}
          </p>
        </header>

        {/* Search Bar */}
        <div
          style={{
            marginBottom: "20px",
            display: "flex",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              position: "relative",
              width: "100%",
              maxWidth: "560px",
            }}
          >
            <img
              src={search_logo}
              alt="search"
              style={{
                position: "absolute",
                left: "10px",
                top: "50%",
                transform: "translateY(-50%)",
                height: "20px",
              }}
            />
            <input
              type="search"
              placeholder="Search events by name..."
              style={{
                width: "100%",
                padding: "10px 15px 10px 35px",
                borderRadius: "4px",
                border: "1px solid #ddd",
                fontSize: "16px",
              }}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        {isLoading && (
          <div
            style={{
              marginBottom: "16px",
              color: "#495057",
              fontSize: "14px",
            }}
          >
            Loading report data...
          </div>
        )}

        {/* Events Table */}
        <div
          style={{
            overflowX: "auto",
            marginBottom: "30px",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              backgroundColor: "white",
              borderRadius: "8px",
              boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            }}
          >
            <thead>
              <tr
                style={{
                  backgroundColor: "#f8f9fa",
                  borderBottom: "1px solid #ddd",
                }}
              >
                <th style={{ padding: tableCellPadding, textAlign: "left" }}>
                  Event Name
                </th>
                <th style={{ padding: tableCellPadding, textAlign: "left" }}>
                  Date
                </th>
                <th style={{ padding: tableCellPadding, textAlign: "left" }}>
                  Location
                </th>
                <th style={{ padding: tableCellPadding, textAlign: "left" }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((event) => (
                <tr
                  key={event.id}
                  style={{
                    borderBottom: "1px solid #eee",
                  }}
                >
                  <td style={{ padding: tableCellPadding }}>{event.name}</td>
                  <td style={{ padding: tableCellPadding }}>
                    {formatEventDate(event)}
                  </td>
                  <td style={{ padding: tableCellPadding }}>{event.location}</td>
                  <td style={{ padding: tableCellPadding }}>
                    <div
                      style={{
                        display: "flex",
                        gap: "10px",
                        flexWrap: "wrap",
                      }}
                    >
                      <button
                        style={{
                          backgroundColor: PRIMARY_COLOR,
                          opacity: isLoading ? 0.7 : 1,
                          ...actionButtonStyle,
                        }}
                        onClick={() => handleViewReport(event)}
                        disabled={isLoading}
                      >
                        View Report
                      </button>
                      <button
                        style={{
                          backgroundColor: SECONDARY_COLOR,
                          ...actionButtonStyle,
                        }}
                        onClick={async () => {
                          const report = await handleViewReport(event);
                          if (report) handleDownloadCSVReport(report);
                        }}
                        disabled={isLoading}
                      >
                        <FaDownload /> {!isMobile && "CSV"}
                      </button>
                      <button
                        style={{
                          backgroundColor: ACCENT_COLOR,
                          ...actionButtonStyle,
                        }}
                        onClick={async () => {
                          const report = await handleViewReport(event);
                          if (report) handleDownloadPDFReport(report);
                        }}
                        disabled={isLoading}
                      >
                        <FaDownload /> {!isMobile && "PDF"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredEvents.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    style={{
                      padding: "20px",
                      textAlign: "center",
                      color: "#666",
                    }}
                  >
                    No matching events found. Try a different search term.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Report Modal */}
        {selectedEvent && attendanceReport && (
          <Modal
            isOpen={true}
            onRequestClose={() => setSelectedEvent(null)}
            ariaHideApp={false}
            style={{
              overlay: {
                backgroundColor: "rgba(0, 0, 0, 0.5)",
                zIndex: 1000,
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                padding: "20px",
              },
              content: {
                position: "relative",
                backgroundColor: "white",
                borderRadius: "8px",
                padding: contentPadding,
                maxWidth: "900px",
                width: isMobile ? "100%" : "90%",
                maxHeight: "90vh",
                overflow: "auto",
                border: "none",
                boxShadow: "0 5px 15px rgba(0, 0, 0, 0.3)",
              },
            }}
          >
            <div
              style={{
                marginBottom: "20px",
                display: "flex",
                flexWrap: "wrap",
                gap: "0.75rem",
                alignItems: "center",
              }}
            >
              <h3
                style={{
                  marginBottom: "5px",
                  color: PRIMARY_COLOR,
                }}
              >
                {attendanceReport.event_name} - Attendance Report
              </h3>
              <p
                style={{
                  color: SECONDARY_COLOR,
                  marginTop: "0",
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                }}
              >
                <span>{attendanceReport.event_date}</span>
                <span>•</span>
                <span>{attendanceReport.event_location}</span>
              </p>
            </div>

            {/* Filter Dropdown */}
            <div
              style={{
                marginBottom: "20px",
              }}
            >
              <label
                htmlFor="program-filter"
                style={{
                  marginRight: "10px",
                }}
              >
                Filter by Program:
              </label>
              <select
                id="program-filter"
                value={selectedProgram}
                onChange={(e) =>
                  setSelectedProgram(
                    e.target.value === "all" ? "all" : Number(e.target.value)
                  )
                }
                style={{
                  padding: "8px 12px",
                  borderRadius: "8px",
                  border: "1px solid #ddd",
                  minWidth: isMobile ? "100%" : "220px",
                }}
              >
                <option value="all">All Programs</option>
                {attendanceReport.programs.map((program) => (
                  <option key={program.id} value={program.id}>
                    {program.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Attendance Summary */}
            <div
              style={{
                marginBottom: "30px",
              }}
            >
              <h4
                style={{
                  borderBottom: "1px solid #eee",
                  paddingBottom: "10px",
                  color: PRIMARY_COLOR,
                }}
              >
                Attendance Summary
              </h4>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                  gap: "20px",
                  marginTop: "20px",
                }}
              >
                <div
                  style={{
                    backgroundColor: "#f8f9fa",
                    borderRadius: "8px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontSize: "14px",
                      color: "#666",
                    }}
                  >
                    Total Participants
                  </span>
                  <span
                    style={{
                      display: "block",
                      fontSize: "24px",
                      fontWeight: "bold",
                      color: PRIMARY_COLOR,
                    }}
                  >
                    {selectedProgram === "all"
                      ? attendanceReport.total_participants
                      : selectedProgramBreakdown?.total || 0}
                  </span>
                </div>
                <div
                  style={{
                    backgroundColor: "#e8f5e9",
                    borderRadius: "8px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontSize: "14px",
                      color: "#666",
                    }}
                  >
                    Attendees
                  </span>
                  <span
                    style={{
                      display: "block",
                      fontSize: "24px",
                      fontWeight: "bold",
                      color: "#4CAF50",
                    }}
                  >
                    {selectedProgram === "all"
                      ? attendanceReport.attendees
                      : selectedProgramAttendees}
                  </span>
                </div>
                <div
                  style={{
                    backgroundColor: "#fff4e5",
                    borderRadius: "8px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontSize: "14px",
                      color: "#666",
                    }}
                  >
                    Late
                  </span>
                  <span
                    style={{
                      display: "block",
                      fontSize: "24px",
                      fontWeight: "bold",
                      color: "#F57C00",
                    }}
                  >
                    {selectedProgram === "all"
                      ? attendanceReport.late_attendees
                      : selectedProgramBreakdown?.late || 0}
                  </span>
                </div>
                <div
                  style={{
                    backgroundColor: "#ffebee",
                    borderRadius: "8px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontSize: "14px",
                      color: "#666",
                    }}
                  >
                    Absentees
                  </span>
                  <span
                    style={{
                      display: "block",
                      fontSize: "24px",
                      fontWeight: "bold",
                      color: "#F44336",
                    }}
                  >
                    {selectedProgram === "all"
                      ? attendanceReport.absentees
                      : selectedProgramBreakdown?.absent || 0}
                  </span>
                </div>
                <div
                  style={{
                    backgroundColor: "#e3f2fd",
                    borderRadius: "8px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontSize: "14px",
                      color: "#666",
                    }}
                  >
                    Attendance Rate
                  </span>
                  <span
                    style={{
                      display: "block",
                      fontSize: "24px",
                      fontWeight: "bold",
                      color: PRIMARY_COLOR,
                    }}
                  >
                    {selectedProgram === "all"
                      ? `${attendanceReport.attendance_rate}%`
                      : selectedProgramBreakdown
                      ? `${Math.round(
                          (selectedProgramAttendees /
                            Math.max(selectedProgramBreakdown.total, 1)) *
                            100
                        )}%`
                      : "0%"}
                  </span>
                </div>
              </div>
            </div>

            {/* Charts Section */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  isMobile || selectedProgram !== "all" ? "1fr" : "1fr 1fr",
                gap: "20px",
                marginBottom: "30px",
              }}
            >
              <div>
                <h5
                  style={{
                    color: PRIMARY_COLOR,
                    marginBottom: "15px",
                  }}
                >
                  Attendance Distribution
                </h5>
                <div
                  style={{
                    height: isMobile ? "260px" : "300px",
                    backgroundColor: "white",
                    borderRadius: "8px",
                    padding: "15px",
                  }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={getChartData()}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={2}
                        dataKey="value"
                        label={({ name, percent }) =>
                          `${name}: ${(percent * 100).toFixed(0)}%`
                        }
                      >
                        <Cell fill="#4CAF50" />
                        <Cell fill="#FFB74D" />
                        <Cell fill="#F44336" />
                      </Pie>
                      <Tooltip
                        formatter={(value) => [`${value} participants`, ""]}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {selectedProgram === "all" && (
                <div>
                  <h5
                    style={{
                      color: PRIMARY_COLOR,
                      marginBottom: "15px",
                    }}
                  >
                    Attendance by Program
                  </h5>
                  <div
                    style={{
                      height: isMobile ? "260px" : "300px",
                      backgroundColor: "white",
                      borderRadius: "8px",
                      padding: "15px",
                    }}
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={getProgramChartData()}
                        margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                        layout={isMobile ? "vertical" : "horizontal"}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        {isMobile ? (
                          <>
                            <YAxis
                              type="category"
                              dataKey="name"
                              interval={0}
                            />
                            <XAxis type="number" />
                          </>
                        ) : (
                          <>
                            <XAxis
                              type="category"
                              dataKey="name"
                              interval={0}
                              angle={-45}
                              textAnchor="end"
                            />
                            <YAxis type="number" />
                          </>
                        )}
                        <Tooltip
                          formatter={(value) => [`${value} participants`, ""]}
                        />
                        <Legend />
                        <Bar
                          dataKey="present"
                          name="Present"
                          fill="#4CAF50"
                        />
                        <Bar dataKey="late" name="Late" fill="#FFB74D" />
                        <Bar dataKey="absent" name="Absentees" fill="#F44336" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>

            {/* Program Breakdown Table */}
            <div>
              <h5
                style={{
                  color: PRIMARY_COLOR,
                  marginBottom: "15px",
                  borderBottom: "1px solid #eee",
                  paddingBottom: "10px",
                }}
              >
                Program Breakdown
              </h5>
              <div
                style={{
                  overflowX: "auto",
                }}
              >
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    backgroundColor: "white",
                    borderRadius: "8px",
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        backgroundColor: "#f8f9fa",
                      }}
                    >
                      <th style={{ padding: tableCellPadding, textAlign: "left" }}>
                        Program
                      </th>
                      <th style={{ padding: tableCellPadding, textAlign: "right" }}>
                        Total
                      </th>
                      <th style={{ padding: tableCellPadding, textAlign: "right" }}>
                        Present
                      </th>
                      <th style={{ padding: tableCellPadding, textAlign: "right" }}>
                        Late
                      </th>
                      <th style={{ padding: tableCellPadding, textAlign: "right" }}>
                        Absent
                      </th>
                      <th style={{ padding: tableCellPadding, textAlign: "right" }}>
                        Rate
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {attendanceReport.program_breakdown.map((program) => (
                      <tr
                        key={program.program}
                        style={{
                          borderBottom: "1px solid #eee",
                        }}
                      >
                        <td style={{ padding: tableCellPadding }}>
                          {program.program}
                        </td>
                        <td
                          style={{ padding: tableCellPadding, textAlign: "right" }}
                        >
                          {program.total}
                        </td>
                        <td
                          style={{
                            padding: tableCellPadding,
                            textAlign: "right",
                            color: "#4CAF50",
                          }}
                        >
                          {program.present}
                        </td>
                        <td
                          style={{
                            padding: tableCellPadding,
                            textAlign: "right",
                            color: "#F57C00",
                          }}
                        >
                          {program.late}
                        </td>
                        <td
                          style={{
                            padding: tableCellPadding,
                            textAlign: "right",
                            color: "#F44336",
                          }}
                        >
                          {program.absent}
                        </td>
                        <td
                          style={{
                            padding: tableCellPadding,
                            textAlign: "right",
                            color: PRIMARY_COLOR,
                          }}
                        >
                          {Math.round(
                            ((program.present + program.late) /
                              Math.max(program.total, 1)) *
                              100
                          )}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div
              style={{
                marginTop: "30px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "10px",
                width: "100%",
              }}
            >
              <button
                onClick={() => handleDownloadCSVReport()}
                style={{
                  backgroundColor: SECONDARY_COLOR,
                  ...actionButtonStyle,
                }}
              >
                <FaDownload /> Download CSV Report
              </button>
              <button
                onClick={() => handleDownloadPDFReport()}
                style={{
                  backgroundColor: ACCENT_COLOR,
                  ...actionButtonStyle,
                }}
              >
                <FaDownload /> Download PDF Report
              </button>
              <button
                onClick={() => setSelectedEvent(null)}
                style={{
                  backgroundColor: "#6c757d",
                  marginTop: "10px",
                  ...actionButtonStyle,
                }}
              >
                Close
              </button>
            </div>
          </Modal>
        )}
      </div>
    </div>
  );
};

export default Reports;
