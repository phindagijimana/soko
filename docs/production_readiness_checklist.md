# Production Readiness Checklist

## Implemented in repo
- Environment-based settings and `.env.example`
- Configurable CORS and trusted host settings
- OTP expiry, resend cooldown, attempt counting, and lockout
- Token expiry and logout
- Public browse / authenticated action gating
- Role-based authorization for farmers, buyers, and admins
- Local image upload validation including MIME and basic signature checks
- Verification request workflow and admin review
- Review flow linked to completed orders
- Support ticket workflow for disputes and abuse reports
- Audit logging
- Health, readiness, and admin metrics endpoints
- In-memory rate limiting middleware
- SQLite backup helper
- Alembic scaffolding for migrations
- Navy and white production-style frontend theme

## External or placeholder by necessity
- Live SMS provider credentials and delivery callbacks
- Hosted PostgreSQL with managed backups
- HTTPS, domain, reverse proxy, WAF, and deployment network controls
- Centralized monitoring, error aggregation, and alerting
- Cloud object storage and malware scanning for uploads
- Legal documents and public support process

## Tests completed
- Backend automated API tests: auth, listings, orders, reviews, admin actions, support tickets, logout, public browse
- Frontend production build

## Recommended launch sequence
1. Set production environment variables
2. Deploy backend and frontend to staging
3. Switch to PostgreSQL and generate real migrations
4. Wire live SMS provider
5. Run pilot with real farmers and buyers
6. Fix pilot issues
7. Add monitoring and managed backups in production
8. Launch public beta
