from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
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
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")


def get_user_id(authorization: str) -> int:
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(401, "Token inválido")


@app.get("/dashboard/summary")
def get_summary(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT name, plan, plan_renewal FROM users WHERE id_user=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close(); conn.close()
        raise HTTPException(404, "Usuário não encontrado")

    cursor.execute("""SELECT DATE(finished_at) as day FROM workout_logs
                      WHERE user_id=%s AND completed=1 ORDER BY day DESC""", (user_id,))
    rows = cursor.fetchall()
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

    cursor.execute("""SELECT COUNT(DISTINCT DATE(finished_at)) as cnt FROM workout_logs
                      WHERE user_id=%s AND completed=1 AND YEARWEEK(finished_at,1)=YEARWEEK(NOW(),1)""", (user_id,))
    trainings_week = cursor.fetchone()["cnt"]

    cursor.execute("""SELECT DATEDIFF(MAX(DATE(finished_at)), MIN(DATE(created_at))) + 1 as days
                      FROM workout_logs WHERE user_id=%s AND completed=1""", (user_id,))
    days_row = cursor.fetchone()
    days_active = days_row["days"] or 0

    cursor.execute("SELECT id FROM workout_plans WHERE user_id=%s AND active=1 ORDER BY created_at DESC LIMIT 1", (user_id,))
    plan_row = cursor.fetchone()
    week = []
    today_workout = None
    if plan_row:
        cursor.execute("""SELECT wd.id, wd.week_day, wd.name, wd.duration_min, wd.is_rest
                          FROM workout_days wd WHERE wd.plan_id=%s ORDER BY wd.sort_order""", (plan_row["id"],))
        days = cursor.fetchall()
        cursor.execute("""SELECT DISTINCT wd.week_day FROM workout_logs wl
                          JOIN workout_days wd ON wd.id = wl.day_id
                          WHERE wl.user_id=%s AND wl.completed=1
                          AND YEARWEEK(wl.finished_at,1)=YEARWEEK(NOW(),1)""", (user_id,))
        completed_days = {r["week_day"] for r in cursor.fetchall()}
        today_weekday = date.today().isoweekday()
        for d in days:
            if d["week_day"] in completed_days:
                status = "done"
            elif d["week_day"] == today_weekday:
                status = "today"
            elif d["is_rest"]:
                status = "rest"
            else:
                status = "pending"
            week.append({"week_day": d["week_day"], "name": d["name"], "status": status})
            if d["week_day"] == today_weekday and not d["is_rest"]:
                cursor.execute("SELECT COUNT(*) as cnt FROM exercises WHERE day_id=%s", (d["id"],))
                ex_count = cursor.fetchone()["cnt"]
                today_workout = {"day_id": d["id"], "name": d["name"],
                                 "duration_min": d["duration_min"], "exercises_count": ex_count}

    cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE user_id=%s AND read_at IS NULL", (user_id,))
    unread = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM user_badges WHERE user_id=%s", (user_id,))
    badges_earned = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) as cnt FROM badges", ())
    badges_total = cursor.fetchone()["cnt"]

    cursor.close(); conn.close()
    return {
        "user": {"name": user["name"], "plan": user["plan"], "plan_renewal": str(user["plan_renewal"]) if user["plan_renewal"] else None},
        "stats": {"streak": streak, "trainings_this_week": trainings_week, "days_active": days_active},
        "week": week,
        "today_workout": today_workout,
        "unread_notifications": unread,
        "badges_earned": badges_earned,
        "badges_total": badges_total
    }
