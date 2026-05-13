"""Article path validation and filesystem mapping under storage/."""

from __future__ import annotations

import re
from pathlib import Path

# Logical article path: leading slash, segments [a-zA-Z0-9/_-]+
_PATH_RE = re.compile(r"^/[a-zA-Z0-9/_-]+$")

_RESERVED_PREFIXES = ("/cms", "/fonts")
_RESERVED_EXACT = frozenset({"", "/"})


def normalize_article_path(path: str) -> str:
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    p = p.rstrip("/") or "/"
    if p != "/" and p.endswith("/"):
        p = p.rstrip("/")
    return p


def is_valid_article_path(path: str) -> bool:
    n = normalize_article_path(path)
    if n in _RESERVED_EXACT:
        return False
    for pref in _RESERVED_PREFIXES:
        if n == pref or n.startswith(pref + "/"):
            return False
    if not _PATH_RE.match(n):
        return False
    if ".." in n or "//" in n:
        return False
    return True


def path_to_storage_relative(article_path: str) -> str:
    """Map /blog/post -> blog/post (no leading slash, safe segments)."""
    n = normalize_article_path(article_path)
    if n == "/":
        raise ValueError("invalid path")
    rel = n.lstrip("/")
    parts = rel.split("/")
    for part in parts:
        if part in ("", ".", "..") or ".." in part:
            raise ValueError("unsafe path segment")
    return rel


def storage_article_dir(storage_root: Path, article_path: str) -> Path:
    rel = path_to_storage_relative(article_path)
    return (storage_root / rel).resolve()


def storage_fonts_dir(storage_root: Path) -> Path:
    return (storage_root / "fonts").resolve()
