from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import sys, os, jwt
sys.path.append('..')
from database import get_db

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

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


@app.get("/notifications")
def list_notifications(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 50", (user_id,))
    notifications = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE user_id=%s AND read_at IS NULL", (user_id,))
    unread = cursor.fetchone()["cnt"]
    cursor.close(); conn.close()
    return {"unread_count": unread, "notifications": notifications}


@app.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET read_at=%s WHERE id=%s AND user_id=%s AND read_at IS NULL",
                   (datetime.utcnow(), notification_id, user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Notificação marcada como lida."}


@app.post("/notifications/read-all")
def mark_all_read(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET read_at=%s WHERE user_id=%s AND read_at IS NULL",
                   (datetime.utcnow(), user_id))
    conn.commit()
    updated = cursor.rowcount
    cursor.close(); conn.close()
    return {"message": f"{updated} notificações marcadas como lidas."}


@app.get("/notifications/unread-count")
def unread_count(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id=%s AND read_at IS NULL", (user_id,))
    count = cursor.fetchone()["count"]
    cursor.close(); conn.close()
    return {"unread_count": count}
