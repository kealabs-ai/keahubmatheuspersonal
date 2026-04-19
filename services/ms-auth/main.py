from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import sys, os, bcrypt, jwt, secrets, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
sys.path.append('..')
from database import get_db

app = FastAPI()
ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_EXPIRE = 3600
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.hostinger.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_SSL = os.getenv("SMTP_SSL", "true").lower() == "true"
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://matheuspersonal.com.br")


def make_token(user_id: int, role: str):
    payload = {"sub": user_id, "role": role, "exp": datetime.utcnow() + timedelta(seconds=JWT_EXPIRE)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def send_reset_email(to_email: str, to_name: str, reset_link: str):
    year = datetime.utcnow().year
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0f0f0f;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f0f;padding:40px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#1a1a1a;border-radius:16px;overflow:hidden;max-width:600px;width:100%;">

        <!-- Header / Logo -->
        <tr>
          <td style="background:linear-gradient(135deg,#c8a96e 0%,#a07840 100%);padding:40px 40px 30px;text-align:center;">
            <div style="font-size:32px;font-weight:900;color:#0f0f0f;letter-spacing:2px;text-transform:uppercase;">MATHEUS</div>
            <div style="font-size:13px;font-weight:600;color:#0f0f0f;letter-spacing:6px;text-transform:uppercase;margin-top:2px;">PERSONAL</div>
            <div style="width:40px;height:3px;background:#0f0f0f;margin:12px auto 0;border-radius:2px;"></div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 30px;">
            <p style="color:#c8a96e;font-size:13px;font-weight:600;letter-spacing:3px;text-transform:uppercase;margin:0 0 16px;">Recuperacao de Senha</p>
            <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0 0 20px;line-height:1.3;">Ola, {to_name}!</h1>
            <p style="color:#aaaaaa;font-size:15px;line-height:1.7;margin:0 0 24px;">
              Recebemos uma solicitacao para redefinir a senha da sua conta no
              <strong style="color:#ffffff;">MatheusPersonal</strong>.
              Clique no botao abaixo para criar uma nova senha.
            </p>
            <p style="color:#aaaaaa;font-size:14px;line-height:1.7;margin:0 0 32px;">
              Este link e valido por <strong style="color:#c8a96e;">1 hora</strong>.
              Se voce nao solicitou a recuperacao, ignore este e-mail.
            </p>

            <!-- CTA Button -->
            <table cellpadding="0" cellspacing="0" style="margin:0 auto 32px;">
              <tr>
                <td style="background:linear-gradient(135deg,#c8a96e 0%,#a07840 100%);border-radius:8px;">
                  <a href="{reset_link}" style="display:inline-block;padding:16px 40px;color:#0f0f0f;font-size:15px;font-weight:700;text-decoration:none;letter-spacing:1px;">REDEFINIR SENHA</a>
                </td>
              </tr>
            </table>

            <!-- Fallback link -->
            <p style="color:#666666;font-size:12px;line-height:1.6;margin:0;word-break:break-all;">
              Ou copie e cole este link no navegador:<br>
              <a href="{reset_link}" style="color:#c8a96e;text-decoration:none;">{reset_link}</a>
            </p>
          </td>
        </tr>

        <!-- Divider -->
        <tr><td style="padding:0 40px;"><div style="height:1px;background:#2a2a2a;"></div></td></tr>

        <!-- Footer -->
        <tr>
          <td style="padding:24px 40px;text-align:center;">
            <p style="color:#444444;font-size:12px;margin:0 0 6px;">&copy; {year} MatheusPersonal. Todos os direitos reservados.</p>
            <p style="color:#444444;font-size:12px;margin:0;">Este e um e-mail automatico, nao responda.</p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Recuperacao de Senha - MatheusPersonal"
    msg["From"] = f"MatheusPersonal <{SMTP_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))
    if SMTP_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())


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
        "SELECT id_user as id, name, email, password, plan, COALESCE(role,'student') as role, COALESCE(active,1) as active, avatar_url FROM users WHERE email=%s",
        (body.email,)
    )
    user = cursor.fetchone()
    if not user:
        cursor.close(); conn.close()
        raise HTTPException(401, "Usuario nao encontrado")
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
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"Erro ao salvar refresh_token: {str(e)}")
    cursor.close(); conn.close()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": JWT_EXPIRE,
        "user": {"id": user["id"], "name": user["name"], "plan": user["plan"], "role": user["role"], "avatar_url": user.get("avatar_url")}
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
        raise HTTPException(401, "Refresh token invalido ou expirado")
    cursor.execute("SELECT id_user as id, role FROM users WHERE id_user=%s", (rt["user_id"],))
    user = cursor.fetchone()
    access_token = make_token(user["id"], user["role"])
    cursor.close(); conn.close()
    return {"access_token": access_token, "expires_in": JWT_EXPIRE}


@app.post("/auth/forgot-password")
def forgot_password(body: ForgotRequest):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id_user as id, name FROM users WHERE email=%s AND active=1",
        (body.email,)
    )
    user = cursor.fetchone()
    if user:
        token = secrets.token_hex(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        cursor.execute(
            "INSERT INTO reset_tokens (user_id, token, expires_at) VALUES (%s,%s,%s)",
            (user["id"], token, expires_at)
        )
        conn.commit()
        reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
        try:
            send_reset_email(body.email, user["name"], reset_link)
        except Exception as e:
            cursor.close(); conn.close()
            raise HTTPException(500, f"Erro ao enviar e-mail: {str(e)}")
    cursor.close(); conn.close()
    return {"message": "Se o e-mail estiver cadastrado, voce recebera as instrucoes em breve."}


@app.post("/auth/reset-password")
def reset_password(body: ResetRequest):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT user_id FROM reset_tokens WHERE token=%s AND expires_at > NOW()",
        (body.token,)
    )
    rt = cursor.fetchone()
    if not rt:
        cursor.close(); conn.close()
        raise HTTPException(400, "Token invalido ou expirado")
    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    cursor.execute("UPDATE users SET password=%s WHERE id_user=%s", (hashed, rt["user_id"]))
    cursor.execute("DELETE FROM reset_tokens WHERE token=%s", (body.token,))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Senha redefinida com sucesso."}
