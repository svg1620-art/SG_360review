web: alembic upgrade head && gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}
worker: python -m app.worker
