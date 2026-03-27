"""Transport helpers for the email service package."""

from __future__ import annotations

import base64
from urllib.parse import quote

from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core.config import Settings

from .config import (
    TEMPORARY_GMAIL_API_STATUS_CODES,
    TEMPORARY_SMTP_ERROR_CODES,
    EmailConnectionStatus,
    EmailDeliveryError,
)


def _build_smtp_client(settings: Settings):
    from . import _IPv4PreferredSMTP, _IPv4PreferredSMTP_SSL, smtplib, ssl

    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    if settings.smtp_prefer_ipv4:
        smtp_class = _IPv4PreferredSMTP_SSL if settings.smtp_use_ssl else _IPv4PreferredSMTP

    if settings.smtp_use_ssl:
        return smtp_class(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
            context=ssl.create_default_context(),
            local_hostname=settings.smtp_ehlo_name or None,
        )
    return smtp_class(
        settings.smtp_host,
        settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
        local_hostname=settings.smtp_ehlo_name or None,
    )


def _request_google_oauth_access_token(settings: Settings) -> str:
    from . import httpx

    try:
        response = httpx.post(
            settings.google_oauth_token_url,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": settings.google_oauth_refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=settings.smtp_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text.strip()
        detail = body[:300] if body else exc.response.reason_phrase
        if exc.response.status_code == 400 and "invalid_grant" in body.lower():
            raise EmailDeliveryError(
                "Google OAuth refresh token is invalid, expired, or revoked. "
                "Generate a new refresh token and update GOOGLE_OAUTH_REFRESH_TOKEN."
            ) from exc
        raise EmailDeliveryError(
            f"Failed to refresh the Google OAuth access token: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise EmailDeliveryError(
            "Could not reach the Google OAuth token endpoint. Check outbound network access and GOOGLE_OAUTH_TOKEN_URL."
        ) from exc

    access_token = response.json().get("access_token")
    if not access_token:
        raise EmailDeliveryError(
            "Google OAuth token response did not include an access_token."
        )
    return access_token


def _authenticate_smtp_connection(
    smtp,
    settings: Settings,
    *,
    auth_mode: str,
) -> None:
    from . import _request_google_oauth_access_token, smtplib, ssl

    if settings.smtp_use_tls and not settings.smtp_use_ssl:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()

    if auth_mode == "password":
        smtp.login(settings.smtp_username, settings.smtp_password)
        return

    if auth_mode == "xoauth2":
        access_token = _request_google_oauth_access_token(settings)
        xoauth2_payload = base64.b64encode(
            f"user={settings.smtp_username}\x01auth=Bearer {access_token}\x01\x01".encode("utf-8")
        ).decode("ascii")
        code, response = smtp.docmd("AUTH", f"XOAUTH2 {xoauth2_payload}")
        if code != 235:
            raise smtplib.SMTPAuthenticationError(code, response)


def _decode_smtp_response(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _extract_google_api_error_detail(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (response.text or response.reason_phrase or "").strip()

    error_payload = payload.get("error")
    if isinstance(error_payload, dict):
        message = (error_payload.get("message") or "").strip()
        status = (error_payload.get("status") or "").strip()
        if message and status:
            return f"{status}: {message}"
        return message or status or (response.reason_phrase or "").strip()
    if isinstance(error_payload, str):
        return error_payload.strip()
    return (response.text or response.reason_phrase or "").strip()


def _build_gmail_api_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _gmail_api_timeout(settings: Settings) -> float:
    return float(settings.smtp_timeout_seconds)


def _verify_gmail_api_sender(
    *,
    settings: Settings,
    resolved_delivery,
    access_token: str,
) -> None:
    from . import httpx
    from .config import _normalize_email

    normalized_username = _normalize_email(settings.smtp_username, "SMTP_USERNAME", allow_blank=True)
    if resolved_delivery.from_email == normalized_username:
        return

    send_as_url = (
        settings.google_gmail_api_base_url.rstrip("/")
        + "/users/me/settings/sendAs/"
        + quote(resolved_delivery.from_email, safe="@")
    )
    try:
        response = httpx.get(
            send_as_url,
            headers=_build_gmail_api_headers(access_token),
            timeout=_gmail_api_timeout(settings),
        )
    except httpx.HTTPError as exc:
        raise EmailDeliveryError(
            "Could not reach the Gmail API send-as settings endpoint. Check outbound HTTPS access."
        ) from exc

    detail = _extract_google_api_error_detail(response)
    if response.status_code == 200:
        send_as = response.json()
        is_primary = bool(send_as.get("isPrimary"))
        verification_status = (send_as.get("verificationStatus") or "").strip().lower()
        if is_primary or verification_status in {"accepted", "verified"}:
            return
        raise EmailDeliveryError(
            "Gmail API found the configured sender address, but it is not verified yet. "
            "Verify the send-as alias in Gmail settings before using it."
        )

    if response.status_code == 403 and "scope" in detail.lower():
        raise EmailDeliveryError(
            "The Google OAuth token cannot verify the configured custom sender because it lacks "
            "the Gmail settings scope. Reauthorize with "
            "https://www.googleapis.com/auth/gmail.settings.basic or use the authenticated mailbox as the sender."
        )

    if response.status_code == 404:
        raise EmailDeliveryError(
            "Gmail API does not recognize the configured sender address. "
            "Set SMTP_FROM_EMAIL to the authenticated mailbox or configure this address as a verified Gmail send-as alias first."
        )

    if response.status_code in TEMPORARY_GMAIL_API_STATUS_CODES:
        raise EmailDeliveryError(f"Temporary Gmail API sender-verification failure: {detail}")

    raise EmailDeliveryError(f"Gmail API sender verification failed: {detail}")


def _encode_message_for_gmail_api(msg: EmailMessage) -> str:
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


def _send_via_gmail_api(
    *,
    settings: Settings,
    resolved_delivery,
    msg: EmailMessage,
    recipient_email: str,
) -> None:
    from . import _request_google_oauth_access_token, httpx

    access_token = _request_google_oauth_access_token(settings)
    send_url = settings.google_gmail_api_base_url.rstrip("/") + "/users/me/messages/send"
    payload = {"raw": _encode_message_for_gmail_api(msg)}

    try:
        response = httpx.post(
            send_url,
            headers=_build_gmail_api_headers(access_token),
            json=payload,
            timeout=_gmail_api_timeout(settings),
        )
    except httpx.TimeoutException as exc:
        raise EmailDeliveryError(
            "Timed out while calling the Gmail API. Check outbound HTTPS access from the deployment host."
        ) from exc
    except httpx.HTTPError as exc:
        raise EmailDeliveryError(
            "Could not reach the Gmail API send endpoint. Check outbound HTTPS access from the deployment host."
        ) from exc

    if response.status_code == 200:
        return

    detail = _extract_google_api_error_detail(response)
    detail_lower = detail.lower()
    if response.status_code == 400 and (
        "from header" in detail_lower
        or "invalid argument" in detail_lower
        or "bad request" in detail_lower
    ):
        raise EmailDeliveryError(
            "Gmail API rejected the configured sender address. "
            "Use the authenticated mailbox as SMTP_FROM_EMAIL or configure the custom sender as a verified Gmail send-as alias."
        )
    if response.status_code == 401:
        raise EmailDeliveryError(
            "Google OAuth access token was rejected by the Gmail API. Reauthorize and update the refresh token."
        )
    if response.status_code == 403:
        if "insufficient permission" in detail_lower or "scope" in detail_lower:
            raise EmailDeliveryError(
                "The Google OAuth token does not include the required Gmail API permissions. "
                "Reauthorize with https://www.googleapis.com/auth/gmail.send."
            )
        raise EmailDeliveryError(f"Gmail API request was forbidden: {detail}")
    if response.status_code in TEMPORARY_GMAIL_API_STATUS_CODES:
        raise EmailDeliveryError(
            f"Temporary Gmail API failure ({response.status_code}). Retry later: {detail}"
        )
    raise EmailDeliveryError(
        f"Gmail API send failed with status {response.status_code}: {detail or response.reason_phrase}"
    )


def _wrap_email_delivery_exception(
    exc: Exception,
    *,
    settings: Settings,
    auth_mode: str,
    sender_email: str,
) -> EmailDeliveryError:
    from . import smtplib
    from .config import _is_google_gmail_host, _is_google_workspace_relay_host

    if isinstance(exc, EmailDeliveryError):
        return exc

    if isinstance(exc, smtplib.SMTPAuthenticationError):
        if _is_google_gmail_host(settings) or _is_google_workspace_relay_host(settings):
            if auth_mode == "password":
                return EmailDeliveryError(
                    "Google SMTP authentication failed. Do not use the normal account password. "
                    "Use a Google App Password with 2-Step Verification enabled, or switch to SMTP_AUTH_MODE=xoauth2."
                )
            if auth_mode == "xoauth2":
                return EmailDeliveryError(
                    "Google XOAUTH2 authentication failed. Check GOOGLE_OAUTH_CLIENT_ID, "
                    "GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REFRESH_TOKEN, and confirm the refresh token is still valid."
                )
        return EmailDeliveryError(
            f"SMTP authentication failed: {_decode_smtp_response(exc.smtp_error)}"
        )

    if isinstance(exc, smtplib.SMTPSenderRefused):
        return EmailDeliveryError(
            "SMTP rejected the configured sender address "
            f"{sender_email}. If you are using personal Gmail, the sender must be the authenticated Gmail address "
            "or a verified Gmail alias. For a true no-reply@your-domain sender, configure a Google Workspace mailbox, "
            "alias, or SMTP relay first."
        )

    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        refused = ", ".join(sorted(exc.recipients.keys()))
        return EmailDeliveryError(f"SMTP rejected the recipient address: {refused}")

    if isinstance(exc, smtplib.SMTPConnectError):
        return EmailDeliveryError(
            f"Could not connect to the SMTP server: {_decode_smtp_response(exc.smtp_error)}"
        )

    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return EmailDeliveryError(
            "SMTP server disconnected unexpectedly. Check network access, TLS mode, and Google relay settings."
        )

    if isinstance(exc, smtplib.SMTPDataError):
        detail = _decode_smtp_response(exc.smtp_error)
        if exc.smtp_code in TEMPORARY_SMTP_ERROR_CODES:
            return EmailDeliveryError(
                f"Temporary SMTP failure ({exc.smtp_code}). Google or the relay asked the app to retry later: {detail}"
            )
        return EmailDeliveryError(f"SMTP refused the message data ({exc.smtp_code}): {detail}")

    if isinstance(exc, smtplib.SMTPResponseException):
        detail = _decode_smtp_response(exc.smtp_error)
        if exc.smtp_code in TEMPORARY_SMTP_ERROR_CODES:
            return EmailDeliveryError(
                f"Temporary SMTP failure ({exc.smtp_code}). Retry later: {detail}"
            )
        return EmailDeliveryError(f"SMTP error ({exc.smtp_code}): {detail}")

    return EmailDeliveryError(str(exc))


def _build_message(
    *,
    resolved_delivery,
    recipient_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    reply_to: str | None = None,
) -> EmailMessage:
    from .config import _normalize_runtime_email

    recipient = _normalize_runtime_email(recipient_email, "recipient_email")
    effective_reply_to = (
        _normalize_runtime_email(reply_to, "reply_to")
        if reply_to is not None
        else resolved_delivery.reply_to
    )
    if not subject.strip():
        raise EmailDeliveryError("Email subject cannot be blank.")
    if not text_body.strip():
        raise EmailDeliveryError("Email body cannot be blank.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = resolved_delivery.from_header
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=resolved_delivery.from_email.split("@", 1)[-1])
    if effective_reply_to:
        msg["Reply-To"] = effective_reply_to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    return msg


def send_transactional_email(
    *,
    recipient_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    reply_to: str | None = None,
) -> None:
    from . import (
        _authenticate_smtp_connection,
        _build_smtp_client,
        _send_via_gmail_api,
        _wrap_email_delivery_exception,
        get_settings,
        logger,
        validate_email_delivery_settings,
    )

    settings = get_settings()
    resolved_delivery = validate_email_delivery_settings(settings)

    for warning in resolved_delivery.warnings:
        logger.warning(warning)

    msg = _build_message(
        resolved_delivery=resolved_delivery,
        recipient_email=recipient_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        reply_to=reply_to,
    )

    try:
        if resolved_delivery.transport == "gmail_api":
            _send_via_gmail_api(
                settings=settings,
                resolved_delivery=resolved_delivery,
                msg=msg,
                recipient_email=recipient_email,
            )
            return

        with _build_smtp_client(settings) as smtp:
            _authenticate_smtp_connection(
                smtp,
                settings,
                auth_mode=resolved_delivery.auth_mode,
            )
            from .config import _normalize_runtime_email

            smtp.send_message(
                msg,
                from_addr=resolved_delivery.from_email,
                to_addrs=[_normalize_runtime_email(recipient_email, "recipient_email")],
            )
    except Exception as exc:
        raise _wrap_email_delivery_exception(
            exc,
            settings=settings,
            auth_mode=resolved_delivery.auth_mode,
            sender_email=resolved_delivery.from_email,
        ) from exc


def send_plain_email(
    *,
    recipient_email: str,
    subject: str,
    body: str,
) -> None:
    send_transactional_email(
        recipient_email=recipient_email,
        subject=subject,
        text_body=body,
    )


def check_email_delivery_connection(
    *,
    settings: Settings | None = None,
    verify_sender: bool = True,
) -> EmailConnectionStatus:
    from . import (
        _authenticate_smtp_connection,
        _build_smtp_client,
        _request_google_oauth_access_token,
        _verify_gmail_api_sender,
        get_settings,
        logger,
        validate_email_delivery_settings,
    )
    from .config import _gmail_api_host

    resolved_settings = settings or get_settings()
    resolved_delivery = validate_email_delivery_settings(resolved_settings)

    for warning in resolved_delivery.warnings:
        logger.warning(warning)

    if resolved_delivery.transport == "gmail_api":
        access_token = _request_google_oauth_access_token(resolved_settings)
        if verify_sender:
            _verify_gmail_api_sender(
                settings=resolved_settings,
                resolved_delivery=resolved_delivery,
                access_token=access_token,
            )
        return EmailConnectionStatus(
            host=_gmail_api_host(resolved_settings),
            port=443,
            transport=resolved_delivery.transport,
            auth_mode=resolved_delivery.auth_mode,
            sender=resolved_delivery.from_email,
            reply_to=resolved_delivery.reply_to,
            warnings=resolved_delivery.warnings,
        )

    try:
        with _build_smtp_client(resolved_settings) as smtp:
            _authenticate_smtp_connection(
                smtp,
                resolved_settings,
                auth_mode=resolved_delivery.auth_mode,
            )
            code, response = smtp.noop()
            if code >= 400:
                raise EmailDeliveryError(
                    f"SMTP NOOP failed after authentication ({code}): {_decode_smtp_response(response)}"
                )

            if verify_sender:
                from . import smtplib

                code, response = smtp.mail(resolved_delivery.from_email)
                if code >= 400:
                    raise smtplib.SMTPSenderRefused(code, response, resolved_delivery.from_email)
                smtp.rset()
    except Exception as exc:
        raise _wrap_email_delivery_exception(
            exc,
            settings=resolved_settings,
            auth_mode=resolved_delivery.auth_mode,
            sender_email=resolved_delivery.from_email,
        ) from exc

    return EmailConnectionStatus(
        host=resolved_settings.smtp_host,
        port=resolved_settings.smtp_port,
        transport=resolved_delivery.transport,
        auth_mode=resolved_delivery.auth_mode,
        sender=resolved_delivery.from_email,
        reply_to=resolved_delivery.reply_to,
        warnings=resolved_delivery.warnings,
    )


def get_email_delivery_summary(settings: Settings | None = None) -> dict[str, object]:
    from . import get_settings, validate_email_delivery_settings
    from .config import _gmail_api_host

    resolved_settings = settings or get_settings()
    resolved_delivery = validate_email_delivery_settings(resolved_settings)
    host = resolved_settings.smtp_host
    port = resolved_settings.smtp_port
    if resolved_delivery.transport == "gmail_api":
        host = _gmail_api_host(resolved_settings)
        port = 443
    return {
        "transport": resolved_delivery.transport,
        "host": host,
        "port": port,
        "auth_mode": resolved_delivery.auth_mode,
        "sender": resolved_delivery.from_email,
        "reply_to": resolved_delivery.reply_to,
        "google_account_type": resolved_delivery.google_account_type,
        "warnings": list(resolved_delivery.warnings),
    }


def send_test_email(
    *,
    recipient_email: str,
    subject: str | None = None,
    body: str | None = None,
) -> None:
    resolved_subject = subject or "VALID8 SMTP connectivity test"
    resolved_body = body or (
        "This is a production-style SMTP smoke test from VALID8.\n\n"
        "If you received this email, the backend authenticated to the configured SMTP server "
        "and completed a real message delivery attempt."
    )
    send_transactional_email(
        recipient_email=recipient_email,
        subject=resolved_subject,
        text_body=resolved_body,
        html_body=(
            "<p>This is a production-style SMTP smoke test from <strong>VALID8</strong>.</p>"
            "<p>If you received this email, the backend authenticated to the configured SMTP server "
            "and completed a real message delivery attempt.</p>"
        ),
    )
