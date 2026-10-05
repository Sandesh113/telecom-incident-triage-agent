"""Vectorless knowledge access. The catalog is an index, never an arbitrary file reader."""
import json
import re
from pathlib import Path, PurePosixPath


def allowed(key: str) -> bool:
    path = PurePosixPath(key)
    if "\\" in key or path.is_absolute() or ".." in path.parts:
        return False
    return key in ("SKILL.md", "catalog.json", "shared-rules.md") or (
        len(path.parts) == 2 and path.parts[0] in ("sops", "reference") and path.suffix == ".md")


class Knowledge:
    def __init__(self, reader):
        self._reader = reader
        self.skill = self.read("SKILL.md")
        self.catalog = json.loads(self.read("catalog.json"))
        self.nodes = {}
        for doc in self.catalog["documents"]:
            for node in doc["sections"] + ([doc["doc_node"]] if "doc_node" in doc else []):
                if not allowed(node["file"]):
                    raise ValueError("catalog contains a forbidden path")
                self.nodes[node["node_id"]] = {**node, "doc_id": doc["doc_id"]}

    @classmethod
    def local(cls, root):
        root = Path(root).resolve()
        def reader(key):
            path = (root / key).resolve()
            if not path.is_relative_to(root):
                raise ValueError("knowledge symlink escapes root")
            return path.read_text(encoding="utf-8")
        return cls(reader)

    @classmethod
    def s3(cls, client, bucket):
        def reader(key):
            with client.get_object(Bucket=bucket, Key=key)["Body"] as body:
                return body.read().decode("utf-8")
        return cls(reader)

    def read(self, key):
        if not allowed(key):
            raise ValueError("forbidden knowledge path")
        return self._reader(key)

    def list_sections(self, doc_id=None):
        return [{key: node[key] for key in ("node_id", "title", "summary", "doc_id")}
                for node in self.nodes.values() if doc_id is None or node["doc_id"] == doc_id]

    def read_section(self, node_id):
        node = self.nodes[node_id]
        lines = self.read(node["file"]).splitlines()
        start = next((i for i, line in enumerate(lines)
                      if re.match(r"^(#{1,3}) \[" + re.escape(node_id) + r"\] ", line)), None)
        if start is None:
            raise ValueError(f"catalog heading absent: {node_id}")
        level = len(re.match(r"^#+", lines[start]).group())
        end = len(lines)
        for i in range(start + 1, len(lines)):
            heading = re.match(r"^(#{1,3}) ", lines[i])
            if heading and len(heading[1]) <= level:
                end = i
                break
        return "\n".join(lines[start:end])
