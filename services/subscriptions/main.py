from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
import sys
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Subscription(BaseModel):
    id_user: int
    plan_name: str
    plan_price: Decimal
    plan_frequency: str
    status: str = 'active'

@app.post("/subscriptions")
def create_subscription(sub: Subscription):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""INSERT INTO subscriptions (id_user, plan_name, plan_price, plan_frequency, status) 
                         VALUES (%s,%s,%s,%s,%s)""",
                      (sub.id_user, sub.plan_name, sub.plan_price, sub.plan_frequency, sub.status))
        conn.commit()
        return {"id": cursor.lastrowid}
    finally:
        cursor.close()
        conn.close()

@app.get("/subscriptions/user/{user_id}")
def get_user_subscriptions(user_id: int):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM subscriptions WHERE id_user=%s", (user_id,))
    subs = cursor.fetchall()
    cursor.close()
    conn.close()
    return subs

@app.post("/subscriptions/{sub_id}/update")
def update_subscription(sub_id: int, status: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET status=%s WHERE id_subscription=%s", (status, sub_id))
    conn.commit()
    updated = cursor.rowcount
    cursor.close()
    conn.close()
    return {"updated": updated}

@app.post("/subscriptions/{sub_id}/cancel")
def cancel_subscription(sub_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET status='cancelled' WHERE id_subscription=%s", (sub_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"cancelled": True}
