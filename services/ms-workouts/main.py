from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import sys, os, jwt
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

class StartLog(BaseModel):
    day_id: int

class FinishLog(BaseModel):
    completed: bool = True

class ExerciseLogItem(BaseModel):
    exercise_id: int
    weight_kg: Optional[float] = None
    sets_done: Optional[int] = None
    reps_done: Optional[int] = None
    completed: bool = False

class ExerciseLogsInput(BaseModel):
    exercises: List[ExerciseLogItem]

def day_status(week_day: int, completed_days: set) -> str:
    today_weekday = date.today().isoweekday()  # 1=Mon...7=Sun
    if week_day in completed_days:
        return "done"
    if week_day == today_weekday:
        return "today"
    return "pending"

@app.get("/workouts/plan")
def get_active_plan(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM workout_plans WHERE user_id=%s AND active=1 ORDER BY created_at DESC LIMIT 1", (user_id,))
    plan = cursor.fetchone()
    if not plan:
        cursor.close(); conn.close()
        raise HTTPException(404, "Nenhum plano ativo encontrado")
    cursor.execute("SELECT id, week_day, name, duration_min, is_rest FROM workout_days WHERE plan_id=%s ORDER BY sort_order", (plan["id"],))
    days = cursor.fetchall()
    # Buscar dias concluídos esta semana
    cursor.execute("""SELECT DISTINCT wd.week_day FROM workout_logs wl
                      JOIN workout_days wd ON wd.id = wl.day_id
                      WHERE wl.user_id=%s AND wl.completed=1
                      AND YEARWEEK(wl.finished_at, 1) = YEARWEEK(NOW(), 1)""", (user_id,))
    completed_days = {r["week_day"] for r in cursor.fetchall()}
    for d in days:
        cursor.execute("SELECT COUNT(*) as cnt FROM exercises WHERE day_id=%s", (d["id"],))
        d["exercises_count"] = cursor.fetchone()["cnt"]
        d["status"] = day_status(d["week_day"], completed_days)
    cursor.close(); conn.close()
    plan["days"] = days
    return {"plan": plan}

@app.get("/workouts/plan/{plan_id}/days")
def get_plan_days(plan_id: int, authorization: str = Header(...)):
    get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM workout_days WHERE plan_id=%s ORDER BY sort_order", (plan_id,))
    days = cursor.fetchall()
    cursor.close(); conn.close()
    return {"days": days}

@app.get("/workouts/days/{day_id}/exercises")
def get_day_exercises(day_id: int, authorization: str = Header(...)):
    get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM workout_days WHERE id=%s", (day_id,))
    day = cursor.fetchone()
    if not day:
        cursor.close(); conn.close()
        raise HTTPException(404, "Dia não encontrado")
    cursor.execute("SELECT * FROM exercises WHERE day_id=%s ORDER BY sort_order", (day_id,))
    day["exercises"] = cursor.fetchall()
    cursor.close(); conn.close()
    return day

@app.post("/workouts/logs", status_code=201)
def start_log(body: StartLog, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    started_at = datetime.utcnow()
    cursor.execute("INSERT INTO workout_logs (user_id, day_id, started_at) VALUES (%s,%s,%s)",
                   (user_id, body.day_id, started_at))
    conn.commit()
    log_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"log_id": log_id, "started_at": started_at.isoformat() + "Z"}

@app.put("/workouts/logs/{log_id}")
def finish_log(log_id: int, body: FinishLog, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    finished_at = datetime.utcnow()
    cursor.execute("UPDATE workout_logs SET finished_at=%s, completed=%s WHERE id=%s AND user_id=%s",
                   (finished_at, body.completed, log_id, user_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Treino finalizado com sucesso."}

@app.post("/workouts/logs/{log_id}/exercises")
def log_exercises(log_id: int, body: ExerciseLogsInput, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    for ex in body.exercises:
        cursor.execute("""INSERT INTO exercise_logs (log_id, exercise_id, weight_kg, reps_done, sets_done, completed)
                          VALUES (%s,%s,%s,%s,%s,%s)
                          ON DUPLICATE KEY UPDATE weight_kg=%s, reps_done=%s, sets_done=%s, completed=%s""",
                       (log_id, ex.exercise_id, ex.weight_kg, ex.reps_done, ex.sets_done, ex.completed,
                        ex.weight_kg, ex.reps_done, ex.sets_done, ex.completed))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Exercícios registrados com sucesso."}

@app.get("/workouts/logs/history")
def get_history(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT wl.id, wd.name, wl.started_at, wl.finished_at, wl.completed
                      FROM workout_logs wl JOIN workout_days wd ON wd.id = wl.day_id
                      WHERE wl.user_id=%s ORDER BY wl.started_at DESC LIMIT 50""", (user_id,))
    logs = cursor.fetchall()
    cursor.close(); conn.close()
    return {"history": logs}

@app.get("/workouts/streak")
def get_streak(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT DATE(finished_at) as day FROM workout_logs
                      WHERE user_id=%s AND completed=1 ORDER BY day DESC""", (user_id,))
    rows = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as total FROM workout_logs WHERE user_id=%s AND completed=1", (user_id,))
    total = cursor.fetchone()["total"]
    cursor.execute("""SELECT COUNT(DISTINCT DATE(finished_at)) as cnt FROM workout_logs
                      WHERE user_id=%s AND completed=1 AND YEARWEEK(finished_at,1)=YEARWEEK(NOW(),1)""", (user_id,))
    this_week = cursor.fetchone()["cnt"]
    cursor.execute("""SELECT DATEDIFF(MAX(DATE(finished_at)), MIN(DATE(created_at))) + 1 as days
                      FROM workout_logs WHERE user_id=%s AND completed=1""", (user_id,))
    days_active_row = cursor.fetchone()
    cursor.close(); conn.close()

    # Calcular streak atual
    streak = 0
    prev = None
    for r in rows:
        d = r["day"]
        if prev is None:
            streak = 1
        elif (prev - d).days == 1:
            streak += 1
        else:
            break
        prev = d

    return {
        "current_streak": streak,
        "longest_streak": streak,
        "trainings_this_week": this_week,
        "total_trainings": total,
        "days_active": days_active_row["days"] or 0
    }
