"""Draft the reader-facing content for every imported verse with Claude, using the Message Batches API.

For each verse it writes:
  translation   a faithful plain-English translation (our own work)
  meaning       one or two very simple sentences: what the verse is saying, for a first-time reader
  explanation   a short paragraph of context (who is speaking, what is happening, why it matters)
  keywords      3-5 key Sanskrit words with their meanings

Results go to content/enrich/<import-file>.json and load as drafts (hidden until reviewed).
Verses that already have an enrich entry are skipped, so the script can be re-run safely.

Run (needs ANTHROPIC_API_KEY in the environment):
  pip install anthropic
  python3 scripts/enrich/generate.py submit [--only gita] [--limit 200]   # creates batches, saves their ids
  python3 scripts/enrich/generate.py status                               # shows progress
  python3 scripts/enrich/generate.py collect                              # writes finished results

Batches cost half the normal price and usually finish within an hour.
"""

import argparse
import glob
import json
import os
import sys

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMPORT_DIR = os.path.join(ROOT, "content", "import")
ENRICH_DIR = os.path.join(ROOT, "content", "enrich")
STATE = os.path.join(ROOT, ".cache", "enrich", "batches.json")

MODEL = os.environ.get("VEDA_ENRICH_MODEL", "claude-opus-5-5")
CHUNK = 8  # consecutive verses per request, so the model sees the flow of the passage
BATCH_MAX = 10_000  # requests per batch (the API allows up to 100,000)

SYSTEM = """You write content for a free app that helps ordinary people read India's scriptures one verse at a time.
For each verse you are given its reference, the Sanskrit (IAST) and, when available, a public-domain English translation.

For every verse, produce:
- translation: a faithful, plain modern English translation of this verse (not a paraphrase of the whole passage). Keep names. No archaic words like "thou" or "hath".
- meaning: one or two short, simple sentences (under 40 words) saying what the verse means, for a reader with no background. Warm, clear, no jargon.
- explanation: 50 to 90 words of context: who is speaking to whom, what is happening at this point, and why the verse matters. Stay true to the text; do not invent events.
- keywords: 3 to 5 important Sanskrit words that actually appear in the verse, in IAST, each with a short English meaning.

Rules: base everything on the Sanskrit given. If a verse is a list of names or a ritual detail, say so plainly rather than inventing a lesson. Never add Sanskrit that is not in the verse."""

SCHEMA = {
    "type": "object",
    "properties": {
        "verses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "translation": {"type": "string"},
                    "meaning": {"type": "string"},
                    "explanation": {"type": "string"},
                    "keywords": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"word": {"type": "string"}, "meaning": {"type": "string"}},
                            "required": ["word", "meaning"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "translation", "meaning", "explanation", "keywords"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verses"],
    "additionalProperties": False,
}


def load_imports(only):
    for path in sorted(glob.glob(os.path.join(IMPORT_DIR, "*.json"))):
        name = os.path.basename(path)[:-5]
        if only and not name.startswith(only):
            continue
        yield name, json.load(open(path, encoding="utf-8"))


def load_enriched(name):
    path = os.path.join(ENRICH_DIR, name + ".json")
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}


def prompt_for(scripture, chunk):
    parts = [f"Scripture: {scripture}"]
    for v in chunk:
        parts.append(f"\nid: {v['id']}\nreference: {v['reference']}" + (f"\nspeaker: {v['speaker']}" if v.get("speaker") else ""))
        parts.append("sanskrit (IAST):\n" + v["transliteration"])
        if v["translation"].get("en"):
            parts.append("public-domain translation: " + v["translation"]["en"])
    parts.append(f"\nReturn one entry for each of the {len(chunk)} verses above, in order, using the same ids.")
    return "\n".join(parts)


def submit(args):
    client = anthropic.Anthropic()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"batches": []}
    pending = {cid for b in state["batches"] if not b.get("collected") for cid in b["custom_ids"]}
    requests = []
    for name, data in load_imports(args.only):
        done = load_enriched(name)
        todo = [v for v in data["verses"] if v["id"] not in done]
        scripture = data["scripture"].replace("-", " ").title()
        for i in range(0, len(todo), CHUNK):
            chunk = todo[i : i + CHUNK]
            cid = f"{name}--{chunk[0]['id']}"[:64]
            if cid in pending:
                continue
            requests.append(Request(
                custom_id=cid,
                params=MessageCreateParamsNonStreaming(
                    model=MODEL,
                    max_tokens=16000,
                    output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
                    system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                    messages=[{"role": "user", "content": prompt_for(scripture, chunk)}],
                ),
            ))
            if args.limit and len(requests) * CHUNK >= args.limit:
                break
        if args.limit and len(requests) * CHUNK >= args.limit:
            break
    if not requests:
        print("Nothing to submit.")
        return
    for i in range(0, len(requests), BATCH_MAX):
        part = requests[i : i + BATCH_MAX]
        batch = client.messages.batches.create(requests=part)
        state["batches"].append({"id": batch.id, "custom_ids": [r["custom_id"] for r in part]})
        print(f"Submitted batch {batch.id}: {len(part)} requests")
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w"), indent=1)


def status(args):
    client = anthropic.Anthropic()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"batches": []}
    for b in state["batches"]:
        r = client.messages.batches.retrieve(b["id"])
        c = r.request_counts
        print(f"{b['id']}: {r.processing_status}, {c.succeeded} ok, {c.errored} errored, {c.processing} processing" + (" (collected)" if b.get("collected") else ""))


def collect(args):
    client = anthropic.Anthropic()
    state = json.load(open(STATE))
    os.makedirs(ENRICH_DIR, exist_ok=True)
    ids_by_file = {name: {v["id"] for v in data["verses"]} for name, data in load_imports(None)}
    for b in state["batches"]:
        if b.get("collected") or client.messages.batches.retrieve(b["id"]).processing_status != "ended":
            continue
        out, failed = {}, 0
        for result in client.messages.batches.results(b["id"]):
            name = result.custom_id.split("--")[0]
            if result.result.type != "succeeded" or result.result.message.stop_reason != "end_turn":
                failed += 1  # left out, so the next `submit` retries it
                continue
            text = next(x.text for x in result.result.message.content if x.type == "text")
            for v in json.loads(text)["verses"]:
                if v["id"] in ids_by_file[name]:  # ignore anything that is not a verse we asked about
                    out.setdefault(name, {})[v["id"]] = {k: v[k] for k in ("translation", "meaning", "explanation", "keywords")}
        for name, entries in out.items():
            merged = {**load_enriched(name), **entries}
            with open(os.path.join(ENRICH_DIR, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(dict(sorted(merged.items())), f, ensure_ascii=False, indent=1)
                f.write("\n")
            print(f"{name}: {len(entries)} verses written ({len(merged)} in total)")
        b["collected"] = True
        print(f"{b['id']}: collected, {failed} requests to retry")
    json.dump(state, open(STATE, "w"), indent=1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--only", help="only import files starting with this, e.g. gita or ramayana-1")
    s.add_argument("--limit", type=int, help="stop after about this many verses")
    sub.add_parser("status")
    sub.add_parser("collect")
    a = p.parse_args()
    {"submit": submit, "status": status, "collect": collect}[a.cmd](a)
