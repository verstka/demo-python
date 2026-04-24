"""Write ADMINS into .env for first-run CMS bootstrap (no secrets in code)."""

from __future__ import annotations

import json
import re
from pathlib import Path


def merge_admins_into_dotenv(*, dotenv_path: Path, admins: dict[str, str]) -> None:
    """
    Set or replace ADMINS=... in dotenv_path while preserving other lines.

    Writes a single-line JSON object (email -> argon2 hash). Uses atomic replace.
    """
    payload = json.dumps(admins, separators=(",", ":"), ensure_ascii=False)
    new_line = f"ADMINS={payload}\n"

    dotenv_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    if dotenv_path.exists():
        text = dotenv_path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)

    admins_key = re.compile(r"^(export\s+)?ADMINS\s*=")

    out: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.lstrip()
        if admins_key.match(stripped):
            if not replaced:
                out.append(new_line)
                replaced = True
            continue
        out.append(line)

    if not replaced:
        if out and not out[-1].endswith("\n"):
            out[-1] = out[-1] + "\n"
        out.append(new_line)

    body = "".join(out)
    tmp = dotenv_path.with_name(dotenv_path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(dotenv_path)


def default_dotenv_path() -> Path:
    """Path to .env relative to process working directory (same as pydantic-settings)."""
    return Path(".env")
