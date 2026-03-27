"""Use: Contains the main backend rules for email building and sending.
Where to use: Use this from routers, workers, or other services when email building and sending logic is needed.
Role: Service package. It splits email configuration, transport, rendering, and use-case senders while preserving the public import path.
"""

from __future__ import annotations

import httpx
import logging
import smtplib
import ssl

from app.core.config import Settings, get_settings
from app.services.password_change_policy import get_welcome_email_password_notice

from .config import (
    ALLOWED_EMAIL_TRANSPORTS,
    ALLOWED_GOOGLE_ACCOUNT_TYPES,
    ALLOWED_SMTP_AUTH_MODES,
    GOOGLE_GMAIL_API_HOST,
    GOOGLE_GMAIL_SMTP_HOST,
    GOOGLE_WORKSPACE_RELAY_HOST,
    TEMPORARY_GMAIL_API_STATUS_CODES,
    TEMPORARY_SMTP_ERROR_CODES,
    EmailConfigurationError,
    EmailConnectionStatus,
    EmailDeliveryError,
    ResolvedEmailDeliverySettings,
    _IPv4PreferredSMTP,
    _IPv4PreferredSMTP_SSL,
    validate_email_delivery_on_startup,
    validate_email_delivery_settings,
)
from .rendering import (
    _send_email,
    build_import_onboarding_email_content,
    build_mfa_code_email_content,
    build_password_reset_email_content,
    build_welcome_email_content,
)
from .transport import (
    _authenticate_smtp_connection,
    _build_gmail_api_headers,
    _build_message,
    _build_smtp_client,
    _decode_smtp_response,
    _encode_message_for_gmail_api,
    _extract_google_api_error_detail,
    _gmail_api_timeout,
    _request_google_oauth_access_token,
    _send_via_gmail_api,
    _verify_gmail_api_sender,
    _wrap_email_delivery_exception,
    check_email_delivery_connection,
    get_email_delivery_summary,
    send_plain_email,
    send_test_email,
    send_transactional_email,
)
from .use_cases import (
    send_import_onboarding_email,
    send_mfa_code_email,
    send_password_reset_email,
    send_welcome_email,
)

logger = logging.getLogger(__name__)

__all__ = [name for name in globals() if not name.startswith("__")]
