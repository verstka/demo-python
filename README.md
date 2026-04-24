# Verstka CMS (demo)

A minimal **FastAPI** + **SQLite** + **verstka-sdk** app: CMS at `/cms`, Verstka callbacks at `/verstka/`, static pages under **`storage/`** served by **nginx** without hitting Python.

## Requirements

- Python **3.10+** (this repo works well with [uv](https://github.com/astral-sh/uv)).
- A Verstka account and API keys for `session/open` and callbacks.

## Setup

```bash
cd demo-python
uv venv -p 3.11 .venv
source .venv/bin/activate
uv pip install -e .
# or: uv pip install 'verstka-sdk[fastapi]' fastapi uvicorn ...
```

Copy `.env.example` to `.env` and fill in the variables.

### First run without `ADMINS`

If **`ADMINS`** in `.env` has **no users** (empty object `{}` or the variable is missing) and the **`cms_users`** table is empty, opening **`/cms/login`** shows a form to create the first administrator: email and password are written to **`ADMINS`** as an argon2 hash only. Then **restart the application** (`systemctl restart …` or restart the worker) so the process reloads the environment and imports the user into SQLite on startup. Then sign in at **`/cms/login`** with the same credentials.

### `ADMINS` and Verstka `user_email`

- The **`cms_users`** table is the single source of admins for `/cms` and for **`on_content_pre_save`**: **`metadata["user_email"]`** in the Verstka callback must match **`cms_users.user_email`**.
- On startup, if **`cms_users`** is empty, rows are imported from **`ADMINS`** in `.env` (JSON: `user_email` → **argon2** hash).
- In the Verstka editor, set the author email field to the **same email** as in the CMS.

Generate a password hash for `.env`:

```bash
python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('yourpassword'))"
```

### `VERSTKA_CALLBACK_URL`

Must match the public URL of the SDK callback endpoint, for example:

`https://your-domain/verstka/callback`

(the `/verstka` prefix matches `build_callback_router` by default.)

## Run (development)

```bash
source .venv/bin/activate
export DATABASE_URL=sqlite+aiosqlite:///./data.db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Create an article with path **`/index`** for the home page (nginx redirects `/` → `/index/`).

## Nginx and static files

Example config: [`staff/nginx.conf`](staff/nginx.conf).

- **`root`** points at **`storage/`**, where the app writes `index.html`, article media, and `sitemap.xml` / `favicon.ico`.
- **`/cms`** and **`/verstka/`** are proxied to uvicorn.
- **`/confs/*.conf`** is served directly from the **`confs/`** directory.
- **`/`** → **`/index/`**; articles are served with **`try_files`** and **`index.html`**.

## Autostart (systemd)

Example unit file: [`staff/demo-cms.service.example`](staff/demo-cms.service.example). Copy to `/etc/systemd/system/`, adjust paths, then run `systemctl daemon-reload` and `systemctl enable --now …`.

## Reserved article paths

You cannot create articles with an empty path, **`/cms`**, or **`/fonts`**. The **`storage/fonts/`** directory is reserved for Verstka fonts; the article template links **`/fonts/fonts.css`** when that file exists.

## Layout

- `app/` — application code, Jinja2 templates, static favicon source.
- `storage/` — generated files (listed in `.gitignore`).
- `staff/` — nginx and systemd examples.
