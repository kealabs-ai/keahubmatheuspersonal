from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from datetime import date
import sys
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Coupon(BaseModel):
    code: str
    description: str
    discount_type: str
    discount_value: Decimal
    valid_from: date
    valid_until: date
    usage_limit: int = None
    min_purchase_amount: Decimal = 0

@app.post("/coupons")
def create_coupon(coupon: Coupon):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""INSERT INTO coupons (code, description, discount_type, discount_value, 
                         valid_from, valid_until, usage_limit, min_purchase_amount) 
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                      (coupon.code, coupon.description, coupon.discount_type, coupon.discount_value,
                       coupon.valid_from, coupon.valid_until, coupon.usage_limit, coupon.min_purchase_amount))
        conn.commit()
        return {"id": cursor.lastrowid}
    finally:
        cursor.close()
        conn.close()

@app.get("/coupons/{code}")
def validate_coupon(code: str):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT * FROM coupons WHERE code=%s AND is_active=1 
                     AND valid_from <= CURDATE() AND valid_until >= CURDATE()""", (code,))
    coupon = cursor.fetchone()
    cursor.close()
    conn.close()
    if not coupon:
        raise HTTPException(404, "Coupon not found or expired")
    if coupon['usage_limit'] and coupon['usage_count'] >= coupon['usage_limit']:
        raise HTTPException(400, "Coupon usage limit reached")
    return coupon

@app.post("/coupons/{coupon_id}/use")
def use_coupon(coupon_id: int, user_id: int, order_id: str, discount_applied: Decimal):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""INSERT INTO coupon_usage (id_coupon, id_user, order_id, discount_applied) 
                         VALUES (%s,%s,%s,%s)""", (coupon_id, user_id, order_id, discount_applied))
        cursor.execute("UPDATE coupons SET usage_count = usage_count + 1 WHERE id_coupon=%s", (coupon_id,))
        conn.commit()
        return {"used": True}
    finally:
        cursor.close()
        conn.close()

@app.get("/coupons")
def list_coupons():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM coupons WHERE is_active=1")
    coupons = cursor.fetchall()
    cursor.close()
    conn.close()
    return coupons
