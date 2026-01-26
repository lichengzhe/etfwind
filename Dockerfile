FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8080"]
