"""Use: Contains the main backend rules for bulk import header and row validation.
Where to use: Use this from routers, workers, or other services when bulk import header and row validation logic is needed.
Role: Service layer. It keeps business logic out of the route files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, Iterable, List, Optional, Tuple

from email_validator import EmailNotValidError, validate_email

EXPECTED_HEADERS = [
    "Student_ID",
    "Email",
    "Last Name",
    "First Name",
    "Middle Name",
    "Department",
    "Course",
]

_FORMULA_PREFIXES = ("=", "+", "-", "@")


class HeaderValidationError(Exception):
    pass


@dataclass
class ValidationContext:
    target_school_id: int
    department_lookup: Dict[str, int]
    course_lookup: Dict[str, int]
    department_course_pairs: set[Tuple[int, int]] = field(default_factory=set)
    seen_emails: set[str] = field(default_factory=set)
    seen_school_student: set[Tuple[int, str]] = field(default_factory=set)
    seen_rows: set[Tuple[str, ...]] = field(default_factory=set)


def normalize_header(header: str) -> str:
    return re.sub(r"\s+", " ", str(header or "").strip().lower())


def normalize_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def validate_headers(header_row: Iterable[object]) -> None:
    received = [normalize_header(cell) for cell in header_row]
    expected = [normalize_header(h) for h in EXPECTED_HEADERS]

    if not any(received):
        raise HeaderValidationError("Missing header row")

    if received != expected:
        raise HeaderValidationError(
            "Invalid header structure or order. Expected: "
            + " | ".join(EXPECTED_HEADERS)
        )


def _has_formula_injection(value: str) -> bool:
    stripped = value.lstrip()
    return bool(stripped) and stripped.startswith(_FORMULA_PREFIXES)


def validate_and_transform_row(
    row_number: int,
    row_values: Iterable[object],
    context: ValidationContext,
) -> tuple[Optional[dict], List[str], dict]:
    normalized_values = [normalize_cell(value) for value in row_values]

    # Ensure expected column count for predictable validation.
    if len(normalized_values) < len(EXPECTED_HEADERS):
        normalized_values.extend([""] * (len(EXPECTED_HEADERS) - len(normalized_values)))
    elif len(normalized_values) > len(EXPECTED_HEADERS):
        normalized_values = normalized_values[: len(EXPECTED_HEADERS)]

    row_data = dict(zip(EXPECTED_HEADERS, normalized_values))
    errors: List[str] = []

    if not any(normalized_values):
        return None, ["empty row"], row_data

    for column_name, value in row_data.items():
        if not value:
            errors.append(f"{column_name} is required")
        elif _has_formula_injection(value):
            errors.append(f"{column_name} contains unsafe spreadsheet formula prefix")

    # File-level duplicate detection is scoped by the authenticated school context.
    fingerprint = (str(context.target_school_id),) + tuple(
        value.lower() for value in normalized_values
    )
    if fingerprint in context.seen_rows:
        errors.append("duplicate row in uploaded file")
    else:
        context.seen_rows.add(fingerprint)

    school_id: Optional[int] = context.target_school_id
    student_id = row_data["Student_ID"].upper()
    email = row_data["Email"].lower()

    if school_id is not None:
        school_student_key = (school_id, student_id)
        if school_student_key in context.seen_school_student:
            errors.append("duplicate Student_ID within the same School_ID in file")
        else:
            context.seen_school_student.add(school_student_key)

    if row_data["Email"]:
        try:
            validate_email(email, check_deliverability=False)
        except EmailNotValidError:
            errors.append("invalid email format")

        if email in context.seen_emails:
            errors.append("duplicate Email in uploaded file")
        else:
            context.seen_emails.add(email)

    department_name = " ".join(row_data["Department"].strip().split())
    course_name = " ".join(row_data["Course"].strip().split())
    department_key = department_name.lower()
    course_key = course_name.lower()

    department_id = context.department_lookup.get(department_key)
    course_id = context.course_lookup.get(course_key)

    if errors:
        return None, errors, row_data

    transformed = {
        "row_number": row_number,
        "school_id": school_id,
        "student_id": student_id,
        "email": email,
        "last_name": row_data["Last Name"],
        "first_name": row_data["First Name"],
        "middle_name": row_data["Middle Name"],
        "department_name": department_name,
        "program_name": course_name,
        "department_id": department_id,
        "program_id": course_id,
    }
    return transformed, [], row_data


def sanitize_excel_output(value: str) -> str:
    text = normalize_cell(value)
    if _has_formula_injection(text):
        return "'" + text
    return text


def suggest_fixes(errors: List[str]) -> List[str]:
    suggestions: List[str] = []
    for error in errors:
        lowered = error.lower()
        if "invalid header" in lowered or "missing header" in lowered:
            suggestions.append("Download the latest template and keep the column order unchanged.")
        elif "department does not exist" in lowered:
            suggestions.append("Use an existing department name exactly as listed in the system.")
        elif "course does not exist" in lowered:
            suggestions.append("Use an existing course/program name exactly as listed in the system.")
        elif "not offered by the selected department" in lowered:
            suggestions.append("Choose a course/program that is linked to the selected department.")
        elif "duplicate student_id" in lowered:
            suggestions.append("Ensure Student_ID values are unique within the school and file.")
        elif "duplicate email" in lowered:
            suggestions.append("Use one unique email per student row.")
        elif "invalid email format" in lowered:
            suggestions.append("Enter a valid email format (example: student@example.edu).")
        elif "unsafe spreadsheet formula" in lowered:
            suggestions.append("Remove formula prefixes (=, +, -, @) from cell values.")
        elif "is required" in lowered:
            suggestions.append("Fill all required fields before re-uploading.")
        elif "email already exists" in lowered:
            suggestions.append("Use a different email or update the existing user instead of importing.")
        elif "duplicate student_id within school_id" in lowered:
            suggestions.append("Change Student_ID to a unique value for this school.")

    # Keep output concise and unique.
    deduped: List[str] = []
    for item in suggestions:
        if item not in deduped:
            deduped.append(item)
    return deduped[:5]
