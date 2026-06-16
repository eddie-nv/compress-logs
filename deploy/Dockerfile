FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir drain3 fastapi uvicorn tiktoken

COPY compression/ compression/

CMD ["uvicorn", "compression.api:app", "--host", "0.0.0.0", "--port", "8000"]
