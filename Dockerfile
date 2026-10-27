FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 TMPDIR=/tmp
WORKDIR /app
RUN useradd --no-create-home --uid 1000 appuser
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY --chown=1000:1000 main.py agente.py estrategia.py ./
USER 1000:1000
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
