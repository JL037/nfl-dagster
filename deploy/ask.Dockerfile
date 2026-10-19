# The Ask page (nfl_ask.web) as one container, for Railway (railway.json points here).
# Only the website runs here: the pipeline runs on Dagster+, the data is in Prisma Postgres.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY . .
# Editable, so the catalog finds dbt_project/models (mart descriptions and definitions) next to
# the code, as it does on a laptop.
RUN pip install -e .

# Secrets come from the host's variables: ANTHROPIC_API_KEY, SERVING_DB_URL_PROD_POOLED, plus
# NFL_ENV=prod and ASK_TRUST_PROXY=1 (Railway's proxy sets X-Forwarded-For). No access log:
# it would keep every visitor's IP address, and the page promises we keep nothing.
CMD exec uvicorn nfl_ask.web:create_production_app --factory --host 0.0.0.0 --port ${PORT:-8000} --no-access-log
