from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional
import os
import httpx
import datetime
import time
import sys

ONBOARDING_URL = os.getenv("ONBOARDING_URL", "http://ms-onboarding-service:8000/onboarding/activate")
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[ERROR] Unhandled exception: {type(exc).__name__}: {exc}", flush=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {str(exc)}"})

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
    api_key = os.getenv("ASAAS_API_KEY") or os.getenv("ASSAS_API_KEY")  # fallback typo
    if not api_key:
        raise HTTPException(500, "ASAAS_API_KEY não configurada")
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "access_token": api_key,
    }

@app.get("/asaas/health")
def health():
    key = os.getenv("ASAAS_API_KEY") or os.getenv("ASSAS_API_KEY")
    return {
        "ASAAS_API_KEY_set": bool(key),
        "ASAAS_API_KEY_preview": (key[:10] + "...") if key else None,
        "ASAAS_BASE_URL": os.getenv("ASAAS_BASE_URL"),
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
    id_user: int
    billing_type: str
    amount: Decimal
    due_date: Optional[str] = None
    description: Optional[str] = None
    external_reference: Optional[str] = None
    installments: int = 1
    remote_ip: Optional[str] = None
    # Dados do cliente (vindos do frontend)
    customer_name: str
    customer_email: str
    customer_cpf_cnpj: str
    customer_phone: Optional[str] = None
    # Dados do cartão (vindos do frontend)
    card_number: Optional[str] = None
    card_name: Optional[str] = None
    card_expiry: Optional[str] = None   # formato MM/YY ou MM/YYYY
    card_cvv: Optional[str] = None
    # Endereço (opcional, buscado do banco se não enviado)
    postal_code: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None

class AsaasCustomer(BaseModel):
    name: str
    email: str
    cpf_cnpj: str
    phone: Optional[str] = None

def get_or_create_customer(customer: AsaasCustomer) -> str:
    headers = get_headers()
    with httpx.Client() as client:
        print(f"[ASAAS] GET /customers headers={headers} params={{cpfCnpj: {customer.cpf_cnpj}}}", flush=True)
        res = client.get(f"{ASAAS_BASE_URL}/customers", headers=headers, params={"cpfCnpj": customer.cpf_cnpj})
        print(f"[ASAAS] GET /customers status={res.status_code} body={res.text}", flush=True)
        if res.status_code != 200:
            raise HTTPException(400, f"Asaas customers GET error {res.status_code}: {res.text}")
        data = res.json()
        if data.get("data"):
            return data["data"][0]["id"]
        payload = {"name": customer.name, "email": customer.email, "cpfCnpj": customer.cpf_cnpj}
        if customer.phone:
            payload["mobilePhone"] = customer.phone
        print(f"[ASAAS] POST /customers headers={headers} body={payload}", flush=True)
        res = client.post(f"{ASAAS_BASE_URL}/customers", headers=headers, json=payload)
        print(f"[ASAAS] POST /customers status={res.status_code} body={res.text}", flush=True)
        if res.status_code not in (200, 201):
            raise HTTPException(400, f"Asaas customers POST error {res.status_code}: {res.text}")
        return res.json()["id"]

@app.post("/asaas/checkout", status_code=200)
def create_checkout(payment: AsaasPayment, request: Request):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar endereço do usuário no banco se não enviado
        postal_code = payment.postal_code
        address_number = payment.address_number
        address_complement = payment.address_complement
        headers = get_headers()
        if not postal_code or not address_number:
            cursor.execute("SELECT cep, number, complement FROM user_addresses WHERE id_user=%s AND is_primary=1", (payment.id_user,))
            addr = cursor.fetchone()
            if addr:
                postal_code = postal_code or addr["cep"]
                address_number = address_number or addr["number"]
                address_complement = address_complement or addr["complement"]

        # Criar ou buscar customer no Asaas
        customer_id = get_or_create_customer(AsaasCustomer(
            name=payment.customer_name,
            email=payment.customer_email,
            cpf_cnpj=payment.customer_cpf_cnpj,
            phone=payment.customer_phone,
        ))
        print(f"[ASAAS] customer_id resolvido: {customer_id}", flush=True)
        if not customer_id:
            raise HTTPException(400, "Falha ao criar/buscar customer no Asaas")

        due_date = payment.due_date or datetime.date.today().isoformat()
        remote_ip = payment.remote_ip or request.client.host

        payload = {
            "customer": customer_id,
            "billingType": payment.billing_type,
            "value": float(payment.amount),
            "dueDate": due_date,
            "description": payment.description or f"Pedido #{payment.id_order}",
            "externalReference": payment.external_reference or str(payment.id_order),
            "remoteIp": remote_ip,
        }

        if payment.billing_type == "CREDIT_CARD":
            if not payment.card_number or not payment.card_name or not payment.card_expiry or not payment.card_cvv:
                raise HTTPException(400, "Dados do cartão incompletos")

            # Parsear card_expiry MM/YY ou MM/YYYY
            expiry_parts = payment.card_expiry.replace("-", "/").split("/")
            expiry_month = expiry_parts[0].strip()
            expiry_year = expiry_parts[1].strip()
            if len(expiry_year) == 2:
                expiry_year = "20" + expiry_year

            if payment.installments > 1:
                payload["installmentCount"] = payment.installments
                payload["installmentValue"] = round(float(payment.amount) / payment.installments, 2)

            # Buscar telefone do usuário no banco se não enviado
            mobile_phone = payment.customer_phone
            if not mobile_phone:
                cursor.execute("SELECT phone FROM users WHERE id_user=%s", (payment.id_user,))
                user_row = cursor.fetchone()
                if user_row:
                    mobile_phone = user_row["phone"]
            if not mobile_phone:
                raise HTTPException(400, "Telefone do titular do cartão é obrigatório")

            payload["creditCard"] = {
                "holderName": payment.card_name,
                "number": payment.card_number,
                "expiryMonth": expiry_month,
                "expiryYear": expiry_year,
                "ccv": payment.card_cvv,
            }
            payload["creditCardHolderInfo"] = {
                "name": payment.customer_name,
                "email": payment.customer_email,
                "cpfCnpj": payment.customer_cpf_cnpj,
                "postalCode": postal_code,
                "addressNumber": address_number,
                "addressComplement": address_complement,
                "mobilePhone": mobile_phone,
            }

        print(f"[ASAAS] POST /payments headers={headers} body={payload}", flush=True)
        with httpx.Client() as client:
            res = client.post(f"{ASAAS_BASE_URL}/payments", headers=headers, json=payload)
            print(f"[ASAAS] POST /payments status={res.status_code} body={res.text}", flush=True)
            if res.status_code not in (200, 201):
                raise HTTPException(400, f"Asaas payments error {res.status_code}: {res.text}")
            asaas_data = res.json()

        asaas_id = asaas_data["id"]
        status = STATUS_MAP.get(asaas_data.get("status", "PENDING"), "pending")
        boleto_url = asaas_data.get("bankSlipUrl")
        invoice_url = asaas_data.get("invoiceUrl")
        pix_code = None

        if payment.billing_type == "PIX":
            with httpx.Client() as client:
                for _ in range(5):
                    pix_res = client.get(f"{ASAAS_BASE_URL}/payments/{asaas_id}/pixQrCode", headers=headers)
                    print(f"[ASAAS] GET pixQrCode status={pix_res.status_code} body={pix_res.text}", flush=True)
                    if pix_res.status_code == 200:
                        pix_data = pix_res.json()
                        pix_code = pix_data.get("payload") or pix_data.get("encodedImage")
                        if pix_code:
                            break
                    time.sleep(1)

        cursor.execute("""INSERT INTO payments (id_order, payment_method, amount, installments,
                         payment_status, transaction_id)
                         VALUES (%s,%s,%s,%s,%s,%s)""",
                      (payment.id_order, payment.billing_type.lower(), payment.amount,
                       payment.installments, status, asaas_id))
        payment_id = cursor.lastrowid

        if status == "approved":
            cursor.execute("UPDATE orders SET payment_status='approved' WHERE id_order=%s", (payment.id_order,))
            cursor.execute("UPDATE users SET active=1 WHERE id_user=%s", (payment.id_user,))

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
    except HTTPException:
        conn.rollback()
        raise
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
            for _ in range(5):
                pix_res = client.get(f"{ASAAS_BASE_URL}/payments/{asaas_id}/pixQrCode", headers=headers)
                print(f"[ASAAS] GET pixQrCode status={pix_res.status_code} body={pix_res.text}", flush=True)
                if pix_res.status_code == 200:
                    pix_data = pix_res.json()
                    pix_code = pix_data.get("payload") or pix_data.get("encodedImage")
                    if pix_code:
                        break
                time.sleep(1)
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
            cursor.execute(
                """SELECT o.id_user, oi.plan_name, oi.plan_frequency
                   FROM orders o JOIN order_items oi ON oi.id_order = o.id_order
                   WHERE o.id_order=%s LIMIT 1""",
                (order_id,)
            )
            order_row = cursor.fetchone()
            if order_row:
                cursor.execute("UPDATE users SET active=1 WHERE id_user=%s", (order_row["id_user"],))
        elif new_status == "rejected":
            cursor.execute("UPDATE payments SET payment_status='rejected' WHERE id_payment=%s", (payment_id,))
            cursor.execute("UPDATE orders SET payment_status='rejected' WHERE id_order=%s", (order_id,))
            order_row = None
        elif new_status == "refunded":
            cursor.execute("UPDATE payments SET payment_status='refunded' WHERE id_payment=%s", (payment_id,))
            order_row = None
        else:
            cursor.execute("UPDATE payments SET payment_status=%s WHERE id_payment=%s", (new_status, payment_id))
            order_row = None

        conn.commit()

        # Acionar onboarding após commit (fora da transação)
        if new_status == "approved" and order_row:
            try:
                with httpx.Client(timeout=10) as client:
                    client.post(ONBOARDING_URL, json={
                        "id_order": order_id,
                        "id_user": order_row["id_user"],
                        "plan_name": order_row["plan_name"],
                        "plan_frequency": order_row["plan_frequency"],
                    })
            except Exception:
                pass  # Onboarding falhou silenciosamente; pode ser reprocessado

        return {"success": True, "event": event, "status": new_status}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()
