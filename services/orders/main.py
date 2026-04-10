from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from decimal import Decimal
from typing import List, Optional
import sys, os, jwt
sys.path.append('..')
from database import get_db
import uuid

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

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "body": str(exc.body)})

class OrderItem(BaseModel):
    plan_name: str
    plan_price: Decimal
    plan_frequency: str
    quantity: int = 1

class Order(BaseModel):
    id_user: int
    items: List[OrderItem]
    payment_method: str
    id_coupon: Optional[int] = None

@app.post("/orders")
def create_order(order: Order):
    conn = get_db()
    cursor = conn.cursor()
    try:
        subtotal = sum(item.plan_price * item.quantity for item in order.items)
        discount = Decimal(0)
        
        if order.id_coupon:
            cursor.execute("SELECT * FROM coupons WHERE id_coupon=%s AND is_active=1", (order.id_coupon,))
            coupon = cursor.fetchone()
            if coupon:
                if coupon[3] == 'percent':
                    discount = subtotal * (coupon[4] / 100)
                else:
                    discount = coupon[4]
        
        total = subtotal - discount
        order_number = str(uuid.uuid4())[:8].upper()
        
        cursor.execute("""INSERT INTO orders (order_number, id_user, subtotal, discount_amount, 
                         total_amount, payment_method, id_coupon) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                      (order_number, order.id_user, subtotal, discount, total, order.payment_method, order.id_coupon))
        order_id = cursor.lastrowid
        
        for item in order.items:
            cursor.execute("""INSERT INTO order_items (id_order, plan_name, plan_price, plan_frequency, quantity) 
                             VALUES (%s,%s,%s,%s,%s)""",
                          (order_id, item.plan_name, item.plan_price, item.plan_frequency, item.quantity))
        
        conn.commit()
        return {"order_id": order_id, "order_number": order_number, "total": float(total)}
    finally:
        cursor.close()
        conn.close()

@app.get("/orders")
def get_all_orders(authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT o.*, u.name as user_name, u.email as user_email
           FROM orders o
           JOIN users u ON u.id_user = o.id_user
           ORDER BY o.created_at DESC"""
    )
    orders = cursor.fetchall()
    for order in orders:
        cursor.execute("SELECT * FROM order_items WHERE id_order=%s", (order["id_order"],))
        order["items"] = cursor.fetchall()
    cursor.close(); conn.close()
    return {"orders": orders, "total": len(orders)}


@app.get("/orders/user/{user_id}")
def get_user_orders(user_id: int):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE id_user=%s ORDER BY created_at DESC", (user_id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return orders


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT o.*, u.name as user_name, u.email as user_email
           FROM orders o
           JOIN users u ON u.id_user = o.id_user
           ORDER BY o.created_at DESC"""
    )
    orders = cursor.fetchall()
    for order in orders:
        cursor.execute("SELECT * FROM order_items WHERE id_order=%s", (order["id_order"],))
        order["items"] = cursor.fetchall()
    cursor.close(); conn.close()
    return {"orders": orders, "total": len(orders)}
