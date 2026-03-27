# Backend Google Email Delivery Guide

## Purpose

This guide documents the production-ready Google mail delivery setup for VALID8 transactional emails such as forgot-password approvals, MFA codes, onboarding emails, and generic notifications.

## Stack Context

- backend framework: FastAPI
- runtime mailer package: `Backend/app/services/email_service/`
  - `config.py`
  - `transport.py`
  - `rendering.py`
  - `use_cases.py`
- supported Google transports:
  - Gmail API over HTTPS with OAuth refresh token
  - `smtp.gmail.com` with App Password
  - `smtp.gmail.com` with XOAUTH2
  - `smtp-relay.gmail.com` for Google Workspace SMTP relay

## Current Decision Logic

The backend now chooses the sender path based on the configured transport and sender account type:

- if `EMAIL_TRANSPORT=gmail_api`, the backend refreshes a Google OAuth access token and sends through the Gmail API over HTTPS
- if `SMTP_HOST=smtp.gmail.com` and `SMTP_USERNAME` is a personal Gmail address such as `user@gmail.com`, the backend treats the account as `personal`
- if a personal Gmail account tries to send as `no-reply@your-domain`, the backend falls back to the authenticated Gmail address because personal Gmail cannot reliably send as an arbitrary custom-domain sender
- if `SMTP_HOST=smtp.gmail.com` and the sender is a Google Workspace mailbox or alias, the backend allows a branded sender only when `SMTP_GOOGLE_ALLOW_CUSTOM_FROM=true`
- if `SMTP_HOST=smtp-relay.gmail.com`, the backend supports Google Workspace SMTP relay with `SMTP_AUTH_MODE=none` or `SMTP_AUTH_MODE=password`

## Recommended Deployment Choice

### Railway Or Any Host With Restricted SMTP Egress

Use Gmail API delivery over HTTPS:

- `EMAIL_TRANSPORT=gmail_api`
- `SMTP_USERNAME=<gmail-or-workspace-mailbox>`
- `SMTP_FROM_EMAIL=<same mailbox or verified send-as alias>`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`

This is the recommended path for the current Railway deployment because live Gmail SMTP delivery still times out from that host, while Railway supports outbound HTTPS.

## Recommended Approach By Account Type

### Personal Gmail

Use `smtp.gmail.com` with:

- `SMTP_AUTH_MODE=password`
- a Google App Password
- `SMTP_USERNAME` equal to the Gmail address
- `SMTP_FROM_EMAIL` left blank or equal to the Gmail address

This is the safest supported fallback when you do not have Google Workspace for your custom domain.

Important:

- do not use the normal Gmail password
- App Passwords require 2-Step Verification on the Google account
- the backend will fall back to the authenticated Gmail address if `SMTP_FROM_EMAIL` is set to an unsupported custom sender
- keep `SMTP_REPLY_TO` separate if replies should go to another inbox
- if SMTP is blocked or unreliable on your host, use Gmail API transport instead of SMTP for the same Gmail account

### Google Workspace Mailbox Or Alias

If you control the domain and want a real sender such as `no-reply@your-domain`, the simplest path is:

1. create a real Google Workspace mailbox `no-reply@your-domain`, or create an alias on a real mailbox that is allowed to send as `no-reply@your-domain`
2. enable 2-Step Verification on the authenticating mailbox
3. create an App Password for that mailbox
4. set:
   - `SMTP_HOST=smtp.gmail.com`
   - `SMTP_PORT=587`
   - `SMTP_USE_TLS=true`
   - `SMTP_AUTH_MODE=password`
   - `SMTP_USERNAME=no-reply@your-domain`
   - `SMTP_PASSWORD=<google-app-password>`
   - `SMTP_FROM_EMAIL=no-reply@your-domain`
   - `SMTP_GOOGLE_ACCOUNT_TYPE=workspace`
   - `SMTP_GOOGLE_ALLOW_CUSTOM_FROM=true`

This is the best option when you want the sender identity to be the mailbox itself and the application volume is moderate.

### Google Workspace SMTP Relay

Use Google Workspace SMTP relay when:

- the app runs from a stable server environment
- you want domain-based no-reply senders such as `no-reply@your-domain`
- you prefer relay-style server mail delivery over mailbox-authenticated SMTP
- you want to allow application-generated mail from addresses in your domain without binding the app to one user mailbox

Set:

- `SMTP_HOST=smtp-relay.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USE_TLS=true`
- `SMTP_AUTH_MODE=none` for IP-authenticated relay, or `password` if you explicitly use SMTP AUTH in the relay rule
- `SMTP_FROM_EMAIL=no-reply@your-domain`
- `SMTP_GOOGLE_ACCOUNT_TYPE=workspace`
- `SMTP_GOOGLE_ALLOW_CUSTOM_FROM=true`

This is usually more appropriate than `smtp.gmail.com` when the sender is a domain-level application identity instead of a user mailbox.

### Google XOAUTH2

The backend also supports `SMTP_AUTH_MODE=xoauth2` on `smtp.gmail.com`.

Use XOAUTH2 when:

- your security policy forbids App Passwords
- you already manage Google OAuth refresh tokens securely
- you want token-based authentication to Google SMTP

Required variables:

- `SMTP_AUTH_MODE=xoauth2`
- `SMTP_USERNAME=<google-account-or-workspace-mailbox>`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GOOGLE_OAUTH_TOKEN_URL=https://oauth2.googleapis.com/token`

The OAuth client used for SMTP should request offline access and the `https://mail.google.com/` scope.

### Gmail API Over HTTPS

Use Gmail API transport when:

- your host can reach Google HTTPS endpoints but SMTP is blocked or times out
- you want Google-supported OAuth delivery without relying on port `587` or `465`
- you are deploying on Railway Hobby, Trial, or Free where outbound SMTP is not available

Set:

- `EMAIL_TRANSPORT=gmail_api`
- `SMTP_USERNAME=<gmail-or-workspace-mailbox>`
- `SMTP_FROM_EMAIL=<same mailbox or verified send-as alias>`
- `SMTP_REPLY_TO=<optional>`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GOOGLE_OAUTH_AUTH_URL=https://accounts.google.com/o/oauth2/v2/auth`
- `GOOGLE_OAUTH_TOKEN_URL=https://oauth2.googleapis.com/token`
- `GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/gmail.settings.basic`
- `GOOGLE_GMAIL_API_BASE_URL=https://gmail.googleapis.com/gmail/v1`

The backend uses `gmail.send` to deliver mail and `gmail.settings.basic` to verify a custom send-as alias during connectivity checks.

## Exact Google Setup Steps

### Gmail API Setup For Railway Or Other SMTP-Restricted Hosts

1. Open Google Cloud Console.
2. Create or select the Google Cloud project that will own the mail credentials.
3. Enable the Gmail API for that project.
4. Configure the OAuth consent screen.
5. Add the Gmail API scopes:
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/gmail.settings.basic`
6. Create an OAuth client. A Desktop App client is the simplest option for the refresh-token helper script in this repo.
7. Run:

`python Backend/scripts/generate_google_oauth_refresh_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET`

8. Sign in with the Gmail or Google Workspace mailbox that should send mail.
9. Copy the printed values into the deployment environment:
   - `EMAIL_TRANSPORT=gmail_api`
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`
   - `GOOGLE_OAUTH_REFRESH_TOKEN`
10. Redeploy the backend.
11. Run the backend smoke test:

`python Backend/scripts/send_test_email.py --recipient your-address@example.com`

### Personal Gmail App Password Setup

1. Sign in to the Gmail account that will send mail.
2. Turn on 2-Step Verification in the Google Account security settings.
3. Open the Google Account App Passwords page.
4. Generate a new App Password for this application.
5. Copy the generated 16-character App Password immediately. Google only shows it once.
6. Put that value in `SMTP_PASSWORD`.
7. Set `SMTP_USERNAME` to the full Gmail address.
8. Keep `SMTP_FROM_EMAIL` blank or equal to that Gmail address.
9. Optionally set `SMTP_REPLY_TO` to a support mailbox.

### Google Workspace Mailbox Or Alias Setup For `no-reply@your-domain`

1. In Google Admin, create the mailbox `no-reply@your-domain`, or add `no-reply@your-domain` as a sendable alias on the mailbox that will authenticate.
2. Confirm the mailbox can sign in to Gmail and can send as the alias if you used an alias instead of a dedicated mailbox.
3. Turn on 2-Step Verification for the authenticating mailbox.
4. Generate an App Password for that mailbox.
5. Set `SMTP_GOOGLE_ACCOUNT_TYPE=workspace`.
6. Set `SMTP_GOOGLE_ALLOW_CUSTOM_FROM=true`.
7. Set `SMTP_FROM_EMAIL=no-reply@your-domain`.
8. Run the backend email smoke test before enabling production traffic.

### Google Workspace SMTP Relay Setup For `no-reply@your-domain`

1. Open Google Admin.
2. Go to `Apps -> Google Workspace -> Gmail -> Routing`.
3. Open `SMTP relay service`.
4. Create or edit a relay rule.
5. Choose an allowed sender policy:
   - `Only addresses in my domains` is the safest common choice for app mail
   - avoid `Any addresses` unless you explicitly need it and understand the abuse risk
6. Choose authentication:
   - `Only accept mail from the specified IP addresses` if your server has a stable public IP
   - optionally also enable `Require SMTP Authentication` if you want Google to identify the sending domain through SMTP AUTH
7. Enable `Require TLS encryption` if your application supports TLS. VALID8 does.
8. Save the rule and wait for the change to propagate.
9. Point the backend to `smtp-relay.gmail.com` on port `587`.
10. Set `SMTP_FROM_EMAIL=no-reply@your-domain`.
11. Run the backend email smoke test.

## Environment Variables

The backend loads `.env` values from either:

- `Backend/.env`
- repo-root `.env`

Use `Backend/.env.example` as the reference file.

Key mail variables:

- `EMAIL_TRANSPORT`
- `EMAIL_REQUIRED_ON_STARTUP`
- `EMAIL_VERIFY_CONNECTION_ON_STARTUP`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_TIMEOUT_SECONDS`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`
- `SMTP_EHLO_NAME`
- `SMTP_PREFER_IPV4`
- `SMTP_AUTH_MODE`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_NAME`
- `SMTP_FROM_EMAIL`
- `SMTP_REPLY_TO`
- `SMTP_GOOGLE_ACCOUNT_TYPE`
- `SMTP_GOOGLE_ALLOW_CUSTOM_FROM`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GOOGLE_OAUTH_AUTH_URL`
- `GOOGLE_OAUTH_TOKEN_URL`
- `GOOGLE_OAUTH_SCOPES`
- `GOOGLE_GMAIL_API_BASE_URL`

## Backend Behavior

The mailer now provides:

- reusable generic `send_transactional_email(...)`
- forgot-password email through `send_password_reset_email(...)`
- HTML plus plain-text transactional bodies
- startup validation via FastAPI lifespan
- optional connection verification during startup with `EMAIL_VERIFY_CONNECTION_ON_STARTUP=true`
- standalone smoke testing through `Backend/scripts/send_test_email.py`
- standalone refresh-token generation through `Backend/scripts/generate_google_oauth_refresh_token.py`

## Local Testing

From `Backend/`:

1. confirm the resolved config:

`python -c "from app.services.email_service import get_email_delivery_summary; print(get_email_delivery_summary())"`

2. verify the configured mail transport without sending:

`python scripts/send_test_email.py --recipient your-address@example.com --check-only`

3. send a real transactional smoke test:

`python scripts/send_test_email.py --recipient your-address@example.com`

## Production Testing

1. set the real mail variables in the deployment environment
2. deploy the backend
3. enable `EMAIL_VERIFY_CONNECTION_ON_STARTUP=true` temporarily if you want the service to fail fast on bad mail config
4. run:

`python scripts/send_test_email.py --recipient your-address@example.com`

5. test an actual forgot-password approval flow through the app

### Railway-specific note

If Railway or another cloud runtime resolves `smtp.gmail.com` to IPv6 first and mail sends fail with `Network is unreachable`, set:

- `SMTP_PREFER_IPV4=true`

This makes the backend open SMTP sockets using IPv4 addresses only while keeping the same Gmail host, sender, and auth settings. After confirming the fix, enable:

- `EMAIL_VERIFY_CONNECTION_ON_STARTUP=true`

so the service fails clearly on future deploys if Gmail SMTP becomes unreachable again.

If SMTP still fails or your Railway plan does not allow outbound SMTP, switch to:

- `EMAIL_TRANSPORT=gmail_api`

and use the Gmail API OAuth setup above.

## Common Google Failure Cases

### Authentication failed

Cause:

- normal Gmail password used instead of App Password
- 2-Step Verification is not enabled
- App Password was revoked after changing the Google password
- XOAUTH2 refresh token is missing, expired, or revoked

Fix:

- use a fresh App Password or valid OAuth credentials

### Refresh token expires or stops working

Cause:

- the Google refresh token was revoked
- the OAuth client was deleted or rotated
- the OAuth consent screen is still in Testing mode and the refresh token expired

Fix:

- generate a new refresh token with `Backend/scripts/generate_google_oauth_refresh_token.py`
- move the OAuth consent screen to Production before long-term use
- update `GOOGLE_OAUTH_REFRESH_TOKEN` in the deployment environment

### Custom no-reply sender rejected

Cause:

- personal Gmail account trying to send as `no-reply@your-domain`
- Workspace alias exists but the mailbox is not configured to send as that address
- Workspace relay rule does not allow the configured sender

Fix:

- for personal Gmail, use the Gmail address as sender and keep `SMTP_REPLY_TO` separate
- for Workspace, create a real mailbox or alias and set `SMTP_GOOGLE_ALLOW_CUSTOM_FROM=true`
- for relay, adjust the SMTP relay allowed-sender policy

### Temporary SMTP failures or rate limiting

Cause:

- Google throttling
- relay quotas
- temporary downstream delivery issues

Fix:

- retry later
- reduce burst size
- for higher-volume domain mail, prefer Google Workspace SMTP relay

### Gmail API permission errors

Cause:

- the refresh token was created without `gmail.send`
- a custom sender is configured but the token lacks `gmail.settings.basic`

Fix:

- reauthorize with:
  - `https://www.googleapis.com/auth/gmail.send`
  - `https://www.googleapis.com/auth/gmail.settings.basic`
- if you do not need a custom sender, set `SMTP_FROM_EMAIL` to the authenticated mailbox
