from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date
import sys
sys.path.append('..')
from database import get_db
import bcrypt

app = FastAPI()

from typing import Optional

class User(BaseModel):
    name: str
    email: str
    phone: str
    cpf: str
    birth_date: Optional[date] = None
    cep: str
    address: str
    number: str
    neighborhood: str
    city: str
    state: str
    username: str
    password: str
    country_code: str = '+55'

@app.post("/users")
def create_user(user: User):
    conn = get_db()
    cursor = conn.cursor()
    hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
    try:
        cursor.execute("""INSERT INTO users (name, email, phone, cpf, birth_date, cep, address, number, 
                         neighborhood, city, state, country_code, username, password) 
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                      (
                          user.name,
                          user.email,
                          user.phone,
                          user.cpf,
                          user.birth_date if user.birth_date is not None else None,
                          user.cep,
                          user.address,
                          user.number,
                          user.neighborhood,
                          user.city,
                          user.state,
                          user.country_code,
                          user.username,
                          hashed
                      ))
        conn.commit()
        return {"id": cursor.lastrowid}
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/users/{user_id}")
def get_user(user_id: int):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id_user=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user:
        raise HTTPException(404, "User not found")
    return user

@app.post("/users/{user_id}/update")
def update_user(user_id: int, user: User):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""UPDATE users SET name=%s, email=%s, phone=%s, address=%s, number=%s, 
                         neighborhood=%s, city=%s, state=%s, birth_date=%s WHERE id_user=%s""",
                      (
                          user.name,
                          user.email,
                          user.phone,
                          user.address,
                          user.number,
                          user.neighborhood,
                          user.city,
                          user.state,
                          user.birth_date if user.birth_date is not None else None,
                          user_id
                      ))
        conn.commit()
        return {"updated": cursor.rowcount}
    finally:
        cursor.close()
        conn.close()

@app.post("/users/{user_id}/delete")
def delete_user(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id_user=%s", (user_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    return {"deleted": deleted}
