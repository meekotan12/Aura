"""Use: Tests email service behavior.
Where to use: Use this when running `pytest` to check that this backend behavior still works.
Role: Test layer. It protects the app from regressions.
"""

import json
from types import SimpleNamespace

from app.services import email_service


def _smtp_settings(**overrides):
    defaults = {
        "email_transport": "smtp",
        "email_required_on_startup": True,
        "email_verify_connection_on_startup": False,
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_timeout_seconds": 20,
        "smtp_username": "mailer@example.com",
        "smtp_password": "secret",
        "smtp_from_email": "mailer@example.com",
        "smtp_from_name": "VALID8 Notifications",
        "smtp_reply_to": "",
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
        "smtp_ehlo_name": "app.example.com",
        "smtp_prefer_ipv4": False,
        "smtp_auth_mode": "auto",
        "smtp_google_account_type": "auto",
        "smtp_google_allow_custom_from": False,
        "google_oauth_client_id": "",
        "google_oauth_client_secret": "",
        "google_oauth_refresh_token": "",
        "google_oauth_auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "google_oauth_token_url": "https://oauth2.googleapis.com/token",
        "google_oauth_scopes": [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.settings.basic",
        ],
        "google_gmail_api_base_url": "https://gmail.googleapis.com/gmail/v1",
        "login_url": "https://valid8.example/login",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_send_welcome_email_allows_temporary_password_after_login(monkeypatch) -> None:
    sent: dict[str, str] = {}

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(login_url="https://valid8.example/login"),
    )

    def fake_send_email(*, subject: str, recipient_email: str, body: str, **kwargs) -> None:
        sent["subject"] = subject
        sent["recipient_email"] = recipient_email
        sent["body"] = body
        sent["html_body"] = kwargs.get("html_body") or ""

    monkeypatch.setattr(email_service, "_send_email", fake_send_email)

    email_service.send_welcome_email(
        recipient_email="new.user@example.com",
        temporary_password="TempPass123!",
        first_name="New",
        system_name="VALID8",
    )

    assert sent["recipient_email"] == "new.user@example.com"
    assert "You can keep using it after login" in sent["body"]
    assert (
        "You are required to change your password immediately after your first login."
        not in sent["body"]
    )
    assert "Login Credentials" in sent["html_body"]


def test_send_password_reset_email_still_requires_password_change(monkeypatch) -> None:
    sent: dict[str, str] = {}

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(login_url="https://valid8.example/login"),
    )

    def fake_send_email(*, subject: str, recipient_email: str, body: str, **kwargs) -> None:
        sent["subject"] = subject
        sent["recipient_email"] = recipient_email
        sent["body"] = body
        sent["html_body"] = kwargs.get("html_body") or ""

    monkeypatch.setattr(email_service, "_send_email", fake_send_email)

    email_service.send_password_reset_email(
        recipient_email="existing.user@example.com",
        temporary_password="TempPass123!",
        first_name="Existing",
        system_name="VALID8",
    )

    assert sent["recipient_email"] == "existing.user@example.com"
    assert "You are required to change this temporary password immediately after login." in sent["body"]
    assert "Temporary Login Credentials" in sent["html_body"]


def test_send_welcome_email_with_user_supplied_password_uses_generic_password_copy(monkeypatch) -> None:
    sent: dict[str, str] = {}

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(login_url="https://valid8.example/login"),
    )

    def fake_send_email(*, subject: str, recipient_email: str, body: str, **kwargs) -> None:
        sent["subject"] = subject
        sent["recipient_email"] = recipient_email
        sent["body"] = body

    monkeypatch.setattr(email_service, "_send_email", fake_send_email)

    email_service.send_welcome_email(
        recipient_email="provided.password@example.com",
        temporary_password="ChosenPass123!",
        first_name="Chosen",
        system_name="VALID8",
        password_is_temporary=False,
    )

    assert sent["recipient_email"] == "provided.password@example.com"
    assert "Password: ChosenPass123!" in sent["body"]
    assert "Temporary Password:" not in sent["body"]
    assert "You can change it anytime from your account settings" in sent["body"]


def test_send_plain_email_uses_starttls_when_tls_enabled(monkeypatch) -> None:
    calls: list[str] = []

    class FakeSMTP:
        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append("exit")
            return False

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self, context=None):
            calls.append("starttls")

        def login(self, username: str, password: str):
            calls.append(f"login:{username}:{password}")

        def send_message(self, msg, from_addr=None, to_addrs=None):
            calls.append(f"send:{from_addr}:{','.join(to_addrs)}")

    monkeypatch.setattr(email_service, "get_settings", lambda: _smtp_settings())
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *args, **kwargs: FakeSMTP())

    email_service.send_plain_email(
        recipient_email="recipient@example.com",
        subject="Subject",
        body="Body",
    )

    assert calls == [
        "enter",
        "ehlo",
        "starttls",
        "ehlo",
        "login:mailer@example.com:secret",
        "send:mailer@example.com:recipient@example.com",
        "exit",
    ]


def test_send_plain_email_uses_smtp_ssl_when_enabled(monkeypatch) -> None:
    calls: list[str] = []

    class FakeSMTPSSL:
        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append("exit")
            return False

        def login(self, username: str, password: str):
            calls.append(f"login:{username}:{password}")

        def send_message(self, msg, from_addr=None, to_addrs=None):
            calls.append(f"send:{from_addr}:{','.join(to_addrs)}")

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: _smtp_settings(smtp_port=465, smtp_use_tls=False, smtp_use_ssl=True),
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", lambda *args, **kwargs: FakeSMTPSSL())

    email_service.send_plain_email(
        recipient_email="recipient@example.com",
        subject="Subject",
        body="Body",
    )

    assert calls == [
        "enter",
        "login:mailer@example.com:secret",
        "send:mailer@example.com:recipient@example.com",
        "exit",
    ]


def test_build_smtp_client_prefers_ipv4_when_enabled(monkeypatch) -> None:
    sentinel = object()

    monkeypatch.setattr(email_service, "_IPv4PreferredSMTP", lambda *args, **kwargs: sentinel)

    client = email_service._build_smtp_client(_smtp_settings(smtp_prefer_ipv4=True))

    assert client is sentinel


def test_send_plain_email_uses_google_xoauth2_when_configured(monkeypatch) -> None:
    calls: list[str] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"access_token": "access-token"}

    class FakeSMTP:
        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append("exit")
            return False

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self, context=None):
            calls.append("starttls")

        def docmd(self, command: str, payload: str):
            calls.append(f"docmd:{command}")
            assert command == "AUTH"
            assert payload.startswith("XOAUTH2 ")
            return 235, b"2.7.0 Accepted"

        def send_message(self, msg, from_addr=None, to_addrs=None):
            calls.append(f"send:{from_addr}:{','.join(to_addrs)}")

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: _smtp_settings(
            smtp_host="smtp.gmail.com",
            smtp_username="mailer@example.com",
            smtp_password="",
            smtp_from_email="mailer@example.com",
            smtp_auth_mode="xoauth2",
            smtp_google_account_type="workspace",
            smtp_google_allow_custom_from=True,
            google_oauth_client_id="client-id",
            google_oauth_client_secret="client-secret",
            google_oauth_refresh_token="refresh-token",
        ),
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *args, **kwargs: FakeSMTP())
    monkeypatch.setattr(email_service.httpx, "post", lambda *args, **kwargs: FakeResponse())

    email_service.send_plain_email(
        recipient_email="recipient@example.com",
        subject="Subject",
        body="Body",
    )

    assert calls == [
        "enter",
        "ehlo",
        "starttls",
        "ehlo",
        "docmd:AUTH",
        "send:mailer@example.com:recipient@example.com",
        "exit",
    ]


def test_check_email_delivery_connection_verifies_sender_when_requested(monkeypatch) -> None:
    calls: list[str] = []

    class FakeSMTP:
        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append("exit")
            return False

        def noop(self):
            calls.append("noop")
            return 250, b"OK"

        def mail(self, sender: str):
            calls.append(f"mail:{sender}")
            return 250, b"2.1.0 OK"

        def rset(self):
            calls.append("rset")

    settings = _smtp_settings(
        smtp_host="smtp-relay.gmail.com",
        smtp_username="",
        smtp_password="",
        smtp_from_email="no-reply@example.com",
        smtp_use_tls=False,
        smtp_auth_mode="none",
        smtp_google_account_type="workspace",
        smtp_google_allow_custom_from=True,
    )

    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *args, **kwargs: FakeSMTP())

    status = email_service.check_email_delivery_connection(settings=settings)

    assert status.sender == "no-reply@example.com"
    assert status.auth_mode == "none"
    assert calls == ["enter", "noop", "mail:no-reply@example.com", "rset", "exit"]


def test_validate_email_delivery_settings_rejects_conflicting_tls_modes(monkeypatch) -> None:
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: _smtp_settings(smtp_use_tls=True, smtp_use_ssl=True),
    )

    try:
        email_service.validate_email_delivery_settings()
    except email_service.EmailDeliveryError as exc:
        assert "cannot both be enabled" in str(exc)
    else:
        raise AssertionError("Expected EmailDeliveryError for conflicting SMTP TLS settings")


def test_validate_email_delivery_settings_falls_back_to_authenticated_personal_gmail_sender() -> None:
    resolved = email_service.validate_email_delivery_settings(
        _smtp_settings(
            smtp_host="smtp.gmail.com",
            smtp_username="person@gmail.com",
            smtp_password="app-password",
            smtp_from_email="no-reply@example.com",
            smtp_google_account_type="personal",
        )
    )

    assert resolved.from_email == "person@gmail.com"
    assert resolved.warnings


def test_validate_email_delivery_settings_rejects_workspace_custom_sender_without_opt_in() -> None:
    try:
        email_service.validate_email_delivery_settings(
            _smtp_settings(
                smtp_host="smtp.gmail.com",
                smtp_username="mailer@school.edu",
                smtp_password="app-password",
                smtp_from_email="no-reply@school.edu",
                smtp_google_account_type="workspace",
                smtp_google_allow_custom_from=False,
            )
        )
    except email_service.EmailConfigurationError as exc:
        assert "SMTP_GOOGLE_ALLOW_CUSTOM_FROM=true" in str(exc)
    else:
        raise AssertionError("Expected EmailConfigurationError for an unapproved custom Workspace sender")


def test_send_plain_email_surfaces_google_auth_failure_with_app_password_guidance(monkeypatch) -> None:
    class FakeSMTP:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self, context=None):
            return None

        def login(self, username: str, password: str):
            raise email_service.smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: _smtp_settings(
            smtp_host="smtp.gmail.com",
            smtp_username="person@gmail.com",
            smtp_password="wrong-password",
            smtp_from_email="person@gmail.com",
            smtp_google_account_type="personal",
        ),
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda *args, **kwargs: FakeSMTP())

    try:
        email_service.send_plain_email(
            recipient_email="recipient@example.com",
            subject="Subject",
            body="Body",
        )
    except email_service.EmailDeliveryError as exc:
        assert "App Password" in str(exc)
    else:
        raise AssertionError("Expected EmailDeliveryError for Google SMTP authentication failure")


def test_validate_email_delivery_settings_accepts_gmail_api_transport() -> None:
    resolved = email_service.validate_email_delivery_settings(
        _smtp_settings(
            email_transport="gmail_api",
            smtp_host="",
            smtp_username="mailer@gmail.com",
            smtp_password="",
            google_oauth_client_id="client-id",
            google_oauth_client_secret="client-secret",
            google_oauth_refresh_token="refresh-token",
        )
    )

    assert resolved.transport == "gmail_api"
    assert resolved.auth_mode == "oauth2"
    assert resolved.from_email == "mailer@gmail.com"


def test_check_email_delivery_connection_verifies_gmail_api_custom_sender(monkeypatch) -> None:
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object]):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)
            self.reason_phrase = "OK"

        def json(self):
            return self._payload

    settings = _smtp_settings(
        email_transport="gmail_api",
        smtp_host="",
        smtp_username="mailer@school.edu",
        smtp_password="",
        smtp_from_email="no-reply@school.edu",
        smtp_google_account_type="workspace",
        smtp_google_allow_custom_from=True,
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_refresh_token="refresh-token",
    )

    monkeypatch.setattr(email_service, "_request_google_oauth_access_token", lambda settings: "access-token")

    def fake_get(url: str, headers=None, timeout=None):
        calls.append(url)
        return FakeResponse(
            200,
            {"sendAsEmail": "no-reply@school.edu", "isPrimary": False, "verificationStatus": "accepted"},
        )

    monkeypatch.setattr(email_service.httpx, "get", fake_get)

    status = email_service.check_email_delivery_connection(settings=settings)

    assert status.transport == "gmail_api"
    assert status.host == "gmail.googleapis.com"
    assert calls


def test_send_plain_email_uses_gmail_api_transport(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        reason_phrase = "OK"
        text = ""

        def json(self):
            return {"id": "message-id"}

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: _smtp_settings(
            email_transport="gmail_api",
            smtp_host="",
            smtp_username="mailer@gmail.com",
            smtp_password="",
            google_oauth_client_id="client-id",
            google_oauth_client_secret="client-secret",
            google_oauth_refresh_token="refresh-token",
        ),
    )
    monkeypatch.setattr(email_service, "_request_google_oauth_access_token", lambda settings: "access-token")

    def fake_post(url: str, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(email_service.httpx, "post", fake_post)

    email_service.send_plain_email(
        recipient_email="recipient@example.com",
        subject="Subject",
        body="Body",
    )

    assert captured["url"] == "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    assert captured["headers"]["Authorization"] == "Bearer access-token"
    assert isinstance(captured["json"]["raw"], str)


def test_send_plain_email_surfaces_gmail_api_scope_errors(monkeypatch) -> None:
    class FakeResponse:
        status_code = 403
        reason_phrase = "Forbidden"
        text = json.dumps({"error": {"status": "PERMISSION_DENIED", "message": "Request had insufficient authentication scopes."}})

        def json(self):
            return {"error": {"status": "PERMISSION_DENIED", "message": "Request had insufficient authentication scopes."}}

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: _smtp_settings(
            email_transport="gmail_api",
            smtp_host="",
            smtp_username="mailer@gmail.com",
            smtp_password="",
            google_oauth_client_id="client-id",
            google_oauth_client_secret="client-secret",
            google_oauth_refresh_token="refresh-token",
        ),
    )
    monkeypatch.setattr(email_service, "_request_google_oauth_access_token", lambda settings: "access-token")
    monkeypatch.setattr(email_service.httpx, "post", lambda *args, **kwargs: FakeResponse())

    try:
        email_service.send_plain_email(
            recipient_email="recipient@example.com",
            subject="Subject",
            body="Body",
        )
    except email_service.EmailDeliveryError as exc:
        assert "gmail.send" in str(exc)
    else:
        raise AssertionError("Expected EmailDeliveryError for Gmail API scope failure")
