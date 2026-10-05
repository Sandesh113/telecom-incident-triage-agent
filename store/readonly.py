"""Read-only wrapper. The agent's tools receive this, never a writable store.

Why: CLAUDE.md rule 8 says the agent never writes the evidence table (reports go to S3).
The IAM role already enforces it on AWS; this enforces it in code locally, so the same
rule holds in `make demo-local` and in the tests.
"""

from __future__ import annotations

from .base import Store, StoreError


class ReadOnlyStore(Store):
    def __init__(self, inner: Store):
        self._inner = inner

    def _put(self, *args, **kwargs):
        raise StoreError("store is read-only for the agent: it never writes evidence")

    def _delete_run(self, run_id):
        raise StoreError("store is read-only for the agent: it never deletes evidence")

    def _get(self, run_id, collection, doc_id, version):
        return self._inner.get(run_id, collection, doc_id, version)

    def _query(self, run_id, collection):
        return self._inner.query(run_id, collection)

    def _versions(self, run_id, collection, doc_id):
        return self._inner.versions(run_id, collection, doc_id)

    def close(self):
        self._inner.close()
