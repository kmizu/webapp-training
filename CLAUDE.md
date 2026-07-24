# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This is a Japanese-language training curriculum ("Python + PostgreSQL ToDo アプリ研修") that teaches Python + PostgreSQL fundamentals by building a small ToDo web app. It has two independent parts, each with its own `pyproject.toml`/lockfile and `uv` environment:

- `docs/` — the MkDocs Material curriculum text (numbered chapters `00-setup.md` … `18-deploy.md` + two appendices). Managed by the root `pyproject.toml` (`docs` dependency group only).
- `sample/todo-app/` — a standalone FastAPI + PostgreSQL app that is the finished reference implementation of what readers build while following the curriculum. Has its own `pyproject.toml` and dependencies.

`site/` is MkDocs's generated build output — gitignored, never hand-edit it.

Because the sample app mirrors the curriculum step by step, chapters 10–16 (`docs/10-data-read.md` … `docs/16-ui-htmx.md`) each correspond to specific modules under `sample/todo-app/app/`. When changing the sample app's structure or public behavior, check whether the matching chapter's prose/code listings need to stay in sync.

## Commands

### Docs site (run from repo root)

```bash
uv sync --group docs
uv run mkdocs serve           # live preview at http://127.0.0.1:8000/
uv run mkdocs build --strict  # what CI runs before deploying to GitHub Pages
```

### Sample app

```bash
docker compose up -d                  # Postgres 16 (docker-compose.yml lives at repo root)
cd sample/todo-app
uv sync
uv run python -m app.cli init-db      # apply migrations/*.sql
uv run uvicorn app.main:app --reload  # http://127.0.0.1:8000/
```

Tests require the live Postgres container from `docker compose up -d` (nothing is mocked):

```bash
cd sample/todo-app
uv run pytest -v
uv run pytest tests/test_repositories.py::test_create_and_get -v   # single test
```

Note on test isolation: `tests/test_repositories.py` calls repository functions directly against the `conn` fixture in `tests/conftest.py`, which rolls back after every test. `tests/test_api.py` instead drives the app through `TestClient`, which goes through the real pooled connection in `app/db.py` and **commits** — so API-level test runs leave rows behind in the dev database. Run `uv run python -m app.cli reset-db && uv run python -m app.cli init-db` to get back to a clean state.

## Architecture (sample/todo-app)

Layering is deliberately simple and ORM-free (the curriculum's stated pedagogical goal is to keep raw SQL visible, see `docs/index.md`):

- **`app/routers/`** — HTTP layer only, two parallel router families mounted in `app/main.py`:
  - `todos.py` — JSON API under `/api` prefix (`/api/todos`, `/api/tags`), using `app/schemas.py` Pydantic models for request/response validation.
  - `pages.py` — server-rendered Jinja2 pages (`/`) plus htmx partial-update endpoints (`/partials/list`, `/htmx/todos/*`) that return HTML fragments instead of JSON.
  Both call the same repository functions directly; there is no shared service layer between them.
- **`app/repositories.py`** — all SQL lives here as plain psycopg3 queries (no query builder/ORM). Rows come back as `dict_row` and are converted to dataclasses via the module's `_row_to_todo`/`_row_to_tag` helpers. Handles the `todos` ↔ `tags` many-to-many via a `todo_tags` join table, with an upsert-by-name pattern (`ON CONFLICT (name) DO NOTHING`) in `attach_tags`/`replace_tags`.
- **`app/models.py`** — plain dataclasses (`Todo`, `Tag`); this is the domain model returned by the repository layer.
- **`app/schemas.py`** — Pydantic models (`TodoOut`, `TodoCreate`, `TodoPatch`, …) used only at the API boundary; routers convert with `TodoOut.model_validate(todo)`.
- **`app/services.py`** — thin business-rule layer sitting between routers and repositories (currently just due-date validation). Expect this layer to grow as the curriculum's later chapters add more rules.
- **`app/db.py`** — a single lazily-created module-level `psycopg_pool.ConnectionPool` (`get_pool()`), wrapped by the `connection()` context manager used as a FastAPI dependency in each router (`get_conn`). Pool-managed connections auto-commit on clean exit / auto-rollback on exception.
- **`app/config.py`** — a frozen `Settings` dataclass reading straight from `os.getenv` (see `.env.example` for the variables) with local-dev defaults baked in. There's no `.env`-loading library wired in, so environment variables must be exported (or sourced via something like `direnv`) to override the defaults.
- **`migrations/`** — plain numbered `.sql` files, applied in filename order by `app/cli.py init-db`, which tracks applied versions in a `schema_versions` table so re-running `init-db` is idempotent. There is no down-migration support; `reset-db` just drops all tables.

## CI

`.github/workflows/deploy.yml` builds the docs site with `mkdocs build --strict` and deploys `site/` to GitHub Pages on every push to `main`. It does not build, lint, or test `sample/todo-app`.
