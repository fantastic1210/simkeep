FROM python:3.12-slim AS frontend
WORKDIR /build
COPY index.html style.css app.js api.js core.js money.js countries.js favicon.svg ./
COPY scripts/build.py ./scripts/build.py
RUN python scripts/build.py

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SIMKEEP_DB=/app/data/simkeep.db SIMKEEP_STATIC_DIR=/app/dist
COPY requirements.txt LICENSE ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
COPY scripts/backup.py scripts/restore.py ./scripts/
COPY --from=frontend /build/dist ./dist
RUN groupadd --gid 10001 simkeep && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin simkeep && install -d -m 0700 -o simkeep -g simkeep /app/data
USER 10001:10001
EXPOSE 5180
CMD ["python", "-m", "uvicorn", "server.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "5180", "--workers", "1", "--no-access-log"]
