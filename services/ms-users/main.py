from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os, bcrypt, jwt, base64, uuid, re
sys.path.append('..')
from database import get_db

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads/avatars")
BASE_URL    = os.getenv("BASE_URL", "https://srv1023256.hstgr.cloud")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")


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


class UpdateProfile(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    birthdate: Optional[date] = None
    goal: Optional[str] = None
    gender: Optional[str] = None
    recurring_billing: Optional[bool] = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class MetricsInput(BaseModel):
    weight: Optional[float] = None
    height: Optional[float] = None
    body_fat: Optional[float] = None
    waist: Optional[float] = None
    arm: Optional[float] = None
    leg: Optional[float] = None
    chest: Optional[float] = None
    recorded_at: date

class FeedbackInput(BaseModel):
    message: str

class AvatarInput(BaseModel):
    avatar_base64: str   # data:image/jpeg;base64,... ou base64 puro


class AdminUpdateUser(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    plan: Optional[str] = None
    plan_start: Optional[date] = None
    plan_renewal: Optional[date] = None
    goal: Optional[str] = None
    active: Optional[int] = None
    role: Optional[str] = None


@app.get("/users/all")
def get_all_users(authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id_user as id, name, email, phone, plan, plan_start, plan_renewal, active, role FROM users ORDER BY name"
    )
    users = cursor.fetchall()
    cursor.close(); conn.close()
    return {"users": users, "total": len(users)}


@app.get("/users/me")
def get_me(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id_user as id, name, email, phone, birth_date, goal, plan, plan_start, plan_renewal, avatar_url, COALESCE(recurring_billing, 0) as recurring_billing, gender FROM users WHERE id_user=%s",
        (user_id,)
    )
    user = cursor.fetchone()
    if not user:
        cursor.close(); conn.close()
        raise HTTPException(404, "Usuário não encontrado")
    cursor.execute(
        "SELECT weight, height, body_fat, waist, arm, leg, recorded_at FROM body_metrics WHERE user_id=%s ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    lm = cursor.fetchone()
    if lm and hasattr(lm.get('recorded_at'), 'isoformat'):
        lm['recorded_at'] = lm['recorded_at'].isoformat()
    user["latest_metrics"] = lm
    cursor.close(); conn.close()
    return user


@app.post("/users/me/update")
def update_me(body: UpdateProfile, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    fields = {
        ("birth_date" if k == "birthdate" else k): v
        for k, v in body.model_dump().items()
        if v is not None and k != "recurring_billing"
    }
    if "recurring_billing" in body.model_dump() and body.recurring_billing is not None:
        fields["recurring_billing"] = 1 if body.recurring_billing else 0    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE users SET {set_clause} WHERE id_user=%s", (*fields.values(), user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Perfil atualizado com sucesso."}


@app.post("/users/me/password")
def change_password(body: ChangePassword, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password FROM users WHERE id_user=%s", (user_id,))
    user = cursor.fetchone()
    if not bcrypt.checkpw(body.current_password.encode(), user["password"].encode()):
        cursor.close(); conn.close()
        raise HTTPException(400, "Senha atual incorreta")
    hashed = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    cursor.execute("UPDATE users SET password=%s WHERE id_user=%s", (hashed, user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Senha alterada com sucesso."}


@app.get("/users/me/metrics")
def get_metrics(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM body_metrics WHERE user_id=%s ORDER BY id DESC", (user_id,))
    metrics = cursor.fetchall()
    cursor.close(); conn.close()
    return {"metrics": metrics}


@app.post("/users/me/metrics", status_code=201)
def add_metrics(body: MetricsInput, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "INSERT INTO body_metrics (user_id, weight, height, body_fat, waist, arm, leg, chest, recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (user_id, body.weight, body.height, body.body_fat, body.waist, body.arm, body.leg, body.chest, body.recorded_at)
    )
    conn.commit()
    metric_id = cursor.lastrowid
    cursor.execute(
        "SELECT weight, height, body_fat, waist, arm, leg, recorded_at FROM body_metrics WHERE id=%s",
        (metric_id,)
    )
    saved = cursor.fetchone()
    # Converte recorded_at para string se for objeto date
    if saved and hasattr(saved.get('recorded_at'), 'isoformat'):
        saved['recorded_at'] = saved['recorded_at'].isoformat()
    cursor.close(); conn.close()
    return {"id": metric_id, "message": "Medição registrada com sucesso.", "metrics": saved}


@app.post("/users/me/feedback", status_code=201)
def send_feedback(body: FeedbackInput, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO student_feedbacks (user_id, message) VALUES (%s,%s)", (user_id, body.message))
    conn.commit()
    fb_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"id": fb_id, "message": "Feedback enviado com sucesso."}


@app.post("/users/me/avatar")
def upload_avatar(body: AvatarInput, authorization: str = Header(...)):
    user_id = get_user_id(authorization)

    # Se for URL direta (avatar preset), salva direto no banco sem upload
    avatar_b64 = body.avatar_base64.strip()
    if avatar_b64.startswith('http://') or avatar_b64.startswith('https://'):
        avatar_url = avatar_b64
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET avatar_url=%s WHERE id_user=%s", (avatar_url, user_id))
        conn.commit()
        cursor.close(); conn.close()
        return {"avatar_url": avatar_url, "message": "Avatar atualizado com sucesso."}

    # Upload de arquivo base64
    match = re.match(r"data:(image/[\w+]+);base64,(.+)", avatar_b64, re.DOTALL)
    if match:
        mime, b64_data = match.group(1), match.group(2)
    else:
        mime, b64_data = "image/jpeg", avatar_b64

    ext = mime.split("/")[1].replace("jpeg", "jpg").replace("+xml", "")
    if ext not in ("jpg", "jpeg", "png", "webp", "svg"):
        ext = "jpg"

    try:
        image_bytes = base64.b64decode(b64_data.strip())
    except Exception:
        raise HTTPException(400, "Base64 inválido")

    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(400, "Imagem muito grande. Máximo 5MB.")

    filename  = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath  = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    avatar_url = f"{BASE_URL}/uploads/avatars/{filename}"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET avatar_url=%s WHERE id_user=%s", (avatar_url, user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"avatar_url": avatar_url, "message": "Avatar atualizado com sucesso."}


@app.post("/users/admin/{user_id}")
def admin_update_user(user_id: int, body: AdminUpdateUser, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE users SET {set_clause} WHERE id_user=%s", (*fields.values(), user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Usuário atualizado com sucesso."}


@app.post("/users/me/recurring-billing")
def set_recurring_billing(authorization: str = Header(...), enabled: bool = True):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET recurring_billing=%s WHERE id_user=%s", (1 if enabled else 0, user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Preferência de cobrança recorrente atualizada.", "recurring_billing": enabled}


@app.get("/users/recurring-billing/due")
def get_due_recurring(authorization: str = Header(...)):
    """Retorna alunos com cobrança recorrente ativa e plano vencendo hoje ou já vencido."""
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT id_user, name, email, plan, plan_renewal
           FROM users
           WHERE recurring_billing = 1
             AND active = 1
             AND plan_renewal <= CURDATE()"""
    )
    users = cursor.fetchall()
    cursor.close(); conn.close()
    return {"users": users, "total": len(users)}
