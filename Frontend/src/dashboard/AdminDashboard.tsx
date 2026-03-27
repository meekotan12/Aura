import React from "react";
import { NavbarAdmin } from "../components/NavbarAdmin";
import DashboardHomeLayout from "../components/DashboardHomeLayout";

// Import colorful icons
import {
  FaKey,
  FaSchool,
  FaUserShield,
} from "react-icons/fa";

export const AdminDashboard: React.FC = () => {
  const cards = [
    {
      title: "Manage Schools & Campus Admin",
      description: "Create schools and manage Campus Admin accounts.",
      icon: <FaSchool style={{ color: "#dc3545" }} />, // Red color
      link: "/admin_manage_users",
    },
    {
      title: "Facial Verification",
      description: "Manage live face enrollment and anti-spoof verification for privileged accounts.",
      icon: <FaUserShield style={{ color: "#162f65" }} />,
      link: "/admin_face_verification",
    },
    {
      title: "Password Reset Requests",
      description: "Review reset requests for student and campus admin accounts that need platform approval.",
      icon: <FaKey style={{ color: "#d97706" }} />,
      link: "/admin_password_resets",
    },
  ];

  return (
    <DashboardHomeLayout
      navbar={<NavbarAdmin />}
      title="Welcome Admin!"
      description="Your central hub for creating and managing schools and Campus Admin accounts."
      cards={cards}
    />
  );
};

export default AdminDashboard;


