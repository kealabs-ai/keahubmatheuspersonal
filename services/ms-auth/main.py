from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import sys, os, bcrypt, jwt, secrets
sys.path.append('..')
from database import get_db

app = FastAPI()
ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRE = 3600


def make_token(user_id: int, role: str):
    payload = {"sub": user_id, "role": role, "exp": datetime.utcnow() + timedelta(seconds=JWT_EXPIRE)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


class LoginRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotRequest(BaseModel):
    email: str

class ResetRequest(BaseModel):
    token: str
    password: str


@app.post("/auth/login")
def login(body: LoginRequest):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id_user as id, name, email, password, plan, COALESCE(role,'student') as role, COALESCE(active,1) as active FROM users WHERE email=%s",
        (body.email,)
    )
    user = cursor.fetchone()
    if not user:
        cursor.close(); conn.close()
        raise HTTPException(401, "Usuário não encontrado")
    try:
        pwd_match = bcrypt.checkpw(body.password.encode("utf-8"), user["password"].encode("utf-8"))
    except Exception as e:
        cursor.close(); conn.close()
        raise HTTPException(401, f"Erro ao verificar senha: {str(e)}")
    if not pwd_match:
        cursor.close(); conn.close()
        raise HTTPException(401, "Senha incorreta")
    if not user["active"]:
        cursor.close(); conn.close()
        raise HTTPException(403, "Conta inativa")
    access_token = make_token(user["id"], user["role"])
    refresh_token = secrets.token_hex(64)
    expires_at = datetime.utcnow() + timedelta(days=30)
    try:
        cursor.execute(
            "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES (%s,%s,%s)",
            (user["id"], refresh_token, expires_at)
        )
        conn.commit()
    except Exception as e:
        cursor.close(); conn.close()
        raise HTTPException(500, f"Erro ao salvar refresh_token: {str(e)}")
    cursor.close(); conn.close()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": JWT_EXPIRE,
        "user": {"id": user["id"], "name": user["name"], "plan": user["plan"], "role": user["role"]}
    }


@app.post("/auth/logout")
def logout(body: RefreshRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM refresh_tokens WHERE token=%s", (body.refresh_token,))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Logout realizado com sucesso."}


@app.post("/auth/refresh")
def refresh(body: RefreshRequest):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM refresh_tokens WHERE token=%s AND expires_at > NOW()",
        (body.refresh_token,)
    )
    rt = cursor.fetchone()
    if not rt:
        cursor.close(); conn.close()
        raise HTTPException(401, "Refresh token inválido ou expirado")
    cursor.execute("SELECT id_user as id, role FROM users WHERE id_user=%s", (rt["user_id"],))
    user = cursor.fetchone()
    access_token = make_token(user["id"], user["role"])
    cursor.close(); conn.close()
    return {"access_token": access_token, "expires_in": JWT_EXPIRE}


@app.post("/auth/forgot-password")
def forgot_password(body: ForgotRequest):
    # Sempre retorna 200 para não expor e-mails cadastrados
    return {"message": "E-mail de recuperação enviado."}


@app.post("/auth/reset-password")
def reset_password(body: ResetRequest):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT user_id FROM refresh_tokens WHERE token=%s AND expires_at > NOW()",
        (body.token,)
    )
    rt = cursor.fetchone()
    if not rt:
        cursor.close(); conn.close()
        raise HTTPException(400, "Token inválido ou expirado")
    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    cursor.execute("UPDATE users SET password=%s WHERE id_user=%s", (hashed, rt["user_id"]))
    cursor.execute("DELETE FROM refresh_tokens WHERE token=%s", (body.token,))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Senha redefinida com sucesso."}
