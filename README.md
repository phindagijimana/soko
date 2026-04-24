# Agri Marketplace

Pilot-ready agricultural marketplace for Rwanda and East Africa. Guests can browse listings, while farmers and buyers must create phone-based profiles before posting harvest, placing orders, leaving reviews, or requesting verification.

## What is implemented
- Public browsing for listings and reviews
- Phone-based profile creation and OTP sign-in
- OTP expiry, cooldown, lockout, and token expiry
- Farmer-only listing creation
- Buyer-only order placement
- Farmer order status updates
- Review flow tied to completed orders
- Verification request workflow
- Admin review endpoints and metrics summary
- Support ticket workflow for disputes, abuse, bugs, and general issues
- Local or S3-compatible image storage (`STORAGE_BACKEND`)
- Audit logging, health checks, readiness checks, and in-memory rate limiting
- Navy blue and white frontend theme

## Still environment-specific (configure for production)
- **SMS:** Set `SMS_PROVIDER=twilio` with real `TWILIO_*` values (Account SID must start with `AC`). Until then, `file` / `console` or Twilio-with-placeholder creds log to `SMS_LOG_PATH`. Live delivery uses Twilio’s REST API (`httpx`).
- **Database:** `DATABASE_URL` (SQLite or PostgreSQL). With Docker, `CREATE_TABLES_ON_STARTUP=false` and run `alembic upgrade head` (see `backend/Dockerfile`).
- **Backups:** `python scripts/backup_database.py` (SQLite copy or `pg_dump`).
- **Object storage:** `STORAGE_BACKEND=local` (default) or `s3` with `S3_BUCKET_NAME`, `MEDIA_PUBLIC_BASE_URL`, and optional `AWS_ENDPOINT_URL` (MinIO). See `.env.example`.
- **Monitoring:** optional `SENTRY_DSN` (initializes `sentry-sdk` on startup). `/health` reports `sentry: true/false`.
- **HTTPS / TLS:** terminate at your cloud load balancer or add certificates in front of Nginx; repo ships HTTP reverse proxy only.

Seed marketplace listings stay enabled via `ENABLE_SEED_DATA` (only when the user table is empty).

## Docker (Postgres + API + Nginx)

From the repository root (requires Docker):

```bash
docker compose up --build
```

- **Postgres** on host port `5432`, **API** on `8000`, **Nginx** on `8080` (proxies to the API).
- Migrations run on container start; uploads use a named volume (`api_uploads`).
- **Optional S3/MinIO stack:** `docker compose --profile s3 up --build` starts MinIO and an **`api-s3`** service on host port `8001` (configure browser/CORS for your environment).

## Local dev (CLI)

From the repository root:

```bash
./soko install
./soko start
./soko stop
```

This creates `backend/.venv`, runs `pip install` and `npm install`, then starts the API on the first free port from **2500–2550** (preferring **2500**) and the Vite dev server on the first free port from **2000–2050** (preferring **2000**). Ports are saved in `.soko/backend.port` and `.soko/frontend.port`, and `frontend/.env.development.local` is written so the UI calls the correct API URL. Pin or adjust ports with `SOKO_BACKEND_PORT`, `SOKO_BACKEND_PORT_RANGE_LO` / `SOKO_BACKEND_PORT_RANGE_HI`, `SOKO_FRONTEND_PORT`, and `SOKO_FRONTEND_PORT_RANGE_LO` / `SOKO_FRONTEND_PORT_RANGE_HI`. Set `SOKO_NPM_REGISTRY` if npm should not use the public registry.

**If the page will not load:** use the URL printed by `./soko start`, or open `http://127.0.0.1:` plus the number in `.soko/frontend.port` (not port **5173** unless you started Vite yourself that way). After editing `vite.config.js`, run `./soko restart`.

## Local backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 2500
```

## Local frontend
```bash
cd frontend
npm install
npm run build
npm run dev
```

## Tests run for this package
### Backend
```bash
cd backend
pytest -q
```

### Frontend build
```bash
cd frontend
npm run build
```

## Migrations
Alembic includes `0001_initial_placeholder` and `6de51aeafae6_full_schema` (creates all tables from SQLAlchemy models). For new changes:
```bash
cd backend
PYTHONPATH=. alembic revision --autogenerate -m "describe change"
PYTHONPATH=. alembic upgrade head
```
Set `CREATE_TABLES_ON_STARTUP=false` when the database is managed only via Alembic (e.g. Docker).

## Backup script
SQLite (file copy) or PostgreSQL (`pg_dump`):
```bash
cd backend
# optional: DATABASE_URL=... BACKUP_DIR=./backups
python scripts/backup_database.py
```
For PostgreSQL, install client tools so `pg_dump` is on `PATH`. Use your host’s managed backups in production if preferred.

## Suggested next real-world step
Deploy to staging, wire a real SMS provider, switch to PostgreSQL, and run a controlled pilot with 10 farmers and 5 buyers.


## Engineering notes

- The backend keeps domain rules in small helper modules so route handlers stay readable.
- The frontend intentionally keeps guest browsing open while gating actions behind profile + OTP sign-in.
- SMS is implemented for **file**, **console**, and **Twilio REST** (when credentials are non-placeholder); order/verification SMS failures are logged without rolling back orders.
- **Uploads** use **local disk** or **S3-compatible** storage; optional **Sentry** via `SENTRY_DSN`.
- **Docker Compose** runs Postgres, migrates with Alembic, and fronts the API with **Nginx** (HTTP).
- Build artifacts, local databases, uploads, and node_modules should not be committed; see `.gitignore`.
