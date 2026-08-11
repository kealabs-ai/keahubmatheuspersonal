from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from datetime import date
from typing import Optional
import sys
sys.path.append('..')
from database import get_db

ALLOWED_ORIGINS = [
    "https://www.matheuspersonal.com.br",
    "https://matheuspersonal.com.br",
    "https://srv1023256.hstgr.cloud",
]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Coupon(BaseModel):
    code: str
    description: str
    discount_type: str  # 'percent' | 'fixed'
    discount_value: Decimal
    valid_from: date
    valid_until: date
    usage_limit: Optional[int] = None
    min_purchase_amount: Decimal = Decimal('0')

class CouponUpdate(BaseModel):
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    usage_limit: Optional[int] = None
    min_purchase_amount: Optional[Decimal] = None
    is_active: Optional[int] = None


@app.get("/coupons")
def list_coupons():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM coupons ORDER BY created_at DESC")
    coupons = cursor.fetchall()
    for c in coupons:
        for k in ('valid_from', 'valid_until', 'created_at', 'updated_at'):
            if c.get(k) and hasattr(c[k], 'isoformat'):
                c[k] = c[k].isoformat()
        for k in ('discount_value', 'min_purchase_amount'):
            if c.get(k) is not None:
                c[k] = float(c[k])
    cursor.close(); conn.close()
    return {"coupons": coupons}


@app.post("/coupons", status_code=201)
def create_coupon(coupon: Coupon):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO coupons (code, description, discount_type, discount_value,
               valid_from, valid_until, usage_limit, min_purchase_amount)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (coupon.code.upper(), coupon.description, coupon.discount_type,
             coupon.discount_value, coupon.valid_from, coupon.valid_until,
             coupon.usage_limit, coupon.min_purchase_amount)
        )
        conn.commit()
        return {"id": cursor.lastrowid, "message": "Cupão criado com sucesso."}
    except Exception as e:
        raise HTTPException(400, f"Erro ao criar cupão: {str(e)}")
    finally:
        cursor.close(); conn.close()


@app.post("/coupons/{coupon_id}/update")
def update_coupon(coupon_id: int, body: CouponUpdate):
    conn = get_db()
    cursor = conn.cursor()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        cursor.close(); conn.close()
        return {"message": "Nenhum campo para atualizar"}
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    cursor.execute(f"UPDATE coupons SET {set_clause} WHERE id_coupon=%s", (*fields.values(), coupon_id))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Cupão atualizado com sucesso."}


@app.post("/coupons/{coupon_id}/delete")
def delete_coupon(coupon_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE coupons SET is_active=0 WHERE id_coupon=%s", (coupon_id,))
    conn.commit()
    cursor.close(); conn.close()
    return {"message": "Cupão desativado com sucesso."}


class ValidateCouponBody(BaseModel):
    code: str


@app.get("/coupons/validate")
def validate_coupon_by_query(code: str = None):
    if not code:
        raise HTTPException(422, "Parâmetro 'code' é obrigatório")
    return validate_coupon(code.upper())


@app.post("/coupons/validate")
def validate_coupon_by_body(body: ValidateCouponBody):
    return validate_coupon(body.code.upper())


@app.get("/coupons/{code}")
def validate_coupon(code: str):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT * FROM coupons WHERE UPPER(code)=%s AND is_active=1
           AND valid_from <= CURDATE() AND valid_until >= CURDATE()""",
        (code.upper(),)
    )
    coupon = cursor.fetchone()
    cursor.close(); conn.close()
    if not coupon:
        raise HTTPException(404, "Cupão não encontrado ou expirado")
    if coupon['usage_limit'] and coupon['usage_count'] >= coupon['usage_limit']:
        raise HTTPException(400, "Limite de uso atingido")
    for k in ('discount_value', 'min_purchase_amount'):
        if coupon.get(k) is not None:
            coupon[k] = float(coupon[k])
    return coupon


@app.post("/coupons/{coupon_id}/use")
def use_coupon(coupon_id: int, user_id: int, order_id: str, discount_applied: Decimal):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO coupon_usage (id_coupon, id_user, order_id, discount_applied) VALUES (%s,%s,%s,%s)",
            (coupon_id, user_id, order_id, discount_applied)
        )
        cursor.execute("UPDATE coupons SET usage_count = usage_count + 1 WHERE id_coupon=%s", (coupon_id,))
        conn.commit()
        return {"used": True}
    finally:
        cursor.close(); conn.close()
