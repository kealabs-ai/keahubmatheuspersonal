from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sys
sys.path.append('..')
from database import get_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Feedback(BaseModel):
    name: str
    age: int
    city: str
    title: str
    testimonial: str
    rating: int = Field(..., ge=1, le=5)

@app.post("/feedbacks", status_code=200)
def create_feedback(feedback: Feedback):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""INSERT INTO feedbacks (name, age, city, title, testimonial, rating)
                         VALUES (%s,%s,%s,%s,%s,%s)""",
                      (feedback.name, feedback.age, feedback.city, feedback.title,
                       feedback.testimonial, feedback.rating))
        conn.commit()
        return {"id": cursor.lastrowid, "status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/feedbacks")
def list_feedbacks():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM feedbacks WHERE status='approved' ORDER BY created_at DESC")
    feedbacks = cursor.fetchall()
    cursor.close()
    conn.close()
    return feedbacks

@app.get("/feedbacks/{feedback_id}")
def get_feedback(feedback_id: int):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM feedbacks WHERE id_feedback=%s", (feedback_id,))
    feedback = cursor.fetchone()
    cursor.close()
    conn.close()
    if not feedback:
        raise HTTPException(404, "Feedback not found")
    return feedback

@app.post("/feedbacks/{feedback_id}/approve")
def approve_feedback(feedback_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE feedbacks SET status='approved' WHERE id_feedback=%s", (feedback_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"updated": True}

@app.post("/feedbacks/{feedback_id}/reject")
def reject_feedback(feedback_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE feedbacks SET status='rejected' WHERE id_feedback=%s", (feedback_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"updated": True}
