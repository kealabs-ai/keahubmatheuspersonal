from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
from dateutil.relativedelta import relativedelta
import sys
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://asaas-service:8000"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

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

        is_new_student = not user["plan"] or not user["active"]
        today = date.today()
        months = PLAN_DURATION_MONTHS.get(req.plan_frequency.lower(), 1)
        renewal = today + relativedelta(months=months)

        # 2. Ativar/atualizar plano no usuário (idempotente)
        cursor.execute(
            """UPDATE users
               SET plan=%s, plan_start=COALESCE(plan_start, %s), plan_renewal=%s, active=1
               WHERE id_user=%s""",
            (req.plan_name.upper(), today, renewal, req.id_user)
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

        # 4. Notificação de boas-vindas (apenas uma vez por usuário)
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
            "plan": req.plan_name.upper(),
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
