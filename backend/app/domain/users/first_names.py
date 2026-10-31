"""First names a user can pick, so a caller can say their name.

Nothing a user types may reach the model, so the name is never free text: it
must be an entry of ``first_names.txt`` (one name per line), and the stored
spelling is always the list's. The list is ours, written by hand from common
names in Germany and English-speaking countries; add a name with a line.
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

from app.core.errors import UnknownFirstName

_FILE = Path(__file__).with_name("first_names.txt")
SEARCH_LIMIT = 20


def _key(name: str) -> str:
    return unicodedata.normalize("NFC", name.strip()).casefold()


@lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    lines = _FILE.read_text(encoding="utf-8").splitlines()
    return {_key(n): n for n in lines if n.strip()}


def all_names() -> list[str]:
    return list(_names().values())


def canonical(name: str) -> str | None:
    """The list's spelling of ``name``, or None when it isn't on the list."""
    return _names().get(_key(name))


def require(name: str) -> str:
    found = canonical(name)
    if found is None:
        raise UnknownFirstName()
    return found


def search(query: str, limit: int = SEARCH_LIMIT) -> list[str]:
    """Names starting with ``query``, ignoring case, in list order."""
    key = _key(query)
    if not key:
        return []
    return [n for k, n in _names().items() if k.startswith(key)][:limit]
