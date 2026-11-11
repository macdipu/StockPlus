# ADR 0003 — PostgreSQL + SQLAlchemy 2 (async) + Alembic replace SQLite
Status: Accepted
**Context.** Two ad-hoc SQLite files with schemas created at import time; one writer only; no upgrade path.
**Decision.** PostgreSQL 17, async SQLAlchemy 2 ORM in each feature's `infrastructure/`, one Alembic history
(`backend/alembic`) run on deploy (`alembic upgrade head` in the container command).
**Consequences.** Concurrent writers (worker + API), reviewed migrations, `NUMERIC` prices. ORM models never leave
infrastructure; mappers convert to domain entities.
