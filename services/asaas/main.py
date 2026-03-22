from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional
import os
import httpx
import datetime
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

class CreditCard(BaseModel):
    holder_name: str
    number: str
    expiry_month: str
    expiry_year: str
    ccv: str

class CreditCardHolderInfo(BaseModel):
    name: str
    email: str
    cpf_cnpj: str
    postal_code: str
    address_number: str
    address_complement: Optional[str] = None
    phone: Optional[str] = None
    mobile_phone: Optional[str] = None

class AsaasPayment(BaseModel):
    id_order: int
    customer: str                    # ID do cliente já criado no Asaas ex: cus_000005041014
    billing_type: str                # PIX, BOLETO, CREDIT_CARD
    amount: Decimal
    due_date: Optional[str] = None   # YYYY-MM-DD, default hoje
    description: Optional[str] = None
    external_reference: Optional[str] = None
    installments: int = 1
    remote_ip: Optional[str] = None
    # Cartão
    credit_card: Optional[CreditCard] = None
    credit_card_holder_info: Optional[CreditCardHolderInfo] = None

@app.post("/asaas/checkout", status_code=200)
def create_checkout(payment: AsaasPayment, request: Request):
    conn = get_db()
    cursor = conn.cursor()
    headers = get_headers()
    try:
        due_date = payment.due_date or datetime.date.today().isoformat()
        remote_ip = payment.remote_ip or request.client.host

        payload = {
            "customer": payment.customer,
            "billingType": payment.billing_type,
            "value": float(payment.amount),
            "dueDate": due_date,
            "description": payment.description or f"Pedido #{payment.id_order}",
            "externalReference": payment.external_reference or str(payment.id_order),
            "remoteIp": remote_ip,
        }

        if payment.billing_type == "CREDIT_CARD":
            if not payment.credit_card or not payment.credit_card_holder_info:
                raise HTTPException(400, "credit_card e credit_card_holder_info são obrigatórios para CREDIT_CARD")
            if payment.installments > 1:
                payload["installmentCount"] = payment.installments
                payload["installmentValue"] = round(float(payment.amount) / payment.installments, 2)
            payload["creditCard"] = {
                "holderName": payment.credit_card.holder_name,
                "number": payment.credit_card.number,
                "expiryMonth": payment.credit_card.expiry_month,
                "expiryYear": payment.credit_card.expiry_year,
                "ccv": payment.credit_card.ccv,
            }
            payload["creditCardHolderInfo"] = {
                "name": payment.credit_card_holder_info.name,
                "email": payment.credit_card_holder_info.email,
                "cpfCnpj": payment.credit_card_holder_info.cpf_cnpj,
                "postalCode": payment.credit_card_holder_info.postal_code,
                "addressNumber": payment.credit_card_holder_info.address_number,
                "addressComplement": payment.credit_card_holder_info.address_complement,
                "phone": payment.credit_card_holder_info.phone,
                "mobilePhone": payment.credit_card_holder_info.mobile_phone,
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
