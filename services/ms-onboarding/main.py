from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from dateutil.relativedelta import relativedelta
import sys, os, jwt, json
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")

PLAN_DURATION_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}

PLAN_NAME_MAP = {
    "bronze": "BRONZE", "prata": "PRATA", "ouro": "OURO", "diamante": "DIAMANTE",
    "plano bronze": "BRONZE", "plano prata": "PRATA", "plano ouro": "OURO", "plano diamante": "DIAMANTE",
    "silver": "PRATA", "gold": "OURO", "diamond": "DIAMANTE",
}


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


def get_onboarding_config(cursor) -> dict:
    cursor.execute("SELECT * FROM onboarding_config WHERE id=1")
    cfg = cursor.fetchone()
    if not cfg:
        raise HTTPException(500, "Configuração de onboarding não encontrada")
    if isinstance(cfg["default_week_template"], str):
        cfg["default_week_template"] = json.loads(cfg["default_week_template"])
    return cfg


# ── Models ───────────────────────────────────────────────

class OnboardingRequest(BaseModel):
    id_order: int
    id_user: int
    plan_name: str
    plan_frequency: str


class WeekDayTemplate(BaseModel):
    week_day: int        # 1=SEG ... 7=DOM
    name: str
    duration_min: int = 0
    is_rest: bool = False


class OnboardingConfigUpdate(BaseModel):
    default_workout_name: Optional[str] = None
    welcome_message: Optional[str] = None
    welcome_notification_title: Optional[str] = None
    welcome_notification_body: Optional[str] = None
    default_week_template: Optional[List[WeekDayTemplate]] = None


# ── Config endpoints ─────────────────────────────────────

@app.get("/onboarding/config")
def get_config(authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cfg = get_onboarding_config(cursor)
    finally:
        cursor.close(); conn.close()
    return cfg


@app.post("/onboarding/config")
def update_config(body: OnboardingConfigUpdate, authorization: str = Header(...)):
    admin_id = require_admin(authorization)
    fields = body.model_dump(exclude_none=True)
    if not fields:
        return {"message": "Nenhum campo para atualizar"}

    if "default_week_template" in fields:
        fields["default_week_template"] = json.dumps(
            [d.model_dump() for d in body.default_week_template]
        )

    fields["updated_by"] = admin_id
    set_clause = ", ".join(f"{k}=%s" for k in fields)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(f"UPDATE onboarding_config SET {set_clause} WHERE id=1", (*fields.values(),))
        conn.commit()
    finally:
        cursor.close(); conn.close()
    return {"message": "Configuração atualizada com sucesso."}


# ── Debug / Activate ─────────────────────────────────────

@app.get("/onboarding/debug/{user_id}")
def debug_user(user_id: int):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id_user, name, plan, plan_start, plan_renewal, active, role FROM users WHERE id_user=%s",
            (user_id,)
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")
        cursor.execute(
            "SELECT id_order, id_user FROM orders WHERE id_user=%s ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        last_order = cursor.fetchone()
        order_items = []
        if last_order:
            cursor.execute(
                "SELECT plan_name, plan_price, plan_frequency FROM order_items WHERE id_order=%s",
                (last_order["id_order"],)
            )
            order_items = cursor.fetchall()
        cursor.execute(
            "SELECT id_subscription, plan_name, status FROM subscriptions WHERE id_user=%s ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        subscription = cursor.fetchone()
        return {"user": user, "last_order": last_order, "order_items": order_items, "subscription": subscription}
    finally:
        cursor.close(); conn.close()


@app.post("/onboarding/activate", status_code=200)
def activate(req: OnboardingRequest):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_user, name, plan, active FROM users WHERE id_user=%s", (req.id_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        cfg = get_onboarding_config(cursor)
        is_new_student = not user["active"]
        today = date.today()
        months = PLAN_DURATION_MONTHS.get(req.plan_frequency.lower(), 1)
        renewal = today + relativedelta(months=months)
        plan_enum = PLAN_NAME_MAP.get(req.plan_name.lower().strip(), req.plan_name.upper())

        print(f"[ONBOARDING] user_id={req.id_user} plan='{plan_enum}'", flush=True)

        # 1. Ativar usuário
        cursor.execute(
            "UPDATE users SET plan=%s, plan_start=COALESCE(plan_start, %s), plan_renewal=%s, active=1 WHERE id_user=%s",
            (plan_enum, today, renewal, req.id_user)
        )

        # 2. Assinatura
        cursor.execute(
            "SELECT id_subscription, status FROM subscriptions WHERE id_user=%s ORDER BY created_at DESC LIMIT 1",
            (req.id_user,)
        )
        sub = cursor.fetchone()
        if sub:
            if sub["status"] != "active":
                cursor.execute("UPDATE subscriptions SET status='active' WHERE id_subscription=%s", (sub["id_subscription"],))
        else:
            cursor.execute(
                "INSERT INTO subscriptions (id_user, plan_name, plan_price, plan_frequency, status) SELECT %s, oi.plan_name, oi.plan_price, oi.plan_frequency, 'active' FROM order_items oi WHERE oi.id_order=%s LIMIT 1",
                (req.id_user, req.id_order)
            )

        # 3. Plano de treino inicial usando config do banco
        cursor.execute("SELECT id FROM workout_plans WHERE user_id=%s LIMIT 1", (req.id_user,))
        if not cursor.fetchone():
            cursor.execute("SELECT id_user FROM users WHERE role IN ('trainer','admin') AND active=1 ORDER BY id_user LIMIT 1")
            trainer_row = cursor.fetchone()
            trainer_id = trainer_row["id_user"] if trainer_row else req.id_user

            cursor.execute(
                "INSERT INTO workout_plans (user_id, trainer_id, name, week_start, active) VALUES (%s, %s, %s, %s, 1)",
                (req.id_user, trainer_id, cfg["default_workout_name"], today)
            )
            plan_id = cursor.lastrowid

            week_template = cfg["default_week_template"]
            cursor.executemany(
                "INSERT INTO workout_days (plan_id, week_day, name, duration_min, is_rest, sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
                [(plan_id, d["week_day"], d["name"], d["duration_min"], d["is_rest"], i + 1)
                 for i, d in enumerate(week_template)]
            )

        # 4. Notificação de boas-vindas
        cursor.execute(
            "SELECT id FROM notifications WHERE user_id=%s AND type='system' AND title=%s LIMIT 1",
            (req.id_user, cfg["welcome_notification_title"])
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO notifications (user_id, type, title, body) VALUES (%s, 'system', %s, %s)",
                (req.id_user, cfg["welcome_notification_title"], cfg["welcome_notification_body"])
            )

        conn.commit()
        return {"success": True, "user_id": req.id_user, "plan": plan_enum, "plan_renewal": renewal.isoformat(), "is_new_student": is_new_student}
    except HTTPException:
        conn.rollback(); raise
    except Exception as e:
        conn.rollback(); raise HTTPException(500, str(e))
    finally:
        cursor.close(); conn.close()
