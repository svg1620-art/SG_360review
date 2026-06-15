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
        company_id = cur.fetchone()[0]
    db.commit()

    seed_default_competencies(db, company_id)
    click.echo(
        f"Создана компания id={company_id} «{name}» с дефолтным шаблоном компетенций."
    )


def init_app(app):
    app.cli.add_command(seed_demo_company)
