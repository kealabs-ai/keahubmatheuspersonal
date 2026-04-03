from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
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


class MealLogInput(BaseModel):
    meal_id: int
    consumed_at: date


@app.get("/nutrition/plan")
def get_active_plan(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT np.*, u.name as nutritionist_name, n.crn
           FROM nutrition_plans np
           JOIN nutritionists n ON n.id = np.nutritionist_id
           JOIN users u ON u.id = n.user_id
           WHERE np.user_id=%s AND np.active=1
           ORDER BY np.created_at DESC LIMIT 1""",
        (user_id,)
    )
    plan = cursor.fetchone()
    cursor.close(); conn.close()
    if not plan:
        raise HTTPException(404, "Nenhum plano ativo encontrado")
    return {"plan": {
        "id": plan["id"], "name": plan["name"],
        "goal_calories": plan["goal_calories"], "goal_protein_g": plan["goal_protein_g"],
        "goal_carbs_g": plan["goal_carbs_g"], "goal_fat_g": plan["goal_fat_g"],
        "water_goal_ml": plan["water_goal_ml"],
        "nutritionist": {"name": plan["nutritionist_name"], "crn": plan["crn"]}
    }}


@app.get("/nutrition/plan/{plan_id}/meals")
def get_plan_meals(plan_id: int, authorization: str = Header(...)):
    get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM meals WHERE plan_id=%s ORDER BY sort_order", (plan_id,))
    meals = cursor.fetchall()
    for meal in meals:
        cursor.execute("SELECT * FROM meal_items WHERE meal_id=%s ORDER BY sort_order", (meal["id"],))
        meal["items"] = cursor.fetchall()
    cursor.close(); conn.close()
    return {"meals": meals}


@app.get("/nutrition/today")
def get_today(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    today = date.today()
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, goal_calories FROM nutrition_plans WHERE user_id=%s AND active=1 ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    plan = cursor.fetchone()
    if not plan:
        cursor.close(); conn.close()
        raise HTTPException(404, "Nenhum plano ativo")
    cursor.execute("SELECT * FROM meals WHERE plan_id=%s ORDER BY sort_order", (plan["id"],))
    meals = cursor.fetchall()
    cursor.execute("SELECT meal_id FROM meal_logs WHERE user_id=%s AND consumed_at=%s", (user_id, today))
    consumed_ids = {r["meal_id"] for r in cursor.fetchall()}
    totals = {"calories_consumed": 0, "calories_goal": plan["goal_calories"], "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    result_meals = []
    for meal in meals:
        cursor.execute("SELECT * FROM meal_items WHERE meal_id=%s ORDER BY sort_order", (meal["id"],))
        items = cursor.fetchall()
        consumed = meal["id"] in consumed_ids
        cal = sum(i["calories"] or 0 for i in items)
        if consumed:
            totals["calories_consumed"] += cal
            totals["protein_g"] += sum(float(i["protein_g"] or 0) for i in items)
            totals["carbs_g"] += sum(float(i["carbs_g"] or 0) for i in items)
            totals["fat_g"] += sum(float(i["fat_g"] or 0) for i in items)
        result_meals.append({**meal, "consumed": consumed, "calories": cal, "items": items})
    cursor.close(); conn.close()
    return {"date": str(today), "meals": result_meals, "totals": totals}


@app.post("/nutrition/logs", status_code=201)
def log_meal(body: MealLogInput, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO meal_logs (user_id, meal_id, consumed_at) VALUES (%s,%s,%s)",
            (user_id, body.meal_id, body.consumed_at)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise HTTPException(409, "Refeição já marcada como consumida")
    finally:
        cursor.close(); conn.close()
    return {"message": "Refeição marcada como consumida."}


@app.post("/nutrition/logs/{meal_id}/delete")
def unlog_meal(meal_id: int, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM meal_logs WHERE user_id=%s AND meal_id=%s AND consumed_at=CURDATE()",
        (user_id, meal_id)
    )
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Refeição desmarcada."}


@app.get("/nutrition/note")
def get_note(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT nn.id, u.name as nutritionist, n.crn, nn.message, nn.updated_at
           FROM nutritionist_notes nn
           JOIN nutritionists n ON n.id = nn.nutritionist_id
           JOIN users u ON u.id = n.user_id
           WHERE nn.user_id=%s ORDER BY nn.updated_at DESC LIMIT 1""",
        (user_id,)
    )
    note = cursor.fetchone()
    cursor.close(); conn.close()
    if not note:
        raise HTTPException(404, "Nenhum recado encontrado")
    return note


@app.get("/nutrition/history")
def get_history(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT np.id, np.name, np.valid_from, np.valid_until, np.active, u.name as nutritionist
           FROM nutrition_plans np
           JOIN nutritionists n ON n.id = np.nutritionist_id
           JOIN users u ON u.id = n.user_id
           WHERE np.user_id=%s ORDER BY np.created_at DESC""",
        (user_id,)
    )
    plans = cursor.fetchall()
    cursor.close(); conn.close()
    return {"plans": plans}
