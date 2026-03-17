# Backend Frontend Auth Onboarding Guide

## Purpose

This guide explains how the frontend should handle login, optional password-change prompts, privileged face onboarding, and first-login credentials after the 2026-03-15 backend changes.

## Main Backend Changes

- new login response field: `password_change_recommended`
- new route: `POST /auth/password-change-prompt/dismiss`
- privileged users with `face_pending` tokens can now access `POST /auth/change-password`
- new onboarding users are no longer forced through password change unless `must_change_password=true`
- `POST /users/` now honors a supplied password or returns `generated_temporary_password`
- `POST /api/school/admin/create-school-it` now honors `school_it_password` or returns `generated_temporary_password`
- protected backend routes now enforce server-side role guards before handler logic runs
- protected backend routes also re-check inactive account and inactive school state on every authenticated request
- deactivating or reactivating a Campus Admin through the admin school-account route now also deactivates or reactivates the whole school

## Frontend Decision Order After Login

Use this order after a successful `POST /login`, `POST /token`, or `POST /auth/mfa/verify` response.

1. If `mfa_required === true`, show the MFA screen and complete `POST /auth/mfa/verify`.
2. If `must_change_password === true`, send the user to the forced change-password screen.
3. If `password_change_recommended === true`, show an optional prompt:
   - `Change password now`
   - `Skip for now`
4. If the user chooses `Change password now`, call `POST /auth/change-password`.
5. If the user chooses `Skip for now`, call `POST /auth/password-change-prompt/dismiss`.
6. After the optional prompt flow finishes, if `token_type === "face_pending"` or `face_verification_pending === true`, continue to privileged face onboarding.
7. If none of the above applies, continue to the normal app destination.

## Meaning Of Login Response Fields

### `must_change_password`

- hard backend gate
- use this for reset-password or security-enforced flows
- if this is `true`, the frontend should not treat password change as optional

### `password_change_recommended`

- optional one-time onboarding prompt
- does not block access by itself
- intended for brand-new onboarding accounts
- becomes `false` after:
  - successful `POST /auth/change-password`
  - successful `POST /auth/password-change-prompt/dismiss`

### `token_type`

- `bearer`: normal access token
- `face_pending`: limited token for privileged onboarding before face verification completes

### `face_verification_required`

- tells the frontend whether the account is part of the privileged face-verification flow

### `face_reference_enrolled`

- `true` if the privileged user already has a saved face reference
- `false` if they still need to register one

### `face_verification_pending`

- `true` means the user still needs to complete the privileged face flow before full access

## Recommended Frontend Flow

### Privileged user first login

1. User logs in.
2. Backend may return:
   - `token_type: "face_pending"`
   - `password_change_recommended: true`
   - `must_change_password: false`
3. Show the optional password prompt.
4. If the user chooses `Change password now`, call `POST /auth/change-password`.
5. If the user chooses `Skip for now`, call `POST /auth/password-change-prompt/dismiss`.
6. Continue to:
   - `GET /auth/security/face-status`
   - `POST /auth/security/face-liveness`
   - `POST /auth/security/face-reference` if no reference exists
   - `POST /auth/security/face-verify` to complete onboarding
7. After face verification succeeds, treat the returned token as the new active session token.

### Normal new user first login

1. User logs in.
2. Backend may return:
   - `password_change_recommended: true`
   - `must_change_password: false`
   - `token_type: "bearer"`
3. Show the optional password prompt.
4. If the user skips, call `POST /auth/password-change-prompt/dismiss`.
5. Continue to the normal dashboard.

### Forced reset flow

1. User logs in with a reset-issued password.
2. Backend returns `must_change_password: true`.
3. Frontend must send the user to `POST /auth/change-password`.
4. Do not show the optional prompt as the main decision in this flow.

## Route Summary For Frontend

### Login and password prompt

- `POST /login`
- `POST /token`
- `POST /auth/mfa/verify`
- `POST /auth/change-password`
- `POST /auth/password-change-prompt/dismiss`

### Privileged face onboarding

- `GET /auth/security/face-status`
- `POST /auth/security/face-liveness`
- `POST /auth/security/face-reference`
- `DELETE /auth/security/face-reference`
- `POST /auth/security/face-verify`

### Student face registration

- `POST /face/register`

Important:
- `/face/register` is for student face registration
- `/auth/security/face-*` is for admin and Campus Admin onboarding or privileged security flows

## Server-Side Role Enforcement Notes

The frontend should still hide protected screens, but the backend now rejects protected route calls early if the session role does not match the route family.

Examples:

- Campus Admin and admin routes such as `/users/*`, `/school-settings/*`, `/api/subscription/*`, and `/api/governance/announcements/monitor` require `admin` or `campus_admin` on the server
- student face registration routes require the `student` role on the server
- governance routes require either:
  - `admin`
  - `campus_admin`
  - `student`
  - or active governance membership for transitional governance users

Frontend rule:

- never assume a hidden menu item is enough protection
- handle `403` responses as expected role-enforcement behavior and route the user to a safe page
- if the backend returns `This account's school is inactive.`, clear the local session and send the user back to login because the school was disabled after the token was issued
- treat the same inactive-school response as valid after either:
  - `PATCH /api/school/admin/{school_id}/status`
  - `PATCH /api/school/admin/school-it-accounts/{user_id}/status`

## Example Login Responses

### Optional prompt plus privileged face onboarding

```json
{
  "access_token": "token-value",
  "token_type": "face_pending",
  "must_change_password": false,
  "password_change_recommended": true,
  "face_verification_required": true,
  "face_reference_enrolled": false,
  "face_verification_pending": true
}
```

### Forced password change

```json
{
  "access_token": "token-value",
  "token_type": "bearer",
  "must_change_password": true,
  "password_change_recommended": false
}
```

### Normal login without prompt

```json
{
  "access_token": "token-value",
  "token_type": "bearer",
  "must_change_password": false,
  "password_change_recommended": false
}
```

## Create-Account Credential Contract

### `POST /users/`

- if the request includes `password`, that exact password becomes the initial login password
- if the request does not include `password`, the backend generates one
- when the backend generates one, the response includes:

```json
{
  "generated_temporary_password": "generated-value"
}
```

### `POST /api/school/admin/create-school-it`

- if the request includes `school_it_password`, that exact password becomes the initial login password
- if the request omits `school_it_password`, the backend generates one
- when the backend generates one, the response includes `generated_temporary_password`

Frontend rule:
- only rely on `generated_temporary_password` when the caller did not supply the password
- if the caller supplied the password, the frontend should use that submitted value as the real login password

## Suggested Frontend Implementation Notes

- keep the login response in state until the optional prompt decision finishes
- if the user skips, call the dismiss endpoint before routing away so the prompt does not reappear next login
- after successful `POST /auth/change-password`, refresh the user flow using the current login response state:
  - privileged user: continue to face onboarding
  - normal user: continue to app
- when `must_change_password=true`, do not offer `Skip for now`
- when `token_type="face_pending"`, do not route directly to the main protected app until face verification finishes

## Manual QA Checklist For Frontend

1. Log in as a new privileged user and confirm the optional password prompt appears.
2. Choose `Change password now` and confirm `POST /auth/change-password` succeeds while the token is still `face_pending`.
3. Log in again as a new privileged user, choose `Skip for now`, and confirm `POST /auth/password-change-prompt/dismiss` succeeds.
4. After skip, confirm the frontend continues to privileged face onboarding.
5. Complete `POST /auth/security/face-verify` and confirm the app stores the final returned token.
6. Log in as a reset-password user and confirm the frontend forces the password-change screen without showing skip as the main path.
7. Create a new user through `POST /users/` without a password and confirm the UI captures `generated_temporary_password`.
8. Create a new user through `POST /users/` with a password and confirm the UI does not expect a generated password.
9. Create a School IT account with and without `school_it_password` and confirm the credential handling matches the request.
10. Deactivate a Campus Admin from the admin school-account route and confirm an already signed-in student is forced back to login after the next protected API call returns `This account's school is inactive.`
11. Reactivate that Campus Admin and confirm a normal student login succeeds again without frontend changes.
