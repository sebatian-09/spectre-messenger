FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY crypto.py .
COPY anonymizer.py .
COPY mixnet.py .
COPY messenger.py .
COPY server.py .

EXPOSE 8765

CMD ["python", "server.py"]
