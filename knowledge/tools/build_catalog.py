"""Build catalog.json (the agent's section index) from the knowledge Markdown files.

Deterministic, no LLM. Each section is a heading "## [ID] Title" (or "# [ID] Title")
followed by a "> summary:" line. Validates: unique IDs, every [ID] reference
resolves (including ranges like [RULES.1]–[RULES.9]), and every ID referenced by
SKILL.md exists. Exits non-zero on any error.

Usage: python tools/build_catalog.py  (run from the knowledge/ folder)
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ["shared-rules.md", "sops/*.md", "reference/*.md"]
HEAD = re.compile(r"^(#{1,3}) \[([A-Z0-9.\-]+)\] (.+)$")
REF = re.compile(r"\[([A-Z]+(?:-[A-Z]+)?(?:-\d+)?(?:\.[A-Z0-9]+)?)\](?:\s*[–-]\s*\[([A-Z]+(?:-[A-Z]+)?\.\d+)\])?")
PLAIN_SOP = re.compile(r"\bSOP-0\d\.\d\b")

def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1); fm[k.strip()] = v.strip().strip('"')
    return fm

def parse(path):
    text = path.read_text(encoding="utf-8")
    fm = front_matter(text)
    lines = text.splitlines()
    doc = {"doc_id": fm.get("doc_id"), "file": path.relative_to(ROOT).as_posix(),
           "version": fm.get("version"), "summary": None, "sections": []}
    if fm.get("triggers"):
        doc["triggers"] = [t.strip() for t in fm["triggers"].strip("[]").split(",") if t.strip()]
    first_summary_done = False
    for i, line in enumerate(lines):
        if line.startswith("> summary:") and not first_summary_done:
            doc["summary"] = line.split(":", 1)[1].strip(); first_summary_done = True
        m = HEAD.match(line)
        if not m:
            continue
        level, nid, title = len(m.group(1)), m.group(2), m.group(3)
        summary = next((l.split(":", 1)[1].strip() for l in lines[i + 1:i + 4] if l.startswith("> summary:")), None)
        node = {"node_id": nid, "title": title, "summary": summary, "file": doc["file"], "anchor": line.lstrip("# ").strip()}
        body = "\n".join(lines[i + 1:i + 12])
        if "step_type: read_only" in body:
            node["step_type"] = "read_only"
        if level == 1:
            doc["doc_node"] = node
        else:
            doc["sections"].append(node)
    return doc, text

def expand(a, b):
    if not b:
        return [a]
    pa, na = a.rsplit(".", 1); pb, nb = b.rsplit(".", 1)
    return [f"{pa}.{n}" for n in range(int(na), int(nb) + 1)] if pa == pb else [a, b]

def main():
    docs, texts, errors = [], {}, []
    for pattern in SOURCES:
        for p in sorted(ROOT.glob(pattern)):
            d, t = parse(p); docs.append(d); texts[d["file"]] = t
    ids = {}
    for d in docs:
        nodes = d["sections"] + ([d["doc_node"]] if "doc_node" in d else [])
        for n in nodes:
            if n["node_id"] in ids:
                errors.append(f"duplicate ID {n['node_id']} in {d['file']} and {ids[n['node_id']]}")
            ids[n["node_id"]] = d["file"]
        if d.get("doc_id") and d["doc_id"] not in ids:
            ids[d["doc_id"]] = d["file"]
        if any(n["summary"] is None for n in d["sections"]):
            errors.append(f"missing summary line in {d['file']}")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    texts["SKILL.md"] = skill
    for f, t in texts.items():
        body = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)
        for m in REF.finditer(body):
            for rid in expand(m.group(1), m.group(2)):
                if rid not in ids and not rid.startswith("REF-0"):
                    errors.append(f"{f}: unresolved reference [{rid}]")
        for rid in PLAIN_SOP.findall(body):
            if rid not in ids:
                errors.append(f"{f}: unresolved step reference {rid}")
    catalog = {
        "catalog_version": "0.1",
        "generated_from": [d["file"] for d in docs],
        "usage": "list_sections returns this tree; read_section(node_id) returns the section text.",
        "documents": [{k: v for k, v in d.items() if k != "sections"} | {"sections": d["sections"]} for d in docs],
        "counts": {"documents": len(docs), "sections": sum(len(d["sections"]) for d in docs)},
    }
    (ROOT / "catalog.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    per = {d["doc_id"]: len(d["sections"]) for d in docs}
    print("sections per document:", per)
    print("reference sections:", sum(v for k, v in per.items() if k.startswith("REF")))
    if errors:
        print("ERRORS:"); [print(" -", e) for e in errors]; sys.exit(1)
    print("catalog.json written; all IDs unique and every reference resolves.")

if __name__ == "__main__":
    main()
