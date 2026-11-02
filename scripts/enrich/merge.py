"""Merge hand-written or session-written entries into content/enrich/<name>.json.

Usage: python3 scripts/enrich/merge.py <name> <entries.json>
entries.json maps verse id -> {translation, meaning, explanation, keywords}. Checks ids exist in
content/import/<name>.json and that every field is present, then merges (newer entries win).
"""
import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
name, src = sys.argv[1], sys.argv[2]
ids = {v["id"] for v in json.load(open(os.path.join(ROOT, "content", "import", name + ".json"), encoding="utf-8"))["verses"]}
new = json.load(open(src, encoding="utf-8"))
for vid, e in new.items():
    if vid not in ids:
        raise SystemExit(f"Unknown verse id {vid}")
    for k in ("translation", "meaning", "explanation", "keywords"):
        if k not in e:
            raise SystemExit(f"{vid}: missing {k}")
    if not e["translation"].strip() or not e["meaning"].strip():
        raise SystemExit(f"{vid}: empty translation or meaning")
path = os.path.join(ROOT, "content", "enrich", name + ".json")
cur = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
cur.update(new)
with open(path, "w", encoding="utf-8") as f:
    json.dump(dict(sorted(cur.items(), key=lambda kv: [int(x) if x.isdigit() else x for x in kv[0].split("-")])), f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"{name}: +{len(new)} -> {len(cur)} verses")
