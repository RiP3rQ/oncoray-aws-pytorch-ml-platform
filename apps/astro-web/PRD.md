# OncoRay Frontend — Authentication & Prediction PRD

## Overview

This document outlines the implementation plan for adding authenticated access, model selection, and image prediction
functionality to the OncoRay Astro frontend. Currently the application has static pages with no client-side
interactivity or API integration.

---

## Current State

### Frontend Stack

- **Framework**: Astro 6.1.3 + @astrojs/react 5.0.2
- **Styling**: Tailwind CSS 4.2.2 with custom CSS variables (dark medical theme, cyan/warm accents)
- **Fonts**: Manrope (body), Syne (headings)
- **Pages**: `index.astro`, `login.astro`, `register.astro` — all static HTML forms
- **Components**: `ImageDropzone.tsx` — drag/drop UI but no API submission

### Backend API Endpoints

| Method | Path                        | Purpose                                                       |
|--------|-----------------------------|---------------------------------------------------------------|
| POST   | `/user/signup`              | Register new user (body: `UserCreate`)                        |
| POST   | `/user/token`               | Login, get JWT (form: username/password, returns `TokenData`) |
| GET    | `/user/verify`              | Verify email (query: `token`)                                 |
| GET    | `/user/logout`              | Logout, blacklist JWT                                         |
| GET    | `/user/me`                  | Get current user (requires JWT)                               |
| GET    | `/model/`                   | List all models                                               |
| GET    | `/model/{model_id}`         | Get single model                                              |
| POST   | `/model/{model_id}/predict` | Upload image, get prediction (multipart form)                 |

### Backend Schemas

```python
# UserCreate
{email: EmailStr, password: str(8 - 128 chars)}

# UserRead
{id: UUID, email: EmailStr, created_at: datetime, updated_at: datetime}

# TokenData
{access_token: str, token_type: str}

# ModelRead
{id: UUID, name: str, description: str, version: str, created_at: datetime, updated_at: datetime}

# PredictionResponse
{model_id: UUID, prediction: str, confidence: float(0 - 1), image_s3_key: str}
```

---

## Required Packages

Add these to `apps/astro-web/package.json`:

```json
{
  "dependencies": {
    "zod": "^3.23.8",
    "@hookform/resolvers": "^3.9.1",
    "react-hook-form": "^7.54.2",
    "swr": "^2.3.0",
    "react-dropzone": "^14.3.5",
    "sonner": "^1.7.1"
  }
}
```

### Why These Packages

| Package               | Purpose                                                                                        |
|-----------------------|------------------------------------------------------------------------------------------------|
| `zod`                 | Schema validation for forms — matches backend validation rules (email format, password length) |
| `react-hook-form`     | Form state management — performant, minimal re-renders, zod integration via resolvers          |
| `@hookform/resolvers` | Bridge between react-hook-form and zod schemas                                                 |
| `swr`                 | Data fetching with caching, revalidation — for model list fetching                             |
| `react-dropzone`      | Enhanced file dropzone — better than current custom implementation, handles edge cases         |
| `sonner`              | Toast notifications — lightweight, shadcn-compatible, zero-config setup                        |

### shadcn/ui Components

Initialize shadcn in the astro-web app (requires tailwind config adjustment for shadcn):

- `npx shadcn@latest init`
- `npx shadcn@latest add toast`
- `npx shadcn@latest add tabs`

These will add `@radix-ui/react-tabs` and `@radix-ui/react-toast` to dependencies.

---

## Implementation Plan

### Phase 1: Auth Infrastructure

#### 1.1 Auth Context & Storage

Create `src/lib/auth.ts`:

- JWT token storage in `localStorage`
- Auth context provider with React Context
- Token getter/setter/remover helpers
- `isAuthenticated` boolean derived from token presence

#### 1.2 API Client

Create `src/lib/api.ts`:

- Base fetch wrapper with automatic JWT header injection (`Authorization: Bearer <token>`)
- 401 response interceptor → clear token, redirect to `/login`
- Typed response helpers for each endpoint

#### 1.3 Auth Hook

Create `src/hooks/useAuth.ts`:

- `useAuth()` hook returning `{ user, login, logout, register, isAuthenticated, isLoading }`
- `login(email, password)` — POST to `/user/token`, store token, fetch user profile
- `register(email, password)` — POST to `/user/signup`, show toast, redirect to login
- `logout()` — GET `/user/logout`, clear token, redirect to login
- `fetchUser()` — GET `/user/me` to hydrate user state on mount

### Phase 2: Registration Page

#### 2.1 Registration Form Component

Create `src/components/RegisterForm.tsx`:

- Convert `register.astro` from static form to React island
- Zod schema: `{ email: z.string().email(), password: z.string().min(8).max(128) }`
- react-hook-form with `@hookform/resolvers/zod`
- Inline validation errors below each field
- Submit calls `register()` from useAuth hook
- On success: show sonner toast ("Check your email for verification"), redirect to `/login`

#### 2.2 Update register.astro

- Replace static `<form>` with `<RegisterForm client:load />`
- Keep existing layout and styling

### Phase 3: Login Page

#### 3.1 Login Form Component

Create `src/components/LoginForm.tsx`:

- Same zod validation as register (email + password)
- react-hook-form with zod resolver
- Submit calls `login()` from useAuth hook
- On success: redirect to `/`
- On 401 error: show sonner toast ("Invalid credentials")

#### 3.2 Update login.astro

- Replace static `<form>` with `<LoginForm client:load />`
- Keep existing layout and styling

### Phase 4: Route Protection

#### 4.1 Auth Guard Component

Create `src/components/AuthGuard.tsx`:

- Checks auth state on mount
- If no token or token invalid (401 from `/user/me`): redirect to `/register`
- Show loading spinner while checking
- Wrap authenticated pages with this component

#### 4.2 Update index.astro

- Wrap main content with `<AuthGuard client:load />`
- Navigation shows user email + logout button when authenticated

### Phase 5: Main Dashboard (Authenticated)

#### 5.1 Model Selector (Tabs)

Create `src/components/ModelSelector.tsx`:

- shadcn `Tabs` component
- `useSWR('/model/')` to fetch available models
- Each tab shows model name + description
- Selected model ID stored in component state, passed to dropzone

#### 5.2 Prediction Dropzone

Update `src/components/ImageDropzone.tsx`:

- Accept `modelId` prop
- On file select: POST to `/model/{modelId}/predict` with FormData
- Show upload progress/loading state
- Display prediction result below dropzone

#### 5.3 Prediction Result Display

Create `src/components/PredictionResult.tsx`:

- Show prediction label, confidence score (formatted as %)
- Color-coded confidence (green > 80%, yellow > 50%, red < 50%)
- Display image S3 key for reference
- Matches existing card styling (`.glass-card`)

#### 5.4 Update index.astro

- Replace static content with interactive components
- Layout: Tabs → Dropzone → Prediction Result
- All wrapped in AuthGuard

### Phase 6: Toast Integration

#### 6.1 Toaster Setup

- Add `<Toaster />` from sonner to `Layout.astro`
- Position: bottom-right
- Match existing theme colors

#### 6.2 Toast Triggers

- Registration success: "Verification email sent. Check your inbox."
- Login error: "Invalid email or password."
- Logout: "Successfully logged out."
- Prediction complete: "Prediction complete."
- 401 errors: "Session expired. Please log in again."

---

## File Structure

```
apps/astro-web/src/
├── components/
│   ├── AuthGuard.tsx          (NEW)
│   ├── LoginForm.tsx          (NEW)
│   ├── RegisterForm.tsx       (NEW)
│   ├── ModelSelector.tsx      (NEW)
│   ├── PredictionResult.tsx   (NEW)
│   ├── ImageDropzone.tsx      (UPDATE - add API submission)
│   └── Welcome.astro          (EXISTING)
├── hooks/
│   └── useAuth.ts             (NEW)
├── lib/
│   ├── api.ts                 (NEW)
│   └── auth.ts                (NEW)
├── layouts/
│   └── Layout.astro           (UPDATE - add Toaster)
└── pages/
    ├── index.astro            (UPDATE - add AuthGuard, interactive components)
    ├── login.astro            (UPDATE - use LoginForm)
    └── register.astro         (UPDATE - use RegisterForm)
```

---

## Auth Flow

```
[Unauthenticated] → /register
       ↓
[Register Form] → POST /user/signup → Toast("Check email") → /login
       ↓
[Login Form] → POST /user/token → Store JWT → /
       ↓
[Dashboard] → GET /user/me (hydrate) → Show tabs + dropzone
       ↓
[Upload Image] → POST /model/{id}/predict → Show result
       ↓
[Logout] → GET /user/logout → Clear JWT → /login
       ↓
[401 Anywhere] → Clear JWT → /login (via api.ts interceptor)
```

---

## Error Handling

| Scenario                 | Handler                | User Feedback                      |
|--------------------------|------------------------|------------------------------------|
| Invalid form input       | zod (client-side)      | Inline error below field           |
| Registration email taken | API 409                | Toast: "Email already registered"  |
| Invalid login            | API 401                | Toast: "Invalid credentials"       |
| Token expired            | API 401 on any request | Auto-logout + redirect to /login   |
| Network error            | fetch catch            | Toast: "Network error. Try again." |
| Image too large          | API 413                | Toast: "Image exceeds 2 MB limit"  |

---

## Verification Checklist

- [ ] Unauthenticated users redirected to `/register`
- [ ] Registration form validates email format + password length
- [ ] Toast appears after successful registration
- [ ] Redirect to `/login` after registration
- [ ] Login form validates with same rules
- [ ] JWT stored after successful login
- [ ] JWT attached to all API requests
- [ ] 401 responses trigger logout + redirect
- [ ] Model tabs fetch and display available models
- [ ] Image upload sends to correct model endpoint
- [ ] Prediction result displayed below dropzone
- [ ] Logout clears token and redirects

---

## Notes

- The existing `ImageDropzone.tsx` already has drag/drop UI but no API integration. We will enhance it rather than
  replace it.
- Astro islands architecture: use `client:load` for interactive components (forms, tabs, dropzone) since they need
  immediate hydration.
- The dark medical theme and existing CSS variables should be preserved — all new components must use the existing
  design tokens.
- shadcn components will need to be configured for the dark theme variables already in `global.css`.
