"""Use: Defines request and response data shapes for user and student API data.
Where to use: Use this in routers and services when validating or returning user and student API data.
Role: Schema layer. It keeps API payloads clear and typed.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.attendance import Attendance as AttendanceSchema
from app.schemas.role import Role


class RoleEnum(str, Enum):
    student = "student"
    campus_admin = "campus_admin"
    admin = "admin"


class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    middle_name: str | None = None
    last_name: str


class StudentProfileBase(BaseModel):
    student_id: str | None = Field(
        None,
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9-]+$",
        description="Official student ID following format: [DepartmentCode]-[Year]-[SequenceNumber]",
        json_schema_extra={"example": "CS-2023-001"},
    )
    department_id: int | None = Field(
        None,
        description="ID of the department the student belongs to",
    )
    program_id: int | None = Field(
        None,
        description="ID of the academic program the student is enrolled in",
    )
    year_level: int | None = Field(
        None,
        ge=1,
        le=5,
        description="Year level must be between 1 and 5",
    )


class StudentProfileWithAttendances(StudentProfileBase):
    id: int
    attendances: list[AttendanceSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    password: str | None = None
    roles: list[RoleEnum]


class StudentAccountCreate(UserBase):
    department_id: int = Field(
        ...,
        description="ID of the department the student belongs to",
    )
    program_id: int = Field(
        ...,
        description="ID of the academic program the student is enrolled in",
    )
    year_level: int = Field(
        1,
        ge=1,
        le=5,
        description="Year level defaults to 1 when omitted",
    )


class UserUpdate(BaseModel):
    """Schema for partially updating user information."""

    email: EmailStr | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None


class StudentProfileCreate(StudentProfileBase):
    user_id: int = Field(
        ...,
        description="The ID of the user to be assigned as a student",
    )

    @field_validator("student_id")
    @classmethod
    def validate_student_id_format(cls, value: str | None) -> str | None:
        """Require a mixed student identifier when one is provided."""
        if value is None:
            return value
        if not any(char.isalpha() for char in value):
            raise ValueError("Student ID must contain at least one letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Student ID must contain at least one number")
        return value.upper()


class PasswordUpdate(BaseModel):
    password: str = Field(
        ...,
        min_length=8,
        description="New password",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """Validate password has minimum strength requirements."""
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        return value


class UserRoleUpdate(BaseModel):
    roles: list[RoleEnum] = Field(
        ...,
        description="List of roles to assign to the user",
    )


class UserIdList(BaseModel):
    """Schema for bulk operations on users."""

    user_ids: list[int] = Field(
        ...,
        min_length=1,
        description="List of user IDs for bulk operations",
    )


class UserFilter(BaseModel):
    """Optional schema for advanced user filtering."""

    department_id: int | None = None
    program_id: int | None = None
    year_level: int | None = None
    role: RoleEnum | None = None
    is_active: bool | None = None


class UserRoleResponse(BaseModel):
    role: Role

    model_config = ConfigDict(from_attributes=True)


class StudentProfile(StudentProfileBase):
    id: int
    is_face_registered: bool = False
    registration_complete: bool = False
    attendances: list[AttendanceSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class User(UserBase):
    id: int
    school_id: int | None = None
    is_active: bool
    face_scan_bypass_enabled: bool = False
    created_at: datetime
    roles: list[UserRoleResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UserCreateResponse(User):
    generated_temporary_password: str | None = None


class UserWithRelations(User):
    student_profile: StudentProfile | None = None


User.model_rebuild()
StudentProfileWithAttendances.model_rebuild()
