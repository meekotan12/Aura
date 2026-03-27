import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchCurrentUserProfile,
  updateSchoolScopedUser,
} from "../api/userApi";
import LogoutButton from "../components/LogoutButton";
import NavbarStudent from "../components/NavbarStudent";
import NavbarAdmin from "../components/NavbarAdmin";
import NavbarSSG from "../components/NavbarSSG";
import NavbarSG from "../components/NavbarSG";
import NavbarORG from "../components/NavbarORG";
import NavbarSchoolIT from "../components/NavbarSchoolIT";
import defaultAvatar from "../assets/images/userprofile1.png";
import { FaSave, FaEdit, FaSpinner, FaTimes, FaCheck } from "react-icons/fa";
import "../css/Profile.css";

// Corrected interfaces
interface Role {
  id?: number;
  name: string;
}

interface UserRoleResponse {
  role: Role;
}

interface UserData {
  id: number;
  email: string;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  is_active: boolean;
  created_at: string;
  roles: UserRoleResponse[];
  student_profile?: {
    id: number;
    student_id?: string | null;
    department_id?: number | null;
    program_id?: number | null;
    year_level?: number | null;
  } | null;
}

interface ProfileProps {
  role: string;
}

export const Profile: React.FC<ProfileProps> = ({ role }) => {
  const navigate = useNavigate();
  const [userData, setUserData] = useState<UserData | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedEmail, setEditedEmail] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    const fetchUserData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const data = await fetchCurrentUserProfile();
        setUserData(data);
        setEditedEmail(data.email);
      } catch (error) {
        console.error("Failed to fetch user data:", error);
        const message =
          error instanceof Error ? error.message : "Failed to load profile. Please try again later.";
        setError(
          message.includes("authentication token")
            ? "You must be logged in to access this page"
            : message
        );
      } finally {
        setIsLoading(false);
      }
    };

    void fetchUserData();
  }, [navigate]);

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEditedEmail(e.target.value);
  };

  // Modify your handleSave function to include success handling
  const handleSave = async () => {
    if (!userData) return;

    setIsSubmitting(true);
    setError(null);
    try {
      // Only send email update
      const updateData = {
        email: editedEmail,
      };

      await updateSchoolScopedUser(userData.id, updateData);

      // Show success message
      setSuccessMessage("Email successfully updated!");

      // Refresh user data after update
      const updatedData = await fetchCurrentUserProfile();
      setUserData(updatedData);

      // Clear success message after 3 seconds
      setTimeout(() => {
        setSuccessMessage(null);
        setIsEditing(false);
      }, 3000);
    } catch (error) {
      console.error("Failed to update profile:", error);
      setError(
        error instanceof Error
          ? error.message
          : "Failed to update profile. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading && !userData) {
    return (
      <div className="profile-loading">
        <div className="spinner"></div>
        <p>Loading profile...</p>
      </div>
    );
  }

  if (error && !userData) {
    return (
      <div className="profile-error">
        <p>{error}</p>
        <button onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  if (!userData) {
    return (
      <div className="profile-error">
        <p>Could not load profile data.</p>
        <button onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  const navbar = role === "student" ? (
    <NavbarStudent />
  ) : role === "admin" ? (
    <NavbarAdmin />
  ) : role === "campus_admin" ? (
    <NavbarSchoolIT />
  ) : role === "ssg" ? (
    <NavbarSSG />
  ) : role === "sg" ? (
    <NavbarSG />
  ) : role === "org" ? (
    <NavbarORG />
  ) : (
    <h1>Role Not Found</h1>
  );

  // Helper function to render a login prompt if not authenticated
  const renderLoginPrompt = () => (
    <div className="profile-page">
      {navbar}

      <div className="profile-container">
        <div className="error-message">
          <FaTimes className="error-icon" />
          {error}
        </div>
        <div className="login-prompt">
          <p>Please log in to access your profile.</p>
          <button onClick={() => navigate("/login")} className="primary-button">
            Go to Login
          </button>
        </div>
      </div>
    </div>
  );

  // Return login prompt if authentication error occurs
  if (
    !isLoading &&
    error &&
    (error.includes("log in") || error.includes("authentication token"))
  ) {
    return renderLoginPrompt();
  }

  const fullName = `${userData.first_name} ${
    userData.middle_name ? userData.middle_name + " " : ""
  }${userData.last_name}`;

  const userRoles = userData.roles
    ? userData.roles.map((roleResponse) => roleResponse.role.name).join(", ")
    : "No roles assigned";

  return (
    <div className="profile-page">
      {navbar}

      <div className="profile-container">
        <div className="profile-header">
          <h1>User Profile</h1>
          {!isEditing && (
            <button className="edit-button" onClick={() => setIsEditing(true)}>
              <FaEdit /> Edit Profile
            </button>
          )}
        </div>

        <div className="avatar-container">
          <img
            src={defaultAvatar}
            alt="user profile"
            className="profile-avatar"
          />
        </div>

        <div className="profile-info">
          <div className="info-item">
            <label>Name:</label>
            <p>{fullName}</p>
          </div>

          <div className="info-item">
            <label>Role:</label>
            <p>{userRoles}</p>
          </div>

          <div className="info-item">
            <label>Email:</label>
            {isEditing ? (
              <input
                type="email"
                value={editedEmail}
                onChange={handleEmailChange}
                className="email-input"
              />
            ) : (
              <p>{userData.email}</p>
            )}
          </div>

          {userData.student_profile && (
            <div className="info-item">
              <label>Student ID:</label>
              <p>{userData.student_profile.student_id}</p>
            </div>
          )}

          {userData.student_profile && (
            <div className="info-item">
              <label>Year Level:</label>
              <p>{userData.student_profile.year_level}</p>
            </div>
          )}
        </div>

        {successMessage && (
          <div className="success-message">
            <FaCheck className="success-icon" />
            {successMessage}
          </div>
        )}

        {error && <div className="error-message">{error}</div>}

        {isEditing ? (
          <div className="action-buttons">
            <button
              className="save-button"
              onClick={handleSave}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <FaSpinner className="spinner-icon" /> Saving...
                </>
              ) : (
                <>
                  <FaSave /> Save Changes
                </>
              )}
            </button>
            <button
              className="cancel-button"
              onClick={() => {
                setIsEditing(false);
                setEditedEmail(userData.email);
                setError(null);
              }}
              disabled={isSubmitting}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="logout-container">
            <LogoutButton />
          </div>
        )}
      </div>
    </div>
  );
};

export default Profile;
