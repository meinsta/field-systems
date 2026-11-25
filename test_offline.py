"""Offline checks against an in-memory stand-in for the cluster. Run: python3 test_offline.py"""
import json, os, re, tempfile

from fieldkit import qdrant as Q

from fieldsys import card, keep_current as KC

words = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
OLD = "The old key keeps working for 24 hours."
ROWS = {}


def _row(source, text, **extra):
    pid = Q.point_id(source, text)
    ROWS[pid] = {"id": pid, "payload": {"text": text, "source": source, **extra}}
    return pid


def _fake():
    ROWS.clear()
    Q.get = lambda name, ids: [ROWS[i] for i in ids if i in ROWS]
    Q.hybrid_query = lambda name, q, limit=1, flt=None, **k: sorted(
        [r for r in ROWS.values() if r["payload"]["source"] == flt["must"][0]["match"]["value"]],
        key=lambda r: -len(words(q) & words(r["payload"]["text"])))[:limit]
    os.chdir(tempfile.mkdtemp())
    json.dump([{"id": "sec", "title": "Security card", "topics": ["can we rotate a key and keep the old one working?"]}], open("registry.json", "w"))


def test_build_detect_approve_apply():
    _fake()
    old_id = _row("docs", OLD)
    _row("field", "Security blocks the rollout without key rotation.", segment="enterprise", vertical="grocery delivery")
    card.build()
    md = open("cards/sec.md").read()
    assert f"- Docs: {OLD} `[{old_id}]`" in md and "- Customer (enterprise, grocery delivery): Security blocks" in md
    assert KC.detect() == []                                           # nothing drifted yet

    del ROWS[old_id]                                                   # the docs changed; the refresh pruned the old row
    new_id = _row("docs", "The old key keeps working for 48 hours.")
    (p,) = KC.detect()
    assert p["old"].endswith(f"`[{old_id}]`") and p["new"] == f"- Docs: The old key keeps working for 48 hours. `[{new_id}]`"
    assert p["id"] in open("review/digest.md").read()

    assert KC.apply() == [] and open("cards/sec.md").read() == md       # proposed, not approved: the card is untouched
    open("review/approved.txt", "w").write(p["id"] + "  # checked against the docs\n")
    assert KC.apply() == [p["id"]] and "48 hours" in open("cards/sec.md").read() and "24 hours" not in open("cards/sec.md").read()
    assert KC.detect() == [] and KC.apply() == []                      # current again; a second apply is a no-op


def test_a_line_with_no_current_source_is_proposed_for_removal():
    _fake()
    old_id = _row("docs", OLD)
    card.build()
    ROWS.clear()
    (p,) = KC.detect()
    assert p["new"] is None
    open("review/approved.txt", "w").write(p["id"])
    KC.apply()
    assert old_id not in open("cards/sec.md").read()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
