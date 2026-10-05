"""DynamoDB backend (AWS mode). Targets the on-demand table `sop-rca-evidence` (infra/dynamodb.tf).

Key design (single table, same contract as SQLite):
    pk = "RUN#<run_id>"
    sk = "<collection>#<doc_id>#<version>"        ('#' is forbidden inside each part)
    doc = the document as a JSON *string*

Why a JSON string and not native attributes: boto3 rejects Python floats (it wants
Decimal), the KPI data is full of floats, and the store never filters server-side.
A string round-trips exactly and keeps backend behaviour identical to SQLite.

Not exercised against real AWS in Phase 1: tests use moto (an in-memory fake).
The agent's IAM role is read-only (GetItem/Query), so only the harness and
enrichment ever call the write methods.
"""

from __future__ import annotations

import json
import os
import time

from .base import Store


class DynamoDBStore(Store):
    def __init__(self, table_name: str | None = None, region: str | None = None, resource=None):
        if resource is None:
            import boto3  # imported lazily: the local SQLite path never needs AWS libraries

            resource = boto3.resource("dynamodb", region_name=region or os.environ.get("AWS_REGION", "eu-north-1"))
        self._table = resource.Table(table_name or os.environ.get("EVIDENCE_TABLE_NAME", "sop-rca-evidence"))

    @staticmethod
    def _pk(run_id: str) -> str:
        return f"RUN#{run_id}"

    def _items(self, run_id: str, sk_prefix: str) -> list[dict]:
        """All items of a run whose sort key starts with sk_prefix (handles pagination)."""
        from boto3.dynamodb.conditions import Key

        items: list[dict] = []
        condition = Key("pk").eq(self._pk(run_id))
        if sk_prefix:  # DynamoDB rejects begins_with(sk, ""): an empty prefix means "the whole run"
            condition = condition & Key("sk").begins_with(sk_prefix)
        paginator = self._table.meta.client.get_paginator("query")
        for page in paginator.paginate(TableName=self._table.name, KeyConditionExpression=condition,
                                       ConsistentRead=True):
            items.extend(page["Items"])
        return items

    def _put(self, run_id, collection, doc_id, doc, version):
        self._table.put_item(
            Item={
                "pk": self._pk(run_id),
                "sk": f"{collection}#{doc_id}#{version}",
                "run_id": run_id,  # lets the table's gsi1-run-id index find a whole run
                "collection": collection,
                "doc_id": doc_id,
                "version": version,
                "seq": time.time_ns(),  # write order; ns resolution is enough for one writer
                "doc": json.dumps(doc, sort_keys=True),
            }
        )

    def _get(self, run_id, collection, doc_id, version):
        if version is not None:
            item = self._table.get_item(Key={"pk": self._pk(run_id), "sk": f"{collection}#{doc_id}#{version}"}, ConsistentRead=True).get("Item")
            return json.loads(item["doc"]) if item else None
        items = self._items(run_id, f"{collection}#{doc_id}#")  # trailing '#' stops "A" matching "AB"
        return json.loads(max(items, key=lambda i: int(i["seq"]))["doc"]) if items else None

    def _query(self, run_id, collection):
        latest: dict[str, dict] = {}
        for item in self._items(run_id, f"{collection}#"):
            current = latest.get(item["doc_id"])
            if current is None or int(item["seq"]) > int(current["seq"]):
                latest[item["doc_id"]] = item
        return [json.loads(latest[doc_id]["doc"]) for doc_id in sorted(latest)]

    def _versions(self, run_id, collection, doc_id):
        items = sorted(self._items(run_id, f"{collection}#{doc_id}#"), key=lambda i: int(i["seq"]))
        return [i["version"] for i in items]

    def _delete_run(self, run_id):
        items = self._items(run_id, "")
        with self._table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
        return len(items)
