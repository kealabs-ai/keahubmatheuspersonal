from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys, os, jwt
sys.path.append('..')
from database import get_db

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


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


class VideoInput(BaseModel):
    title: str
    description: Optional[str] = None
    url: str
    thumbnail_url: Optional[str] = None
    category: str = "Geral"
    duration_min: Optional[int] = None


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    category: Optional[str] = None
    duration_min: Optional[int] = None


@app.get("/admin/videos")
def list_videos(authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM videos ORDER BY created_at DESC")
    videos = cursor.fetchall()
    cursor.close(); conn.close()
    return videos


@app.post("/admin/videos", status_code=201)
def create_video(body: VideoInput, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO videos (title, description, url, thumbnail_url, category, duration_min) VALUES (%s,%s,%s,%s,%s,%s)",
        (body.title, body.description, body.url, body.thumbnail_url, body.category, body.duration_min)
    )
    conn.commit()
    video_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"id": video_id, "title": body.title, "description": body.description,
            "url": body.url, "thumbnail_url": body.thumbnail_url,
            "category": body.category, "duration_min": body.duration_min}


@app.post("/admin/videos/{video_id}")
def update_video(video_id: int, body: VideoUpdate, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE videos SET {set_clause} WHERE id=%s", (*fields.values(), video_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Vídeo atualizado com sucesso."}


@app.delete("/admin/videos/{video_id}")
def delete_video(video_id: int, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM videos WHERE id=%s", (video_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close(); conn.close()
    if not deleted:
        raise HTTPException(404, "Vídeo não encontrado")
    return {"message": "Vídeo removido com sucesso."}
