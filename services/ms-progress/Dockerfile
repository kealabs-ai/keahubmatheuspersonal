FROM python:3.11-slim
WORKDIR /app
COPY ms-progress/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ms-progress/ .
COPY database.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
