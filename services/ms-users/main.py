from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os, bcrypt, jwt
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")


def get_user_id(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(401, "Token inválido")


class UpdateProfile(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    birthdate: Optional[date] = None
    goal: Optional[str] = None

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


@app.get("/users/me")
def get_me(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, email, phone, birthdate, goal, plan, plan_start, plan_renewal, avatar_url FROM users WHERE id=%s",
        (user_id,)
    )
    user = cursor.fetchone()
    if not user:
        cursor.close(); conn.close()
        raise HTTPException(404, "Usuário não encontrado")
    cursor.execute(
        "SELECT weight, height, body_fat, waist, arm, leg, recorded_at FROM body_metrics WHERE user_id=%s ORDER BY recorded_at DESC LIMIT 1",
        (user_id,)
    )
    user["latest_metrics"] = cursor.fetchone()
    cursor.close(); conn.close()
    return user


@app.post("/users/me/update")
def update_me(body: UpdateProfile, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE users SET {set_clause} WHERE id=%s", (*fields.values(), user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Perfil atualizado com sucesso."}


@app.post("/users/me/password")
def change_password(body: ChangePassword, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    if not bcrypt.checkpw(body.current_password.encode(), user["password_hash"].encode()):
        cursor.close(); conn.close()
        raise HTTPException(400, "Senha atual incorreta")
    hashed = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    cursor.execute("UPDATE users SET password_hash=%s WHERE id=%s", (hashed, user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Senha alterada com sucesso."}


@app.get("/users/me/metrics")
def get_metrics(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM body_metrics WHERE user_id=%s ORDER BY recorded_at DESC", (user_id,))
    metrics = cursor.fetchall()
    cursor.close(); conn.close()
    return {"metrics": metrics}


@app.post("/users/me/metrics", status_code=201)
def add_metrics(body: MetricsInput, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO body_metrics (user_id, weight, height, body_fat, waist, arm, leg, chest, recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (user_id, body.weight, body.height, body.body_fat, body.waist, body.arm, body.leg, body.chest, body.recorded_at)
    )
    conn.commit()
    metric_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"id": metric_id, "message": "Medição registrada com sucesso."}


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
