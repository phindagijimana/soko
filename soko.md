# Soko — requirements for developers and use cases

*Version: 1.0 (aligned to current Soko / Agri Marketplace codebase)*

*Audience: software developers, DevOps, and product owners building or operating the pilot.*

A Markdown version of the same content as [soko.docx](soko.docx).

---

## 1. Purpose of this document

This document captures functional expectations (use cases) and non-functional / engineering requirements so new developers can run, extend, and deploy Soko with confidence. It reflects the pilot design for Rwanda and East Africa: phone-based profiles, listings, orders, trust, and admin support.

## 2. Product summary

Soko is a web-based agricultural marketplace. Guests may browse public listings and reviews. Registered users (farmers and buyers) authenticate with phone and OTP, then perform role-specific actions. Administrators manage verification, support, and read operational metrics. In-app card or mobile payments are not in scope for this pilot; settlement is expected outside the application.

## 3. Actors

- **Guest:** unauthenticated visitor; can browse and read public data.
- **Farmer:** authenticated user with role farmer; can create listings, manage incoming orders, request verification.
- **Buyer:** authenticated user with role buyer; can place orders and submit reviews (subject to business rules).
- **Admin:** user flagged `is_admin`; can access Soko Admin (metrics, verification queue, audit, support tickets).

## 4. Developer requirements

### 4.1 Technology stack

- **Backend:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2, Alembic, Pydantic v2, httpx, pytest.
- **Auth:** phone + OTP, bearer tokens; Twilio (or file/console) for SMS in development.
- **Database:** SQLite for local; PostgreSQL recommended for production with Alembic migrations.
- **Frontend:** React 18, Vite 5, react-router-dom v6, static build for production.
- **Deployment:** static UI can be served from GitHub Pages; API must be hosted on a public HTTPS origin.

### 4.2 Repository layout (expectation)

- `backend/` — FastAPI app (`app/main.py`, models, settings, storage, tests).
- `frontend/` — Vite + React; `public/` for favicon, `.nojekyll`; `dist/` is build output (not committed).
- `infra/` — e.g. Nginx when using Docker Compose.
- `docker-compose.yml` — optional Postgres, API, Nginx (and S3 profile).
- `./soko` — project CLI: install, start, stop, status, restart (local dev).

### 4.3 Local development

- Run `./soko install` then `./soko start` from the repository root (creates venv, installs deps, starts API + Vite).
- **Backend alone:** `cd backend && uvicorn app.main:app --reload --port 2500` (after `pip install -r requirements.txt`).
- **Frontend alone:** `cd frontend && npm run dev` (expects API URL; Vite may use `frontend/.env.development.local` from `./soko start`).
- Run **backend tests:** `cd backend && pytest -q`. **Frontend:** `npm run build` to verify the bundle.

### 4.4 Environment and configuration (production expectations)

- Set `ENVIRONMENT=production`, `DEBUG=false`, and a strong `SECRET_KEY`; never use defaults in public deployments.
- Configure `DATABASE_URL` (PostgreSQL) and run `alembic upgrade head`; set `CREATE_TABLES_ON_STARTUP=false` when the DB is managed only via migrations.
- **ALLOWED_ORIGINS:** must include the exact browser origin of the static site (e.g. `https://<user>.github.io`).
- **TRUSTED_HOSTS:** include the public hostname of the API so `TrustedHostMiddleware` allows requests.
- **SMS:** `SMS_PROVIDER=twilio` with real `AC…` Account SID and valid `TWILIO_*`; test delivery in a staging project first.
- **Storage:** for multi-instance or scale, set `STORAGE_BACKEND=s3` with bucket, keys, and `MEDIA_PUBLIC_BASE_URL` (images must load in the browser).
- **SENTRY_DSN:** optional, for error monitoring; health endpoint reports Sentry state.
- **TLS:** terminate HTTPS at a load balancer or reverse proxy; repository ships HTTP-oriented examples only.
- **CORS:** production uses explicit origins (not `*`); see settings for dev vs production behavior.

### 4.5 Frontend build and hosting

- Vite **base path** must match GitHub project Pages: `basename: import.meta.env.BASE_URL` (e.g. `/soko/`).
- **VITE_API_URL:** set at build time to the public API base URL (no trailing slash); required for a working UI against a remote API.
- **GitHub Pages:** workflow builds frontend and deploys `dist`; include `404.html` = `index.html` for SPA deep links (e.g. `/soko/admin`).
- **Two UI surfaces:** public marketplace at `/`; Soko Admin at `/admin` (admin users only, others redirected to `/`).

### 4.6 API surface (summary for integrators)

The REST API is JSON over HTTPS. Public reads include `GET /listings`, `GET /reviews`, `GET /recommendations`. Write operations require `Authorization: Bearer <token>` except where noted. See OpenAPI (FastAPI) at `/docs` when the server is running.

- **Auth:** `POST /users`, `POST /auth/request-otp`, `POST /auth/verify-otp`, `POST /auth/logout`, `GET /me`
- **Listings & media:** `GET`/`POST /listings`, `POST /images/upload`
- **Orders:** `POST`/`GET /orders`, `PATCH /orders/{id}`
- **Reviews:** `GET`/`POST /reviews`
- **Verification:** `POST /verification/request`; admin `GET`/`PATCH` on `/admin/verification-requests`
- **Support:** `POST`/`GET /support-tickets`, admin `PATCH /admin/support-tickets/{id}`
- **Engagement:** `POST /interactions`, `GET /recommendations`
- **Admin:** `GET /metrics/summary`, `GET /admin/audit-logs`, `GET /admin/users`
- **Health:** `GET /health`, `GET /ready`

### 4.7 Engineering standards

- Run tests before merging critical backend changes; keep domain rules in small modules to preserve readability.
- **Rate limiting:** in-memory for a single instance; plan Redis or edge limits if you scale out horizontally.
- **Audit log** exists for key actions; do not log secrets in plain text responses.

## 5. Use cases to cover (functional)

Each use case should be testable in staging with realistic SMS and a shared database policy.

### UC-01 — Guest browses the marketplace

| Field | Description |
|--------|-------------|
| **Actor** | Guest |
| **Preconditions** | API reachable; optional seed or existing listings |
| **Main flow** | Open site; use search/filters. View recommended and all listings; read public reviews. May record interactions when logged in; guests do not need to sign in to browse. |
| **Success** | User understands offerings and trust signals without an account. |

### UC-02 — User registers a profile

| Field | Description |
|--------|-------------|
| **Actor** | Prospective farmer or buyer |
| **Preconditions** | Valid phone not yet registered; SMS or dev placeholder for OTP |
| **Main flow** | Submit name, phone, role, location on Create profile. Receive confirmation and proceed to OTP flow. |
| **Success** | User record created; can request OTP to sign in. |

### UC-03 — User signs in with phone OTP

| Field | Description |
|--------|-------------|
| **Actor** | Registered user |
| **Preconditions** | OTP service configured; rate limits and lockout rules respected |
| **Main flow** | Request OTP, enter code within expiry. Session token stored client-side. Optional logout invalidates server-side when implemented. |
| **Success** | Authenticated session; `/me` returns role and profile fields. |

### UC-04 — Farmer creates and manages listings

| Field | Description |
|--------|-------------|
| **Actor** | Farmer |
| **Preconditions** | Signed in as farmer |
| **Main flow** | Create listing (crop, quantity, price, location, description, optional image URL and/or file upload). Listings appear in search and market views. Farmer cannot place buyer orders with farmer profile (role guard). |
| **Success** | Listing persisted; media stored per `STORAGE_BACKEND`; farmer can receive orders for own listings. |

### UC-05 — Buyer places and tracks an order

| Field | Description |
|--------|-------------|
| **Actor** | Buyer |
| **Preconditions** | Signed in as buyer; valid listing |
| **Main flow** | Submit order for listing and quantity. Order appears in buyer’s list. Farmer can update status (e.g. accepted, rejected, completed) per business rules. SMS notifications use configured provider in production. |
| **Success** | Order state visible to both parties; review flow can reference completed orders where applicable. |

### UC-06 — Buyer leaves a review

| Field | Description |
|--------|-------------|
| **Actor** | Buyer |
| **Preconditions** | Signed in as buyer; rules on order linkage as implemented |
| **Main flow** | Submit review for a farmer (score, text, optional order id). Review appears in public list and supports trust in recommendations. |
| **Success** | New review stored; public trust signals update. |

### UC-07 — User requests account verification

| Field | Description |
|--------|-------------|
| **Actor** | Farmer (or as implemented) |
| **Preconditions** | Signed in |
| **Main flow** | Submit verification request with document metadata. Request enters pending state for admin review. |
| **Success** | Admin can later approve or reject; user verification flag updates accordingly. |

### UC-08 — User opens a support ticket

| Field | Description |
|--------|-------------|
| **Actor** | Signed-in user |
| **Preconditions** | Valid session |
| **Main flow** | Create ticket with category (general, dispute, abuse, bug), subject, message. User sees their tickets; admin sees all in Soko Admin. |
| **Success** | Ticket stored with status; admin can add notes and change status (in_progress, resolved, closed). |

### UC-09 — Admin uses Soko Admin

| Field | Description |
|--------|-------------|
| **Actor** | Admin (`is_admin`) |
| **Preconditions** | Admin phone configured in `ADMIN_PHONE_NUMBERS`; user promoted or seeded as admin |
| **Main flow** | From public site, follow “Soko Admin” to `/admin`. View metrics, verification queue, audit log, and moderate all support tickets. Return to public site via back link. Non-admins cannot access `/admin` (redirect to `/`). |
| **Success** | Operational visibility and moderation without exposing admin UI to the general marketplace navigation tabs. |

### UC-10 — Listings and recommendations use engagement data

| Field | Description |
|--------|-------------|
| **Actor** | Signed-in user |
| **Preconditions** | Token present |
| **Main flow** | Track views/clicks; recommendations blend trust, recency, location, and behavior per implemented ranking. |
| **Success** | Personalized or ranked experiences improve for active users while guests still see default ranking. |

### UC-11 — System health and readiness

| Field | Description |
|--------|-------------|
| **Actor** | Operator / DevOps |
| **Preconditions** | Service deployed with dependencies (DB, optional S3, SMS) |
| **Main flow** | `GET /health` and `/ready` for probes; optional Sentry enabled based on `SENTRY_DSN`. Backups run per runbook (SQLite or `pg_dump`). |
| **Success** | Team can monitor uptime and data protection expectations. |

## 6. Explicitly out of scope (current pilot)

- In-app or embedded payment collection (e.g. card, MoMo API) — business settlement is out of band.
- Full legal KYC/ID document upload pipeline beyond placeholder references — may be added later with storage and policy.
- Multi-language UI and accessibility audit beyond best-effort (future improvement).

## 7. Traceability to implementation

- **Backend:** `backend/app/main.py`, `models.py`, `settings.py`, auth, storage, SMS.
- **Frontend:** `frontend/src/App.jsx` (routes, marketplace vs Soko Admin), `frontend/src/lib/api.js`.
- **Operations:** `README.md`, `.env.example`, `docker-compose.yml`, `.github/workflows/deploy-github-pages.yml`.
