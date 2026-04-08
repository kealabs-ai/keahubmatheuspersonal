from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import sys, os, jwt
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")

DAY_OF_WEEK_MAP = {"SEG": 1, "TER": 2, "QUA": 3, "QUI": 4, "SEX": 5, "SAB": 6, "DOM": 7}


def get_user_id(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(401, "Token inválido")


# ── Models ──────────────────────────────────────────────

class CreatePlan(BaseModel):
    name: str
    description: Optional[str] = None
    goal: Optional[str] = None
    gender: Optional[str] = None

class CreateDay(BaseModel):
    name: str
    day_of_week: str
    duration_min: Optional[int] = None
    is_rest: bool = False

class CreateExercise(BaseModel):
    name: str
    sets: Optional[int] = None
    reps: Optional[str] = None
    rest_seconds: Optional[int] = None
    muscle_group: Optional[str] = None
    video_url: Optional[str] = None

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


# ── Helpers ─────────────────────────────────────────────

def day_status(week_day: int, completed_days: set) -> str:
    today_weekday = date.today().isoweekday()
    if week_day in completed_days:
        return "done"
    if week_day == today_weekday:
        return "today"
    return "pending"


# ── Onboarding ──────────────────────────────────────────

@app.post("/workouts/plans", status_code=201)
def create_plan(body: CreatePlan, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("UPDATE workout_plans SET active=0 WHERE user_id=%s", (user_id,))
    cursor.execute("SELECT id_user FROM users WHERE role='trainer' AND active=1 LIMIT 1")
    trainer = cursor.fetchone()
    trainer_id = trainer["id_user"] if trainer else user_id
    cursor.execute(
        "INSERT INTO workout_plans (user_id, trainer_id, name, week_start, active) VALUES (%s,%s,%s,%s,1)",
        (user_id, trainer_id, body.name, date.today())
    )
    conn.commit()
    plan_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"plan_id": plan_id}


@app.post("/workouts/plans/{plan_id}/days", status_code=201)
def create_day(plan_id: int, body: CreateDay, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM workout_plans WHERE id=%s AND user_id=%s", (plan_id, user_id))
    if not cursor.fetchone():
        cursor.close(); conn.close()
        raise HTTPException(403, "Plano não encontrado ou sem permissão")
    week_day = DAY_OF_WEEK_MAP.get(body.day_of_week.upper())
    if not week_day:
        cursor.close(); conn.close()
        raise HTTPException(400, f"day_of_week inválido. Use: {list(DAY_OF_WEEK_MAP.keys())}")
    cursor.execute("SELECT COUNT(*) as cnt FROM workout_days WHERE plan_id=%s", (plan_id,))
    sort_order = cursor.fetchone()["cnt"] + 1
    cursor.execute(
        "INSERT INTO workout_days (plan_id, week_day, name, duration_min, is_rest, sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
        (plan_id, week_day, body.name, body.duration_min, body.is_rest, sort_order)
    )
    conn.commit()
    day_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"day_id": day_id}


@app.post("/workouts/days/{day_id}/exercises", status_code=201)
def create_exercise(day_id: int, body: CreateExercise, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT wd.id FROM workout_days wd
           JOIN workout_plans wp ON wp.id = wd.plan_id
           WHERE wd.id=%s AND wp.user_id=%s""",
        (day_id, user_id)
    )
    if not cursor.fetchone():
        cursor.close(); conn.close()
        raise HTTPException(403, "Dia não encontrado ou sem permissão")
    cursor.execute("SELECT COUNT(*) as cnt FROM exercises WHERE day_id=%s", (day_id,))
    sort_order = cursor.fetchone()["cnt"] + 1
    cursor.execute(
        "INSERT INTO exercises (day_id, name, muscle_group, sets, reps, rest_seconds, video_url, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (day_id, body.name, body.muscle_group, body.sets, body.reps, body.rest_seconds, body.video_url, sort_order)
    )
    conn.commit()
    exercise_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"exercise_id": exercise_id}


# ── Consultas ────────────────────────────────────────────

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


@app.post("/workouts/logs/{log_id}/finish")
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
