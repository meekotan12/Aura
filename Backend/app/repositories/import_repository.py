"""Use: Handles database reads and writes for bulk import jobs.
Where to use: Use this from import routes, services, or workers when working with import job records.
Role: Repository layer. It keeps import-job database access in one place.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Sequence, Tuple

from sqlalchemy import delete, func, insert as sa_insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.associations import program_department_association
from app.models.department import Department
from app.models.import_job import BulkImportError, BulkImportJob, EmailDeliveryLog
from app.models.program import Program
from app.models.role import Role
from app.models.user import StudentProfile, User, UserRole
from app.services.password_change_policy import (
    must_change_password_for_new_account,
    should_prompt_password_change_for_new_account,
)


BULK_LOOKUP_CHUNK_SIZE = 500


class ImportRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _chunked(sequence: Sequence, chunk_size: int = BULK_LOOKUP_CHUNK_SIZE):
        step = max(1, chunk_size)
        for index in range(0, len(sequence), step):
            yield sequence[index : index + step]

    @staticmethod
    def _normalize_catalog_name(value: str | None) -> str:
        return " ".join(str(value or "").strip().split()).lower()

    @staticmethod
    def _clean_catalog_name(value: str | None) -> str:
        return " ".join(str(value or "").strip().split())

    def _dialect_name(self) -> str:
        bind = self.db.get_bind()
        if bind is None:
            return ""
        return bind.dialect.name

    def _supports_on_conflict(self) -> bool:
        return self._dialect_name() in {"postgresql", "sqlite"}

    def _insert_statement(self, target):
        dialect_name = self._dialect_name()
        if dialect_name == "postgresql":
            return pg_insert(target)
        if dialect_name == "sqlite":
            return sqlite_insert(target)
        return sa_insert(target)

    def create_job(self, job: BulkImportJob) -> BulkImportJob:
        self.db.add(job)
        self.db.flush()
        return job

    def get_job(self, job_id: str) -> BulkImportJob | None:
        return self.db.query(BulkImportJob).filter(BulkImportJob.id == job_id).first()

    def mark_processing(self, job_id: str) -> None:
        self.db.execute(
            update(BulkImportJob)
            .where(BulkImportJob.id == job_id)
            .values(status="processing", started_at=datetime.utcnow(), last_heartbeat=datetime.utcnow())
        )

    def update_progress(
        self,
        job_id: str,
        *,
        total_rows: int,
        processed_rows: int,
        success_count: int,
        failed_count: int,
        eta_seconds: int | None,
    ) -> None:
        self.db.execute(
            update(BulkImportJob)
            .where(BulkImportJob.id == job_id)
            .values(
                total_rows=total_rows,
                processed_rows=processed_rows,
                success_count=success_count,
                failed_count=failed_count,
                eta_seconds=eta_seconds,
                last_heartbeat=datetime.utcnow(),
            )
        )

    def mark_completed(self, job_id: str, failed_report_path: str | None = None) -> None:
        self.db.execute(
            update(BulkImportJob)
            .where(BulkImportJob.id == job_id)
            .values(
                status="completed",
                completed_at=datetime.utcnow(),
                failed_report_path=failed_report_path,
                eta_seconds=0,
                last_heartbeat=datetime.utcnow(),
            )
        )

    def mark_failed(self, job_id: str, error_summary: str) -> None:
        self.db.execute(
            update(BulkImportJob)
            .where(BulkImportJob.id == job_id)
            .values(
                status="failed",
                completed_at=datetime.utcnow(),
                error_summary=error_summary[:2000],
                last_heartbeat=datetime.utcnow(),
            )
        )

    def add_errors(self, job_id: str, errors: Sequence[dict]) -> None:
        if not errors:
            return
        values = [
            {
                "job_id": job_id,
                "row_number": item["row"],
                "error_message": item["error"],
                "row_data": item.get("row_data"),
            }
            for item in errors
        ]
        self.db.execute(self._insert_statement(BulkImportError), values)

    def fetch_errors(self, job_id: str, limit: int = 1000) -> List[BulkImportError]:
        return (
            self.db.query(BulkImportError)
            .filter(BulkImportError.job_id == job_id)
            .order_by(BulkImportError.row_number.asc(), BulkImportError.id.asc())
            .limit(max(1, min(limit, 10000)))
            .all()
        )

    def count_recent_jobs(self, created_by_user_id: int, window_seconds: int) -> int:
        cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
        return (
            self.db.query(func.count(BulkImportJob.id))
            .filter(
                BulkImportJob.created_by_user_id == created_by_user_id,
                BulkImportJob.created_at >= cutoff,
            )
            .scalar()
            or 0
        )

    def get_student_role_id(self) -> int:
        role = self.db.query(Role).filter(Role.name == "student").first()
        if not role:
            raise RuntimeError("Role 'student' is missing")
        return role.id

    def lock_import_processing(self, school_id: int) -> None:
        # School-scoped advisory lock prevents same-school races without serializing every tenant.
        if self._dialect_name() != "postgresql":
            return
        self.db.execute(select(func.pg_advisory_lock(883_501_221, int(school_id))))

    def unlock_import_processing(self, school_id: int) -> None:
        if self._dialect_name() != "postgresql":
            return
        self.db.execute(select(func.pg_advisory_unlock(883_501_221, int(school_id))))

    def existing_emails(self, emails: Iterable[str]) -> set[str]:
        email_list = list({email for email in emails if email})
        if not email_list:
            return set()
        existing: set[str] = set()
        for chunk in self._chunked(email_list):
            rows = self.db.execute(select(User.email).where(User.email.in_(chunk))).scalars().all()
            existing.update(email.lower() for email in rows)
        return existing

    def existing_school_student_pairs(self, pairs: Iterable[Tuple[int, str]]) -> set[Tuple[int, str]]:
        pair_list = list({(int(school_id), student_id) for school_id, student_id in pairs if student_id})
        if not pair_list:
            return set()

        grouped_student_ids: dict[int, list[str]] = {}
        for school_id, student_id in pair_list:
            grouped_student_ids.setdefault(int(school_id), []).append(student_id)

        existing: set[Tuple[int, str]] = set()
        for school_id, student_ids in grouped_student_ids.items():
            deduped_student_ids = list(dict.fromkeys(student_ids))
            for chunk in self._chunked(deduped_student_ids):
                rows = self.db.execute(
                    select(StudentProfile.school_id, StudentProfile.student_id).where(
                        StudentProfile.school_id == school_id,
                        StudentProfile.student_id.in_(chunk),
                    )
                ).all()
                existing.update((int(found_school_id), found_student_id) for found_school_id, found_student_id in rows)

        return existing

    def _load_department_lookup(self, school_id: int) -> dict[str, int]:
        return {
            self._normalize_catalog_name(name): int(department_id)
            for department_id, name in (
                self.db.query(Department.id, Department.name)
                .filter(Department.school_id == school_id)
                .all()
            )
        }

    def _load_program_lookup(self, school_id: int) -> dict[str, int]:
        return {
            self._normalize_catalog_name(name): int(program_id)
            for program_id, name in (
                self.db.query(Program.id, Program.name)
                .filter(Program.school_id == school_id)
                .all()
            )
        }

    def _bulk_insert_catalog_rows(self, model, values: list[dict], index_elements: list) -> None:
        if not values:
            return

        statement = self._insert_statement(model).values(values)
        if self._supports_on_conflict():
            statement = statement.on_conflict_do_nothing(index_elements=index_elements)
            self.db.execute(statement)
            return

        for value in values:
            self.db.add(model(**value))
        self.db.flush()

    def ensure_catalog_for_rows(self, rows: Sequence[dict]) -> None:
        if not rows:
            return

        school_ids = {int(row["school_id"]) for row in rows if row.get("school_id") is not None}
        if len(school_ids) != 1:
            raise RuntimeError("Bulk import rows must belong to exactly one school")
        school_id = school_ids.pop()

        department_names: dict[str, str] = {}
        program_names: dict[str, str] = {}
        for row in rows:
            department_name = self._clean_catalog_name(row.get("department_name"))
            program_name = self._clean_catalog_name(row.get("program_name"))
            if department_name:
                department_names.setdefault(self._normalize_catalog_name(department_name), department_name)
            if program_name:
                program_names.setdefault(self._normalize_catalog_name(program_name), program_name)

        department_lookup = self._load_department_lookup(school_id)
        missing_departments = [
            {"school_id": school_id, "name": display_name}
            for normalized_name, display_name in department_names.items()
            if normalized_name not in department_lookup
        ]
        self._bulk_insert_catalog_rows(
            Department,
            missing_departments,
            [Department.school_id, Department.name],
        )
        if missing_departments:
            department_lookup = self._load_department_lookup(school_id)

        program_lookup = self._load_program_lookup(school_id)
        missing_programs = [
            {"school_id": school_id, "name": display_name}
            for normalized_name, display_name in program_names.items()
            if normalized_name not in program_lookup
        ]
        self._bulk_insert_catalog_rows(
            Program,
            missing_programs,
            [Program.school_id, Program.name],
        )
        if missing_programs:
            program_lookup = self._load_program_lookup(school_id)

        desired_pairs: dict[tuple[int, int], dict[str, int]] = {}
        for row in rows:
            normalized_department = self._normalize_catalog_name(row.get("department_name"))
            normalized_program = self._normalize_catalog_name(row.get("program_name"))
            department_id = department_lookup.get(normalized_department)
            program_id = program_lookup.get(normalized_program)
            if department_id is None or program_id is None:
                raise RuntimeError("Academic catalog lookup failed during bulk import")
            row["department_id"] = department_id
            row["program_id"] = program_id
            desired_pairs[(program_id, department_id)] = {
                "program_id": program_id,
                "department_id": department_id,
            }

        if not desired_pairs:
            return

        program_ids = [pair["program_id"] for pair in desired_pairs.values()]
        department_ids = [pair["department_id"] for pair in desired_pairs.values()]
        existing_pairs = set(
            self.db.execute(
                select(
                    program_department_association.c.program_id,
                    program_department_association.c.department_id,
                ).where(
                    program_department_association.c.program_id.in_(program_ids),
                    program_department_association.c.department_id.in_(department_ids),
                )
            ).all()
        )
        missing_pairs = [
            value
            for key, value in desired_pairs.items()
            if key not in existing_pairs
        ]
        if not missing_pairs:
            return

        statement = self._insert_statement(program_department_association).values(missing_pairs)
        if self._supports_on_conflict():
            statement = statement.on_conflict_do_nothing(index_elements=["program_id", "department_id"])
        self.db.execute(statement)

    def bulk_insert_students(
        self,
        rows: Sequence[dict],
        student_role_id: int,
        *,
        shared_password_hash: str,
        trust_preview: bool = False,
    ) -> tuple[List[dict], List[dict]]:
        if not rows:
            return [], []

        existing_emails = self.existing_emails(row["email"] for row in rows)
        existing_pairs = self.existing_school_student_pairs(
            (row["school_id"], row["student_id"]) for row in rows
        )

        candidate_rows: List[dict] = []
        errors: List[dict] = []

        for row in rows:
            row_errors = []
            if row["email"] in existing_emails:
                row_errors.append("Email already exists")
            if (row["school_id"], row["student_id"]) in existing_pairs:
                row_errors.append("Duplicate Student_ID within School_ID")

            if row_errors:
                errors.append(
                    {
                        "row": row["row_number"],
                        "error": "; ".join(row_errors),
                        "row_data": row["raw_row_data"],
                    }
                )
            else:
                candidate_rows.append(row)

        if not candidate_rows:
            return [], errors

        self.ensure_catalog_for_rows(candidate_rows)

        user_values = [
            {
                "email": row["email"],
                "school_id": row["school_id"],
                "password_hash": shared_password_hash,
                "first_name": row["first_name"],
                "middle_name": row["middle_name"],
                "last_name": row["last_name"],
                "is_active": True,
                "must_change_password": must_change_password_for_new_account(),
                "should_prompt_password_change": should_prompt_password_change_for_new_account(),
            }
            for row in candidate_rows
        ]

        user_insert_statement = self._insert_statement(User).values(user_values)
        if self._supports_on_conflict():
            user_insert_statement = user_insert_statement.on_conflict_do_nothing(index_elements=[User.email])
        inserted_user_rows = self.db.execute(
            user_insert_statement.returning(User.id, User.email)
        ).all()

        inserted_user_map: Dict[str, int] = {email.lower(): user_id for user_id, email in inserted_user_rows}

        inserted_candidates: List[dict] = []
        skipped_candidates: List[dict] = []
        for row in candidate_rows:
            user_id = inserted_user_map.get(row["email"])
            if user_id is None:
                skipped_candidates.append(row)
            else:
                row["user_id"] = user_id
                inserted_candidates.append(row)

        for row in skipped_candidates:
            errors.append(
                {
                    "row": row["row_number"],
                    "error": (
                        "Email already exists after preview approval"
                        if trust_preview
                        else "Email already exists"
                    ),
                    "row_data": row["raw_row_data"],
                }
            )

        if not inserted_candidates:
            return [], errors

        user_role_values = [{"user_id": row["user_id"], "role_id": student_role_id} for row in inserted_candidates]
        self.db.execute(self._insert_statement(UserRole), user_role_values)

        profile_values = [
            {
                "user_id": row["user_id"],
                "school_id": row["school_id"],
                "student_id": row["student_id"],
                "department_id": row["department_id"],
                "program_id": row["program_id"],
                "year_level": 1,
            }
            for row in inserted_candidates
        ]

        profile_insert_statement = self._insert_statement(StudentProfile).values(profile_values)
        if self._supports_on_conflict():
            profile_insert_statement = profile_insert_statement.on_conflict_do_nothing(
                index_elements=["school_id", "student_id"]
            )
        inserted_profiles = self.db.execute(
            profile_insert_statement.returning(StudentProfile.user_id)
        ).scalars().all()

        inserted_profile_user_ids = set(inserted_profiles)
        orphan_rows = [row for row in inserted_candidates if row["user_id"] not in inserted_profile_user_ids]

        if orphan_rows:
            orphan_user_ids = [row["user_id"] for row in orphan_rows]
            self.db.execute(delete(UserRole).where(UserRole.user_id.in_(orphan_user_ids)))
            self.db.execute(delete(User).where(User.id.in_(orphan_user_ids)))
            for row in orphan_rows:
                errors.append(
                    {
                        "row": row["row_number"],
                        "error": (
                            "Duplicate Student_ID within School_ID after preview approval"
                            if trust_preview
                            else "Duplicate Student_ID within School_ID"
                        ),
                        "row_data": row["raw_row_data"],
                    }
                )

        successful_rows = [row for row in inserted_candidates if row["user_id"] in inserted_profile_user_ids]
        return successful_rows, errors

    def log_email_delivery(
        self,
        *,
        job_id: str | None,
        user_id: int | None,
        email: str,
        status: str,
        error_message: str | None = None,
        retry_count: int = 0,
    ) -> None:
        self.db.add(
            EmailDeliveryLog(
                job_id=job_id,
                user_id=user_id,
                email=email,
                status=status,
                error_message=error_message,
                retry_count=retry_count,
            )
        )
