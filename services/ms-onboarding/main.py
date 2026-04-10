from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
from dateutil.relativedelta import relativedelta
import sys
sys.path.append('..')
from database import get_db

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PLAN_DURATION_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}


class OnboardingRequest(BaseModel):
    id_order: int
    id_user: int
    plan_name: str
    plan_frequency: str  # monthly | quarterly | semiannual | annual


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
        return {
            "user": user,
            "last_order": last_order,
            "order_items": order_items,
            "subscription": subscription,
        }
    finally:
        cursor.close()
        conn.close()


@app.post("/onboarding/activate", status_code=200)
def activate(req: OnboardingRequest):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Verificar se o usuário existe
        cursor.execute(
            "SELECT id_user, name, plan, active FROM users WHERE id_user=%s",
            (req.id_user,)
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(404, "Usuário não encontrado")

        is_new_student = not user["active"]
        today = date.today()
        months = PLAN_DURATION_MONTHS.get(req.plan_frequency.lower(), 1)
        renewal = today + relativedelta(months=months)

        # Normaliza plan_name para o ENUM do banco: BRONZE | PRATA | OURO | DIAMANTE
        PLAN_NAME_MAP = {
            "bronze": "BRONZE", "prata": "PRATA", "ouro": "OURO", "diamante": "DIAMANTE",
            "plano bronze": "BRONZE", "plano prata": "PRATA", "plano ouro": "OURO", "plano diamante": "DIAMANTE",
            "silver": "PRATA", "gold": "OURO", "diamond": "DIAMANTE",
        }
        plan_enum = PLAN_NAME_MAP.get(req.plan_name.lower().strip(), req.plan_name.upper())

        print(f"[ONBOARDING] user_id={req.id_user} plan_name_received='{req.plan_name}' plan_enum_resolved='{plan_enum}'", flush=True)

        # 2. Ativar/atualizar plano no usuário (idempotente)
        cursor.execute(
            """UPDATE users
               SET plan=%s, plan_start=COALESCE(plan_start, %s), plan_renewal=%s, active=1
               WHERE id_user=%s""",
            (plan_enum, today, renewal, req.id_user)
        )

        # 3. Garantir assinatura ativa — sem duplicar
        cursor.execute(
            """SELECT id_subscription, status FROM subscriptions
               WHERE id_user=%s ORDER BY created_at DESC LIMIT 1""",
            (req.id_user,)
        )
        sub = cursor.fetchone()
        if sub:
            if sub["status"] != "active":
                cursor.execute(
                    "UPDATE subscriptions SET status='active' WHERE id_subscription=%s",
                    (sub["id_subscription"],)
                )
        else:
            cursor.execute(
                """INSERT INTO subscriptions (id_user, plan_name, plan_price, plan_frequency, status)
                   SELECT %s, oi.plan_name, oi.plan_price, oi.plan_frequency, 'active'
                   FROM order_items oi WHERE oi.id_order=%s LIMIT 1""",
                (req.id_user, req.id_order)
            )

        # 4. Plano de treino inicial — apenas para alunos novos, sem duplicar
        cursor.execute(
            "SELECT id FROM workout_plans WHERE user_id=%s LIMIT 1",
            (req.id_user,)
        )
        if not cursor.fetchone():
            # Buscar o primeiro usuário com role trainer/admin como personal padrão
            cursor.execute(
                "SELECT id_user FROM users WHERE role IN ('trainer','admin') AND active=1 ORDER BY id_user LIMIT 1"
            )
            trainer_row = cursor.fetchone()
            trainer_id = trainer_row["id_user"] if trainer_row else req.id_user

            cursor.execute(
                """INSERT INTO workout_plans (user_id, trainer_id, name, week_start, active)
                   VALUES (%s, %s, 'Plano Inicial', %s, 1)""",
                (req.id_user, trainer_id, today)
            )
            plan_id = cursor.lastrowid

            # Semana padrão: 3 treinos + 4 descansos
            default_week = [
                (1, "Peito + Tríceps",   50, 0, 1),
                (2, "Descanso",           0, 1, 2),
                (3, "Costas + Bíceps",   50, 0, 3),
                (4, "Descanso",           0, 1, 4),
                (5, "Pernas + Ombros",   55, 0, 5),
                (6, "Descanso",           0, 1, 6),
                (7, "Descanso",           0, 1, 7),
            ]
            cursor.executemany(
                """INSERT INTO workout_days (plan_id, week_day, name, duration_min, is_rest, sort_order)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                [(plan_id, wd, name, dur, rest, order) for wd, name, dur, rest, order in default_week]
            )

        # 5. Notificação de boas-vindas (apenas uma vez por usuário)
        cursor.execute(
            """SELECT id FROM notifications
               WHERE user_id=%s AND type='system' AND title='Bem-vindo ao MatheusPersonal!' LIMIT 1""",
            (req.id_user,)
        )
        if not cursor.fetchone():
            cursor.execute(
                """INSERT INTO notifications (user_id, type, title, body)
                   VALUES (%s, 'system', 'Bem-vindo ao MatheusPersonal!',
                   'Seu plano foi ativado com sucesso. Acesse a área do aluno e comece sua jornada!')""",
                (req.id_user,)
            )

        conn.commit()
        return {
            "success": True,
            "user_id": req.id_user,
            "plan": plan_enum,
            "plan_renewal": renewal.isoformat(),
            "is_new_student": is_new_student,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()
