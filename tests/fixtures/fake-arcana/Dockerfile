FROM python:3.13-slim

WORKDIR /app

# Install Verum Python SDK (editable from workspace mount)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY client.py workload.yaml ./

CMD ["python", "client.py"]
