"""keep_current.py: the weekly check. Detect, propose, never apply without approval.

A card line cites the id of the row it came from, and a row's id is derived from its text. When a
source changes a sentence, the grounding refresh removes the old row, so the cited id stops
resolving: that is drift. The proposal is the nearest current row from the same source.

    python3 -m fieldsys.keep_current --detect     # -> review/proposals.json, review/digest.md
    # a person lists the proposal ids they accept in review/approved.txt
    python3 -m fieldsys.keep_current --apply      # rewrites only the approved lines
"""
import glob, hashlib, json, os, sys

from fieldkit import approvals, qdrant as Q

from . import card

CARDS, REVIEW = "cards", "review"


def detect():
    proposals = []
    for path in sorted(glob.glob(os.path.join(CARDS, "*.md"))):
        cited = [(l, m) for l in open(path).read().splitlines() if (m := card.LINE.match(l))]
        live = {str(p["id"]) for p in Q.get(card.COLL, [m["id"] for _, m in cited])}
        for old, m in cited:
            if m["id"] in live:
                continue
            new = card.best(m["text"], "docs" if m["label"] == "Docs" else "field")
            proposals.append({"id": hashlib.sha1(f"{path}|{m['id']}".encode()).hexdigest()[:8], "asset": path,
                              "why": "the cited source line was retired", "old": old,
                              "new": card.line(new) if new else None})
    os.makedirs(REVIEW, exist_ok=True)
    json.dump(proposals, open(os.path.join(REVIEW, "proposals.json"), "w"), indent=1)
    digest = [f"# Keep-current digest: {len(proposals)} proposal(s)", ""]
    for p in proposals:
        digest += [f"## {p['id']} in {p['asset']}", f"Why: {p['why']}", f"Now:      {p['old']}",
                   f"Proposed: {p['new'] or '(remove the line: no current source says this)'}", ""]
    open(os.path.join(REVIEW, "digest.md"), "w").write("\n".join(digest))
    return proposals


def apply():
    """Rewrite only the lines a person approved. Returns the ids applied."""
    approved = approvals.read_id_list(os.path.join(REVIEW, "approved.txt"))
    done, queue = [], os.path.join(REVIEW, "proposals.json")
    for p in (json.load(open(queue)) if os.path.exists(queue) else []):
        if p["id"] not in approved:
            continue
        lines = open(p["asset"]).read().split("\n")
        if p["old"] not in lines:
            continue                                # already applied, or the card was rebuilt
        i = lines.index(p["old"])
        lines[i:i + 1] = [p["new"]] if p["new"] else []
        open(p["asset"], "w").write("\n".join(lines))
        done.append(p["id"])
    return done


if __name__ == "__main__":
    if "--apply" in sys.argv:
        print(f"applied: {apply() or 'nothing approved'}")
    else:
        found = detect()
        print(open(os.path.join(REVIEW, "digest.md")).read() if found else "all cited lines are current")
