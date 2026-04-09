from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional
import sys, os, jwt
sys.path.append('..')
from database import get_db
import bcrypt

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")


def require_admin(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(401, "Token inválido")
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM users WHERE id_user=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close(); conn.close()
    if not user or user["role"] not in ("admin", "trainer"):
        raise HTTPException(403, "Acesso restrito")
    return user_id

app = FastAPI()

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PLAN_DURATION_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}

class User(BaseModel):
    name: str
    email: str
    phone: str
    cpf: str
    birth_date: Optional[date] = None
    cep: str
    address: str
    number: str
    complement: Optional[str] = None
    neighborhood: str
    city: str
    state: str
    username: str
    password: str
    country_code: str = '+55'
    plan: Optional[str] = None
    plan_frequency: Optional[str] = None  # monthly | quarterly | semiannual | annual
    goal: Optional[str] = None
    role: str = 'student'

@app.post("/users", status_code=200)
def create_user(user: User):
    conn = get_db()
    cursor = conn.cursor()
    try:
        hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()

        plan_start = date.today() if user.plan else None
        plan_renewal = None
        if plan_start and user.plan_frequency:
            months = PLAN_DURATION_MONTHS.get(user.plan_frequency.lower(), 1)
            plan_renewal = plan_start + relativedelta(months=months)

        cursor.execute(
            """INSERT INTO users (name, email, phone, cpf, birth_date, cep, address, number,
               neighborhood, city, state, country_code, username, password,
               plan, plan_start, plan_renewal, goal, role, active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)""",
            (user.name, user.email, user.phone, user.cpf, user.birth_date, user.cep,
             user.address, user.number, user.neighborhood, user.city, user.state,
             user.country_code, user.username, hashed,
             user.plan, plan_start, plan_renewal, user.goal, user.role)
        )
        user_id = cursor.lastrowid

        cursor.execute("""INSERT INTO user_addresses (id_user, cep, address, number, complement,
                         neighborhood, city, state, is_primary)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1)""",
                      (user_id, user.cep, user.address, user.number, user.complement,
                       user.neighborhood, user.city, user.state))

        conn.commit()
        return {
            "id": user_id,
            "status": "success",
            "plan": user.plan,
            "plan_start": plan_start.isoformat() if plan_start else None,
            "plan_renewal": plan_renewal.isoformat() if plan_renewal else None,
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/users/{user_id}")
def get_user(user_id: int):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id_user=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        raise HTTPException(404, "User not found")
    cursor.execute("SELECT * FROM user_addresses WHERE id_user=%s ORDER BY is_primary DESC", (user_id,))
    user["addresses"] = cursor.fetchall()
    cursor.close()
    conn.close()
    return user

@app.post("/users/{user_id}/update")
def update_user(user_id: int, user: User):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""UPDATE users SET name=%s, email=%s, phone=%s, address=%s, number=%s,
                         neighborhood=%s, city=%s, state=%s, cep=%s WHERE id_user=%s""",
                      (user.name, user.email, user.phone, user.address, user.number,
                       user.neighborhood, user.city, user.state, user.cep, user_id))
        cursor.execute("""UPDATE user_addresses SET cep=%s, address=%s, number=%s, complement=%s,
                         neighborhood=%s, city=%s, state=%s WHERE id_user=%s AND is_primary=1""",
                      (user.cep, user.address, user.number, user.complement,
                       user.neighborhood, user.city, user.state, user_id))
        conn.commit()
        return {"updated": cursor.rowcount}
    finally:
        cursor.close()
        conn.close()

@app.post("/users/{user_id}/delete")
def delete_user(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id_user=%s", (user_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    return {"deleted": deleted}

@app.get("/users")
def list_all_users(authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_user, name, email, phone, cpf, plan, active, role, created_at FROM users ORDER BY id_user DESC")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"users": users, "total": len(users)}
