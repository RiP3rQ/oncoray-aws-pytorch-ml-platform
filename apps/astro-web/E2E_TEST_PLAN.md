# Astro Web E2E Plan

## Setup Direction
- Keep first E2E layer frontend-owned inside `apps/astro-web`.
- Run Playwright against local Astro app on `http://127.0.0.1:4321`.
- Mock API at browser route layer for now. Reason: current task focus frontend setup, repo has no ready full-stack dev orchestration for stable E2E runs.
Current smoke coverage implemented now:
- Unauthenticated visit to `/` redirects to `/login`.
- Login happy path reaches dashboard and renders model tabs.
- Upload happy path returns mocked prediction and populates result card.

## Priority 1
- Register happy path sends signup request and redirects to `/login`.
- Login validation shows inline errors for empty or malformed form data.
- Login failure shows invalid-credentials toast on `401`.
- Duplicate registration shows conflict toast on `409`.
- Authenticated dashboard shows current user email and default-selected first model.
- Logout clears session and redirects back to `/login`.

## Priority 2
- Session-expired `401` from `/model/` clears token and redirects to `/login`.
- Session-expired `401` from prediction request clears token and redirects to `/login`.
- Model list failure shows retry state.
- Empty model list shows no-models state.
- Prediction `413` shows image-size toast.
- Generic prediction failure shows fallback error toast.
- Generic network failure during login shows fallback error toast.
- Generic network failure during registration shows fallback error toast.

## Priority 3
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
- Add separate backend-coupled E2E job after app and API local orchestration becomes stable.
- Keep browser-mocked suite as fast gate.
- Add small full-stack smoke only for auth, model fetch, and prediction contract.
