"""card.py: build field cards from the grounded collection. This module writes no new facts: every
line is a row from the index, printed with the id it came from, so the keep-current check can ask
later whether that row still exists.

    python3 -m fieldsys.card            # registry.json -> cards/<id>.md
"""
import json, os, re

from fieldkit import qdrant as Q

COLL = os.environ.get("FIELD_COLLECTION", "grounding")
LINE = re.compile(r"^- (?P<label>[^:]+): (?P<text>.*) `\[(?P<id>[0-9a-f-]{36})\]`$")


def line(row):
    """One card line from one index row. Field rows are described by segment and vertical, never by name."""
    p = row["payload"]
    label = "Docs" if p["source"] == "docs" else f"Customer ({p['segment']}, {p['vertical']})"
    return f"- {label}: {p['text']} `[{row['id']}]`"


def best(text, source):
    hits = Q.hybrid_query(COLL, text, limit=1, flt={"must": [{"key": "source", "match": {"value": source}}]})
    return hits[0] if hits else None


def build(registry="registry.json", out="cards"):
    os.makedirs(out, exist_ok=True)
    for asset in json.load(open(registry)):
        md = [f"# {asset['title']}", ""]
        for topic in asset["topics"]:
            md += [f"## {topic}"] + [line(r) for r in (best(topic, "docs"), best(topic, "field")) if r] + [""]
        open(os.path.join(out, asset["id"] + ".md"), "w").write("\n".join(md))
        print(f"built {out}/{asset['id']}.md")


if __name__ == "__main__":
    build()
