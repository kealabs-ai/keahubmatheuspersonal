# MatheusPersonal - Technology Stack

## Core Languages & Runtime
- **Python 3.11** (all services use `python:3.11-slim` Docker base image)
- **SQL** (MySQL 8.0 — schema in `init.sql`, migrations in `migration_*.sql`)

## Frameworks & Libraries

### Web Framework
- **FastAPI 0.104.1** — all services; async-capable, auto Swagger docs at `/docs`
- **Uvicorn 0.24.0** — ASGI server, runs on port 8000 inside each container

### Database
- **SQLAlchemy 2.0.36** — connection pooling engine only (not ORM); raw cursor queries via `engine.raw_connection()`
- **mysql-connector-python 8.2.0** — MySQL driver

### Auth & Security
- **PyJWT 2.8.0** — JWT token creation and validation (used in: ms-auth, ms-users, ms-workouts, ms-progress, ms-notifications, ms-dashboard, ms-nutrition, ms-onboarding, ms-videos, subscriptions, orders, payments, coupons)
- **bcrypt 4.1.1** — password hashing (used in: ms-auth, ms-users)

### Data Validation
- **Pydantic 2.5.0** — request/response models in all services

### HTTP Client
- **httpx 0.25.2** — async HTTP client for inter-service calls and external APIs (used in: asaas)

### Email (ms-auth)
- Python stdlib `smtplib` + `email.mime` — SMTP email sending via Hostinger

## Infrastructure & DevOps

### Containerization
- **Docker** — each service has its own `Dockerfile`
- **Docker Compose** — orchestration for production deployment on Hostinger/EasyPanel

### Reverse Proxy
- **Traefik** — TLS termination, path-based routing, CORS headers via middleware labels
- Network: `easypanel` (external Docker network managed by EasyPanel)

### CI/CD
- **Jenkins** — two pipeline files:
  - `Jenkinsfile` — main pipeline
  - `Jenkinsfile.hostinger` — Hostinger-specific deployment

### Hosting
- **Hostinger VPS** (`srv1023256.hstgr.cloud`) running EasyPanel
- **MySQL** hosted at `srv1078.hstgr.io:3306`

## Environment Configuration

All services receive config via environment variables:

| Variable | Purpose |
|----------|---------|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | MySQL connection |
| `DB_POOL_SIZE` | SQLAlchemy pool size (default: 5) |
| `JWT_SECRET` | Shared JWT signing secret |
| `SMTP_HOST/PORT/SSL/USER/PASS` | Email (ms-auth only) |
| `FRONTEND_URL` | Password reset redirect (ms-auth only) |
| `ASAAS_API_KEY`, `ASAAS_BASE_URL` | Asaas payment API (asaas service only) |
| `BASE_URL` | Public server URL for file serving (ms-users, ms-progress) |
| `UPLOAD_DIR` | File upload path inside container |

## Development Commands

```bash
# Start all services (production compose)
docker-compose up -d

# Build and push a specific service image
docker build -t matheuspersonal/{service}:latest ./services/{service}/
docker push matheuspersonal/{service}:latest

# View logs
docker-compose logs -f {service}-service

# Access Swagger docs (local, if running individually)
# Each service on its own port — see docker-compose for port mappings
```

## Per-Service Dependency Matrix

| Service | bcrypt | PyJWT | httpx | Notes |
|---------|--------|-------|-------|-------|
| ms-auth | ✓ | ✓ | — | + smtplib |
| ms-users | ✓ | ✓ | — | avatar upload |
| ms-workouts | — | ✓ | — | |
| ms-progress | — | ✓ | — | photo upload |
| ms-nutrition | — | ✓ | — | |
| ms-dashboard | — | ✓ | — | |
| ms-notifications | — | ✓ | — | |
| ms-videos | — | ✓ | — | |
| ms-onboarding | — | ✓ | — | |
| asaas | — | — | ✓ | Asaas API calls |
| leads | — | — | — | public endpoint |
| feedbacks | — | ✓ | — | |
| coupons | — | ✓ | — | |
| orders | — | ✓ | — | |
| payments | — | ✓ | — | |
| subscriptions | — | ✓ | — | |
| users (legacy) | — | ✓ | — | |
