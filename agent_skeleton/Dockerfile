# AgentCore Runtime contract: linux/arm64, listen on 0.0.0.0:8080, POST /invocations, GET /ping.
# BedrockAgentCoreApp provides /invocations and /ping.
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
