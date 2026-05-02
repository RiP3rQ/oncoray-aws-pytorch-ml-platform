# Astro Web E2E Plan

## Setup Direction

- Keep first E2E layer frontend-owned inside `apps/astro-web`.
- Playwright starts frontend only and all default E2E tests must execute without skips.
- Frontend tests mock API responses at the browser network boundary unless a full-stack slice explicitly owns its dependencies.
- Full-stack API checks belong in a separate suite that starts the API, database, model runtimes, and storage explicitly.
  Current smoke coverage implemented now:
- Unauthenticated visit to `/` redirects to `/login`.
- Login happy path reaches dashboard through mocked API responses and renders model tabs.
- Logout succeeds through mocked API response and returns user to `/login`.

## Priority 1

- Invalid login shows invalid-credentials toast on `401`.
- Authenticated dashboard shows current user email and default-selected first model.
- Logout clears session and redirects back to `/login`.
- API-down smoke shows frontend fallback state clearly.
- Register flow uses a mocked accepted signup response and verifies redirect behavior.

## Priority 2

- Register happy path sends signup request and redirects to `/login`.
- Login validation shows inline errors for empty or malformed form data.
- Duplicate registration shows conflict toast on `409`.
- Session-expired `401` from `/model/` clears token and redirects to `/login`.
- Model list failure shows retry state.
- Empty model list shows no-models state.
- Generic network failure during login shows fallback error toast.
- Generic network failure during registration shows fallback error toast.

## Priority 3

- Prediction happy path renders one successful mocked Prediction result.
- Session-expired `401` from prediction request clears token and redirects to `/login`.
- Prediction `413` shows image-size toast.
- Generic prediction failure shows fallback error toast.
- Upload button stays disabled until both model and supported image exist.
- Unsupported file type shows validation message.
- Remove image clears preview, filename, and size metadata.
- Replacing image updates preview and metadata.
- Switching tabs changes active model before prediction request.
- Prediction result card overwrites previous result after new upload.

## Priority 4

- Mobile viewport smoke on login, register, and dashboard shell.
- Keyboard-only login flow works without pointer.
- Drag-and-drop upload path works, not only file chooser.
- Toasts appear once per action and do not duplicate across rerenders.
- Route refresh while authenticated reloads user and models cleanly.

## Later Full-Stack Slice

- Add model-service stub or local runtime container so prediction path becomes real-stack too.
- Add local S3-compatible storage or E2E backend flag for upload persistence.
- If suite grows slow, split into fast real-auth smoke and deeper full-stack prediction tests.
