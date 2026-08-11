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
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Oswald:wght@600;700&display=swap" rel="stylesheet">
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:Inter,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:48px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

        <!-- Logo / Header -->
        <tr>
          <td align="center" style="padding-bottom:32px;">
            <div style="display:inline-block;">
              <div style="font-family:Oswald,sans-serif;font-size:36px;font-weight:700;color:#00B4D8;letter-spacing:4px;text-transform:uppercase;line-height:1;">MATHEUS</div>
              <div style="font-family:Inter,sans-serif;font-size:11px;font-weight:600;color:#0096C7;letter-spacing:8px;text-transform:uppercase;margin-top:4px;text-align:center;">PERSONAL</div>
              <div style="width:100%;height:2px;background:linear-gradient(to right,#00B4D8,#0096C7);margin-top:8px;border-radius:1px;"></div>
            </div>
          </td>
        </tr>

        <!-- Card -->
        <tr>
          <td style="background:#1a1a1a;border-radius:12px;border:1px solid #2a2a2a;overflow:hidden;">

            <!-- Card top accent -->
            <tr>
              <td style="height:3px;background:linear-gradient(to right,#00B4D8,#0096C7);"></td>
            </tr>

            <!-- Card body -->
            <tr>
              <td style="padding:48px 48px 40px;">
                <p style="color:#00B4D8;font-size:11px;font-weight:600;letter-spacing:4px;text-transform:uppercase;margin:0 0 20px;">Recuperacao de Senha</p>
                <h1 style="color:#ffffff;font-family:Oswald,sans-serif;font-size:28px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin:0 0 24px;line-height:1.2;">Ola, {to_name}</h1>
                <p style="color:#9ca3af;font-size:15px;line-height:1.7;margin:0 0 16px;">
                  Recebemos uma solicitacao para redefinir a senha da sua conta no
                  <strong style="color:#ffffff;">MatheusPersonal</strong>.
                </p>
                <p style="color:#9ca3af;font-size:15px;line-height:1.7;margin:0 0 36px;">
                  Clique no botao abaixo para criar uma nova senha. Este link e valido por
                  <strong style="color:#00B4D8;">1 hora</strong>.
                </p>

                <!-- CTA -->
                <table cellpadding="0" cellspacing="0" style="margin:0 0 36px;">
                  <tr>
                    <td style="background:linear-gradient(to right,#00B4D8,#0096C7);border-radius:6px;">
                      <a href="{reset_link}" style="display:inline-block;padding:14px 36px;color:#0a0a0a;font-size:13px;font-weight:700;text-decoration:none;letter-spacing:2px;text-transform:uppercase;font-family:Oswald,sans-serif;">REDEFINIR SENHA</a>
                    </td>
                  </tr>
                </table>

                <!-- Divider -->
                <div style="height:1px;background:#2a2a2a;margin-bottom:24px;"></div>

                <!-- Warning -->
                <p style="color:#6b7280;font-size:13px;line-height:1.6;margin:0 0 16px;">
                  Se voce nao solicitou a recuperacao de senha, ignore este e-mail. Sua senha permanece a mesma.
                </p>

                <!-- Fallback link -->
                <p style="color:#6b7280;font-size:12px;line-height:1.6;margin:0;">
                  Ou acesse diretamente:<br>
                  <a href="{reset_link}" style="color:#00B4D8;text-decoration:none;word-break:break-all;">{reset_link}</a>
                </p>
              </td>
            </tr>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:32px 0 0;text-align:center;">
            <p style="color:#374151;font-size:12px;margin:0 0 4px;">&copy; {year} MatheusPersonal. Todos os direitos reservados.</p>
            <p style="color:#374151;font-size:12px;margin:0;">Este e um e-mail automatico, nao responda.</p>
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
