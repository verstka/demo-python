#!/usr/bin/env python3
"""Build and vendor the Verstka viewer wrapper into this portable demo."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def default_frontend_root(repo_root: Path) -> Path | None:
    candidate = repo_root.parent / "frontend"
    return candidate if (candidate / "verstka-viewer" / "package.json").is_file() else None


def parse_args(repo_root: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run `yarn workspace verstka-viewer build` in the Verstka frontend repo "
            "and copy verstka-viewer/dist/index.js into app/static/verstka-viewer/index.js."
        )
    )
    parser.add_argument(
        "--frontend-root",
        type=Path,
        default=default_frontend_root(repo_root),
        help="Path to /Volumes/git/verstka/frontend or another checkout of the frontend repo.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Copy the existing dist/index.js without running yarn build first.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=repo_root / "app" / "static" / "verstka-viewer" / "index.js",
        help="Destination file inside this demo repo.",
    )
    return parser.parse_args()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    args = parse_args(repo_root)
    frontend_root = args.frontend_root

    if frontend_root is None:
        raise SystemExit("Could not infer frontend root. Pass --frontend-root /path/to/frontend.")

    frontend_root = frontend_root.resolve()
    viewer_dir = frontend_root / "verstka-viewer"
    source = viewer_dir / "dist" / "index.js"

    if not (viewer_dir / "package.json").is_file():
        raise SystemExit(f"Not a Verstka frontend checkout: {frontend_root}")

    if not args.skip_build:
        subprocess.run(["yarn", "workspace", "verstka-viewer", "build"], cwd=frontend_root, check=True)

    if not source.is_file():
        raise SystemExit(f"Missing built viewer bundle: {source}")

    target = args.target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"Vendored {source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
