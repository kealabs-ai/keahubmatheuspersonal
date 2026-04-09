from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os, jwt
sys.path.append('..')
from database import get_db

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]) = {"1m": 1, "3m": 3, "6m": 6, "1y": 12}


def get_user_id(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(401, "Token inválido")


class WeightInput(BaseModel):
    weight_kg: float
    recorded_at: date

class PhotoInput(BaseModel):
    photo_url: str
    label: Optional[str] = None
    recorded_at: date


@app.get("/progress/weight")
def get_weight(period: str = Query("6m"), authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    months = PERIOD_MONTHS.get(period, 6)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT DATE_FORMAT(recorded_at, '%%Y-%%m') as date, AVG(weight_kg) as weight
           FROM weight_history WHERE user_id=%s AND recorded_at >= DATE_SUB(NOW(), INTERVAL %s MONTH)
           GROUP BY DATE_FORMAT(recorded_at, '%%Y-%%m') ORDER BY date""",
        (user_id, months)
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()
    if not data:
        return {"data": [], "summary": {}}
    start = float(data[0]["weight"])
    current = float(data[-1]["weight"])
    return {"data": data, "summary": {"start": start, "current": current, "diff": round(current - start, 1)}}


@app.post("/progress/weight", status_code=201)
def add_weight(body: WeightInput, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO weight_history (user_id, weight_kg, recorded_at) VALUES (%s,%s,%s)",
        (user_id, body.weight_kg, body.recorded_at)
    )
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Peso registrado com sucesso."}


@app.get("/progress/strength")
def get_all_records(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM personal_records WHERE user_id=%s ORDER BY exercise_name, recorded_at",
        (user_id,)
    )
    records = cursor.fetchall()
    cursor.close(); conn.close()
    return {"records": records}


@app.get("/progress/strength/{exercise}")
def get_strength(exercise: str, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT DATE_FORMAT(recorded_at, '%%Y-%%m') as date, MAX(weight_kg) as weight
           FROM personal_records WHERE user_id=%s AND exercise_name=%s
           GROUP BY DATE_FORMAT(recorded_at, '%%Y-%%m') ORDER BY date""",
        (user_id, exercise)
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()
    if not data:
        raise HTTPException(404, "Nenhum registro encontrado")
    record = float(max(r["weight"] for r in data))
    gain = round(record - float(data[0]["weight"]), 1)
    return {"exercise": exercise, "data": data, "record": record, "gain": gain}


@app.get("/progress/measurements")
def get_measurements(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM body_metrics WHERE user_id=%s ORDER BY recorded_at DESC", (user_id,))
    data = cursor.fetchall()
    cursor.close(); conn.close()
    return {"measurements": data}


@app.get("/progress/photos")
def get_photos(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM progress_photos WHERE user_id=%s ORDER BY recorded_at DESC", (user_id,))
    photos = cursor.fetchall()
    cursor.close(); conn.close()
    return {"photos": photos}


@app.post("/progress/photos", status_code=201)
def add_photo(body: PhotoInput, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO progress_photos (user_id, photo_url, label, recorded_at) VALUES (%s,%s,%s,%s)",
        (user_id, body.photo_url, body.label, body.recorded_at)
    )
    conn.commit()
    photo_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"id": photo_id, "message": "Foto adicionada com sucesso."}


@app.post("/progress/photos/{photo_id}/delete")
def delete_photo(photo_id: int, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM progress_photos WHERE id=%s AND user_id=%s", (photo_id, user_id))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close(); conn.close()
    if not deleted:
        raise HTTPException(404, "Foto não encontrada")
    return {"message": "Foto removida com sucesso."}


@app.get("/progress/badges")
def get_badges(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT b.slug, b.name, b.icon, ub.earned_at FROM user_badges ub
           JOIN badges b ON b.id = ub.badge_id WHERE ub.user_id=%s""",
        (user_id,)
    )
    earned = cursor.fetchall()
    earned_slugs = {e["slug"] for e in earned}
    cursor.execute("SELECT slug, name, icon FROM badges")
    all_badges = cursor.fetchall()
    locked = [b for b in all_badges if b["slug"] not in earned_slugs]
    cursor.close(); conn.close()
    return {"earned": earned, "locked": locked}
