"""Лимиты тарифов Free/Pro (раздел 9 ТЗ) и проверка плана компании."""
from flask import g

FREE_MAX_EMPLOYEES = 15           # сотрудников в базе
FREE_MAX_ACTIVE_CYCLES = 1        # активных циклов
FREE_MAX_SUBJECTS_PER_CYCLE = 5   # оцениваемых в цикле


def is_pro():
    """True, если у текущей компании тариф Pro."""
    return getattr(g, "plan", None) == "pro"
