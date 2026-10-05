FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# 0.0.0.0 inside the container is standard (Docker handles host binding via -p),
# this is not the same as exposing this on your LAN unprotected — still requires
# AI_SERVICE_API_KEY to be set.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
