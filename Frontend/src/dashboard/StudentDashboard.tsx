import React from "react";
import { NavbarStudent } from "../components/NavbarStudent";
import { useUser } from "../context/UserContext";
import { normalizeLogoUrl } from "../api/schoolSettingsApi";
import DashboardHomeLayout from "../components/DashboardHomeLayout";

// Import colorful icons
import { FaBell, FaCalendarAlt, FaCheckCircle, FaCamera } from "react-icons/fa";

export const StudentDashboard: React.FC = () => {
  const { branding } = useUser();
  const schoolName = branding?.school_name || "Your School";
  const logo = normalizeLogoUrl(branding?.logo_url);

  const cards = [
    {
      title: "Upcoming Events",
      description: "Stay informed about upcoming school events.",
      icon: <FaCalendarAlt style={{ color: "#007bff" }} />, // Blue color
      link: "/student_upcoming_events",
    },
    {
      title: "Events Attended",
      description: "Check and review the events you've attended.",
      icon: <FaCheckCircle style={{ color: "#28a745" }} />, // Green color
      link: "/student_events_attended",
    },
    {
      title: "Event Sign In",
      description: "Verify your live face and location before attendance.",
      icon: <FaCamera style={{ color: "#162f65" }} />,
      link: "/student_event_checkin",
    },
    {
      title: "Notifications",
      description: "Review sign-in, sign-out, late attendance, and reminder alerts.",
      icon: <FaBell style={{ color: "#b66a16" }} />,
      link: "/student_notifications",
    },
  ];

  return (
    <DashboardHomeLayout
      navbar={<NavbarStudent />}
      title={schoolName}
      description="Your central hub for managing events, tracking attendance, and staying organized."
      cards={cards}
      logoSrc={logo}
      logoAlt={`${schoolName} logo`}
    />
  );
};

export default StudentDashboard;
