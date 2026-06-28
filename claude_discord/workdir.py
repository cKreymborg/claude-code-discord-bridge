"""Working-directory discovery for the ``/cd`` and ``/cdnew`` commands.

Pure, filesystem-querying helpers (no Discord) so they are easy to test:
resolve the configured project roots and find matching directories to offer
in slash-command autocomplete.

Roots default to ``~/Developer`` and are configurable via the
``CCDB_PROJECT_ROOTS`` env var (comma-separated, ``~`` expanded).
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path

_DEFAULT_ROOTS = ("~/Developer",)

# Directory names never worth offering as a working dir (noise / build output).
_SKIP_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".cache",
    "target",
    ".idea",
    ".vscode",
}


def resolve_project_roots(
    environ: Mapping[str, str] | None = None,
    *,
    env_var: str = "CCDB_PROJECT_ROOTS",
) -> list[Path]:
    """Return the configured project roots (``~`` expanded).

    Defaults to ``~/Developer`` when the env var is unset/empty.
    """
    env = os.environ if environ is None else environ
    raw = env.get(env_var, "").strip()
    specs = [s.strip() for s in raw.split(",") if s.strip()] if raw else list(_DEFAULT_ROOTS)
    roots: list[Path] = []
    for spec in specs:
        path = Path(spec).expanduser()
        if path not in roots:
            roots.append(path)
    return roots


def _is_offerable(path: Path) -> bool:
    return path.is_dir() and path.name not in _SKIP_NAMES and not path.name.startswith(".")


def _children(directory: Path) -> list[Path]:
    try:
        return sorted(p for p in directory.iterdir() if _is_offerable(p))
    except OSError:
        return []


def find_directories(
    roots: Iterable[Path],
    query: str,
    *,
    limit: int = 25,
    max_depth: int = 2,
) -> list[Path]:
    """Return up to *limit* directories under *roots* matching *query*.

    Empty query → the immediate children of each root (your projects).
    Non-empty query → case-insensitive substring match on the directory name,
    searched up to *max_depth* levels deep, ranking name-prefix matches first.
    """
    roots = list(roots)
    query = query.strip().lower()
    results: list[Path] = []
    seen: set[Path] = set()

    if not query:
        for root in roots:
            for child in _children(root):
                if child not in seen:
                    seen.add(child)
                    results.append(child)
                    if len(results) >= limit:
                        return results
        return results

    matches: list[tuple[int, str, Path]] = []
    for root in roots:
        # Breadth-first walk, bounded by max_depth.
        frontier = [(root, 0)]
        while frontier:
            directory, depth = frontier.pop(0)
            for child in _children(directory):
                name = child.name.lower()
                if query in name:
                    rank = 0 if name.startswith(query) else 1
                    matches.append((rank, str(child).lower(), child))
                if depth + 1 < max_depth:
                    frontier.append((child, depth + 1))

    matches.sort(key=lambda item: (item[0], item[1]))
    for _, _, directory in matches:
        if directory not in seen:
            seen.add(directory)
            results.append(directory)
            if len(results) >= limit:
                break
    return results


def display_label(path: Path) -> str:
    """A short label for a directory choice (relative to home when possible)."""
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)
