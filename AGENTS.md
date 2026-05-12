# AGENTS.md

## Purpose

This repository is a portable Python demo for `/Volumes/git/verstka/frontend`.
It should be possible to put this repo on a server, configure environment
variables, and use it as a small CMS that can create, edit, and display
articles.

Keep the demo self-contained. The local frontend repository path is useful
context, but runtime code in this repo must not depend on that path being
present on the target server.

## Application Shape

- FastAPI app entrypoint: `app/main.py`.
- CMS UI and form routes live under `/cms` in `app/routers/cms.py`.
- Verstka SDK callbacks are installed under `/verstka/` from `app/main.py`.
- Verstka pre-save/finalize behavior is in `app/verstka_handlers.py`.
- SQLite access is split between `app/database.py` and `app/repo.py`.
- Publishing and static file generation live in `app/services/publish.py`.
- HTML page rendering uses Jinja templates in `app/templates/`.
- Generated site files are written to `storage/`, which is intentionally
  ignored by git and intended to be served directly by nginx.

## Product Contract

The core user journey is:

1. An admin logs in at `/cms/login`.
2. The admin creates an article with a logical path such as `/index` or
   `/blog/post`.
3. The admin opens the article in the Verstka editor.
4. Verstka calls back into this app, which saves article HTML/media/fonts.
5. The app writes static output under `storage/`.
6. nginx serves published articles without routing normal article traffic
   through Python.

Preserve this flow when making changes.

## Important Behavior

- Article paths map to static directories:
  - `/index` -> `storage/index/index.html`
  - `/blog/post` -> `storage/blog/post/index.html`
- `/index` is the intended home page; nginx redirects `/` to `/index/`.
- `/cms` and `/fonts` are reserved path prefixes for articles.
- `/menu` and `/footer` are special article paths. When visible and edited,
  they are injected into other rendered article pages, so publishing changes
  there should regenerate visible articles.
- Fonts are stored under `storage/fonts/`; `fonts.css` is linked when present.
- Media uploaded by Verstka should be colocated with the article directory.
- `cms_users` is the source of truth for CMS users and Verstka `user_email`
  pre-save authorization.
- Bootstrap admin creation is supported when `ADMINS` is empty and the
  `cms_users` table has no rows.

## Portability Rules

- Do not hardcode machine-local paths, domains, secrets, or ports into app
  behavior.
- Use `Settings` from `app/config.py` for configurable paths and URLs.
- Keep `storage/`, SQLite databases, `.env`, virtualenvs, caches, and build
  output out of git.
- The app should run behind nginx on a server, with `/cms` and `/verstka/`
  proxied to uvicorn and article pages served from `storage/`.
- Prefer simple server-friendly dependencies and avoid frontend build steps in
  this demo unless the user explicitly asks for them.

## Development Commands

Set up locally:

```bash
uv venv -p 3.11 .venv
source .venv/bin/activate
uv pip install -e .
```

Run locally:

```bash
export DATABASE_URL=sqlite+aiosqlite:///./data.db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Useful checks:

```bash
uv run ruff check .
uv run python -m compileall app
```

There is no dedicated test suite at the time this file was created. For
behavioral changes, manually verify the affected CMS flow and confirm expected
files appear or disappear under `storage/`.

## Coding Guidelines

- Follow the existing small-module style; keep route logic, persistence,
  publishing, rendering, and configuration concerns separated.
- Keep path handling centralized in `app/paths.py`.
- Keep SQL parameterized through `aiosqlite`; do not build SQL with user input.
- Preserve async behavior for request handlers and database operations.
- Do not enable `DEBUG` in production-like examples; it logs sensitive request
  and response data.
- When changing publishing behavior, verify sitemap generation and visibility
  behavior as well as the rendered article file.
- When changing CMS forms, keep the server-side validations in place; templates
  are not a security boundary.

