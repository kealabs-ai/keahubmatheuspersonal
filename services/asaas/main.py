from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional
import os
import httpx
import sys
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3")

STATUS_MAP = {
    "CONFIRMED": "approved",
    "RECEIVED": "approved",
    "RECEIVED_IN_CASH": "approved",
    "PENDING": "pending",
    "AWAITING_RISK_ANALYSIS": "pending",
    "OVERDUE": "pending",
    "REFUNDED": "refunded",
    "REFUND_REQUESTED": "refunded",
    "CHARGEBACK_REQUESTED": "rejected",
    "CHARGEBACK_DISPUTE": "rejected",
    "AWAITING_CHARGEBACK_REVERSAL": "rejected",
    "DUNNING_REQUESTED": "rejected",
    "DUNNING_RECEIVED": "rejected",
    "CANCELLED": "rejected",
}

def get_headers():
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "access_token": os.getenv("ASAAS_API_KEY"),
    }

class AsaasCustomer(BaseModel):
    name: str
    email: str
    cpf_cnpj: str
    phone: Optional[str] = None

class AsaasPayment(BaseModel):
    id_order: int
    id_user: int
    amount: Decimal
    billing_type: str  # PIX, BOLETO, CREDIT_CARD
    description: Optional[str] = None
    installments: int = 1
    customer_name: str
    customer_email: str
    customer_cpf_cnpj: str
    customer_phone: Optional[str] = None
    card_holder_name: Optional[str] = None
    card_number: Optional[str] = None
    card_expiry_month: Optional[str] = None
    card_expiry_year: Optional[str] = None
    card_ccv: Optional[str] = None

def get_or_create_customer(customer: AsaasCustomer) -> str:
    headers = get_headers()
    with httpx.Client() as client:
        res = client.get(f"{ASAAS_BASE_URL}/customers", headers=headers, params={"cpfCnpj": customer.cpf_cnpj})
        res.raise_for_status()
        data = res.json()
        if data.get("data"):
            return data["data"][0]["id"]
        res = client.post(f"{ASAAS_BASE_URL}/customers", headers=headers, json={
            "name": customer.name,
            "email": customer.email,
            "cpfCnpj": customer.cpf_cnpj,
            "phone": customer.phone,
        })
        res.raise_for_status()
        return res.json()["id"]

@app.post("/asaas/checkout", status_code=200)
def create_checkout(payment: AsaasPayment):
    conn = get_db()
    cursor = conn.cursor()
    headers = get_headers()
    try:
        customer_id = get_or_create_customer(AsaasCustomer(
            name=payment.customer_name,
            email=payment.customer_email,
            cpf_cnpj=payment.customer_cpf_cnpj,
            phone=payment.customer_phone,
        ))

        import datetime
        payload = {
            "customer": customer_id,
            "billingType": payment.billing_type,
            "value": float(payment.amount),
            "dueDate": datetime.date.today().isoformat(),
            "description": payment.description or f"Pedido #{payment.id_order}",
        }

        if payment.billing_type == "CREDIT_CARD":
            payload["installmentCount"] = payment.installments
            payload["installmentValue"] = round(float(payment.amount) / payment.installments, 2)
            payload["creditCard"] = {
                "holderName": payment.card_holder_name,
                "number": payment.card_number,
                "expiryMonth": payment.card_expiry_month,
                "expiryYear": payment.card_expiry_year,
                "ccv": payment.card_ccv,
            }
            payload["creditCardHolderInfo"] = {
                "name": payment.customer_name,
                "email": payment.customer_email,
                "cpfCnpj": payment.customer_cpf_cnpj,
                "phone": payment.customer_phone,
            }

        with httpx.Client() as client:
            res = client.post(f"{ASAAS_BASE_URL}/payments", headers=headers, json=payload)
            res.raise_for_status()
            asaas_data = res.json()

        asaas_id = asaas_data["id"]
        status = STATUS_MAP.get(asaas_data.get("status", "PENDING"), "pending")
        boleto_url = asaas_data.get("bankSlipUrl")
        invoice_url = asaas_data.get("invoiceUrl")
        pix_code = None

        if payment.billing_type == "PIX":
            with httpx.Client() as client:
                pix_res = client.get(f"{ASAAS_BASE_URL}/payments/{asaas_id}/pixQrCode", headers=headers)
                if pix_res.status_code == 200:
                    pix_data = pix_res.json()
                    pix_code = pix_data.get("payload") or pix_data.get("encodedImage")

        cursor.execute("""INSERT INTO payments (id_order, payment_method, amount, installments,
                         payment_status, transaction_id)
                         VALUES (%s,%s,%s,%s,%s,%s)""",
                      (payment.id_order, payment.billing_type.lower(), payment.amount,
                       payment.installments, status, asaas_id))
        payment_id = cursor.lastrowid

        if status == "approved":
            cursor.execute("UPDATE orders SET payment_status='approved' WHERE id_order=%s", (payment.id_order,))

        conn.commit()

        return {
            "payment_id": payment_id,
            "asaas_id": asaas_id,
            "status": status,
            "billing_type": payment.billing_type,
            "pix_code": pix_code,
            "boleto_url": boleto_url,
            "invoice_url": invoice_url,
        }
    except httpx.HTTPStatusError as e:
        conn.rollback()
        raise HTTPException(400, e.response.text)
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/asaas/payment/{asaas_id}/status")
def get_payment_status(asaas_id: str):
    headers = get_headers()
    with httpx.Client() as client:
        res = client.get(f"{ASAAS_BASE_URL}/payments/{asaas_id}", headers=headers)
        res.raise_for_status()
        data = res.json()
    pix_code = None
    if data.get("billingType") == "PIX":
        with httpx.Client() as client:
            pix_res = client.get(f"{ASAAS_BASE_URL}/payments/{asaas_id}/pixQrCode", headers=headers)
            if pix_res.status_code == 200:
                pix_data = pix_res.json()
                pix_code = pix_data.get("payload") or pix_data.get("encodedImage")
    return {
        "asaas_id": asaas_id,
        "status": STATUS_MAP.get(data.get("status", "PENDING"), "pending"),
        "raw_status": data.get("status"),
        "value": data.get("value"),
        "billing_type": data.get("billingType"),
        "pix_code": pix_code,
        "boleto_url": data.get("bankSlipUrl"),
        "invoice_url": data.get("invoiceUrl"),
    }

@app.post("/asaas/webhook")
async def asaas_webhook(request: Request):
    conn = get_db()
    cursor = conn.cursor()
    try:
        payload = await request.json()
        event = payload.get("event", "")
        asaas_id = payload.get("payment", {}).get("id")
        raw_status = payload.get("payment", {}).get("status", "PENDING")
        new_status = STATUS_MAP.get(raw_status, "pending")

        cursor.execute("SELECT id_payment, id_order FROM payments WHERE transaction_id=%s", (asaas_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "Payment not found"}

        payment_id, order_id = row

        if new_status == "approved":
            cursor.execute("UPDATE payments SET payment_status='approved', paid_at=NOW() WHERE id_payment=%s", (payment_id,))
            cursor.execute("UPDATE orders SET payment_status='approved' WHERE id_order=%s", (order_id,))
        elif new_status == "rejected":
            cursor.execute("UPDATE payments SET payment_status='rejected' WHERE id_payment=%s", (payment_id,))
            cursor.execute("UPDATE orders SET payment_status='rejected' WHERE id_order=%s", (order_id,))
        elif new_status == "refunded":
            cursor.execute("UPDATE payments SET payment_status='refunded' WHERE id_payment=%s", (payment_id,))
        else:
            cursor.execute("UPDATE payments SET payment_status=%s WHERE id_payment=%s", (new_status, payment_id))

        conn.commit()
        return {"success": True, "event": event, "status": new_status}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()
