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
           JOIN users u ON u.id_user = n.user_id
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
           JOIN users u ON u.id_user = n.user_id
           WHERE nn.user_id=%s ORDER BY nn.updated_at DESC LIMIT 1""",
        (user_id,)
    )
    note = cursor.fetchone()
    cursor.close(); conn.close()
    if not note:
        raise HTTPException(404, "Nenhum recado encontrado")
    return note


@app.get("/nutrition/plans/all")
def list_all_nutrition_plans(authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT np.id, np.user_id, u.name as user_name, np.name, np.goal_calories,
              np.goal_protein_g, np.goal_carbs_g, np.goal_fat_g, np.water_goal_ml,
              np.active, np.valid_from, np.valid_until, np.created_at,
              un.name as nutritionist_name, n.crn
           FROM nutrition_plans np
           JOIN users u ON u.id_user = np.user_id
           JOIN nutritionists n ON n.id = np.nutritionist_id
           JOIN users un ON un.id_user = n.user_id
           ORDER BY np.created_at DESC"""
    )
    plans = cursor.fetchall()
    cursor.close(); conn.close()
    return {"plans": plans, "total": len(plans)}


from typing import Optional

class NutritionPlanInput(BaseModel):
    user_id: int
    nutritionist_id: int
    name: str
    goal_calories: int
    goal_protein_g: float
    goal_carbs_g: float
    goal_fat_g: float
    water_goal_ml: int = 2000
    valid_from: date
    valid_until: date
    active: bool = True

class UpdateNutritionPlan(BaseModel):
    name: Optional[str] = None
    goal_calories: Optional[int] = None
    goal_protein_g: Optional[float] = None
    goal_carbs_g: Optional[float] = None
    goal_fat_g: Optional[float] = None
    water_goal_ml: Optional[int] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    active: Optional[bool] = None

class MealInput(BaseModel):
    name: str
    time_label: Optional[str] = None

class UpdateMeal(BaseModel):
    name: Optional[str] = None
    time_label: Optional[str] = None

class MealItemInput(BaseModel):
    name: str
    quantity_g: Optional[float] = None
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

class UpdateMealItem(BaseModel):
    name: Optional[str] = None
    quantity_g: Optional[float] = None
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

class NoteInput(BaseModel):
    user_id: int
    nutritionist_id: int
    message: str


@app.post("/nutrition/plans", status_code=201)
def create_nutrition_plan(body: NutritionPlanInput, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    try:
        if body.active:
            cursor.execute(
                "UPDATE nutrition_plans SET active=0 WHERE user_id=%s AND active=1",
                (body.user_id,)
            )
        cursor.execute(
            """INSERT INTO nutrition_plans
               (user_id, nutritionist_id, name, goal_calories, goal_protein_g,
                goal_carbs_g, goal_fat_g, water_goal_ml, valid_from, valid_until, active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (body.user_id, body.nutritionist_id, body.name, body.goal_calories,
             body.goal_protein_g, body.goal_carbs_g, body.goal_fat_g, body.water_goal_ml,
             body.valid_from, body.valid_until, int(body.active))
        )
        plan_id = cursor.lastrowid
        conn.commit()
        return {"id": plan_id, "message": "Plano criado com sucesso."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        cursor.close(); conn.close()


@app.post("/nutrition/admin/plans/{plan_id}/update")
def admin_update_plan(plan_id: int, body: UpdateNutritionPlan, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE nutrition_plans SET {set_clause} WHERE id=%s", (*fields.values(), plan_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Plano atualizado com sucesso."}


@app.post("/nutrition/admin/plans/{plan_id}/delete")
def admin_delete_plan(plan_id: int, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM nutrition_plans WHERE id=%s", (plan_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close(); conn.close()
    if not deleted:
        raise HTTPException(404, "Plano não encontrado")
    return {"message": "Plano removido com sucesso."}


@app.post("/nutrition/admin/plans/{plan_id}/meals", status_code=201)
def admin_create_meal(plan_id: int, body: MealInput, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as cnt FROM meals WHERE plan_id=%s", (plan_id,))
    sort_order = cursor.fetchone()["cnt"] + 1
    cursor.execute(
        "INSERT INTO meals (plan_id, name, time_label, sort_order) VALUES (%s,%s,%s,%s)",
        (plan_id, body.name, body.time_label, sort_order)
    )
    conn.commit()
    meal_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"meal_id": meal_id}


@app.post("/nutrition/admin/meals/{meal_id}/update")
def admin_update_meal(meal_id: int, body: UpdateMeal, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE meals SET {set_clause} WHERE id=%s", (*fields.values(), meal_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Refeição atualizada com sucesso."}


@app.post("/nutrition/admin/meals/{meal_id}/delete")
def admin_delete_meal(meal_id: int, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meals WHERE id=%s", (meal_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close(); conn.close()
    if not deleted:
        raise HTTPException(404, "Refeição não encontrada")
    return {"message": "Refeição removida com sucesso."}


@app.post("/nutrition/admin/meals/{meal_id}/items", status_code=201)
def admin_create_meal_item(meal_id: int, body: MealItemInput, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as cnt FROM meal_items WHERE meal_id=%s", (meal_id,))
    sort_order = cursor.fetchone()["cnt"] + 1
    cursor.execute(
        "INSERT INTO meal_items (meal_id, name, quantity_g, calories, protein_g, carbs_g, fat_g, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (meal_id, body.name, body.quantity_g, body.calories, body.protein_g, body.carbs_g, body.fat_g, sort_order)
    )
    conn.commit()
    item_id = cursor.lastrowid
    cursor.close(); conn.close()
    return {"item_id": item_id}


@app.post("/nutrition/admin/items/{item_id}/update")
def admin_update_meal_item(item_id: int, body: UpdateMealItem, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE meal_items SET {set_clause} WHERE id=%s", (*fields.values(), item_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Item atualizado com sucesso."}


@app.post("/nutrition/admin/items/{item_id}/delete")
def admin_delete_meal_item(item_id: int, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meal_items WHERE id=%s", (item_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close(); conn.close()
    if not deleted:
        raise HTTPException(404, "Item não encontrado")
    return {"message": "Item removido com sucesso."}


@app.post("/nutrition/admin/notes", status_code=201)
def admin_create_note(body: NoteInput, authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO nutritionist_notes (user_id, nutritionist_id, message)
           VALUES (%s,%s,%s)
           ON DUPLICATE KEY UPDATE message=%s, updated_at=NOW()""",
        (body.user_id, body.nutritionist_id, body.message, body.message)
    )
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Recado salvo com sucesso."}


@app.get("/nutrition/history")
def get_history(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT np.id, np.name, np.valid_from, np.valid_until, np.active, u.name as nutritionist
           FROM nutrition_plans np
           JOIN nutritionists n ON n.id = np.nutritionist_id
           JOIN users u ON u.id_user = n.user_id
           WHERE np.user_id=%s ORDER BY np.created_at DESC""",
        (user_id,)
    )
    plans = cursor.fetchall()
    cursor.close(); conn.close()
    return {"plans": plans}
