"""Evidence store: one interface, two backends (BUILD SPEC v3 §5.4)."""

from __future__ import annotations

import os

from .base import COLLECTIONS, Store, StoreError
from .readonly import ReadOnlyStore

__all__ = ["COLLECTIONS", "Store", "StoreError", "ReadOnlyStore", "open_store"]


def open_store(kind: str | None = None, *, read_only: bool = False, **kwargs) -> Store:
    """Open the backend named by `kind` or the STORAGE env var (default: sqlite).

    sqlite   -> kwargs: path (default env SOP_RCA_SQLITE_PATH or runs/store.sqlite)
    dynamodb -> kwargs: table_name (default env EVIDENCE_TABLE_NAME), region
    """
    kind = (kind or os.environ.get("STORAGE") or "sqlite").lower()
    if kind == "sqlite":
        from .sqlite_store import SQLiteStore

        store: Store = SQLiteStore(kwargs.pop("path", None) or os.environ.get("SOP_RCA_SQLITE_PATH", "runs/store.sqlite"))
    elif kind == "dynamodb":
        from .dynamodb_store import DynamoDBStore

        store = DynamoDBStore(**kwargs)
    else:
        raise StoreError(f"unknown STORAGE {kind!r}; expected 'sqlite' or 'dynamodb'")
    return ReadOnlyStore(store) if read_only else store
