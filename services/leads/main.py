from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["https://matheuspersonal.com.br"], allow_methods=["*"], allow_headers=["*"])

class Lead(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    message: Optional[str] = None

@app.post("/leads")
def create_lead(lead: Lead):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""INSERT INTO leads (name, email, phone, source, message) 
                         VALUES (%s,%s,%s,%s,%s)""",
                      (lead.name, lead.email, lead.phone, lead.source, lead.message))
        conn.commit()
        return {"id": cursor.lastrowid}
    finally:
        cursor.close()
        conn.close()

@app.get("/leads")
def list_leads():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
    leads = cursor.fetchall()
    cursor.close()
    conn.close()
    return leads

@app.get("/leads/{lead_id}")
def get_lead(lead_id: int):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM leads WHERE id_lead=%s", (lead_id,))
    lead = cursor.fetchone()
    cursor.close()
    conn.close()
    return lead
