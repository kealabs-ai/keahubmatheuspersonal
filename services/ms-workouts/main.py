from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
import sys, os, jwt
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
DAY_OF_WEEK_MAP = {"SEG": 1, "TER": 2, "QUA": 3, "QUI": 4, "SEX": 5, "SAB": 6, "DOM": 7}


def get_user_id(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(401, "Token inválido")


def require_admin(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload["sub"]
        role    = payload.get("role", "student")
    except Exception:
        raise HTTPException(401, "Token inválido")
    if role not in ("admin", "trainer"):
        raise HTTPException(403, "Acesso restrito")
    return user_id


# ── Models ──────────────────────────────────────────────

class CreateTemplate(BaseModel):
    name: str
    goal: str
    description: Optional[str] = None
    level: Optional[str] = "Iniciante"
    gender: Optional[str] = "masculino"
    months: Optional[int] = None

class UpdateTemplate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    description: Optional[str] = None
    level: Optional[str] = None
    active: Optional[bool] = None
    gender: Optional[str] = None
    months: Optional[int] = None

class CreateTemplateDay(BaseModel):
    name: str
    day_of_week: str
    duration_min: Optional[int] = None
    is_rest: bool = False

class UpdateTemplateDay(BaseModel):
    name: Optional[str] = None
    week_day: Optional[int] = None
    duration_min: Optional[int] = None
    is_rest: Optional[bool] = None

class CreateExercise(BaseModel):
    name: str
    sets: Optional[int] = None
    reps: Optional[str] = None
    rest_seconds: Optional[int] = None
    muscle_group: Optional[str] = None
    video_url: Optional[str] = None
    notes: Optional[str] = None

class UpdateExercise(BaseModel):
    name: Optional[str] = None
    sets: Optional[int] = None
    reps: Optional[str] = None
    rest_seconds: Optional[int] = None
    muscle_group: Optional[str] = None
    video_url: Optional[str] = None
    notes: Optional[str] = None

class CreateCycle(BaseModel):
    user_id: int
    template_id: int
    plan_name: str
    valid_from: date
    valid_until: Optional[date] = None  # se omitido, valid_from + 60 dias

class StartLog(BaseModel):
    day_id: int
    training: Optional[str] = None

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


# ── Templates (admin/trainer) ────────────────────────────

@app.post("/workouts/templates", status_code=201)
def create_template(body: CreateTemplate, authorization: str = Header(...)):
    trainer_id = require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO workout_templates (trainer_id, name, goal, description, level, gender, months) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (trainer_id, body.name, body.goal, body.description, body.level, body.gender, body.months)
        )
        conn.commit()
        template_id = cursor.lastrowid
        return {"template_id": template_id}
    finally:
        cursor.close(); conn.close()


@app.get("/workouts/templates")
def list_templates(authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT t.id, t.name, t.goal, t.description, t.level, t.gender, t.months, t.active, u.name as trainer_name, t.created_at
               FROM workout_templates t JOIN users u ON u.id_user = t.trainer_id
               ORDER BY t.months ASC, t.id ASC"""
        )
        templates = cursor.fetchall()
        return {"templates": templates, "total": len(templates)}
    finally:
        cursor.close(); conn.close()


@app.post("/workouts/templates/{template_id}/update")
def update_template(template_id: int, body: UpdateTemplate, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Inclui campos com valor None explicitamente definido (exceto campos não enviados)
        # months pode ser 0 ou None (remover limite), por isso usa model_dump con exclude_unset=False
        fields = {k: v for k, v in body.model_dump().items() if v is not None or k == 'months'}
        # Remove campos que não foram enviados na requisição
        sent   = {k: v for k, v in fields.items() if k in body.model_fields_set}
        if not sent:
            return {"message": "Nenhum campo para atualizar"}
        set_clause = ", ".join(f"{k}=%s" for k in sent)
        cursor.execute(f"UPDATE workout_templates SET {set_clause} WHERE id=%s", (*sent.values(), template_id))
        conn.commit()
        return {"message": "Template atualizado com sucesso."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close(); conn.close()


@app.post("/workouts/templates/{template_id}/delete")
def delete_template(template_id: int, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM workout_templates WHERE id=%s", (template_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(404, "Template não encontrado")
        return {"message": "Template removido com sucesso."}
    finally:
        cursor.close(); conn.close()


# ── Template Days (admin/trainer) ────────────────────────

@app.post("/workouts/templates/{template_id}/days", status_code=201)
def create_template_day(template_id: int, body: CreateTemplateDay, authorization: str = Header(...)):
    require_admin(authorization)
    week_day = DAY_OF_WEEK_MAP.get(body.day_of_week.upper())
    if not week_day:
        raise HTTPException(400, f"day_of_week inválido. Use: {list(DAY_OF_WEEK_MAP.keys())}")
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM workout_template_days WHERE template_id=%s", (template_id,))
        sort_order = cursor.fetchone()["cnt"] + 1
        cursor.execute(
            "INSERT INTO workout_template_days (template_id, week_day, name, duration_min, is_rest, sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
            (template_id, week_day, body.name, body.duration_min, body.is_rest, sort_order)
        )
        conn.commit()
        day_id = cursor.lastrowid
        return {"day_id": day_id}
    finally:
        cursor.close(); conn.close()


@app.get("/workouts/templates/{template_id}/days")
def get_template_days(template_id: int, authorization: str = Header(...)):
    get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM workout_template_days WHERE template_id=%s ORDER BY sort_order",
        (template_id,)
    )
    days = cursor.fetchall()
    cursor.close(); conn.close()
    return {"days": days}


@app.post("/workouts/template-days/{day_id}/update")
def update_template_day(day_id: int, body: UpdateTemplateDay, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE workout_template_days SET {set_clause} WHERE id=%s", (*fields.values(), day_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Dia atualizado com sucesso."}


@app.post("/workouts/template-days/{day_id}/delete")
def delete_template_day(day_id: int, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM workout_template_days WHERE id=%s", (day_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(404, "Dia não encontrado")
        return {"message": "Dia removido com sucesso."}
    finally:
        cursor.close(); conn.close()


# ── Exercises (admin/trainer) ────────────────────────────

@app.post("/workouts/template-days/{day_id}/exercises", status_code=201)
def create_exercise(day_id: int, body: CreateExercise, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM exercises WHERE day_id=%s", (day_id,))
        sort_order = cursor.fetchone()["cnt"] + 1
        cursor.execute(
            "INSERT INTO exercises (day_id, name, muscle_group, sets, reps, rest_seconds, video_url, notes, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (day_id, body.name, body.muscle_group, body.sets, body.reps, body.rest_seconds, body.video_url, body.notes, sort_order)
        )
        conn.commit()
        exercise_id = cursor.lastrowid
        return {"exercise_id": exercise_id}
    finally:
        cursor.close(); conn.close()


@app.get("/workouts/template-days/{day_id}/exercises")
def get_day_exercises(day_id: int, authorization: str = Header(...)):
    get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM workout_template_days WHERE id=%s", (day_id,))
        day = cursor.fetchone()
        if not day:
            raise HTTPException(404, "Dia não encontrado")
        cursor.execute("SELECT * FROM exercises WHERE day_id=%s ORDER BY sort_order", (day_id,))
        day["exercises"] = cursor.fetchall()
        return day
    finally:
        cursor.close(); conn.close()


@app.post("/workouts/exercises/{exercise_id}/update")
def update_exercise(exercise_id: int, body: UpdateExercise, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        if not fields:
            return {"message": "Nenhum campo para atualizar"}
        set_clause = ", ".join(f"{k}=%s" for k in fields)
        cursor.execute(f"UPDATE exercises SET {set_clause} WHERE id=%s", (*fields.values(), exercise_id))
        conn.commit()
        return {"message": "Exercício atualizado com sucesso."}
    finally:
        cursor.close(); conn.close()


@app.post("/workouts/exercises/{exercise_id}/delete")
def delete_exercise(exercise_id: int, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM exercises WHERE id=%s", (exercise_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(404, "Exercício não encontrado")
        return {"message": "Exercício removido com sucesso."}
    finally:
        cursor.close(); conn.close()


# ── Cycles (admin/trainer) ───────────────────────────────

@app.post("/workouts/cycles", status_code=201)
def create_cycle(body: CreateCycle, authorization: str = Header(...)):
    trainer_id = require_admin(authorization)
    valid_until = body.valid_until or (body.valid_from + timedelta(days=60))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # desativa ciclo anterior do aluno (NULL para não violar UNIQUE KEY)
        cursor.execute("UPDATE workout_cycles SET active=NULL WHERE user_id=%s AND active=1", (body.user_id,))

        # calcula próximo cycle_number
        cursor.execute("SELECT COUNT(*) as cnt FROM workout_cycles WHERE user_id=%s", (body.user_id,))
        cycle_number = cursor.fetchone()["cnt"] + 1

        cursor.execute(
            "INSERT INTO workout_cycles (user_id, cycle_number, valid_from, valid_until, active) VALUES (%s,%s,%s,%s,1)",
            (body.user_id, cycle_number, body.valid_from, valid_until)
        )
        conn.commit()
        cycle_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO workout_plans (cycle_id, template_id, trainer_id, name) VALUES (%s,%s,%s,%s)",
            (cycle_id, body.template_id, trainer_id, body.plan_name)
        )
        conn.commit()
        plan_id = cursor.lastrowid
        return {"cycle_id": cycle_id, "plan_id": plan_id, "cycle_number": cycle_number, "valid_until": valid_until.isoformat()}
    except Exception as e:
        conn.rollback(); raise HTTPException(500, str(e))
    finally:
        cursor.close(); conn.close()


@app.get("/workouts/cycles/user/{user_id}")
def get_user_cycles(user_id: int, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT wc.id, wc.cycle_number, wc.valid_from, wc.valid_until, wc.active,
                      wp.id as plan_id, wp.name as plan_name,
                      wt.name as template_name, wt.goal, wt.level
               FROM workout_cycles wc
               JOIN workout_plans wp ON wp.cycle_id = wc.id
               JOIN workout_templates wt ON wt.id = wp.template_id
               WHERE wc.user_id=%s ORDER BY wc.cycle_number DESC""",
            (user_id,)
        )
        cycles = cursor.fetchall()
        return {"cycles": cycles, "total": len(cycles)}
    finally:
        cursor.close(); conn.close()


# ── Consultas do aluno ───────────────────────────────────

@app.get("/workouts/plan")
def get_active_plan(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        # Busca o objetivo, gênero e data de cadastro do usuário
        cursor.execute("SELECT goal, gender, created_at FROM users WHERE id_user=%s", (user_id,))
        user_row = cursor.fetchone()
        user_goal   = user_row["goal"]   if user_row else None
        user_gender = user_row["gender"] if user_row else None

        # Calcula meses desde o cadastro do aluno
        months_since_register = 0
        if user_row and user_row["created_at"]:
            created  = user_row["created_at"]
            ref_date = created.date() if hasattr(created, 'date') else created
            months_since_register = (date.today() - ref_date).days // 30

        # Helper: seleciona o template mais específico para o aluno
        def pick_template(cursor, goal_filter, gender_filter):
            where  = ["active = 1"]
            params = []
            if goal_filter:
                where.append("goal = %s"); params.append(goal_filter)
            if gender_filter:
                where.append("(gender = %s OR gender IS NULL)"); params.append(gender_filter)
            where.append("(months IS NULL OR months >= %s)"); params.append(months_since_register)

            where_sql = " AND ".join(where)
            cursor.execute(
                f"""SELECT id as template_id, name as template_name, goal, level, gender, months
                    FROM workout_templates
                    WHERE {where_sql}
                    ORDER BY
                      CASE WHEN months IS NULL THEN 1 ELSE 0 END ASC,
                      months ASC, id ASC
                    LIMIT 1""",
                params
            )
            return cursor.fetchone()

        # Busca o template via ciclo ativo do aluno
        cursor.execute(
            """SELECT wt.id as template_id, wt.name as template_name, wt.goal, wt.level, wt.gender, wt.months
               FROM workout_cycles wc
               JOIN workout_plans wp ON wp.cycle_id = wc.id
               JOIN workout_templates wt ON wt.id = wp.template_id
               WHERE wc.user_id=%s AND wc.active=1
               LIMIT 1""",
            (user_id,)
        )
        plan = cursor.fetchone()

        # Seleção automática por regras
        if not plan: plan = pick_template(cursor, user_goal, user_gender)
        if not plan and user_goal: plan = pick_template(cursor, user_goal, None)
        if not plan and user_gender: plan = pick_template(cursor, None, user_gender)
        if not plan: plan = pick_template(cursor, None, None)

        # Último recurso
        if not plan:
            cursor.execute(
                "SELECT id as template_id, name as template_name, goal, level, gender, months FROM workout_templates WHERE active=1 ORDER BY id ASC LIMIT 1"
            )
            plan = cursor.fetchone()

        if not plan:
            raise HTTPException(404, "Nenhum plano ativo encontrado")

        cursor.execute(
            "SELECT id, week_day, name, duration_min, is_rest FROM workout_template_days WHERE template_id=%s ORDER BY sort_order",
            (plan["template_id"],)
        )
        days = cursor.fetchall()

        cursor.execute(
            """SELECT DISTINCT wtd.week_day FROM workout_logs wl
               JOIN workout_template_days wtd ON wtd.id = wl.day_id
               WHERE wl.user_id=%s AND wl.completed=1
               AND YEARWEEK(wl.finished_at, 1) = YEARWEEK(NOW(), 1)""",
            (user_id,)
        )
        completed_days = {r["week_day"] for r in cursor.fetchall()}

        for d in days:
            cursor.execute("SELECT COUNT(*) as cnt FROM exercises WHERE day_id=%s", (d["id"],))
            d["exercises_count"] = cursor.fetchone()["cnt"]
            d["status"] = day_status(d["week_day"], completed_days)

        plan["days"]      = days
        plan["user_goal"] = user_goal
        return {"plan": plan}
    finally:
        cursor.close(); conn.close()


@app.get("/workouts/exercises/all")
def get_all_exercises(authorization: str = Header(...)):
    get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT e.id, e.name, e.muscle_group, e.sets, e.reps, e.rest_seconds, e.video_url,
                      wtd.name as day_name, wt.name as template_name, wt.goal
               FROM exercises e
               JOIN workout_template_days wtd ON wtd.id = e.day_id
               JOIN workout_templates wt ON wt.id = wtd.template_id
               ORDER BY wt.id, wtd.sort_order, e.sort_order"""
        )
        exercises = cursor.fetchall()
        return {"exercises": exercises, "total": len(exercises)}
    finally:
        cursor.close(); conn.close()


# ── Logs ─────────────────────────────────────────────────

@app.post("/workouts/logs", status_code=201)
def start_log(body: StartLog, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    started_at = datetime.utcnow()
    try:
        cursor.execute(
            "INSERT INTO workout_logs (user_id, day_id, started_at, training) VALUES (%s,%s,%s,%s)",
            (user_id, body.day_id, started_at, body.training)
        )
        conn.commit()
        log_id = cursor.lastrowid
        return {"log_id": log_id, "started_at": started_at.isoformat() + "Z"}
    finally:
        cursor.close(); conn.close()


@app.post("/workouts/logs/{log_id}/finish")
def finish_log(log_id: int, body: FinishLog, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    finished_at = datetime.utcnow()
    try:
        cursor.execute(
            "UPDATE workout_logs SET finished_at=%s, completed=%s WHERE id=%s AND user_id=%s",
            (finished_at, body.completed, log_id, user_id)
        )
        conn.commit()
        return {"message": "Treino finalizado com sucesso."}
    finally:
        cursor.close(); conn.close()


@app.post("/workouts/logs/{log_id}/exercises")
def log_exercises(log_id: int, body: ExerciseLogsInput, authorization: str = Header(...)):
    get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        for ex in body.exercises:
            cursor.execute(
                """INSERT INTO exercise_logs (log_id, exercise_id, weight_kg, reps_done, sets_done, completed)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE weight_kg=%s, reps_done=%s, sets_done=%s, completed=%s""",
                (log_id, ex.exercise_id, ex.weight_kg, ex.reps_done, ex.sets_done, ex.completed,
                 ex.weight_kg, ex.reps_done, ex.sets_done, ex.completed)
            )
        conn.commit()
        return {"message": "Exercícios registrados com sucesso."}
    finally:
        cursor.close(); conn.close()


@app.get("/workouts/logs/history")
def get_history(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT wl.id, wl.training, wtd.name as day_name, wt.name as template_name,
                      wl.started_at, wl.finished_at, wl.completed
               FROM workout_logs wl
               JOIN workout_template_days wtd ON wtd.id = wl.day_id
               JOIN workout_templates wt ON wt.id = wtd.template_id
               WHERE wl.user_id=%s ORDER BY wl.started_at DESC LIMIT 50""",
            (user_id,)
        )
        logs = cursor.fetchall()
        return {"history": logs}
    finally:
        cursor.close(); conn.close()


@app.get("/workouts/streak")
def get_streak(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT DATE(finished_at) as day FROM workout_logs WHERE user_id=%s AND completed=1 ORDER BY day DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) as total FROM workout_logs WHERE user_id=%s AND completed=1", (user_id,))
        total = cursor.fetchone()["total"]
        cursor.execute(
            """SELECT COUNT(DISTINCT DATE(finished_at)) as cnt FROM workout_logs
               WHERE user_id=%s AND completed=1 AND YEARWEEK(finished_at,1)=YEARWEEK(NOW(),1)""",
            (user_id,)
        )
        this_week = cursor.fetchone()["cnt"]

        streak = 0
        prev = None
        for r in rows:
            d = r["day"]
            if prev is None: streak = 1
            elif (prev - d).days == 1: streak += 1
            else: break
            prev = d

        return {
            "current_streak": streak,
            "trainings_this_week": this_week,
            "total_trainings": total
        }
    finally:
        cursor.close(); conn.close()
