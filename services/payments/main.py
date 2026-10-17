from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional
from datetime import datetime
import sys, os, jwt
sys.path.append('..')
from database import get_db
import json

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


class Payment(BaseModel):
    id_order: int
    payment_method: str
    amount: Decimal
    installments: int = 1
    card_last_digits: Optional[str] = None
    card_brand: Optional[str] = None

@app.post("/payments")
def create_payment(payment: Payment):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""INSERT INTO payments (id_order, payment_method, amount, installments, 
                         card_last_digits, card_brand, payment_status) 
                         VALUES (%s,%s,%s,%s,%s,%s,'pending')""",
                      (payment.id_order, payment.payment_method, payment.amount, 
                       payment.installments, payment.card_last_digits, payment.card_brand))
        payment_id = cursor.lastrowid
        conn.commit()
        return {"payment_id": payment_id, "status": "pending"}
    finally:
        cursor.close()
        conn.close()

@app.post("/payments/{payment_id}/approve")
def approve_payment(payment_id: int, transaction_id: str):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""UPDATE payments SET payment_status='approved', transaction_id=%s, 
                         paid_at=NOW() WHERE id_payment=%s""", (transaction_id, payment_id))
        cursor.execute("SELECT id_order FROM payments WHERE id_payment=%s", (payment_id,))
        order_id = cursor.fetchone()[0]
        cursor.execute("UPDATE orders SET payment_status='approved' WHERE id_order=%s", (order_id,))
        conn.commit()
        return {"approved": True}
    finally:
        cursor.close()
        conn.close()

@app.post("/payments/{payment_id}/reject")
def reject_payment(payment_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE payments SET payment_status='rejected' WHERE id_payment=%s", (payment_id,))
        cursor.execute("SELECT id_order FROM payments WHERE id_payment=%s", (payment_id,))
        order_id = cursor.fetchone()[0]
        cursor.execute("UPDATE orders SET payment_status='rejected' WHERE id_order=%s", (order_id,))
        conn.commit()
        return {"rejected": True}
    finally:
        cursor.close()
        conn.close()

@app.get("/payments")
def list_all_payments(authorization: str = Header(...)):
    require_admin(authorization)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT p.*, o.id_user, u.name as user_name, u.email as user_email
           FROM payments p
           JOIN orders o ON o.id_order = p.id_order
           JOIN users u ON u.id_user = o.id_user
           ORDER BY p.id_payment DESC"""
    )
    payments = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"payments": payments, "total": len(payments)}


# alias para /api/payments/payments
@app.get("/payments/payments")
def list_all_payments_alias(authorization: str = Header(...)):
    return list_all_payments(authorization)


@app.get("/payments/order/{order_id}")
def get_order_payments(order_id: int):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM payments WHERE id_order=%s", (order_id,))
    payments = cursor.fetchall()
    cursor.close(); conn.close()
    return payments
