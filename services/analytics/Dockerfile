FROM python:3.12-slim

WORKDIR /app

COPY services/analytics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/ /libs/
RUN pip install --no-cache-dir /libs/smartcourse_kafka

COPY services/analytics/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
