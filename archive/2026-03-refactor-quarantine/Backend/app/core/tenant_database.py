from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.base import Base
from app.models.governance_hierarchy import GovernancePermission, PERMISSION_DEFINITIONS
from app.models.platform_features import (
    DataGovernanceSetting,
    SchoolSubscriptionSetting,
    TenantUserDirectory,
)
from app.models.role import Role
from app.models.school import School, SchoolSetting
from app.models.user import User, UserRole
from app.services.password_change_policy import (
    must_change_password_for_new_account,
    should_prompt_password_change_for_new_account,
)

settings = get_settings()
platform_url = make_url(settings.database_url)
admin_url = make_url(settings.database_admin_url or settings.database_url)

if admin_url.drivername.startswith("postgresql"):
    admin_url = admin_url.set(database="postgres")

ROLE_NAMES = (
    "student",
    "campus_admin",
    "admin",
    "ssg",
    "sg",
    "org",
)

TENANT_DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

_tenant_engines: dict[str, Engine] = {}
_tenant_session_factories: dict[str, sessionmaker] = {}
_admin_engine: Engine | None = None


class TenantProvisioningError(RuntimeError):
    pass


class TenantDirectoryConflictError(TenantProvisioningError):
    pass


@dataclass(frozen=True)
class SchoolItSeed:
    email: str
    first_name: str
    middle_name: str | None
    last_name: str
    password: str


def _slugify(value: str) -> str:
    collapsed = re.sub(r"[^a-zA-Z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return collapsed or "school"


def ensure_school_tenant_metadata(school: School) -> School:
    slug_source = school.school_code or school.school_name or school.name or f"school_{school.id}"
    slug = _slugify(slug_source)
    prefix = _slugify(settings.tenant_database_prefix).rstrip("_") or "school"

    if not school.tenant_key:
        school.tenant_key = f"{prefix}-{school.id}-{slug}"[:100]
    if not school.tenant_database_name:
        school.tenant_database_name = f"{prefix}_{school.id}_{slug}"[:63].rstrip("_")
    return school


def ensure_platform_school_tenant_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "schools" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("schools")}
    ddl_statements: list[str] = []
    if "tenant_key" not in columns:
        ddl_statements.append("ALTER TABLE schools ADD COLUMN tenant_key VARCHAR(100)")
    if "tenant_database_name" not in columns:
        ddl_statements.append("ALTER TABLE schools ADD COLUMN tenant_database_name VARCHAR(128)")

    with engine.begin() as connection:
        for statement in ddl_statements:
            connection.execute(text(statement))
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_schools_tenant_key ON schools (tenant_key)")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_schools_tenant_database_name "
                "ON schools (tenant_database_name)"
            )
        )


def ensure_platform_tenant_directory_table(engine: Engine) -> None:
    TenantUserDirectory.__table__.create(bind=engine, checkfirst=True)


def _tenant_sqlite_path(database_name: str) -> str:
    configured_database = platform_url.database or ""
    if configured_database and configured_database not in {":memory:"}:
        base_dir = Path(configured_database).resolve().parent
    else:
        base_dir = Path.cwd() / ".tenant_databases"
    base_dir.mkdir(parents=True, exist_ok=True)
    return str((base_dir / f"{database_name}.db").resolve())


def _render_database_url(url: URL) -> str:
    return url.render_as_string(hide_password=False)


def build_tenant_database_url(database_name: str) -> str:
    if platform_url.drivername.startswith("sqlite"):
        return _render_database_url(platform_url.set(database=_tenant_sqlite_path(database_name)))
    return _render_database_url(platform_url.set(database=database_name))


def _build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            future=True,
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_use_lifo=True,
        future=True,
    )


def _ensure_tenant_postgres_types(engine: Engine) -> None:
    if not engine.dialect.name.startswith("postgresql"):
        return

    PGEnum(
        "present",
        "late",
        "absent",
        "excused",
        name="attendancestatus",
    ).create(bind=engine, checkfirst=True)


def get_admin_engine() -> Engine:
    global _admin_engine
    if _admin_engine is None:
        _admin_engine = _build_engine(_render_database_url(admin_url))
    return _admin_engine


def get_tenant_engine(database_name: str) -> Engine:
    engine = _tenant_engines.get(database_name)
    if engine is not None:
        return engine

    engine = _build_engine(build_tenant_database_url(database_name))
    _tenant_engines[database_name] = engine
    return engine


def get_tenant_session_factory(database_name: str) -> sessionmaker:
    factory = _tenant_session_factories.get(database_name)
    if factory is not None:
        return factory

    factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=get_tenant_engine(database_name),
    )
    _tenant_session_factories[database_name] = factory
    return factory


@contextmanager
def tenant_session_scope(database_name: str) -> Iterator[Session]:
    session = get_tenant_session_factory(database_name)()
    try:
        yield session
    finally:
        session.close()


def get_school_by_code(platform_db: Session, school_code: str | None) -> School | None:
    normalized_school_code = (school_code or "").strip().lower()
    if not normalized_school_code:
        return None
    return (
        platform_db.query(School)
        .filter(text("lower(school_code) = :school_code"))
        .params(school_code=normalized_school_code)
        .first()
    )


def get_school_by_id(platform_db: Session, school_id: int | None) -> School | None:
    if school_id is None:
        return None
    return platform_db.query(School).filter(School.id == school_id).first()


def get_school_by_tenant_key(platform_db: Session, tenant_key: str | None) -> School | None:
    if not tenant_key:
        return None
    return platform_db.query(School).filter(School.tenant_key == tenant_key).first()


def normalize_tenant_email(email: str | None) -> str:
    return (email or "").strip().lower()


def get_tenant_directory_entry_by_email(
    platform_db: Session,
    email: str | None,
) -> TenantUserDirectory | None:
    normalized_email = normalize_tenant_email(email)
    if not normalized_email:
        return None
    return (
        platform_db.query(TenantUserDirectory)
        .filter(TenantUserDirectory.normalized_email == normalized_email)
        .first()
    )


def get_tenant_school_by_email(
    platform_db: Session,
    email: str | None,
) -> School | None:
    entry = get_tenant_directory_entry_by_email(platform_db, email)
    if entry is None:
        return None
    return get_school_by_id(platform_db, entry.school_id)


def list_tenant_schools(platform_db: Session) -> list[School]:
    return (
        platform_db.query(School)
        .filter(School.tenant_database_name.isnot(None), School.tenant_key.isnot(None))
        .order_by(School.id.asc())
        .all()
    )


def register_tenant_user_email(
    platform_db: Session,
    *,
    school_id: int,
    email: str,
) -> TenantUserDirectory:
    normalized_email = normalize_tenant_email(email)
    if not normalized_email:
        raise TenantDirectoryConflictError("Email is required for tenant directory registration.")

    platform_user = (
        platform_db.query(User)
        .filter(User.email == normalized_email, User.school_id.is_(None))
        .first()
    )
    if platform_user is not None:
        raise TenantDirectoryConflictError(
            "Email is already assigned to a platform admin account."
        )

    existing_entry = get_tenant_directory_entry_by_email(platform_db, normalized_email)
    if existing_entry is not None:
        if existing_entry.school_id != school_id:
            raise TenantDirectoryConflictError(
                "Email is already assigned to another school's database."
            )
        return existing_entry

    entry = TenantUserDirectory(
        normalized_email=normalized_email,
        school_id=school_id,
    )
    platform_db.add(entry)
    platform_db.flush()
    return entry


def unregister_tenant_user_email(
    platform_db: Session,
    *,
    school_id: int,
    email: str,
) -> None:
    normalized_email = normalize_tenant_email(email)
    if not normalized_email:
        return

    entry = get_tenant_directory_entry_by_email(platform_db, normalized_email)
    if entry is None or entry.school_id != school_id:
        return
    platform_db.delete(entry)


def resolve_school_for_tenant_email(
    platform_db: Session,
    *,
    email: str | None,
) -> School | None:
    normalized_email = normalize_tenant_email(email)
    if not normalized_email:
        return None

    school = get_tenant_school_by_email(platform_db, normalized_email)
    if school is not None and school.tenant_database_name and school.tenant_key:
        return school

    matched_schools: list[School] = []
    for candidate_school in list_tenant_schools(platform_db):
        if not candidate_school.tenant_database_name:
            continue
        with tenant_session_scope(candidate_school.tenant_database_name) as tenant_db:
            exists = (
                tenant_db.query(User.id)
                .filter(User.email == normalized_email)
                .first()
            )
        if exists:
            matched_schools.append(candidate_school)

    if len(matched_schools) > 1:
        raise TenantDirectoryConflictError(
            "This email exists in multiple school databases. Automatic login cannot determine the school."
        )

    if len(matched_schools) == 1:
        register_tenant_user_email(
            platform_db,
            school_id=matched_schools[0].id,
            email=normalized_email,
        )
        platform_db.commit()
        return matched_schools[0]

    return None


def create_tenant_database(database_name: str) -> None:
    if platform_url.drivername.startswith("sqlite"):
        Path(_tenant_sqlite_path(database_name)).touch(exist_ok=True)
        return

    if not TENANT_DATABASE_NAME_PATTERN.fullmatch(database_name):
        raise TenantProvisioningError(f"Unsafe tenant database name: {database_name}")

    with get_admin_engine().connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
            {"database_name": database_name},
        ).scalar()
        if exists:
            raise TenantProvisioningError(f"Tenant database already exists: {database_name}")
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))


def drop_tenant_database(database_name: str) -> None:
    engine = _tenant_engines.pop(database_name, None)
    if engine is not None:
        engine.dispose()
    _tenant_session_factories.pop(database_name, None)

    if platform_url.drivername.startswith("sqlite"):
        tenant_path = Path(_tenant_sqlite_path(database_name))
        if tenant_path.exists():
            tenant_path.unlink()
        return

    with get_admin_engine().connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :database_name
                  AND pid <> pg_backend_pid()
                """
            ),
            {"database_name": database_name},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))


def _ensure_reference_rows(db: Session) -> None:
    existing_roles = {
        role.name
        for role in db.query(Role).filter(Role.name.in_(ROLE_NAMES)).all()
    }
    for role_name in ROLE_NAMES:
        if role_name not in existing_roles:
            db.add(Role(name=role_name))

    existing_permission_codes = {
        permission.permission_code
        for permission in db.query(GovernancePermission).all()
    }
    for permission_code, definition in PERMISSION_DEFINITIONS.items():
        if permission_code not in existing_permission_codes:
            db.add(
                GovernancePermission(
                    permission_code=permission_code,
                    permission_name=definition["permission_name"],
                    description=definition["description"],
                )
            )


def _upsert_school_rows(
    db: Session,
    *,
    school: School,
    updated_by_user_id: int | None,
) -> School:
    source_settings = getattr(school, "settings", None)
    tenant_school = db.query(School).filter(School.id == school.id).first()
    if tenant_school is None:
        tenant_school = School(id=school.id)
        db.add(tenant_school)

    tenant_school.name = school.name
    tenant_school.school_name = school.school_name
    tenant_school.school_code = school.school_code
    tenant_school.tenant_key = school.tenant_key
    tenant_school.tenant_database_name = school.tenant_database_name
    tenant_school.address = school.address
    tenant_school.logo_url = school.logo_url
    tenant_school.primary_color = school.primary_color
    tenant_school.secondary_color = school.secondary_color
    tenant_school.subscription_status = school.subscription_status
    tenant_school.active_status = school.active_status
    tenant_school.subscription_plan = school.subscription_plan
    tenant_school.subscription_start = school.subscription_start
    tenant_school.subscription_end = school.subscription_end
    db.flush()

    settings_row = db.query(SchoolSetting).filter(SchoolSetting.school_id == school.id).first()
    if settings_row is None:
        settings_row = SchoolSetting(school_id=school.id)
        db.add(settings_row)
    settings_row.primary_color = school.primary_color
    settings_row.secondary_color = school.secondary_color or "#2C5F9E"
    settings_row.accent_color = (
        source_settings.accent_color
        if source_settings is not None and getattr(source_settings, "accent_color", None)
        else (school.secondary_color or school.primary_color)
    )
    settings_row.updated_by_user_id = updated_by_user_id
    if source_settings is not None:
        settings_row.event_default_early_check_in_minutes = (
            source_settings.event_default_early_check_in_minutes
        )
        settings_row.event_default_late_threshold_minutes = (
            source_settings.event_default_late_threshold_minutes
        )
        settings_row.event_default_sign_out_grace_minutes = (
            source_settings.event_default_sign_out_grace_minutes
        )

    if db.query(SchoolSubscriptionSetting).filter(SchoolSubscriptionSetting.school_id == school.id).first() is None:
        db.add(SchoolSubscriptionSetting(school_id=school.id))
    if db.query(DataGovernanceSetting).filter(DataGovernanceSetting.school_id == school.id).first() is None:
        db.add(DataGovernanceSetting(school_id=school.id))

    return tenant_school


def _ensure_school_it_account(
    db: Session,
    *,
    school: School,
    school_it_seed: SchoolItSeed,
) -> User:
    existing_user = db.query(User).filter(User.email == school_it_seed.email).first()
    if existing_user is not None:
        raise TenantProvisioningError("Campus Admin email is already registered in this school database.")

    campus_admin_role = db.query(Role).filter(Role.name == "campus_admin").first()
    if campus_admin_role is None:
        raise TenantProvisioningError("Campus Admin role is missing from tenant database.")

    user = User(
        email=school_it_seed.email,
        school_id=school.id,
        first_name=school_it_seed.first_name,
        middle_name=school_it_seed.middle_name,
        last_name=school_it_seed.last_name,
        is_active=True,
        must_change_password=must_change_password_for_new_account(),
        should_prompt_password_change=should_prompt_password_change_for_new_account(),
    )
    user.set_password(school_it_seed.password)
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=campus_admin_role.id))
    return user


def provision_school_tenant(
    *,
    school: School,
    updated_by_user_id: int | None,
    school_it_seed: SchoolItSeed | None = None,
) -> int | None:
    ensure_school_tenant_metadata(school)
    create_tenant_database(school.tenant_database_name)
    try:
        tenant_engine = get_tenant_engine(school.tenant_database_name)
        _ensure_tenant_postgres_types(tenant_engine)
        Base.metadata.create_all(bind=tenant_engine)
        with tenant_session_scope(school.tenant_database_name) as tenant_db:
            _ensure_reference_rows(tenant_db)
            tenant_school = _upsert_school_rows(
                tenant_db,
                school=school,
                updated_by_user_id=updated_by_user_id,
            )
            school_it_user_id: int | None = None
            if school_it_seed is not None:
                tenant_user = _ensure_school_it_account(
                    tenant_db,
                    school=tenant_school,
                    school_it_seed=school_it_seed,
                )
                school_it_user_id = tenant_user.id
            tenant_db.commit()
            return school_it_user_id
    except Exception:
        drop_tenant_database(school.tenant_database_name)
        raise


def sync_platform_school_to_tenant(
    *,
    school: School,
    updated_by_user_id: int | None,
) -> None:
    ensure_school_tenant_metadata(school)
    with tenant_session_scope(school.tenant_database_name) as tenant_db:
        _upsert_school_rows(
            tenant_db,
            school=school,
            updated_by_user_id=updated_by_user_id,
        )
        tenant_db.commit()
