FROM python:3.11-slim

WORKDIR /app

# dependências
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# código (inclui os *_pb2.py gerados)
COPY . .

EXPOSE 50051

CMD ["python", "main.py"]
