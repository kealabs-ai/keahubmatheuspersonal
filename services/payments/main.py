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

class InfinitePayWebhook(BaseModel):
    event: str
    transaction_id: str
    status: str
    amount: Optional[Decimal] = None
    payment_method: Optional[str] = None
    order_id: Optional[int] = None

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


@app.get("/payments/order/{order_id}")
def get_order_payments(order_id: int):
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

# Webhook InfinitePay
@app.post("/payments/webhook/infinitepay")
async def infinitepay_webhook(request: Request):
    conn = get_db()
    cursor = conn.cursor()
    try:
        payload = await request.json()
        
        # Extrair dados do webhook InfinitePay
        event = payload.get('event')
        transaction_id = payload.get('id') or payload.get('transaction_id')
        status = payload.get('status')
        amount = payload.get('amount')
        payment_method = payload.get('payment_method')
        
        # Buscar pagamento pelo transaction_id ou criar novo
        cursor.execute("SELECT id_payment, id_order FROM payments WHERE transaction_id=%s", (transaction_id,))
        payment = cursor.fetchone()
        
        if payment:
            payment_id = payment[0]
            order_id = payment[1]
            
            # Mapear status InfinitePay para status interno
            payment_status_map = {
                'approved': 'approved',
                'paid': 'approved',
                'authorized': 'approved',
                'pending': 'pending',
                'processing': 'pending',
                'rejected': 'rejected',
                'failed': 'rejected',
                'cancelled': 'rejected',
                'refunded': 'refunded'
            }
            
            new_status = payment_status_map.get(status.lower(), 'pending')
            
            # Atualizar pagamento
            if new_status == 'approved':
                cursor.execute("""UPDATE payments SET payment_status=%s, paid_at=NOW() 
                                 WHERE id_payment=%s""", (new_status, payment_id))
                cursor.execute("UPDATE orders SET payment_status='approved' WHERE id_order=%s", (order_id,))
            else:
                cursor.execute("UPDATE payments SET payment_status=%s WHERE id_payment=%s", 
                             (new_status, payment_id))
                if new_status == 'rejected':
                    cursor.execute("UPDATE orders SET payment_status='rejected' WHERE id_order=%s", (order_id,))
            
            conn.commit()
            
            return {
                "success": True,
                "payment_id": payment_id,
                "status": new_status,
                "event": event
            }
        else:
            # Pagamento não encontrado, registrar webhook para análise
            return {
                "success": False,
                "message": "Payment not found",
                "transaction_id": transaction_id
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

# Criar pagamento com InfinitePay
@app.post("/payments/infinitepay/create")
def create_infinitepay_payment(payment: Payment):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Gerar transaction_id temporário (será substituído pelo real do InfinitePay)
        import uuid
        temp_transaction_id = f"TEMP_{uuid.uuid4().hex[:16]}"
        
        cursor.execute("""INSERT INTO payments (id_order, payment_method, amount, installments, 
                         card_last_digits, card_brand, payment_status, transaction_id) 
                         VALUES (%s,%s,%s,%s,%s,%s,'pending',%s)""",
                      (payment.id_order, payment.payment_method, payment.amount, 
                       payment.installments, payment.card_last_digits, payment.card_brand, temp_transaction_id))
        payment_id = cursor.lastrowid
        conn.commit()
        
        return {
            "payment_id": payment_id,
            "transaction_id": temp_transaction_id,
            "status": "pending",
            "message": "Payment created, waiting for InfinitePay confirmation"
        }
    finally:
        cursor.close()
        conn.close()

# Atualizar transaction_id após resposta do InfinitePay
@app.post("/payments/{payment_id}/update-transaction")
def update_transaction_id(payment_id: int, transaction_id: str):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE payments SET transaction_id=%s WHERE id_payment=%s", 
                      (transaction_id, payment_id))
        conn.commit()
        return {"updated": True, "payment_id": payment_id, "transaction_id": transaction_id}
    finally:
        cursor.close()
        conn.close()
