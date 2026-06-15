"""Flask CLI-команды для локальной проверки каркаса."""
import click
from flask.cli import with_appcontext

from .db import get_db
from .seeds.default_competencies import seed_default_competencies


@click.command("seed-demo-company")
@click.option("--name", default="Demo Company", help="Название компании.")
@with_appcontext
def seed_demo_company(name):
    """Создаёт компанию с дефолтным шаблоном компетенций (проверка сида)."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (name) VALUES (%s) RETURNING id",
            (name,),
        )
        company_id = cur.fetchone()["id"]
    db.commit()

    seed_default_competencies(db, company_id)
    click.echo(
        f"Создана компания id={company_id} «{name}» с дефолтным шаблоном компетенций."
    )


@click.command("set-plan")
@click.option("--email", required=True, help="Email админа компании.")
@click.option("--plan", type=click.Choice(["free", "pro"]), required=True)
@with_appcontext
def set_plan(email, plan):
    """Переключает тариф компании (до подключения ЮKassa — ручное управление)."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE companies SET plan = %s
            WHERE id = (SELECT company_id FROM admins WHERE email = %s)
            RETURNING id
            """,
            (plan, email.lower()),
        )
        row = cur.fetchone()
    if row is None:
        click.echo("Админ с таким email не найден.")
        return
    db.commit()
    click.echo(f"Компания id={row['id']} переведена на тариф {plan}.")


def init_app(app):
    app.cli.add_command(seed_demo_company)
    app.cli.add_command(set_plan)
