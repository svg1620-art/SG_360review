"""Фоновые задачи (APScheduler). Пока — авто-закрытие циклов по дедлайну."""
import psycopg
from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = None


def auto_close_due_cycles(conn):
    """Закрывает активные циклы с прошедшим дедлайном. Возвращает число закрытых."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cycles SET status = 'closed'
            WHERE status = 'active' AND deadline IS NOT NULL AND deadline < now()
            """
        )
        closed = cur.rowcount
    conn.commit()
    return closed


def _run(database_url):
    conn = psycopg.connect(database_url)
    try:
        closed = auto_close_due_cycles(conn)
        if closed:
            print(f"[scheduler] авто-закрыто циклов по дедлайну: {closed}")
    finally:
        conn.close()


def init_app(app):
    if not app.config.get("SCHEDULER_ENABLED", True):
        return
    database_url = app.config.get("DATABASE_URL")
    if not database_url:
        return
    global _scheduler
    if _scheduler is not None:
        return
    interval = app.config.get("SCHEDULER_INTERVAL_MIN", 5)
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        lambda: _run(database_url),
        "interval",
        minutes=interval,
        id="auto_close_cycles",
    )
    _scheduler.start()
