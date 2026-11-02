"""Import the principal Upanishads available on GRETIL into content/import/upanishad-<name>.json.

Sanskrit only, from GRETIL (CC BY-NC-SA 4.0). Several files carry Shankara's commentary;
only the Upanishad's own text (the mula) is taken, using the verse markers GRETIL puts on it.
Devanagari is produced from the IAST by rule.

Not on GRETIL as open downloads (TITUS, restricted): Kena, Mundaka. Taittiriya's GRETIL file
does not mark its own text, so it is left for later.

Run:
  pip install indic_transliteration
  python3 scripts/import/upanishads.py            # downloads into .cache/import/upanishads
  python3 scripts/import/upanishads.py --offline  # reuse the cached downloads
"""

import collections
import json
import os
import re
import sys
import time
import urllib.request

from common import devanagari_verse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.path.join(ROOT, ".cache", "import", "upanishads")
OUT = os.path.join(ROOT, "content", "import")
BASE = "https://gretil.sub.uni-goettingen.de/gretil/corpustei/transformations/plaintext/"
UA = "VedaImport/0.1 (https://github.com/rahul-s-code/veda)"

# scripture id -> (GRETIL file, id prefix, parser, expected verse count)
TEXTS = {
    "isha-upanishad": ("sa_IzopaniSad-or-IzAvAsyopaniSadkANva-recension-comm", "isha", "tagged", 18),
    "katha-upanishad": ("sa_kathopaniSad", "katha", "tagged", 119),
    "prashna-upanishad": ("sa_praznopaniSad-comm", "prashna", "prashna", 67),
    "mandukya-upanishad": ("sa_mANDUkyopaniSad-alt", "mandukya", "mandukya", 12),
    "shvetashvatara-upanishad": ("sa_zvetAzvataropaniSad", "shvetashvatara", "lines", 113),
    "aitareya-upanishad": ("sa_aitareyopaniSad-comm", "aitareya", "tagged", 33),
    "chandogya-upanishad": ("sa_chAndogyopaniSad-comm", "chandogya", "tagged", 623),
    "brihadaranyaka-upanishad": ("sa_bRhadAraNyakopaniSadkANva-recension-comm", "brihadaranyaka", "tagged", 433),
}

# Marker on the Upanishad's own text -> section path and verse number.
TAGS = {
    "isha-upanishad": (r"\|\|\s*isup_(\d+)\s*\|\|", lambda g: ([], int(g[0]))),
    # Katha numbers its six vallis 1-6; the book groups them as chapters 1-2 of three sections each.
    "katha-upanishad": (r"//\s*kau_(\d+)\.(\d+)\s*//", lambda g: ([(int(g[0]) - 1) // 3 + 1, (int(g[0]) - 1) % 3 + 1], int(g[1]))),
    "aitareya-upanishad": (r"\|\|\s*aitup_(\d+)(?:,(\d+))?\.(\d+)\s*\|\|", lambda g: ([int(g[0]), int(g[1] or 1)], int(g[2]))),
    "chandogya-upanishad": (r"\|\|\s*chup_(\d+),(\d+)\.(\d+)\s*\|\|", lambda g: ([int(g[0]), int(g[1])], int(g[2]))),
    # A few Brihadaranyaka verses are split into parts (3,9.28:1-8); they are joined back into one verse.
    "brihadaranyaka-upanishad": (r"\|\|\s*brhup_(\d+),(\d+)\.(\d+)(?::\d+)?\s*\|\|", lambda g: ([int(g[0]), int(g[1])], int(g[2]))),
}
LEVEL_NAMES = {
    "katha-upanishad": ["Chapter", "Section"],
    "prashna-upanishad": ["Question"],
    "shvetashvatara-upanishad": ["Chapter"],
    "aitareya-upanishad": ["Chapter", "Section"],
    "chandogya-upanishad": ["Chapter", "Section"],
    "brihadaranyaka-upanishad": ["Chapter", "Section"],
}


def body(text):
    if "Creative Commons Attribution-NonCommercial-ShareAlike 4.0" not in text:
        raise SystemExit("GRETIL's licence line changed; check it before importing.")
    return text.split("# Text", 1)[1]


def split_lines(s):
    """Text with dandas -> list of lines, one per single danda."""
    s = re.sub(r"\s+", " ", s.replace("||", "/").replace("|", "/"))
    parts = [p.strip(" /") for p in re.split(r"\s*/+\s*", s)]
    return [p for p in parts if p and not re.fullmatch(r"[\d.,:]+", p)]


def parse_tagged(text, scripture):
    pattern, place = TAGS[scripture]
    tag = re.compile(pattern)
    out = collections.OrderedDict()
    for block in re.split(r"\n\s*\n", text):
        start = 0
        for m in tag.finditer(block):  # a block can hold several verses back to back
            before = block[start : m.start()]
            # Where GRETIL marks the start of the verse, begin there; this drops any commentary above it.
            starts = list(re.finditer(r"start (?:[a-z]+ )?[\d,.\-]+", before))
            if starts:
                before = before[starts[-1].end():]
            before = "\n".join(l for l in before.splitlines() if not re.match(r"\s*([a-z]+bh_|=+)", l))
            start = m.end()
            # The verse is the text between the previous marker (or the block start) and this one.
            p, v = place(m.groups())
            key = (tuple(p), v)
            if key in out:  # a split verse such as BAU 3,9.28:1-8
                out[key] += split_lines(before)
            else:
                out[key] = split_lines(before)
    return out


def parse_prashna(text):
    out = collections.OrderedDict()
    for m in re.finditer(r"start prup (\d+)\.(\d+)\s*\n(.*?)(?=\nprupbh_|\nstart prup|\Z)", text, re.S):
        mula = re.sub(r"(//|\|\|)\s*prup_[\d.]+\s*(//|\|\|)?", "", m.group(3))
        out[((int(m.group(1)),), int(m.group(2)))] = split_lines(mula)
    return out


def parse_mandukya(text):
    # This file interleaves the Upanishad with Gaudapada's Karika; keep only the Upanishad's verses.
    out, mode, cur = collections.OrderedDict(), None, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("māṇḍūkya upaniṣad"):
            mode, cur = "up", None
        elif line.startswith("māṇḍūkya kārikā") or line.startswith("oṃ śāntiḥ"):
            mode, cur = None, None
        elif mode == "up":
            m = re.match(r"verse (\d+)\s*(.*)", line)
            if m:
                cur = ((), int(m.group(1)))
                out[cur] = []
                line = m.group(2)
            if cur and line:
                out[cur].append(line)
    return collections.OrderedDict((k, split_lines(" / ".join(v))) for k, v in out.items())


def parse_lines(text):
    out, pending = collections.OrderedDict(), []
    for line in text.splitlines():
        line = line.strip()
        m = re.search(r"//\s*SvetUp_(\d+)\.(\d+)\s*$", line)
        if m:
            out[((int(m.group(1)),), int(m.group(2)))] = pending + [line[: m.start()].strip()]
            pending = []
        elif line and not re.search(r"adhyāyaḥ|upaniṣad|^oṃ brahmavādino vadanti$", line):
            pending.append(line)
    return out


def main():
    os.makedirs(CACHE, exist_ok=True)
    catalogue = {s["id"]: s for s in json.load(open(os.path.join(ROOT, "content", "catalogue.json"), encoding="utf-8"))["scriptures"]}
    total = 0
    for scripture, (fname, prefix, kind, expected) in TEXTS.items():
        path = os.path.join(CACHE, fname + ".txt")
        if "--offline" not in sys.argv:
            req = urllib.request.Request(BASE + fname + ".txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                open(path, "wb").write(r.read())
            time.sleep(1)
        text = body(open(path, encoding="utf-8").read())
        verses = {"tagged": lambda t: parse_tagged(t, scripture), "prashna": parse_prashna, "mandukya": parse_mandukya, "lines": parse_lines}[kind](text)

        gaps = []
        by_section = collections.defaultdict(list)
        for (p, v) in verses:
            by_section[p].append(v)
        for p, nums in by_section.items():  # verse numbers in each section must run 1..n
            if sorted(nums) != list(range(1, len(nums) + 1)):
                gaps.append((p, sorted(set(range(1, max(nums) + 1)) - set(nums))))
        if gaps:
            print(f"  {scripture} gaps: {gaps}")
        if len(verses) != expected:
            raise SystemExit(f"{scripture}: expected {expected} verses, found {len(verses)}")
        for (path_, v), lines in verses.items():
            if not lines or any(len(l) > 600 for l in lines):
                raise SystemExit(f"{scripture} {path_}.{v}: empty or suspiciously long text")

        names = LEVEL_NAMES.get(scripture, [])
        name = catalogue[scripture]["name"]
        counts = collections.Counter()
        for p, _ in verses:
            for i in range(1, len(p) + 1):
                counts[p[:i]] += 1
        sections = [{"path": list(p), "title": f"{names[len(p) - 1]} {p[-1]}", "expected_verses": counts[p]} for p in sorted(counts)]
        rows = []
        for (p, v), lines in sorted(verses.items()):
            ref = ", ".join(f"{names[i]} {n}" for i, n in enumerate(p)) + (", " if p else "") + f"Verse {v}"
            rows.append({
                "id": "-".join([prefix, *map(str, p), str(v)]),
                "section_path": list(p),
                "verse": v,
                "reference": ref,
                "sort_key": sum(n * 1000 ** (len(p) - i) for i, n in enumerate(p)) + v,
                "speaker": None,
                "sanskrit": devanagari_verse(lines),
                "transliteration": "\n".join(lines),
                "translation": {},
            })
        data = {
            "scripture": scripture,
            "sanskrit_source": "gretil-upanishads",
            "translation_source": {},
            "notes": f"Generated by scripts/import/upanishads.py from GRETIL {fname}. Do not edit by hand.",
            "sections": sections,
            "verses": rows,
        }
        out = os.path.join(OUT, f"upanishad-{prefix}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        total += len(rows)
        print(f"Wrote {os.path.relpath(out, ROOT)}: {len(rows)} verses ({name})")
    print(f"{total} Upanishad verses in all")


if __name__ == "__main__":
    main()
