"""Use: Verify backend email delivery and optionally send a real test message.
Where to use: Run this from `Backend/` when validating SMTP or Gmail API mail setup locally or in production.
Role: Operator script. It checks config, verifies the active mail transport, and sends a smoke-test email.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.email_service import (
    EmailDeliveryError,
    check_email_delivery_connection,
    get_email_delivery_summary,
    send_test_email,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify email connectivity and send a transactional email smoke test."
    )
    parser.add_argument(
        "--recipient",
        required=True,
        help="Recipient address for the test email.",
    )
    parser.add_argument(
        "--subject",
        default="",
        help="Optional subject override for the test email.",
    )
    parser.add_argument(
        "--body",
        default="",
        help="Optional plain-text body override for the test email.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only verify the configured mail transport and sender acceptance; do not send the test email.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("send_test_email")

    try:
        summary = get_email_delivery_summary()
        logger.info(
            "Email config: transport=%s host=%s port=%s auth_mode=%s sender=%s reply_to=%s",
            summary["transport"],
            summary["host"],
            summary["port"],
            summary["auth_mode"],
            summary["sender"],
            summary["reply_to"] or "<none>",
        )
        if summary["warnings"]:
            for warning in summary["warnings"]:
                logger.warning(warning)

        status = check_email_delivery_connection()
        logger.info(
            "Mail connection verified: host=%s port=%s auth_mode=%s sender=%s",
            status.host,
            status.port,
            status.auth_mode,
            status.sender,
        )

        if args.check_only:
            logger.info("Connectivity check completed successfully. No test email was sent.")
            return 0

        timestamp = datetime.now(timezone.utc).isoformat()
        subject = args.subject.strip() or f"VALID8 SMTP smoke test {timestamp}"
        body = args.body.strip() or (
            "This is a real VALID8 transactional-email smoke test.\n\n"
            f"UTC timestamp: {timestamp}\n"
            "If you received this message, the backend connected to the configured mail transport "
            "and completed a full send."
        )
        send_test_email(
            recipient_email=args.recipient.strip(),
            subject=subject,
            body=body,
        )
        logger.info("Test email accepted for delivery to %s", args.recipient.strip())
        return 0
    except EmailDeliveryError as exc:
        logger.error("Email delivery test failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
