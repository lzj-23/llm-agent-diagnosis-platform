FROM python:3.12-slim
WORKDIR /app
ENV PROJECT_ROOT=/app
COPY backend /app/backend
RUN pip install --no-cache-dir -c /app/backend/requirements-linux.lock /app/backend && useradd -m -u 10001 diagnosis && find /app/backend -type f -name '*.py' -exec chmod 644 {} +
ARG ENABLE_NEURAL=0
RUN if [ "$ENABLE_NEURAL" = "1" ]; then pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir '/app/backend[neural]'; fi
COPY frontend /app/frontend
COPY evaluation-results /app/evaluation-results
RUN mkdir -p /app/runtime && chown -R diagnosis:diagnosis /app/runtime
USER diagnosis
EXPOSE 8000
CMD ["uvicorn", "diagnosis_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
