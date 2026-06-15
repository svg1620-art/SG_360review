"""Фоновые задачи (APScheduler): напоминания оценщикам и авто-закрытие циклов."""
import psycopg
from apscheduler.schedulers.background import BackgroundScheduler

from . import email as email_mod

_scheduler = None


def auto_close_due_cycles(conn):
    """Закрывает активные циклы, у которых день дедлайна уже прошёл. Возвращает число закрытых.

    Семантика «конец дня дедлайна»: цикл активен весь день дедлайна (чтобы успели
    отработать напоминания «в день дедлайна») и закрывается на следующий день.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cycles SET status = 'closed'
            WHERE status = 'active' AND deadline IS NOT NULL
              AND deadline::date < now()::date
            """
        )
        closed = cur.rowcount
    conn.commit()
    return closed


def send_due_reminders(conn, sender, days_before, base_url=""):
    """Шлёт напоминания за N дней и в день дедлайна тем, кто ещё не сдал.

    reminded_at защищает от повторной отправки в течение одного дня; на следующий
    день (например, в день дедлайна после напоминания за N дней) письмо уйдёт снова.
    Возвращает число отправленных писем.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.token, c.title, c.deadline,
                   e.email AS evaluator_email, e.full_name AS evaluator_name,
                   subj.full_name AS subject_name
            FROM assignments a
            JOIN cycles c ON c.id = a.cycle_id
            JOIN employees e ON e.id = a.evaluator_id
            JOIN cycle_subjects cs ON cs.id = a.subject_id
            JOIN employees subj ON subj.id = cs.employee_id
            WHERE c.status = 'active' AND c.deadline IS NOT NULL
              AND a.status <> 'submitted'
              AND e.email IS NOT NULL
              AND (a.reminded_at IS NULL OR a.reminded_at < date_trunc('day', now()))
              AND ((c.deadline::date - now()::date) = %s OR c.deadline::date = now()::date)
            """,
            (days_before,),
        )
        due = cur.fetchall()

    sent = 0
    for row in due:
        link = f"{base_url}/r/{row['token']}" if base_url else f"/r/{row['token']}"
        deadline = row["deadline"].strftime("%Y-%m-%d") if row["deadline"] else ""
        subject = f"Напоминание: анкета 360° по {row['subject_name']}"
        body = (
            f"Здравствуйте, {row['evaluator_name']}!\n\n"
            f"Просим заполнить анкету 360° по сотруднику {row['subject_name']} "
            f"в цикле «{row['title']}». Дедлайн: {deadline}.\n\n"
            f"Ссылка: {link}\n"
        )
        sender.send(row["evaluator_email"], subject, body)
        with conn.cursor() as cur:
            cur.execute("UPDATE assignments SET reminded_at = now() WHERE id = %s", (row["id"],))
        sent += 1
    conn.commit()
    return sent


def _tick(database_url, sender, days_before, base_url):
    conn = psycopg.connect(database_url)
    try:
        reminded = send_due_reminders(conn, sender, days_before, base_url)
        closed = auto_close_due_cycles(conn)
        if reminded or closed:
            print(f"[scheduler] напоминаний: {reminded}, авто-закрыто: {closed}")
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
    sender = email_mod.get_sender(app.config)
    days_before = app.config.get("REMINDER_DAYS_BEFORE", 3)
    base_url = app.config.get("APP_BASE_URL", "")
    interval = app.config.get("SCHEDULER_INTERVAL_MIN", 5)
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        lambda: _tick(database_url, sender, days_before, base_url),
        "interval",
        minutes=interval,
        id="reminders_and_autoclose",
    )
    _scheduler.start()
