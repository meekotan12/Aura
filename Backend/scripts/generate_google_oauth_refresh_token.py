"""Use: Generate a Google OAuth refresh token for Gmail API delivery.
Where to use: Run this from `Backend/` when switching the mail transport to Gmail API.
Role: Operator script. It opens a local OAuth flow, exchanges the authorization code, and prints env-ready values.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings


@dataclass
class OAuthResult:
    code: str | None = None
    error: str | None = None
    error_description: str | None = None
    state: str | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    oauth_result: OAuthResult = OAuthResult()
    completion_event = threading.Event()

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        self.__class__.oauth_result = OAuthResult(
            code=(query.get("code") or [None])[0],
            error=(query.get("error") or [None])[0],
            error_description=(query.get("error_description") or [None])[0],
            state=(query.get("state") or [None])[0],
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if self.__class__.oauth_result.code:
            body = (
                "<html><body><h2>Google authorization complete.</h2>"
                "<p>You can close this window and return to the terminal.</p></body></html>"
            )
        else:
            body = (
                "<html><body><h2>Google authorization failed.</h2>"
                "<p>Return to the terminal for details.</p></body></html>"
            )
        self.wfile.write(body.encode("utf-8"))
        self.__class__.completion_event.set()

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - stdlib signature
        return


def _build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Generate a Google OAuth refresh token for VALID8 Gmail API delivery."
    )
    parser.add_argument("--client-id", default=settings.google_oauth_client_id, help="Google OAuth client ID.")
    parser.add_argument(
        "--client-secret",
        default=settings.google_oauth_client_secret,
        help="Google OAuth client secret.",
    )
    parser.add_argument(
        "--auth-url",
        default=settings.google_oauth_auth_url,
        help="Google OAuth authorization endpoint.",
    )
    parser.add_argument(
        "--token-url",
        default=settings.google_oauth_token_url,
        help="Google OAuth token endpoint.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        default=[],
        help="OAuth scope to request. Repeat for multiple scopes. Defaults to config scopes.",
    )
    parser.add_argument(
        "--login-hint",
        default=settings.smtp_username,
        help="Optional Google account email to prefill during authorization.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Local callback port. Must be allowed by your OAuth client redirect settings if you use a web client.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Local callback host for the browser redirect.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not try to open the authorization URL automatically.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the resulting credentials as JSON.",
    )
    return parser


def _normalize_scopes(args_scopes: list[str], default_scopes: list[str]) -> list[str]:
    if args_scopes:
        return args_scopes
    return default_scopes


def _build_authorization_url(
    *,
    auth_url: str,
    client_id: str,
    redirect_uri: str,
    scopes: list[str],
    state: str,
    login_hint: str,
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    if login_hint:
        params["login_hint"] = login_hint
    return f"{auth_url}?{urlencode(params)}"


def _exchange_code_for_tokens(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, object]:
    payload = {
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if client_secret:
        payload["client_secret"] = client_secret

    response = httpx.post(token_url, data=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.client_id:
        parser.error("Google OAuth client ID is required. Pass --client-id or set GOOGLE_OAUTH_CLIENT_ID.")

    scopes = _normalize_scopes(args.scopes, get_settings().google_oauth_scopes)
    redirect_uri = f"http://{args.host}:{args.port}/oauth2/callback"
    state = secrets.token_urlsafe(24)

    _CallbackHandler.oauth_result = OAuthResult()
    _CallbackHandler.completion_event.clear()

    server = HTTPServer((args.host, args.port), _CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    authorization_url = _build_authorization_url(
        auth_url=args.auth_url,
        client_id=args.client_id,
        redirect_uri=redirect_uri,
        scopes=scopes,
        state=state,
        login_hint=args.login_hint.strip(),
    )

    print("Open this URL in your browser to authorize Gmail API access:\n")
    print(authorization_url)
    print()
    if not args.no_browser:
        webbrowser.open(authorization_url)

    print("Waiting for Google authorization callback...")
    completed = _CallbackHandler.completion_event.wait(timeout=300)
    server.shutdown()
    server.server_close()

    if not completed:
        print("Timed out waiting for the authorization callback.", file=sys.stderr)
        return 1

    result = _CallbackHandler.oauth_result
    if result.state != state:
        print("OAuth state mismatch. Aborting.", file=sys.stderr)
        return 1
    if result.error:
        description = result.error_description or result.error
        print(f"Google authorization failed: {description}", file=sys.stderr)
        return 1
    if not result.code:
        print("Google did not return an authorization code.", file=sys.stderr)
        return 1

    try:
        token_payload = _exchange_code_for_tokens(
            token_url=args.token_url,
            client_id=args.client_id,
            client_secret=args.client_secret,
            code=result.code,
            redirect_uri=redirect_uri,
        )
    except httpx.HTTPError as exc:
        print(f"Token exchange failed: {exc}", file=sys.stderr)
        return 1

    refresh_token = token_payload.get("refresh_token")
    if not refresh_token:
        print(
            "Google did not return a refresh token. Re-run the script with prompt=consent and revoke prior access if needed.",
            file=sys.stderr,
        )
        return 1

    output = {
        "GOOGLE_OAUTH_CLIENT_ID": args.client_id,
        "GOOGLE_OAUTH_CLIENT_SECRET": args.client_secret,
        "GOOGLE_OAUTH_REFRESH_TOKEN": refresh_token,
        "GOOGLE_OAUTH_SCOPES": scopes,
        "EMAIL_TRANSPORT": "gmail_api",
    }

    if args.json:
        print(json.dumps(output, indent=2))
        return 0

    print("OAuth refresh token generated successfully.\n")
    for key, value in output.items():
        if isinstance(value, list):
            print(f"{key}={' '.join(value)}")
        else:
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
