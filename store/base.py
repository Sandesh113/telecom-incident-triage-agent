"""Repository interface for the evidence store (BUILD SPEC v3 §5.4).

What it is: one small document-store contract with two backends (SQLite locally,
DynamoDB on AWS). Every other component talks to this interface, never to a database.

Why it is shaped this way:
  * The target operator platform uses a document database. A document-shaped
    interface (collection + id -> JSON document) keeps the backend swappable.
  * Every document belongs to one run (an opaque UUID), so runs never mix.
  * Some collections are versioned (reports): the same doc_id can hold
    several versions; "latest" means the most recently written one.

At runtime: the harness and enrichment write; the agent only reads (see readonly.py).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

# The collections from BUILD SPEC v3 §5.4, minus `topology`: topology is static reference-file
# content now (see DECISIONS.md), not a queryable store. A typo in a name must fail loudly.
COLLECTIONS: tuple[str, ...] = (
    "events_normalized",
    "observations",
    "kpi_windows",
    "changes",
    "impact_records",
    "incidents",
    "unresolved_ids",
    "unmapped_alarms",
    "reports",  # versioned
)

# '#' is the key separator in the DynamoDB backend, so no backend accepts it in an ID.
_FORBIDDEN_IN_KEYS = "#"


class StoreError(Exception):
    """Raised for bad arguments or a forbidden operation (e.g. a write to a read-only store)."""


def check_key_part(name: str, value: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, str):
        raise StoreError(f"{name} must be a string, got {type(value).__name__}")
    if not value and not allow_empty:
        raise StoreError(f"{name} must not be empty")
    if _FORBIDDEN_IN_KEYS in value:
        raise StoreError(f"{name} {value!r} must not contain {_FORBIDDEN_IN_KEYS!r}")


def check_collection(collection: str) -> None:
    if collection not in COLLECTIONS:
        raise StoreError(f"unknown collection {collection!r}; expected one of {COLLECTIONS}")


def check_document(doc: Any) -> None:
    if not isinstance(doc, dict):
        raise StoreError(f"document must be a dict, got {type(doc).__name__}")
    try:
        json.dumps(doc)
    except (TypeError, ValueError) as exc:  # not JSON-serialisable
        raise StoreError(f"document is not JSON-serialisable: {exc}") from exc


def matches(doc: dict, where: dict[str, Any] | None) -> bool:
    """Top-level equality filter. Deliberately simple so both backends behave the same."""
    return not where or all(doc.get(key) == value for key, value in where.items())


class Store(ABC):
    """The contract. Backends implement the abstract methods; validation lives here."""

    # ---- writes --------------------------------------------------------------------

    def put(self, run_id: str, collection: str, doc_id: str, doc: dict, version: str = "") -> None:
        """Insert or replace one document. Replacing makes it the 'latest' version of doc_id."""
        check_key_part("run_id", run_id)
        check_collection(collection)
        check_key_part("doc_id", doc_id)
        check_key_part("version", version, allow_empty=True)
        check_document(doc)
        self._put(run_id, collection, doc_id, doc, version)

    def put_many(self, run_id: str, collection: str, docs: dict[str, dict]) -> None:
        """Convenience: write {doc_id: doc} (unversioned)."""
        for doc_id, doc in docs.items():
            self.put(run_id, collection, doc_id, doc)

    def delete_run(self, run_id: str) -> int:
        """Remove every document of one run. Returns how many were removed."""
        check_key_part("run_id", run_id)
        return self._delete_run(run_id)

    # ---- reads ---------------------------------------------------------------------

    def get(self, run_id: str, collection: str, doc_id: str, version: str | None = None) -> dict | None:
        """One document, or None. version=None means the latest written version."""
        check_key_part("run_id", run_id)
        check_collection(collection)
        check_key_part("doc_id", doc_id)
        if version is not None:
            check_key_part("version", version, allow_empty=True)
        return self._get(run_id, collection, doc_id, version)

    def query(self, run_id: str, collection: str, where: dict[str, Any] | None = None) -> list[dict]:
        """Latest version of every document in a collection, ordered by doc_id, optionally filtered."""
        check_key_part("run_id", run_id)
        check_collection(collection)
        return [doc for doc in self._query(run_id, collection) if matches(doc, where)]

    def versions(self, run_id: str, collection: str, doc_id: str) -> list[str]:
        """Version labels held for a doc_id, oldest write first."""
        check_key_part("run_id", run_id)
        check_collection(collection)
        check_key_part("doc_id", doc_id)
        return self._versions(run_id, collection, doc_id)

    def close(self) -> None:  # pragma: no cover - default is a no-op
        return None

    # ---- backend hooks -------------------------------------------------------------

    @abstractmethod
    def _put(self, run_id: str, collection: str, doc_id: str, doc: dict, version: str) -> None: ...

    @abstractmethod
    def _get(self, run_id: str, collection: str, doc_id: str, version: str | None) -> dict | None: ...

    @abstractmethod
    def _query(self, run_id: str, collection: str) -> list[dict]: ...

    @abstractmethod
    def _versions(self, run_id: str, collection: str, doc_id: str) -> list[str]: ...

    @abstractmethod
    def _delete_run(self, run_id: str) -> int: ...
