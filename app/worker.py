"""Отдельный процесс планировщика — если web запущен в несколько воркеров.

Тогда на web выставляют SCHEDULER_ENABLED=0, а этот процесс держит единственный
планировщик. Запуск: `python -m app.worker`.
"""
import time

from . import create_app


def main():
    # create_app() стартует APScheduler, если SCHEDULER_ENABLED=1.
    create_app()
    try:
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
