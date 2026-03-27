"""Template rendering helpers for the email service package."""

from __future__ import annotations

import html


def _send_email(
    *,
    subject: str,
    recipient_email: str,
    body: str,
    html_body: str | None = None,
    reply_to: str | None = None,
) -> None:
    from . import send_transactional_email

    send_transactional_email(
        recipient_email=recipient_email,
        subject=subject,
        text_body=body,
        html_body=html_body,
        reply_to=reply_to,
    )


def build_welcome_email_content(
    *,
    recipient_email: str,
    temporary_password: str,
    first_name: str,
    system_name: str,
    login_url: str,
    password_label: str,
    credential_subject: str,
    password_notice: str,
) -> tuple[str, str, str]:
    return (
        f"Welcome to {system_name} - {credential_subject}",
        (
            f"Dear {first_name},\n\n"
            f"Welcome to {system_name}!\n\n"
            "Your account has been successfully created.\n\n"
            "Login Credentials:\n"
            "-----------------------------------\n"
            f"Email: {recipient_email}\n"
            f"{password_label}: {temporary_password}\n"
            f"Login URL: {login_url}\n"
            "-----------------------------------\n\n"
            f"{password_notice}"
            "Do not share your login credentials with anyone.\n\n"
            "If you experience issues, contact your Campus Admin.\n\n"
            "Best regards,\n"
            f"{system_name} Team\n"
        ),
        (
            f"<p>Dear {html.escape(first_name)},</p>"
            f"<p>Welcome to <strong>{html.escape(system_name)}</strong>.</p>"
            "<p>Your account has been successfully created.</p>"
            "<p><strong>Login Credentials</strong><br>"
            f"Email: {html.escape(recipient_email)}<br>"
            f"{html.escape(password_label)}: {html.escape(temporary_password)}<br>"
            f'Login URL: <a href="{html.escape(login_url)}">{html.escape(login_url)}</a></p>'
            f"<p>{html.escape(password_notice).replace(chr(10), '<br>')}</p>"
            "<p>Do not share your login credentials with anyone.</p>"
            "<p>If you experience issues, contact your Campus Admin.</p>"
            f"<p>Best regards,<br>{html.escape(system_name)} Team</p>"
        ),
    )


def build_import_onboarding_email_content(
    *,
    first_name: str,
    system_name: str,
    login_url: str,
) -> tuple[str, str, str]:
    return (
        f"Welcome to {system_name} - Account Ready",
        (
            f"Dear {first_name},\n\n"
            f"Your account has been created in {system_name}.\n\n"
            "To set your first password, open the login page and use the Forgot Password option.\n"
            "A Campus Admin must approve the request before you can sign in.\n\n"
            f"Login URL: {login_url}\n\n"
            "If you experience issues, contact your Campus Admin.\n\n"
            "Best regards,\n"
            f"{system_name} Team\n"
        ),
        (
            f"<p>Dear {html.escape(first_name)},</p>"
            f"<p>Your account has been created in <strong>{html.escape(system_name)}</strong>.</p>"
            "<p>To set your first password, open the login page and use the Forgot Password option. "
            "A Campus Admin must approve the request before you can sign in.</p>"
            f'<p>Login URL: <a href="{html.escape(login_url)}">{html.escape(login_url)}</a></p>'
            "<p>If you experience issues, contact your Campus Admin.</p>"
            f"<p>Best regards,<br>{html.escape(system_name)} Team</p>"
        ),
    )


def build_password_reset_email_content(
    *,
    recipient_email: str,
    temporary_password: str,
    first_name: str,
    system_name: str,
    login_url: str,
) -> tuple[str, str, str]:
    return (
        f"{system_name} - Password Reset Approved",
        (
            f"Dear {first_name},\n\n"
            "Your password reset request has been approved.\n\n"
            "Temporary Login Credentials:\n"
            "-----------------------------------\n"
            f"Email: {recipient_email}\n"
            f"Temporary Password: {temporary_password}\n"
            f"Login URL: {login_url}\n"
            "-----------------------------------\n\n"
            "IMPORTANT:\n"
            "You are required to change this temporary password immediately after login.\n\n"
            "Best regards,\n"
            f"{system_name} Team\n"
        ),
        (
            f"<p>Dear {html.escape(first_name)},</p>"
            "<p>Your password reset request has been approved.</p>"
            "<p><strong>Temporary Login Credentials</strong><br>"
            f"Email: {html.escape(recipient_email)}<br>"
            f"Temporary Password: {html.escape(temporary_password)}<br>"
            f'Login URL: <a href="{html.escape(login_url)}">{html.escape(login_url)}</a></p>'
            "<p><strong>IMPORTANT:</strong><br>"
            "You are required to change this temporary password immediately after login.</p>"
            f"<p>Best regards,<br>{html.escape(system_name)} Team</p>"
        ),
    )


def build_mfa_code_email_content(
    *,
    code: str,
    first_name: str,
    system_name: str,
) -> tuple[str, str, str]:
    return (
        f"{system_name} - MFA Verification Code",
        (
            f"Dear {first_name},\n\n"
            "Use the code below to complete your login:\n\n"
            f"MFA Code: {code}\n\n"
            "This code expires in 10 minutes.\n"
            "If you did not attempt to log in, please reset your password immediately.\n\n"
            f"{system_name} Team\n"
        ),
        (
            f"<p>Dear {html.escape(first_name)},</p>"
            "<p>Use the code below to complete your login:</p>"
            f"<p><strong>MFA Code: {html.escape(code)}</strong></p>"
            "<p>This code expires in 10 minutes. If you did not attempt to log in, please reset your password immediately.</p>"
            f"<p>{html.escape(system_name)} Team</p>"
        ),
    )
