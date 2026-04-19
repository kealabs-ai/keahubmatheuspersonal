from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os, jwt, base64, uuid, re
sys.path.append('..')
from database import get_db

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads/photos")
BASE_URL = os.getenv("BASE_URL", "https://srv1023256.hstgr.cloud")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")

PERIOD_MONTHS = {"1m": 1, "3m": 3, "6m": 6, "1y": 12}


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
    photo_base64: str          # data:image/jpeg;base64,/9j/... ou só o base64 puro
    label: Optional[str] = None
    recorded_at: date


@app.get("/progress/weight")
def get_weight(period: str = Query("6m"), authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    months = PERIOD_MONTHS.get(period, 6)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # Retorna registros individuais ordenados por data
    cursor.execute(
        """SELECT DATE_FORMAT(recorded_at, '%Y-%m-%d') as date,
                  weight_kg as weight, recorded_at
           FROM weight_history
           WHERE user_id=%s AND recorded_at >= DATE_SUB(NOW(), INTERVAL %s MONTH)
           ORDER BY recorded_at ASC""",
        (user_id, months)
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()
    if not data:
        return {"data": [], "summary": {}}
    start   = float(data[0]["weight"])
    current = float(data[-1]["weight"])
    avg     = round(sum(float(r["weight"]) for r in data) / len(data), 1)
    return {
        "data": data,
        "summary": {
            "start":   start,
            "current": current,
            "diff":    round(current - start, 1),
            "avg":     avg,
            "total":   len(data),
        }
    }


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
    # Busca o maior peso registrado por exercício nos logs do aluno
    cursor.execute(
        """SELECT e.name as exercise_name,
                  MAX(el.weight_kg) as weight_kg,
                  COUNT(el.id) as total_sets
           FROM exercise_logs el
           JOIN exercises e ON e.id = el.exercise_id
           JOIN workout_logs wl ON wl.id = el.log_id
           WHERE wl.user_id = %s AND el.weight_kg IS NOT NULL AND el.weight_kg > 0
           GROUP BY e.name
           ORDER BY e.name ASC""",
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
    # Histórico de carga por exercício agrupado por data
    cursor.execute(
        """SELECT DATE_FORMAT(wl.finished_at, '%Y-%m-%d') as date,
                  MAX(el.weight_kg) as weight
           FROM exercise_logs el
           JOIN exercises e ON e.id = el.exercise_id
           JOIN workout_logs wl ON wl.id = el.log_id
           WHERE wl.user_id = %s AND e.name = %s
             AND el.weight_kg IS NOT NULL AND el.weight_kg > 0
             AND wl.finished_at IS NOT NULL
           GROUP BY DATE_FORMAT(wl.finished_at, '%Y-%m-%d')
           ORDER BY date ASC""",
        (user_id, exercise)
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()
    if not data:
        return {"exercise": exercise, "data": [], "record": 0, "gain": 0}
    record = float(max(r["weight"] for r in data))
    gain   = round(record - float(data[0]["weight"]), 1)
    return {"exercise": exercise, "data": data, "record": record, "gain": gain}


@app.get("/progress/measurements")
def get_measurements(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM body_metrics WHERE user_id=%s ORDER BY recorded_at ASC",
        (user_id,)
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()

    FIELDS = {
        'weight':   ('Peso',       'kg'),
        'height':   ('Altura',     'cm'),
        'body_fat': ('% Gordura',  '%'),
        'waist':    ('Cintura',    'cm'),
        'arm':      ('Braço',      'cm'),
        'leg':      ('Perna',      'cm'),
        'chest':    ('Peito',      'cm'),
    }

    if not data:
        return {"measurements": [], "history": []}

    latest = data[-1]
    first  = data[0]

    # Cards com valor atual, inicial e diff
    cards = []
    for key, (label, unit) in FIELDS.items():
        val = latest.get(key)
        if val is None:
            continue
        val     = float(val)
        val_ini = float(first.get(key) or val)
        diff    = round(val - val_ini, 1)
        diff_str = f"+{diff} {unit}" if diff > 0 else f"{diff} {unit}" if diff != 0 else None
        cards.append({
            'label':       label,
            'unit':        unit,
            'value':       val,
            'initial':     val_ini,
            'diff':        diff_str,
            'recorded_at': str(latest.get('recorded_at', '')),
        })

    # Histórico completo para gráficos
    history = [{
        'recorded_at': str(r.get('recorded_at', '')),
        'weight':   float(r['weight'])   if r.get('weight')   else None,
        'body_fat': float(r['body_fat']) if r.get('body_fat') else None,
        'waist':    float(r['waist'])    if r.get('waist')    else None,
        'arm':      float(r['arm'])      if r.get('arm')      else None,
        'leg':      float(r['leg'])      if r.get('leg')      else None,
        'chest':    float(r['chest'])    if r.get('chest')    else None,
    } for r in data]

    return {"measurements": cards, "history": history}


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

    # Suporta "data:image/jpeg;base64,XXX" ou base64 puro
    match = re.match(r"data:(image/\w+);base64,(.+)", body.photo_base64)
    if match:
        mime, b64_data = match.group(1), match.group(2)
    else:
        mime, b64_data = "image/jpeg", body.photo_base64

    ext = mime.split("/")[1]  # jpeg, png, webp
    if ext not in ("jpeg", "jpg", "png", "webp"):
        raise HTTPException(400, "Formato inválido. Use jpeg, png ou webp.")

    try:
        image_bytes = base64.b64decode(b64_data)
    except Exception:
        raise HTTPException(400, "Base64 inválido")

    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(400, "Imagem muito grande. Máximo 10MB.")

    filename = f"{user_id}_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    photo_url = f"{BASE_URL}/uploads/photos/{filename}"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO progress_photos (user_id, photo_url, label, recorded_at) VALUES (%s,%s,%s,%s)",
        (user_id, photo_url, body.label, body.recorded_at)
    )
    conn.commit()
    photo_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"id": photo_id, "photo_url": photo_url, "message": "Foto adicionada com sucesso."}


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
