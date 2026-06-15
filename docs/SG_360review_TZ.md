# SG_360review — Техническое задание

**Версия:** 0.1 (черновик к согласованию)
**Продукт:** отдельный SaaS, мультитенантный, доменно-нейтральный
**Стек:** Flask + Jinja2 + HTMX, PostgreSQL, Railway (EU), Chart.js для диаграмм, APScheduler для напоминаний
**Монетизация:** freemium, ЮKassa

---

## 1. Суть продукта

Сервис оценки сотрудников по методу 360°. Админ компании создаёт периодические **оценочные циклы**, назначает оцениваемых и их оценщиков (самооценка, руководитель, коллеги, подчинённые), система собирает оценки по токен-ссылкам и формирует отчёты с агрегацией, сравнением «я vs другие», радар-диаграммой и зонами роста. Поддерживается сравнение динамики между циклами.

---

## 2. Открытые решения (требуют подтверждения) ⚠️

| # | Вопрос | Рабочее умолчание |
|---|--------|-------------------|
| 1 | Компетенции фиксированные или настраиваемые? | Настраиваемые админом + дефолтный шаблон при регистрации компании |
| 2 | Доступ оценщиков | Без пароля, по уникальной токен-ссылке на назначение |
| 3 | Порог анонимности агрегата | ≥ 3 ответивших в группе (peers / подчинённые) |
| 4 | Email-провайдер для напоминаний | **не выбран** — нужен (Resend / Postmark / SMTP) |
| 5 | Лимиты Free-тарифа | см. раздел 9 |

---

## 3. Роли и доступ

- **Админ компании** — логин/пароль. Единственный, кто видит результаты (по требованию). Создаёт циклы, управляет сотрудниками и компетенциями, следит за прогрессом, открывает отчёты.
- **Оценщик** — не имеет аккаунта. Получает персональную токен-ссылку на каждое назначение, по ней заполняет анкету. Один человек может быть оценщиком для нескольких оцениваемых (получает несколько ссылок).
- **Оцениваемый (subject)** — сотрудник компании. В рамках цикла сам выступает оценщиком для самооценки (тоже по токен-ссылке). Свой отчёт **не видит** (только админ).

> Самооценка и оценка руководителя — **не анонимны** (видны в отчёте как отдельные источники). Оценки коллег и подчинённых — **анонимны**, показываются только агрегатом при достижении порога.

---

## 4. Модель оценки

- **Компетенция** — группа вопросов (напр. «Коммуникация», «Ответственность», «Лидерство»). Настраивается админом, есть дефолтный универсальный шаблон.
- **Вопрос** двух типов:
  - `rating` — шкала **1–5**;
  - `open` — открытый текстовый ответ.
- **Отношение оценщика к оцениваемому** (`relation`): `self`, `manager`, `peer`, `subordinate`.

Анкета формируется из активных компетенций цикла. Один и тот же набор вопросов получают все оценщики оцениваемого (открытые вопросы могут зависеть от типа — опционально, в v1 одинаковые).

---

## 5. Жизненный цикл оценочного цикла

```
draft → active → closed
```

1. **draft** — админ создаёт цикл (название, тип периода, дедлайн), добавляет оцениваемых, для каждого назначает оценщиков с указанием relation. Self добавляется автоматически.
2. **active** — запуск. Генерируются токены, рассылаются ссылки (email + копирование вручную). APScheduler шлёт напоминания за N дней до дедлайна и в день дедлайна тем, кто не сдал.
3. **closed** — закрытие (вручную админом или авто по дедлайну). Открываются отчёты. Незаполненные назначения остаются в статусе `pending`/`in_progress` и в агрегат не попадают.

**Периодичность и динамика:** у цикла есть `period_type` (quarter / half_year / year / custom) и `period_label` (напр. «2026-Q1»). Отчёт оцениваемого может сравниваться с его же отчётами из прошлых циклов — динамика средних по компетенциям.

---

## 6. Схема БД (PostgreSQL)

```sql
-- Тенант
CREATE TABLE companies (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    plan          TEXT NOT NULL DEFAULT 'free',   -- free | pro
    anon_threshold SMALLINT NOT NULL DEFAULT 3,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Админы
CREATE TABLE admins (
    id            BIGSERIAL PRIMARY KEY,
    company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Сотрудники (могут быть и subject, и evaluator)
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

-- Компетенции (настраиваемые, с дефолтным шаблоном)
CREATE TABLE competencies (
    id            BIGSERIAL PRIMARY KEY,
    company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    description   TEXT,
    sort_order    INT NOT NULL DEFAULT 0,
    active        BOOLEAN NOT NULL DEFAULT true
);

-- Вопросы внутри компетенции
CREATE TABLE questions (
    id            BIGSERIAL PRIMARY KEY,
    competency_id BIGINT NOT NULL REFERENCES competencies(id) ON DELETE CASCADE,
    text          TEXT NOT NULL,
    qtype         TEXT NOT NULL DEFAULT 'rating',  -- rating | open
    sort_order    INT NOT NULL DEFAULT 0
);

-- Оценочный цикл
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

-- Снимок компетенций/вопросов на момент цикла (чтобы правки шаблона не ломали прошлые отчёты)
CREATE TABLE cycle_questions (
    id            BIGSERIAL PRIMARY KEY,
    cycle_id      BIGINT NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    competency_name TEXT NOT NULL,
    question_text TEXT NOT NULL,
    qtype         TEXT NOT NULL,
    comp_order    INT NOT NULL DEFAULT 0,
    q_order       INT NOT NULL DEFAULT 0
);

-- Оцениваемые в цикле
CREATE TABLE cycle_subjects (
    id            BIGSERIAL PRIMARY KEY,
    cycle_id      BIGINT NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    employee_id   BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    UNIQUE (cycle_id, employee_id)
);

-- Назначения: кто кого оценивает
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

-- Ответы
CREATE TABLE responses (
    id            BIGSERIAL PRIMARY KEY,
    assignment_id BIGINT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    cycle_question_id BIGINT NOT NULL REFERENCES cycle_questions(id) ON DELETE CASCADE,
    rating        SMALLINT,    -- 1..5, NULL для open
    text_answer   TEXT,        -- для open, NULL для rating
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (assignment_id, cycle_question_id)
);

CREATE INDEX idx_assignments_token ON assignments(token);
CREATE INDEX idx_assignments_cycle ON assignments(cycle_id, status);
CREATE INDEX idx_responses_assignment ON responses(assignment_id);
```

**Почему `cycle_questions`-снимок:** компетенции настраиваемые, а отчёты должны быть сравнимы во времени. Снимок фиксирует формулировки на момент запуска цикла, чтобы редактирование шаблона не искажало историю и динамику.

---

## 7. Логика анонимности (на этапе построения отчёта)

- `self` — показывается как отдельный столбец, всегда.
- `manager` — показывается отдельно (в классическом 360 не анонимизируется; если руководителей несколько — усредняются).
- `peer` / `subordinate` — агрегируются по группе. **Если в группе ответивших < `anon_threshold` (по умолчанию 3) — группа в отчёте скрывается** с пометкой «недостаточно ответов для анонимного отображения».
- Открытые ответы peers/подчинённых выводятся **без привязки к автору и в перемешанном порядке**; при недоборе порога — не выводятся.

---

## 8. Отчёт по оцениваемому (видит только админ)

1. **Сводка по компетенциям** — средний балл (1–5) с разбивкой по источникам: self / manager / peers (avg) / subordinates (avg) / общий по «другим».
2. **Я vs другие** — по каждой компетенции self-балл против среднего «других».
3. **Радар-диаграмма** (Chart.js) — оси = компетенции, две линии: self и «другие».
4. **Зоны:**
   - сильные стороны — топ компетенций по оценке «других»;
   - зоны роста — нижние компетенции по оценке «других»;
   - **слепые зоны** — self высоко, другие низко (Δ > порога);
   - **скрытые сильные стороны** — self низко, другие высоко.
5. **Открытые ответы** — сгруппированы по вопросу, с учётом анонимности.
6. **Динамика** — если у оцениваемого есть прошлые закрытые циклы: линейный график средних по компетенциям от цикла к циклу.
7. **Прогресс заполнения** (для active) — сколько оценщиков сдали по каждому relation.

Экспорт: XLSX (openpyxl) в v1; PDF — позже.

---

## 9. Freemium (предложение, ⚠️ подтвердить)

| | Free | Pro |
|---|------|-----|
| Активных циклов | 1 | без лимита |
| Оцениваемых в цикле | до 5 | без лимита |
| Сотрудников в базе | до 15 | без лимита |
| Компетенции | только дефолтный шаблон | полная настройка |
| Сравнение динамики | — | ✓ |
| Экспорт XLSX | — | ✓ |
| Email-напоминания | ручная рассылка ссылок | авто по расписанию |

Оплата Pro — подписка на компанию через ЮKassa.

---

## 10. Технические заметки

- **Токены назначений** — `secrets.token_urlsafe(32)`, по одному на assignment. Ссылка вида `/r/<token>`.
- **APScheduler** — фоновые задачи: напоминания за N дней / в день дедлайна (`reminded_at` чтобы не дублировать), авто-закрытие циклов по дедлайну.
- **Email** — провайдер на согласовании; интерфейс отправки абстрагировать (легко заменить SMTP↔API).
- **EU-хостинг Railway** — обязательное условие (как для всех Claude/SG-продуктов; здесь Claude API пока не используется, но инфраструктуру держим единообразной).
- **Мультитенантность** — все запросы скоупятся по `company_id` из сессии админа.
- **Дефолтный шаблон компетенций** — сидируется при создании компании (универсальный набор: Коммуникация, Командная работа, Ответственность, Профессионализм, Лидерство, Адаптивность — финальный список согласуем).

---

## 11. Этапы реализации

1. Каркас проекта, БД, миграции, сид дефолтного шаблона.
2. Аутентификация админа, CRUD сотрудников и компетенций.
3. Создание цикла, назначение оценщиков, генерация токенов.
4. Форма оценщика по токену (HTMX), сохранение ответов, статусы.
5. Дашборд прогресса, закрытие цикла.
6. Движок отчёта: агрегация, анонимность, радар, зоны, динамика.
7. APScheduler-напоминания + email-интеграция.
8. Freemium-гейтинг + ЮKassa.
9. Экспорт XLSX.
