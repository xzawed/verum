FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn[standard] numpy pyyaml httpx
COPY app/ ./app/
COPY fixtures/ ./fixtures/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
