"""SQLite backend (local mode). One table; each row is one JSON document.

Why one generic table: the collections are document-shaped and read by key or by
collection, never joined in SQL. That is exactly what DynamoDB offers too, so the two
backends stay behaviourally identical.

Ordering: `seq` is a write counter. "Latest version" of a doc_id = the row with the
highest seq, so re-putting an older version label makes it the latest again.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .base import Store

_SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    run_id     TEXT    NOT NULL,
    collection TEXT    NOT NULL,
    doc_id     TEXT    NOT NULL,
    version    TEXT    NOT NULL,
    seq        INTEGER NOT NULL,
    doc        TEXT    NOT NULL,
    PRIMARY KEY (run_id, collection, doc_id, version)
);
CREATE INDEX IF NOT EXISTS docs_by_collection ON docs (run_id, collection, doc_id, seq);
"""


class SQLiteStore(Store):
    def __init__(self, path: str | Path = "runs/store.sqlite"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # Strands dispatches synchronous tools onto worker threads. Calls are serialized
        # by SequentialToolExecutor; allow the read-only tool session to cross threads.
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def _put(self, run_id, collection, doc_id, doc, version):
        # seq = max(seq)+1 inside the same statement: a single writer per run is assumed.
        self._db.execute(
            """
            INSERT INTO docs (run_id, collection, doc_id, version, seq, doc)
            VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM docs), ?)
            ON CONFLICT (run_id, collection, doc_id, version)
            DO UPDATE SET doc = excluded.doc, seq = excluded.seq
            """,
            (run_id, collection, doc_id, version, json.dumps(doc, sort_keys=True)),
        )
        self._db.commit()

    def _get(self, run_id, collection, doc_id, version):
        if version is None:
            row = self._db.execute(
                "SELECT doc FROM docs WHERE run_id=? AND collection=? AND doc_id=? ORDER BY seq DESC LIMIT 1",
                (run_id, collection, doc_id),
            ).fetchone()
        else:
            row = self._db.execute(
                "SELECT doc FROM docs WHERE run_id=? AND collection=? AND doc_id=? AND version=?",
                (run_id, collection, doc_id, version),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def _query(self, run_id, collection):
        rows = self._db.execute(
            """
            SELECT d.doc FROM docs d
            WHERE d.run_id = ? AND d.collection = ?
              AND d.seq = (SELECT MAX(seq) FROM docs
                           WHERE run_id = d.run_id AND collection = d.collection AND doc_id = d.doc_id)
            ORDER BY d.doc_id
            """,
            (run_id, collection),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def _versions(self, run_id, collection, doc_id):
        rows = self._db.execute(
            "SELECT version FROM docs WHERE run_id=? AND collection=? AND doc_id=? ORDER BY seq",
            (run_id, collection, doc_id),
        ).fetchall()
        return [r[0] for r in rows]

    def _delete_run(self, run_id):
        cur = self._db.execute("DELETE FROM docs WHERE run_id = ?", (run_id,))
        self._db.commit()
        return cur.rowcount

    def close(self):
        self._db.close()
