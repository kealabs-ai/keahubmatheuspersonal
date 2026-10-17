# MatheusPersonal - Development Guidelines

## Service Structure Pattern

Every service is a single `main.py` file. The standard layout order is:
1. Imports
2. `sys.path.append('..')` + `from database import get_db`
3. App instantiation + CORS middleware
4. Module-level constants from `os.getenv()`
5. Auth helper functions (`get_user_id`, `require_admin`)
6. Pydantic models (grouped by resource)
7. Helper functions
8. Route handlers (grouped by resource with section comments)

```python
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys, os, jwt
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
```

## Authentication Pattern

All protected services define these two functions verbatim — copy them as-is:

```python
def get_user_id(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(401, "Token inválido")


def require_admin(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload["sub"]
        role    = payload.get("role", "student")
    except Exception:
        raise HTTPException(401, "Token inválido")
    if role not in ("admin", "trainer"):
        raise HTTPException(403, "Acesso restrito")
    return user_id
```

- Use `get_user_id` for student-facing routes
- Use `require_admin` for admin/trainer-only routes
- Always declare as `authorization: str = Header(...)` in route signature

## Database Access Pattern

Always use `get_db()` for raw connections. The standard pattern:

```python
# With try/finally (preferred for write operations)
conn = get_db()
cursor = conn.cursor(dictionary=True)  # use dictionary=True for SELECT
try:
    cursor.execute("SELECT ...", (param,))
    row = cursor.fetchone()
    return row
finally:
    cursor.close(); conn.close()

# Inline close (acceptable for simple reads)
conn = get_db()
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT * FROM table WHERE id=%s", (id,))
result = cursor.fetchall()
cursor.close(); conn.close()
return result
```

- Always use parameterized queries with `%s` placeholders — never f-strings with user data
- Use `cursor(dictionary=True)` for SELECT queries that return rows
- Use plain `cursor()` for INSERT/UPDATE/DELETE
- Always call `conn.commit()` after write operations
- On exceptions in write operations: call `conn.rollback()` then re-raise

## Dynamic UPDATE Pattern

For partial updates (PATCH-like behavior using POST), build SET clause dynamically:

```python
fields = {k: v for k, v in body.model_dump().items() if v is not None}
if not fields:
    cursor.close(); conn.close()
    return {"message": "Nenhum campo para atualizar"}
set_clause = ", ".join(f"{k}=%s" for k in fields)
cursor.execute(f"UPDATE table SET {set_clause} WHERE id=%s", (*fields.values(), record_id))
conn.commit()
```

For fields that can be explicitly set to `None` (e.g., `months`), use `model_fields_set`:
```python
sent = {k: v for k, v in body.model_dump().items() if k in body.model_fields_set}
```

## Route Naming Conventions

- Use `POST` for create, update, and delete (not PUT/PATCH/DELETE)
- Update routes: `POST /{resource}/{id}/update`
- Delete routes: `POST /{resource}/{id}/delete`
- Student-facing routes use path prefix matching the service name (e.g., `/workouts/...`, `/users/...`)
- Admin routes: `GET/POST /{resource}/admin/...` or `/{resource}/{id}` with `require_admin`

```python
@app.post("/workouts/templates", status_code=201)
def create_template(body: CreateTemplate, authorization: str = Header(...)):
    ...

@app.post("/workouts/templates/{template_id}/update")
def update_template(template_id: int, body: UpdateTemplate, authorization: str = Header(...)):
    ...

@app.post("/workouts/templates/{template_id}/delete")
def delete_template(template_id: int, authorization: str = Header(...)):
    ...
```

## Pydantic Model Conventions

- Create models are named `Create{Resource}` — required fields have no default
- Update models are named `Update{Resource}` — all fields `Optional` with `= None`
- Use `Optional[str] = None` (not `str | None`) for compatibility with Pydantic v2
- Enum-like string fields are validated manually against tuples, not with Pydantic validators:

```python
VALID_GENDERS = ("masculino", "feminino")
VALID_GOALS   = ("Hipertrofia", "Emagrecimento", "Condicionamento", "Saúde Geral", "Performance")

if body.gender is not None and body.gender not in VALID_GENDERS:
    raise HTTPException(400, f"gender inválido. Use: {VALID_GENDERS}")
```

## Response Format Conventions

- Single resource: return the dict directly or `{"field": value}`
- Lists: `{"items": [...], "total": len(items)}` — key name matches resource (e.g., `"users"`, `"templates"`)
- Create success: `{"id_field": new_id}` (e.g., `{"template_id": template_id}`)
- Update/delete success: `{"message": "Recurso atualizado/removido com sucesso."}`
- Messages are in **Portuguese (pt-BR)**

```python
return {"template_id": template_id}                          # create
return {"templates": templates, "total": len(templates)}     # list
return {"message": "Template atualizado com sucesso."}       # update
return {"message": "Template removido com sucesso."}         # delete
```

## Error Handling

- Use `HTTPException(status_code, detail)` — detail string in Portuguese
- 401: `"Token inválido"`
- 403: `"Acesso restrito"`
- 404: `"Recurso não encontrado"`
- 400: validation/business logic errors
- 500: `str(e)` for unexpected errors
- Check `cursor.rowcount == 0` after DELETE to raise 404 if not found
- For external API calls (Asaas), wrap in `try/except HTTPException: raise` then `except Exception as e: raise HTTPException(400, str(e))`

## External HTTP Calls (httpx)

Use synchronous `httpx.Client()` as context manager:

```python
with httpx.Client() as client:
    res = client.post(f"{ASAAS_BASE_URL}/payments", headers=headers, json=payload)
    if res.status_code not in (200, 201):
        raise HTTPException(400, f"Asaas payments error {res.status_code}: {res.text}")
    data = res.json()
```

For inter-service calls that should not fail the main request, swallow exceptions:
```python
try:
    with httpx.Client(timeout=10) as client:
        client.post(ONBOARDING_URL, json={...})
except Exception:
    pass
```

## Logging Pattern

Use `print(..., flush=True)` for debug logging — no logging framework:

```python
safe_payload = {k: v for k, v in payload.items() if k not in ("creditCard", "creditCardHolderInfo")}
print(f"[ASAAS] POST /payments body={safe_payload}", flush=True)
print(f"[ASAAS] POST /payments status={res.status_code}", flush=True)
print(f"[ERROR] Unhandled exception: {type(exc).__name__}: {exc}", flush=True)
```

Prefix with service name in brackets: `[ASAAS]`, `[ERROR]`, etc.

## File Upload Pattern (base64)

Services that handle file uploads (ms-users, ms-progress) accept base64-encoded files in JSON body:

```python
class AvatarInput(BaseModel):
    avatar_base64: str  # data:image/jpeg;base64,... or raw base64

# Parse data URI
match = re.match(r"data:(image/[\w+]+);base64,(.+)", avatar_b64, re.DOTALL)
if match:
    mime, b64_data = match.group(1), match.group(2)
else:
    mime, b64_data = "image/jpeg", avatar_b64

image_bytes = base64.b64decode(b64_data.strip())
filename = f"prefix_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
filepath = os.path.join(UPLOAD_DIR, filename)
with open(filepath, "wb") as f:
    f.write(image_bytes)
avatar_url = f"{BASE_URL}/uploads/avatars/{filename}"
```

- Max file size: 5MB (`5 * 1024 * 1024`)
- Serve files via `app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")`

## Section Comments Style

Use ASCII box comments to separate logical sections within `main.py`:

```python
# ── Models ──────────────────────────────────────────────

# ── Helpers ─────────────────────────────────────────────

# ── Templates (admin/trainer) ────────────────────────────

# ── Consultas do aluno ───────────────────────────────────
```

## Environment Variables

Always read with a safe default:
```python
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "2"))
SMTP_SSL = os.getenv("SMTP_SSL", "true").lower() == "true"
```

Required variables with no safe default should raise at runtime via `HTTPException`:
```python
def get_headers():
    api_key = os.getenv("ASAAS_API_KEY")
    if not api_key:
        raise HTTPException(500, "ASAAS_API_KEY nao configurada")
```

## Adding a New Service Checklist

1. Create `services/{name}/main.py`, `requirements.txt`, `Dockerfile`
2. Copy `services/database.py` into the service directory (or use `sys.path.append('..')`)
3. `requirements.txt` minimum: `fastapi==0.104.1`, `uvicorn==0.24.0`, `mysql-connector-python==8.2.0`, `pydantic==2.5.0`, `SQLAlchemy==2.0.36`
4. Add `PyJWT==2.8.0` if the service needs auth; `bcrypt==4.1.1` if it handles passwords; `httpx==0.25.2` if it calls external APIs
5. Add service to `docker-compose.yml` with Traefik labels following the existing pattern
6. Service listens on port **8000** internally
7. Route prefix must match the Traefik `PathPrefix` and `stripprefix` middleware
