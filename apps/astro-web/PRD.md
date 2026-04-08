# OncoRay Frontend — Authentication & Prediction PRD

## Overview

Adding authenticated access, model selection, and image prediction to the OncoRay Astro frontend.

---

## Completed Work

### ✅ Phase 1: Auth Infrastructure

- **`src/lib/auth.ts`** — JWT token storage (`getToken`, `setToken`, `removeToken`, `getStoredToken`, `isAuthenticated`), `User` interface, `AuthContext`, `useAuthContext` hook
- **`src/lib/api.ts`** — Full API client with automatic JWT header injection, 401 interceptor (clear token → redirect `/login`), typed endpoints: `login`, `signup`, `logout`, `getMe`, `getModels`, `getModel`, `predict`
- **`src/hooks/useAuth.tsx`** — `AuthProvider` with `login`, `register`, `logout`, `fetchUser`, `isLoading` + `isAuthenticated` state

### ✅ Dependencies & shadcn Setup

All packages installed in `package.json`:

- `zod` ^4.3.6, `@hookform/resolvers` ^5.2.2, `react-hook-form` ^7.72.1, `swr` ^2.4.1, `react-dropzone` ^15.0.0, `sonner` ^2.0.7
- `class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`, `radix-ui`
- shadcn initialized (`components.json`, `new-york` style, `cssVariables: true`)
- shadcn components installed: `tabs.tsx`, `sonner.tsx`
- shadcn CSS variables wired in `global.css` (light + dark mode, mapped to OncoRay theme)
- `src/lib/utils.ts` — `cn()` utility

### ✅ Existing Components (UI-only, no API wiring)

- **`src/components/ImageDropzone.tsx`** — drag/drop UI, file preview, validation (PNG/JPG/WEBP), no API submission yet

---

## Remaining Work

### Phase 2: Registration Page

#### 2.1 Create `src/components/RegisterForm.tsx`

- React island component replacing static form in `register.astro`
- Zod schema: `{ email: z.string().email(), password: z.string().min(8).max(128) }`
- react-hook-form with `@hookform/resolvers/zod`
- Inline validation errors below each field
- Submit calls `register()` from `useAuthContext` hook
- On success: sonner toast ("Verification email sent. Check your inbox."), redirect to `/login`
- On 409 error: toast ("Email already registered")

#### 2.2 Update `src/pages/register.astro`

- Replace static `<form>` with `<RegisterForm client:load />`
- Keep existing layout, styling, and sidebar copy sections
- Must wrap in `<AuthProvider>` so form can access auth context

### Phase 3: Login Page

#### 3.1 Create `src/components/LoginForm.tsx`

- Same zod validation (email + password)
- react-hook-form with zod resolver
- Submit calls `login()` from `useAuthContext` hook
- "Keep this workstation signed in" checkbox → controls `persistent` flag for token storage (`localStorage` vs `sessionStorage`)
- On success: redirect to `/`
- On 401 error: toast ("Invalid credentials")

#### 3.2 Update `src/pages/login.astro`

- Replace static `<form>` with `<LoginForm client:load />`
- Keep existing layout, styling, and sidebar copy sections
- Must wrap in `<AuthProvider>`

### Phase 4: Route Protection

#### 4.1 Create `src/components/AuthGuard.tsx`

- Checks auth state on mount
- If no token or token invalid (401 from `/user/me`): redirect to `/register`
- Show loading spinner while checking
- Wrap authenticated pages with this component

#### 4.2 Update `src/pages/index.astro`

- Replace entire static landing page with interactive dashboard wrapped in `<AuthGuard client:load />`
- Navigation shows user email + logout button when authenticated
- Layout: AuthGuard → ModelSelector → ImageDropzone → PredictionResult

### Phase 5: Main Dashboard (Authenticated)

#### 5.1 Create `src/components/ModelSelector.tsx`

- shadcn `Tabs` component
- `useSWR('/model/')` to fetch available models via `api.getModels()`
- Each tab shows model name + description
- Selected model ID stored in component state, passed to dropzone as prop

#### 5.2 Update `src/components/ImageDropzone.tsx`

- Accept `modelId` prop
- Accept `onPrediction` callback prop
- On file select: call `api.predict(modelId, file)` with FormData
- Show loading state during upload
- On success: call `onPrediction(result)` and toast "Prediction complete."
- On error: toast appropriate error message
- Keep existing drag/drop UI, file validation, and preview

#### 5.3 Create `src/components/PredictionResult.tsx`

- Props: `prediction: PredictionResponse | null`
- Show prediction label and confidence score (formatted as %)
- Color-coded confidence: green > 80%, yellow > 50%, red < 50%
- Display image S3 key for reference
- Match existing `.glass-card` styling

#### 5.4 Create `src/components/Dashboard.tsx` (composition component)

- Orchestrates ModelSelector + ImageDropzone + PredictionResult
- Manages selected model ID and prediction result state
- Wraps everything in AuthGuard context

#### 5.5 Update `src/pages/index.astro`

- Import and render `<Dashboard client:load />`
- Remove all static landing page content (hero, queue, report cards)
- Keep Layout wrapper and topbar structure

### Phase 6: Toast & Layout Integration

#### 6.1 Update `src/layouts/Layout.astro`

- Add `<Toaster />` from sonner (bottom-right, dark theme)
- Add `<AuthProvider>` wrapper around `<slot />` so all pages have auth context
- Import `@/components/ui/sonner` and `@/hooks/useAuth`

#### 6.2 Toast triggers (already wired in useAuth.tsx)

- Registration success: "Verification email sent. Check your inbox." ✅
- Login welcome: "Welcome back!" ✅
- Logout: "Successfully logged out." ✅
- 401 interceptor: "Session expired. Please log in again." ✅ (in api.ts)
- Prediction complete: needs wiring in ImageDropzone update
- Network error: needs catch in form components

---

## File Structure (Remaining)

```
apps/astro-web/src/
├── components/
│   ├── AuthGuard.tsx          (NEW)
│   ├── Dashboard.tsx          (NEW - composition)
│   ├── LoginForm.tsx          (NEW)
│   ├── RegisterForm.tsx       (NEW)
│   ├── ModelSelector.tsx      (NEW)
│   ├── PredictionResult.tsx   (NEW)
│   ├── ImageDropzone.tsx      (UPDATE - add modelId, onPrediction, API call)
│   └── ui/                    (DONE)
├── hooks/
│   └── useAuth.tsx            (DONE)
├── lib/
│   ├── api.ts                 (DONE)
│   ├── auth.ts                (DONE)
│   └── utils.ts               (DONE)
├── layouts/
│   └── Layout.astro           (UPDATE - add Toaster + AuthProvider)
└── pages/
    ├── index.astro            (UPDATE - replace landing with dashboard)
    ├── login.astro            (UPDATE - use LoginForm island)
    └── register.astro         (UPDATE - use RegisterForm island)
```

---

## Auth Flow

```
[Unauthenticated] → /register (via AuthGuard redirect)
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
| ------------------------ | ---------------------- | ---------------------------------- |
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

- Astro islands architecture: use `client:load` for interactive components
- Preserve existing dark medical theme and CSS variables — new components use existing design tokens
- `AuthProvider` must wrap all pages in Layout.astro so auth state is available everywhere
- `useAuth` is exposed via `useAuthContext()` hook from `src/lib/auth.ts`
- Current `useAuth.tsx` exports `AuthProvider` component, not a hook — components access auth via `useAuthContext()`
- API client (`api.ts`) already handles 401s by clearing token + redirecting to `/login`
- zod v4 is installed (^4.3.6) — use v4 API (`z.string().email()`, not `z.string().email({})` etc.)
