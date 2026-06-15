"""Начальная схема БД (строго по разделу 6 ТЗ).

Revision ID: 0001
Revises:
Create Date: 2026-06-15

"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE companies (
            id            BIGSERIAL PRIMARY KEY,
            name          TEXT NOT NULL,
            plan          TEXT NOT NULL DEFAULT 'free',   -- free | pro
            anon_threshold SMALLINT NOT NULL DEFAULT 3,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE admins (
            id            BIGSERIAL PRIMARY KEY,
            company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name     TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE employees (
            id            BIGSERIAL PRIMARY KEY,
            company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            full_name     TEXT NOT NULL,
            email         TEXT,
            position      TEXT,
            department    TEXT,
            active        BOOLEAN NOT NULL DEFAULT true,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE competencies (
            id            BIGSERIAL PRIMARY KEY,
            company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            name          TEXT NOT NULL,
            description   TEXT,
            sort_order    INT NOT NULL DEFAULT 0,
            active        BOOLEAN NOT NULL DEFAULT true
        );
        """
    )

    op.execute(
        """
        CREATE TABLE questions (
            id            BIGSERIAL PRIMARY KEY,
            competency_id BIGINT NOT NULL REFERENCES competencies(id) ON DELETE CASCADE,
            text          TEXT NOT NULL,
            qtype         TEXT NOT NULL DEFAULT 'rating',  -- rating | open
            sort_order    INT NOT NULL DEFAULT 0
        );
        """
    )

    op.execute(
        """
        CREATE TABLE cycles (
            id            BIGSERIAL PRIMARY KEY,
            company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            title         TEXT NOT NULL,
            period_type   TEXT NOT NULL DEFAULT 'custom',  -- quarter | half_year | year | custom
            period_label  TEXT,                            -- '2026-Q1'
            starts_at     TIMESTAMPTZ,
            deadline      TIMESTAMPTZ,
            status        TEXT NOT NULL DEFAULT 'draft',   -- draft | active | closed
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE cycle_questions (
            id            BIGSERIAL PRIMARY KEY,
            cycle_id      BIGINT NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
            competency_name TEXT NOT NULL,
            question_text TEXT NOT NULL,
            qtype         TEXT NOT NULL,
            comp_order    INT NOT NULL DEFAULT 0,
            q_order       INT NOT NULL DEFAULT 0
        );
        """
    )

    op.execute(
        """
        CREATE TABLE cycle_subjects (
            id            BIGSERIAL PRIMARY KEY,
            cycle_id      BIGINT NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
            employee_id   BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            UNIQUE (cycle_id, employee_id)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE assignments (
            id            BIGSERIAL PRIMARY KEY,
            cycle_id      BIGINT NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
            subject_id    BIGINT NOT NULL REFERENCES cycle_subjects(id) ON DELETE CASCADE,
            evaluator_id  BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            relation      TEXT NOT NULL,                   -- self | manager | peer | subordinate
            token         TEXT NOT NULL UNIQUE,            -- секретная ссылка
            status        TEXT NOT NULL DEFAULT 'pending', -- pending | in_progress | submitted
            submitted_at  TIMESTAMPTZ,
            reminded_at   TIMESTAMPTZ,
            UNIQUE (cycle_id, subject_id, evaluator_id)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE responses (
            id            BIGSERIAL PRIMARY KEY,
            assignment_id BIGINT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
            cycle_question_id BIGINT NOT NULL REFERENCES cycle_questions(id) ON DELETE CASCADE,
            rating        SMALLINT,    -- 1..5, NULL для open
            text_answer   TEXT,        -- для open, NULL для rating
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (assignment_id, cycle_question_id)
        );
        """
    )

    op.execute("CREATE INDEX idx_assignments_token ON assignments(token);")
    op.execute("CREATE INDEX idx_assignments_cycle ON assignments(cycle_id, status);")
    op.execute("CREATE INDEX idx_responses_assignment ON responses(assignment_id);")


def downgrade():
    # Удаляем в обратном порядке зависимостей FK.
    op.execute("DROP TABLE IF EXISTS responses;")
    op.execute("DROP TABLE IF EXISTS assignments;")
    op.execute("DROP TABLE IF EXISTS cycle_subjects;")
    op.execute("DROP TABLE IF EXISTS cycle_questions;")
    op.execute("DROP TABLE IF EXISTS cycles;")
    op.execute("DROP TABLE IF EXISTS questions;")
    op.execute("DROP TABLE IF EXISTS competencies;")
    op.execute("DROP TABLE IF EXISTS employees;")
    op.execute("DROP TABLE IF EXISTS admins;")
    op.execute("DROP TABLE IF EXISTS companies;")
