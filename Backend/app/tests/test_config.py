from app.core import config as config_module
from app.core.config import get_settings


def test_get_env_candidate_paths_checks_backend_then_repo_root(tmp_path):
    config_file = tmp_path / "Backend" / "app" / "core" / "config.py"
    config_file.parent.mkdir(parents=True)
    config_file.touch()

    paths = config_module._get_env_candidate_paths(config_file)

    assert paths == [
        tmp_path / "Backend" / ".env",
        tmp_path / ".env",
    ]


def test_get_settings_exposes_tenant_database_fields(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/app")
    monkeypatch.setenv("DATABASE_ADMIN_URL", "postgresql://admin:pass@db:5432/postgres")
    monkeypatch.setenv("TENANT_DATABASE_PREFIX", "valid8")
    monkeypatch.setenv("SMTP_USE_SSL", "true")
    monkeypatch.setenv("SMTP_PREFER_IPV4", "true")
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_AUTH_MODE", "password")
    monkeypatch.setenv("SMTP_FROM_NAME", "VALID8 Notifications")

    settings = get_settings()

    assert settings.database_url == "postgresql://user:pass@db:5432/app"
    assert settings.database_admin_url == "postgresql://admin:pass@db:5432/postgres"
    assert settings.tenant_database_prefix == "valid8"
    assert settings.smtp_use_ssl is True
    assert settings.smtp_prefer_ipv4 is True
    assert settings.email_transport == "smtp"
    assert settings.smtp_auth_mode == "password"
    assert settings.smtp_from_name == "VALID8 Notifications"


def test_get_settings_defaults_email_transport_to_disabled_when_smtp_host_is_missing(monkeypatch):
    monkeypatch.delenv("EMAIL_TRANSPORT", raising=False)
    monkeypatch.setenv("SMTP_HOST", "")

    settings = get_settings()

    assert settings.email_transport == "disabled"
    assert settings.email_required_on_startup is False
