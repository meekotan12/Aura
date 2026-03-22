"""Use: Defines database models for users, roles, and student profiles.
Where to use: Use this when the backend needs to store or load users, roles, and student profiles data.
Role: Model layer. It maps Python objects to database tables and relationships.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, LargeBinary, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.utils.passwords import hash_password_bcrypt, verify_password_bcrypt
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    middle_name = Column(String(100))
    last_name = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)
    must_change_password = Column(Boolean, default=True, nullable=False, index=True)
    should_prompt_password_change = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    student_profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    school = relationship("School", back_populates="users")
    face_profile = relationship("UserFaceProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    def set_password(self, password: str):
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        self.password_hash = hash_password_bcrypt(password)
    
    def check_password(self, password: str) -> bool:
        return verify_password_bcrypt(password, self.password_hash)

class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    
    user = relationship("User", back_populates="roles")
    role = relationship("Role")

# app/models/user.py (StudentProfile class)
class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        UniqueConstraint("school_id", "student_id", name="uq_student_profiles_school_student_id"),
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id = Column(String(50), index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    program_id = Column(Integer, ForeignKey("programs.id", ondelete="RESTRICT"), index=True)
    year_level = Column(Integer, nullable=False, default=1)
    face_encoding = Column(LargeBinary)  # Changed from String(2000) to LargeBinary

      # Add these:
    is_face_registered = Column(Boolean, default=False, index=True)
    face_image_url = Column(String(500), nullable=True)  # Made nullable
    registration_complete = Column(Boolean, default=False, index=True)
    
    # Consider adding:
    section = Column(String(50), nullable=True, index=True)  # Made nullable
    rfid_tag = Column(String(100), unique=True, nullable=True)  # Alternative auth  
    last_face_update = Column(DateTime, nullable=True)  # Added this missing field
    
    # Relationships
    user = relationship("User", back_populates="student_profile")
    school = relationship("School", back_populates="student_profiles")
    attendances = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")

    department = relationship("Department")  # REMOVED lazy="joined"
    program = relationship("Program")        # REMOVED lazy="joined"

    
    # ===== ADD THIS METHOD =====
    def update_face_encoding(self, embedding: bytes):
        """Safe update of face data"""
        if len(embedding) > 2048:  # Sanity check for embedding size
            raise ValueError("Face embedding too large (max 2048 bytes)")
        self.face_encoding = embedding
        self.is_face_registered = True
        self.last_face_update = datetime.utcnow()
    # ==========================
