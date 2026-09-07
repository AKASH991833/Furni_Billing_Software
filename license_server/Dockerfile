FROM python:3.12-slim

WORKDIR /app

# Prevent .pyc and buffer output issues
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY admin_web ./admin_web

EXPOSE 8000

# Run the main API server. The admin web UI is a separate optional process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]