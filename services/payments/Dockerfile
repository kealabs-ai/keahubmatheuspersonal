FROM python:3.11-slim
WORKDIR /app
COPY payments/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY payments/ .
COPY database.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
