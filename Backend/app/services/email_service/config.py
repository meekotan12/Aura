"""Configuration helpers for the email service package."""

from __future__ import annotations

import socket
import smtplib
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email as validate_email_address

from app.core.config import Settings

GOOGLE_GMAIL_SMTP_HOST = "smtp.gmail.com"
GOOGLE_WORKSPACE_RELAY_HOST = "smtp-relay.gmail.com"
GOOGLE_GMAIL_API_HOST = "gmail.googleapis.com"
ALLOWED_EMAIL_TRANSPORTS = {"disabled", "smtp", "gmail_api"}
ALLOWED_SMTP_AUTH_MODES = {"auto", "none", "password", "xoauth2"}
ALLOWED_GOOGLE_ACCOUNT_TYPES = {"auto", "personal", "workspace", "unknown"}
TEMPORARY_SMTP_ERROR_CODES = {421, 450, 451, 452, 454}
TEMPORARY_GMAIL_API_STATUS_CODES = {429, 500, 502, 503, 504}


class EmailDeliveryError(Exception):
    pass


class EmailConfigurationError(EmailDeliveryError):
    pass


@dataclass(frozen=True)
class ResolvedEmailDeliverySettings:
    transport: str
    auth_mode: str
    from_email: str
    from_header: str
    reply_to: str | None
    google_account_type: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class EmailConnectionStatus:
    host: str
    port: int
    transport: str
    auth_mode: str
    sender: str
    reply_to: str | None
    warnings: tuple[str, ...]


class _IPv4SMTPMixin:
    def _create_ipv4_socket(self, host: str, port: int, timeout, source_address):
        last_error: OSError | None = None
        addresses = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if not addresses:
            raise OSError(f"No IPv4 address resolved for {host}:{port}")

        for family, socktype, proto, _, sockaddr in addresses:
            client_socket = None
            try:
                client_socket = socket.socket(family, socktype, proto)
                if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                    client_socket.settimeout(timeout)
                if source_address:
                    client_socket.bind(source_address)
                client_socket.connect(sockaddr)
                return client_socket
            except OSError as exc:
                last_error = exc
                if client_socket is not None:
                    client_socket.close()

        if last_error is None:
            raise OSError(f"Could not connect to any IPv4 address for {host}:{port}")
        raise last_error


class _IPv4PreferredSMTP(_IPv4SMTPMixin, smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return self._create_ipv4_socket(
            host,
            port,
            timeout,
            getattr(self, "source_address", None),
        )


class _IPv4PreferredSMTP_SSL(_IPv4SMTPMixin, smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        client_socket = self._create_ipv4_socket(
            host,
            port,
            timeout,
            getattr(self, "source_address", None),
        )
        return self.context.wrap_socket(client_socket, server_hostname=host)


def _normalize_choice(value: str, allowed: set[str], field_name: str) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise EmailConfigurationError(f"{field_name} must be one of: {allowed_values}")
    return normalized


def _normalize_email(value: str | None, field_name: str, *, allow_blank: bool = False) -> str:
    candidate = (value or "").strip()
    if not candidate:
        if allow_blank:
            return ""
        raise EmailConfigurationError(f"{field_name} is not configured")

    try:
        return validate_email_address(candidate, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise EmailConfigurationError(f"{field_name} is not a valid email address: {exc}") from exc


def _normalize_runtime_email(value: str | None, field_name: str) -> str:
    try:
        return validate_email_address((value or "").strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise EmailDeliveryError(f"{field_name} is not a valid email address: {exc}") from exc


def _is_google_gmail_host(settings: Settings) -> bool:
    return settings.smtp_host.strip().lower() == GOOGLE_GMAIL_SMTP_HOST


def _is_google_workspace_relay_host(settings: Settings) -> bool:
    return settings.smtp_host.strip().lower() == GOOGLE_WORKSPACE_RELAY_HOST


def _is_gmail_api_transport(settings: Settings) -> bool:
    return (settings.email_transport or "").strip().lower() == "gmail_api"


def _gmail_api_host(settings: Settings) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(settings.google_gmail_api_base_url)
    return parsed.netloc or GOOGLE_GMAIL_API_HOST


def _resolve_google_account_type(settings: Settings) -> str:
    configured = _normalize_choice(
        settings.smtp_google_account_type or "auto",
        ALLOWED_GOOGLE_ACCOUNT_TYPES,
        "SMTP_GOOGLE_ACCOUNT_TYPE",
    )
    if configured != "auto":
        return configured

    normalized_username = (settings.smtp_username or "").strip().lower()
    if normalized_username.endswith("@gmail.com") or normalized_username.endswith("@googlemail.com"):
        return "personal"
    if normalized_username and (
        _is_gmail_api_transport(settings)
        or _is_google_gmail_host(settings)
        or _is_google_workspace_relay_host(settings)
    ):
        return "workspace"
    return "unknown"


def _resolve_smtp_auth_mode(settings: Settings) -> str:
    configured = _normalize_choice(
        settings.smtp_auth_mode or "auto",
        ALLOWED_SMTP_AUTH_MODES,
        "SMTP_AUTH_MODE",
    )
    if configured != "auto":
        return configured

    has_google_oauth = all(
        [
            settings.smtp_username.strip(),
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
            settings.google_oauth_refresh_token,
        ]
    )
    if has_google_oauth:
        return "xoauth2"

    has_password_pair = bool(settings.smtp_username.strip()) or bool(settings.smtp_password)
    if has_password_pair:
        if not settings.smtp_username.strip() or not settings.smtp_password:
            raise EmailConfigurationError(
                "SMTP_USERNAME and SMTP_PASSWORD must be configured together."
            )
        return "password"

    return "none"


def _resolve_sender_settings(
    settings: Settings,
    *,
    transport: str,
    auth_mode: str,
    google_account_type: str,
) -> ResolvedEmailDeliverySettings:
    from email.utils import formataddr

    normalized_username = _normalize_email(settings.smtp_username, "SMTP_USERNAME", allow_blank=True)
    normalized_from_email = _normalize_email(settings.smtp_from_email, "SMTP_FROM_EMAIL", allow_blank=True)
    reply_to = _normalize_email(settings.smtp_reply_to, "SMTP_REPLY_TO", allow_blank=True) or None
    warnings: list[str] = []

    if transport == "gmail_api" or _is_google_gmail_host(settings):
        if not normalized_from_email:
            normalized_from_email = normalized_username

        if google_account_type == "personal" and normalized_from_email != normalized_username:
            warnings.append(
                "SMTP_FROM_EMAIL was changed to the authenticated Gmail address because personal "
                "Gmail cannot reliably send as an arbitrary custom domain sender."
            )
            normalized_from_email = normalized_username
        elif normalized_from_email != normalized_username and not settings.smtp_google_allow_custom_from:
            raise EmailConfigurationError(
                "SMTP_FROM_EMAIL differs from SMTP_USERNAME. For Google Workspace aliases or "
                "Gmail 'Send mail as' aliases, configure the alias in Google first and then set "
                "SMTP_GOOGLE_ALLOW_CUSTOM_FROM=true. Otherwise use the authenticated mailbox as the sender."
            )
    elif _is_google_workspace_relay_host(settings) and not normalized_from_email:
        normalized_from_email = normalized_username

    if not normalized_from_email:
        raise EmailConfigurationError(
            "SMTP_FROM_EMAIL is not configured. Set a valid sender address for transactional emails."
        )

    from_name = (settings.smtp_from_name or "").strip()
    from_header = formataddr((from_name, normalized_from_email)) if from_name else normalized_from_email

    return ResolvedEmailDeliverySettings(
        transport=transport,
        auth_mode=auth_mode,
        from_email=normalized_from_email,
        from_header=from_header,
        reply_to=reply_to,
        google_account_type=google_account_type,
        warnings=tuple(warnings),
    )


def validate_email_delivery_settings(settings: Settings | None = None) -> ResolvedEmailDeliverySettings:
    from . import get_settings

    resolved_settings = settings or get_settings()
    transport = _normalize_choice(
        resolved_settings.email_transport or "disabled",
        ALLOWED_EMAIL_TRANSPORTS,
        "EMAIL_TRANSPORT",
    )

    if transport == "disabled":
        raise EmailConfigurationError(
            "EMAIL_TRANSPORT is disabled. Set EMAIL_TRANSPORT to smtp or gmail_api to enable outbound email delivery."
        )

    google_account_type = _resolve_google_account_type(resolved_settings)

    if transport == "gmail_api":
        if not resolved_settings.google_gmail_api_base_url.strip():
            raise EmailConfigurationError("GOOGLE_GMAIL_API_BASE_URL is not configured")
        if not resolved_settings.smtp_username.strip():
            raise EmailConfigurationError(
                "SMTP_USERNAME must be configured with the Gmail or Google Workspace mailbox for Gmail API delivery."
            )
        missing_oauth_fields = [
            field_name
            for field_name, value in [
                ("GOOGLE_OAUTH_CLIENT_ID", resolved_settings.google_oauth_client_id),
                ("GOOGLE_OAUTH_CLIENT_SECRET", resolved_settings.google_oauth_client_secret),
                ("GOOGLE_OAUTH_REFRESH_TOKEN", resolved_settings.google_oauth_refresh_token),
                ("GOOGLE_OAUTH_TOKEN_URL", resolved_settings.google_oauth_token_url),
            ]
            if not value
        ]
        if missing_oauth_fields:
            raise EmailConfigurationError(
                "Missing Google OAuth settings for Gmail API delivery: "
                + ", ".join(missing_oauth_fields)
            )
        return _resolve_sender_settings(
            resolved_settings,
            transport=transport,
            auth_mode="oauth2",
            google_account_type=google_account_type,
        )

    if not resolved_settings.smtp_host.strip():
        raise EmailConfigurationError("SMTP_HOST is not configured")
    if resolved_settings.smtp_port <= 0:
        raise EmailConfigurationError("SMTP_PORT must be greater than 0")
    if resolved_settings.smtp_timeout_seconds <= 0:
        raise EmailConfigurationError("SMTP_TIMEOUT_SECONDS must be greater than 0")
    if resolved_settings.smtp_use_ssl and resolved_settings.smtp_use_tls:
        raise EmailConfigurationError("SMTP_USE_SSL and SMTP_USE_TLS cannot both be enabled")

    auth_mode = _resolve_smtp_auth_mode(resolved_settings)
    if auth_mode in {"password", "xoauth2"} and not (
        resolved_settings.smtp_use_ssl or resolved_settings.smtp_use_tls
    ):
        raise EmailConfigurationError(
            "SMTP authentication must use TLS or SSL. Enable SMTP_USE_TLS or SMTP_USE_SSL."
        )

    if auth_mode == "password":
        if not resolved_settings.smtp_username.strip() or not resolved_settings.smtp_password:
            raise EmailConfigurationError(
                "SMTP_USERNAME and SMTP_PASSWORD must be configured for SMTP_AUTH_MODE=password."
            )
    elif auth_mode == "xoauth2":
        if not _is_google_gmail_host(resolved_settings):
            raise EmailConfigurationError(
                "SMTP_AUTH_MODE=xoauth2 is only implemented for smtp.gmail.com."
            )
        missing_oauth_fields = [
            field_name
            for field_name, value in [
                ("SMTP_USERNAME", resolved_settings.smtp_username.strip()),
                ("GOOGLE_OAUTH_CLIENT_ID", resolved_settings.google_oauth_client_id),
                ("GOOGLE_OAUTH_CLIENT_SECRET", resolved_settings.google_oauth_client_secret),
                ("GOOGLE_OAUTH_REFRESH_TOKEN", resolved_settings.google_oauth_refresh_token),
            ]
            if not value
        ]
        if missing_oauth_fields:
            raise EmailConfigurationError(
                "Missing Google OAuth settings for XOAUTH2: "
                + ", ".join(missing_oauth_fields)
            )
    elif auth_mode == "none" and _is_google_gmail_host(resolved_settings):
        raise EmailConfigurationError(
            "smtp.gmail.com requires authentication. Use SMTP_AUTH_MODE=password or SMTP_AUTH_MODE=xoauth2."
        )
    elif auth_mode == "xoauth2" and _is_google_workspace_relay_host(resolved_settings):
        raise EmailConfigurationError(
            "smtp-relay.gmail.com supports SMTP AUTH or IP-based relay, not XOAUTH2."
        )

    return _resolve_sender_settings(
        resolved_settings,
        transport=transport,
        auth_mode=auth_mode,
        google_account_type=google_account_type,
    )


def validate_email_delivery_on_startup() -> None:
    from . import (
        check_email_delivery_connection,
        get_email_delivery_summary,
        get_settings,
        logger,
    )

    settings = get_settings()
    transport = _normalize_choice(
        settings.email_transport or "disabled",
        ALLOWED_EMAIL_TRANSPORTS,
        "EMAIL_TRANSPORT",
    )

    if transport == "disabled":
        if settings.email_required_on_startup:
            raise EmailConfigurationError(
                "EMAIL_REQUIRED_ON_STARTUP is enabled but EMAIL_TRANSPORT is disabled."
            )
        logger.warning(
            "Outbound email delivery is disabled. Forgot-password, MFA, and onboarding emails will not be sent."
        )
        return

    resolved_delivery = validate_email_delivery_settings(settings)
    for warning in resolved_delivery.warnings:
        logger.warning(warning)

    summary = get_email_delivery_summary(settings)
    logger.info(
        "Email delivery configured: host=%s port=%s auth_mode=%s sender=%s",
        summary["host"],
        summary["port"],
        summary["auth_mode"],
        summary["sender"],
    )

    if settings.email_verify_connection_on_startup:
        check_email_delivery_connection(settings=settings)
        logger.info("Email delivery connection verified during startup.")
