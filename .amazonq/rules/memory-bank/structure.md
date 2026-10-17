# MatheusPersonal - Project Structure

## Directory Layout

```
KeaHubMatheusPersonal/
├── services/                    # All microservices
│   ├── database.py              # Shared SQLAlchemy DB connection (imported by all services)
│   │
│   ├── # --- Commerce Services (original) ---
│   ├── users/                   # Legacy user CRUD (port 8001 in old setup)
│   ├── subscriptions/           # Subscription management
│   ├── orders/                  # Order management
│   ├── payments/                # Legacy generic payment records and admin endpoints
│   ├── coupons/                 # Coupon/discount system
│   ├── leads/                   # Lead capture
│   ├── feedbacks/               # Student feedback
│   │
│   ├── # --- ms-* Services (student area / new architecture) ---
│   ├── ms-auth/                 # JWT auth, login, password reset, email
│   ├── ms-users/                # Student profile + avatar upload
│   ├── ms-workouts/             # Workout templates + student assignments
│   ├── ms-nutrition/            # Nutrition plans
│   ├── ms-progress/             # Progress photos + body measurements
│   ├── ms-dashboard/            # Aggregated student dashboard stats
│   ├── ms-notifications/        # In-app notifications
│   ├── ms-videos/               # Video content (admin)
│   ├── ms-onboarding/           # Student onboarding flow
│   │
│   └── asaas/                   # Asaas payment gateway integration + webhooks
│
├── nginx/                       # Nginx config (local dev reverse proxy)
│   ├── nginx.conf
│   ├── nginx.local.conf/
│   ├── cors.conf
│   └── Dockerfile
│
├── docker-compose.yml           # Production deployment (Traefik + easypanel network)
├── init.sql                     # Database schema initialization
├── migration_*.sql              # Incremental schema migrations
├── validate_template_months.sql # Data validation script
├── Jenkinsfile                  # CI/CD pipeline (main)
├── Jenkinsfile.hostinger        # CI/CD pipeline (Hostinger variant)
├── .env                         # Local environment variables
├── .env.example                 # Environment variable template
├── AREA_ALUNO_API.md            # Student area API documentation
├── JENKINS_SETUP.md             # Jenkins configuration guide
└── MatheusPersonal.postman_collection.json  # API test collection
```

## Each Service Structure
Every microservice follows the same flat layout:
```
services/{service-name}/
├── main.py          # FastAPI app, all routes, models, business logic
├── requirements.txt # Python dependencies
└── Dockerfile       # Container build (FROM python:3.11-slim)
```

## Architectural Patterns

### Microservices via Traefik
- All services run on the `easypanel` Docker network
- Traefik acts as reverse proxy/load balancer with TLS termination
- Each service registers itself via Docker labels
- URL routing: `Host + PathPrefix` rules strip `/api` or `/api/aluno` prefix before forwarding
- All services listen internally on port **8000**

### Shared Database
- Single MySQL 8.0 database (`u549746795_mp`) shared by all services
- `services/database.py` is the shared connection module — copied into each service image at build time
- Connection pooling via SQLAlchemy (`pool_size`, `max_overflow`, `pool_recycle`)
- Services use raw cursor-based queries (not ORM), via `get_db()` → `engine.raw_connection()`

### URL Namespace Convention
| Prefix | Audience | Example |
|--------|----------|---------|
| `/api/{service}` | General / admin | `/api/users`, `/api/coupons` |
| `/api/aluno/{service}` | Student-facing | `/api/aluno/workouts`, `/api/aluno/progress` |
| `/api/admin/{service}` | Admin-only | `/api/admin/workouts`, `/api/admin/videos` |

### Inter-Service Communication
- Direct HTTP calls between services (e.g., `asaas` calls `ms-onboarding` at `http://ms-onboarding-service:8000/onboarding/activate`)
- No message queue — synchronous HTTP only

### Authentication
- JWT tokens issued by `ms-auth` service
- All protected routes validate `Authorization: Bearer <token>` header
- JWT secret shared via `JWT_SECRET` environment variable across all services

### File Storage
- Avatar uploads: `ms-users` service, volume `users_uploads`, served at `/uploads/avatars`
- Progress photos: `ms-progress` service, volume `progress_uploads`, served at `/uploads`
- Files served directly by the service via FastAPI StaticFiles or endpoint

### Payment Routing and Scope
- Public Asaas routes use `/api/asaas/*`; Traefik strips `/api` and forwards to `asaas-service`.
- The Asaas provider webhook must use `https://matheuspersonal.com.br/api/asaas/webhook`.
- No frontend source was found in this repository during the payment flow review; the client side of checkout is not documented or validated here.
- See `.amazonq/rules/memory-bank/payments.md` for the Asaas route map and implementation gaps.
