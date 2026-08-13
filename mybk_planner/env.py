"""Minimal KEY=VALUE env loader.

Reads a plain `.env` file (one KEY=VALUE per line, blank lines and # comments
skipped, optional quotes) — the .env format compatible with the portal's own
login scripts.

The .env file is never committed; the loader is only used to obtain the
HCMUT account credentials the operator already possesses.

Primary variable names are ``MYBK_USERNAME`` / ``MYBK_PASSWORD`` /
``MYBK_MSSV``; the legacy ``MYBK_TEST_*`` names keep working as aliases.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str | Path | None) -> dict[str, str]:
    """Parse a KEY=VALUE file into a dict. Missing file -> empty dict."""
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    result: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def resolve(
    key: str,
    env_file_vars: dict[str, str],
    cli_value: str | None = None,
    aliases: tuple[str, ...] = (),
) -> str | None:
    """Priority: CLI argument > OS env > .env file.

    ``aliases`` are fallback variable names tried in order after the primary
    key, across both OS env and the .env file (e.g. ``MYBK_USERNAME`` falling
    back to the legacy ``MYBK_TEST_USERNAME``).
    """
    keys = (key, *aliases)
    if cli_value:
        return cli_value
    for k in keys:
        if os.environ.get(k):
            return os.environ[k]
    for k in keys:
        if env_file_vars.get(k):
            return env_file_vars[k]
    return None


def default_env_path() -> Path | None:
    """Find the credentials file: repo-root `.env` first, then the legacy
    `.env.mybk-test` names for existing setups."""
    for candidate in (".env", "../.env", ".env.mybk-test", "../.env.mybk-test"):
        p = Path(candidate)
        if p.is_file():
            return p.resolve()
    return None
