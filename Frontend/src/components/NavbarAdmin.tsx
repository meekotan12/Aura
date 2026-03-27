import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  FaBell,
  FaHome,
  FaBars,
  FaTimes,
  FaThList,
  FaKey,
  FaSchool,
  FaClipboardList,
  FaShieldAlt,
  FaRegListAlt,
  FaDatabase,
  FaUserShield,
} from "react-icons/fa";
import { useUser } from "../context/UserContext";
import logoValid8 from "../assets/images/logo-valid83.webp";
import defaultAvatar from "../assets/images/userprofile1.png";
import { useRoleSidebarLayout } from "../hooks/useRoleSidebarLayout";
import "../css/NavbarAdmin.css";

export const NavbarAdmin = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const { avatar } = useUser();

  useRoleSidebarLayout({ isExpanded, sidebarOpen });

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  const toggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <>
      {/* Hamburger Icon - Only shows when sidebar is closed */}
      {!sidebarOpen && (
        <div className="admin-hamburger" onClick={toggleSidebar}>
          <FaBars />
        </div>
      )}

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={toggleSidebar}></div>
      )}

      {/* Sidebar */}
      <div
        className={`admin-sidebar ${sidebarOpen ? "open" : ""} ${
          isExpanded ? "expanded" : "collapsed"
        }`}
      >
        {/* Header with Logo, Title, and Close Button */}
        <div className="admin-sidebar-header">
          <div className="header-content-wrapper">
            <img src={logoValid8} alt="Valid 8 logo" className="sidebar-logo" />
            <h1 className="admin-title">Admin</h1>
          </div>
          {sidebarOpen && (
            <button className="sidebar-close-btn" onClick={toggleSidebar}>
              <FaTimes />
            </button>
          )}
        </div>

        {/* Navigation Links */}
        <nav className="admin-nav">
          <ul className="admin-nav-menu">
            {/* Menu Toggle Button */}
            <li className="menu-toggle-item">
              <button
                className="admin-nav-link menu-toggle-btn"
                onClick={toggleExpand}
                title={isExpanded ? "Collapse menu" : "Expand menu"}
              >
                <FaThList className="nav-icon" />
                <span className="nav-text">Menu</span>
              </button>
            </li>

            <li>
              <NavLink
                to="/admin_home"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Home"
              >
                <FaHome className="nav-icon" />
                <span className="nav-text">Home</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/admin_manage_users"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Manage Schools & Campus Admin"
              >
                <FaSchool className="nav-icon" />
                <span className="nav-text">Manage Schools & Campus Admin</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/admin_audit_logs"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Audit Logs"
              >
                <FaClipboardList className="nav-icon" />
                <span className="nav-text">Audit Logs</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/admin_password_resets"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Password Reset Requests"
              >
                <FaKey className="nav-icon" />
                <span className="nav-text">Password Reset Requests</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/admin_notifications"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Notifications"
              >
                <FaBell className="nav-icon" />
                <span className="nav-text">Notifications</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/admin_security"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Security"
              >
                <FaShieldAlt className="nav-icon" />
                <span className="nav-text">Security</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/admin_face_verification"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Facial Verification"
              >
                <FaUserShield className="nav-icon" />
                <span className="nav-text">Facial Verification</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/admin_subscription"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Subscription"
              >
                <FaRegListAlt className="nav-icon" />
                <span className="nav-text">Subscription</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/admin_governance"
                className={({ isActive }) =>
                  isActive ? "admin-nav-link active" : "admin-nav-link"
                }
                onClick={() => setSidebarOpen(false)}
                title="Data Governance"
              >
                <FaDatabase className="nav-icon" />
                <span className="nav-text">Data Governance</span>
              </NavLink>
            </li>
          </ul>
        </nav>

        {/* User Profile Section */}
        <div className="admin-sidebar-footer">
          <NavLink
            to="/admin_profile"
            className={({ isActive }) =>
              isActive ? "admin-profile-link active" : "admin-profile-link"
            }
            onClick={() => setSidebarOpen(false)}
            title="Profile"
          >
            <img
              src={avatar || defaultAvatar}
              alt="user profile"
              className="admin-profile-img"
            />
            <span className="profile-text">Profile</span>
          </NavLink>
        </div>
      </div>

      {/* Main Content Area */}
      <div
        className={`admin-content ${sidebarOpen ? "shifted" : ""} ${
          isExpanded ? "content-expanded" : "content-collapsed"
        }`}
      ></div>
    </>
  );
};

export default NavbarAdmin;


