"""Use-case senders for the email service package."""

from __future__ import annotations


def send_welcome_email(
    recipient_email: str,
    temporary_password: str,
    first_name: str | None = None,
    system_name: str | None = None,
    login_url: str | None = None,
    password_is_temporary: bool = True,
) -> None:
    from . import get_settings, get_welcome_email_password_notice, _send_email
    from .rendering import build_welcome_email_content

    settings = get_settings()

    resolved_first_name = (first_name or "").strip() or "User"
    resolved_system_name = (system_name or "").strip() or "Valid8 Attendance Recognition System"
    resolved_login_url = (login_url or "").strip() or settings.login_url
    password_label = "Temporary Password" if password_is_temporary else "Password"
    credential_subject = "Temporary Login Credentials" if password_is_temporary else "Login Credentials"
    password_notice = get_welcome_email_password_notice(password_is_temporary=password_is_temporary)

    subject, body, html_body = build_welcome_email_content(
        recipient_email=recipient_email,
        temporary_password=temporary_password,
        first_name=resolved_first_name,
        system_name=resolved_system_name,
        login_url=resolved_login_url,
        password_label=password_label,
        credential_subject=credential_subject,
        password_notice=password_notice,
    )
    _send_email(
        subject=subject,
        recipient_email=recipient_email,
        body=body,
        html_body=html_body,
    )


def send_import_onboarding_email(
    *,
    recipient_email: str,
    first_name: str | None = None,
    system_name: str | None = None,
    login_url: str | None = None,
) -> None:
    from . import get_settings, _send_email
    from .rendering import build_import_onboarding_email_content

    settings = get_settings()

    resolved_first_name = (first_name or "").strip() or "User"
    resolved_system_name = (system_name or "").strip() or "Valid8 Attendance Recognition System"
    resolved_login_url = (login_url or "").strip() or settings.login_url

    subject, body, html_body = build_import_onboarding_email_content(
        first_name=resolved_first_name,
        system_name=resolved_system_name,
        login_url=resolved_login_url,
    )
    _send_email(
        subject=subject,
        recipient_email=recipient_email,
        body=body,
        html_body=html_body,
    )


def send_password_reset_email(
    recipient_email: str,
    temporary_password: str,
    first_name: str | None = None,
    system_name: str | None = None,
    login_url: str | None = None,
) -> None:
    from . import get_settings, _send_email
    from .rendering import build_password_reset_email_content

    settings = get_settings()

    resolved_first_name = (first_name or "").strip() or "User"
    resolved_system_name = (system_name or "").strip() or "Valid8 Attendance Recognition System"
    resolved_login_url = (login_url or "").strip() or settings.login_url

    subject, body, html_body = build_password_reset_email_content(
        recipient_email=recipient_email,
        temporary_password=temporary_password,
        first_name=resolved_first_name,
        system_name=resolved_system_name,
        login_url=resolved_login_url,
    )
    _send_email(
        subject=subject,
        recipient_email=recipient_email,
        body=body,
        html_body=html_body,
    )


def send_mfa_code_email(
    *,
    recipient_email: str,
    code: str,
    first_name: str | None = None,
    system_name: str | None = None,
) -> None:
    from . import _send_email
    from .rendering import build_mfa_code_email_content

    resolved_first_name = (first_name or "").strip() or "User"
    resolved_system_name = (system_name or "").strip() or "Valid8 Attendance Recognition System"
    subject, body, html_body = build_mfa_code_email_content(
        code=code,
        first_name=resolved_first_name,
        system_name=resolved_system_name,
    )
    _send_email(
        subject=subject,
        recipient_email=recipient_email,
        body=body,
        html_body=html_body,
    )
