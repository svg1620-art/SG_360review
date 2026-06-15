"""Тариф компании. Оплата Pro через ЮKassa — подключим позже (раздел 9 ТЗ)."""
from flask import Blueprint, g, render_template

from .auth import login_required
from .limits import (
    FREE_MAX_ACTIVE_CYCLES,
    FREE_MAX_EMPLOYEES,
    FREE_MAX_SUBJECTS_PER_CYCLE,
)

bp = Blueprint("billing", __name__)


@bp.route("/billing")
@login_required
def index():
    limits = {
        "employees": FREE_MAX_EMPLOYEES,
        "active_cycles": FREE_MAX_ACTIVE_CYCLES,
        "subjects": FREE_MAX_SUBJECTS_PER_CYCLE,
    }
    return render_template("billing/index.html", plan=g.plan, limits=limits)
