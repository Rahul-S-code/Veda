"""Import all 700 verses of the Bhagavad Gita into content/import/gita.json.

Sanskrit: GRETIL's Bhagavadgita (text of the BORI critical edition, input by
M. Tokunaga et al., revised by John Smith), in IAST. Devanagari is produced
from the IAST by rule, so no Sanskrit is typed by hand.

English: Annie Besant's translation, 4th edition (1922), as proofread on
English Wikisource. Public domain (Besant died in 1933). It numbers every
verse, which lets us align it to the Sanskrit exactly. (Telang's 1882
translation is unnumbered running prose, so it cannot be aligned verse by
verse without guesswork.)

Run:
  pip install indic_transliteration
  python3 scripts/import/gita.py            # downloads into .cache/import/gita
  python3 scripts/import/gita.py --offline  # reuse the cached downloads

The script stops with an error if any verse is missing or misaligned.
"""

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from indic_transliteration import sanscript

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.path.join(ROOT, ".cache", "import", "gita")
OUT = os.path.join(ROOT, "content", "import", "gita.json")
UA = "VedaImport/0.1 (https://github.com/rahul-s-code/veda)"

GRETIL_URL = "https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/2_epic/mbh/ext/bhgce__u.htm"
WIKISOURCE_API = "https://en.wikisource.org/w/api.php"
BESANT_INDEX = "Bhagavad Gita - Annie Besant 4th edition.djvu"

# Verses per chapter in the critical edition (700 in all; chapter 13 has 34).
EXPECTED = [47, 72, 43, 42, 29, 47, 30, 28, 34, 42, 55, 20, 34, 27, 20, 24, 28, 78]

SPEAKERS = {"dhṛtarāṣṭra": "Dhritarashtra", "saṃjaya": "Sanjaya", "śrībhagavān": "Krishna", "arjuna": "Arjuna"}


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except Exception as e:  # Wikimedia rate-limits shared IPs; back off and retry.
            if attempt == 5:
                raise
            wait = 10 * (attempt + 1)
            print(f"  retry in {wait}s: {e}", file=sys.stderr)
            time.sleep(wait)


# ---------------------------------------------------------------- downloads

def fetch(offline):
    os.makedirs(os.path.join(CACHE, "besant"), exist_ok=True)
    gretil = os.path.join(CACHE, "bhgce__u.htm")
    if not offline:
        print("Downloading GRETIL Bhagavadgita...")
        open(gretil, "w", encoding="utf-8").write(get(GRETIL_URL))
        print("Downloading Besant 1922 pages from Wikisource...")
        params = {"action": "query", "format": "json", "formatversion": "2", "prop": "revisions",
                  "rvprop": "content", "rvslots": "main", "generator": "allpages", "gapnamespace": "104",
                  "gapprefix": BESANT_INDEX + "/", "gaplimit": "50"}
        cont = {}
        while True:
            d = json.loads(get(WIKISOURCE_API + "?" + urllib.parse.urlencode({**params, **cont})))
            for p in d["query"]["pages"]:
                n = int(p["title"].rsplit("/", 1)[1])
                text = p["revisions"][0]["slots"]["main"]["content"]
                open(os.path.join(CACHE, "besant", f"p{n:04d}.wiki"), "w", encoding="utf-8").write(text)
            if "continue" not in d:
                break
            cont = d["continue"]
            time.sleep(3)
    return gretil, os.path.join(CACHE, "besant")


# ---------------------------------------------------------------- Sanskrit

CONSONANT_END = re.compile(r"[kgcjṭḍtdpbṅñṇnmyrlvśṣsh]$")


def to_devanagari(iast_line):
    """IAST (words split as in GRETIL) -> Devanagari with words joined the usual printed way.

    A word ending in a consonant is joined to the next word (pāṇḍavāś caiva -> पाण्डवाश्चैव),
    and an avagraha joins to the word before it (saṅgo 'stv -> सङ्गोऽस्त्व).
    """
    words = iast_line.split()
    joined = []
    for w in words:
        if joined and (w.startswith("'") or CONSONANT_END.search(joined[-1])):
            joined[-1] += w
        else:
            joined.append(w)
    text = " ".join(joined).replace("'", "ऽ")
    return sanscript.transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)


def parse_gretil(path):
    text = re.sub(r"<[^>]+>", "", open(path, encoding="utf-8").read())
    text = html.unescape(text)
    verses, pending = {}, None
    for line in text.splitlines():
        m = re.match(r"^(.*?)\s+Bhg_(\d+)\.(\d+)([a-f]?)\s+\[", line)
        if not m:
            continue
        body, ch, v, pada = m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4)
        if not pada:  # "arjuna uvāca" line
            if not body.endswith("uvāca"):
                raise SystemExit(f"Unexpected line: {line}")
            pending = SPEAKERS[body.split()[0]]
            continue
        verse = verses.setdefault((ch, v), {"lines": [], "says": None})
        if pending:
            verse["says"], pending = pending, None
        verse["lines"].append(body.replace(";", ""))
    speaker = None
    for key in sorted(verses):
        verse = verses[key]
        speaker = verse["says"] or speaker
        verse["speaker"] = speaker
    return verses


# ---------------------------------------------------------------- English

ORDINALS = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH",
            "ELEVENTH", "TWELFTH", "THIRTEENTH", "FOURTEENTH", "FIFTEENTH", "SIXTEENTH", "SEVENTEENTH", "EIGHTEENTH"]
DEVANAGARI_DIGITS = "०१२३४५६७८९"
SAID = re.compile(r"^\s*[A-Z][A-Za-zâîûêô ]+ (said|spake):\s*")

TOKENS = re.compile(
    r"(?P<chapter>\b(%s)\s+DISCOURSE)"
    r"|(?P<sanskrit>\{\{lang block\|sa\|(?:(?!DISCOURSE|\{\{lang block|float right).)*?(?:॥\s*(?P<dn>[०-९]+)\s*॥|\}\}\s*\}\}\s*\}\}))"
    r"|(?P<number>\{\{float right\|\{\{larger\|\(?(?P<n>\d+)\)\}\}\}\})" % "|".join(ORDINALS),
    re.S,
)


def clean_english(s):
    s = re.sub(r"\{\{c\|[^{}]*?(said|spake)[^{}]*?\}\}", "", s)
    for _ in range(4):
        s = re.sub(r"\{\{(?:sc|sp|smaller|larger|lang\|[a-z]+|em|tooltip)\|([^{}|]*)(?:\|[^{}]*)?\}\}", r"\1", s)
        s = re.sub(r"\{\{(?:c|center|block center|larger block|right|float right|small-caps|smaller block)\|([^{}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{[a-z -]+/[se](?:\|[^{}]*)?\}\}", " ", s)
    s = re.sub(r"\{\{(?:block center|fine block|larger block|div col)\|(?:width=[^|]*\|)?", " ", s)
    s = re.sub(r"\{\{(?:div col end|parabr|nop|-|dhr|rule[^{}]*)\}\}", " ", s)
    s = s.replace("}}", " ").replace("{{c|", " ")
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = SAID.sub("", s)
    return s


def parse_besant(folder):
    pages = sorted(f for f in os.listdir(folder) if f.endswith(".wiki") and int(f[1:5]) >= 11)
    text = "\n".join(re.sub(r"<noinclude>.*?</noinclude>", "", open(os.path.join(folder, f), encoding="utf-8").read(), flags=re.S) for f in pages)
    text = re.sub(r"\{\{gap(?:\|[^{}]*)?\}\}", "", text)
    text = re.sub(r"\{\{SIC\|[^{}|]*\|([^{}]*)\}\}", r"\1", text)  # {{SIC|printed|corrected}} -> corrected
    text = re.sub(r"\{\{SIC\|([^{}|]*)\}\}", r"\1", text)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"<ref[^>/]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)  # Besant's footnotes

    out, chapter, last, sanskrit_number = {}, 0, 0, None
    for m in TOKENS.finditer(text):
        if m.group("chapter"):
            chapter, last = ORDINALS.index(m.group(2)) + 1, m.end()
        elif m.group("sanskrit"):
            dn = m.group("dn")
            sanskrit_number = int("".join(str(DEVANAGARI_DIGITS.index(c)) for c in dn)) if dn else None
            last = m.end()
        else:
            english = clean_english(text[last:m.start()])
            last = m.end()
            # The printed English number has a few typos; the Sanskrit verse number above it is reliable.
            n = sanskrit_number or int(m.group("n"))
            sanskrit_number = None
            if any(c in english for c in "{}|[]<>"):
                raise SystemExit(f"Unclean English at {chapter}.{n}: {english}")
            if (chapter, n) in out:
                raise SystemExit(f"Duplicate English verse {chapter}.{n}")
            out[(chapter, n)] = english
    return out


# ---------------------------------------------------------------- build

def main():
    gretil_path, besant_dir = fetch("--offline" in sys.argv)
    sanskrit = parse_gretil(gretil_path)
    english = parse_besant(besant_dir)

    verses = []
    for ch, count in enumerate(EXPECTED, start=1):
        for v in range(1, count + 1):
            s = sanskrit.get((ch, v))
            if not s:
                raise SystemExit(f"Sanskrit missing for {ch}.{v}")
            # Besant follows the common printed text, which opens chapter 13 with an extra verse
            # ("Prakriti and Purusha...") that the critical edition leaves out. Shift by one there.
            b = (ch, v + 1) if ch == 13 else (ch, v)
            if b not in english:
                raise SystemExit(f"English missing for {ch}.{v}")
            lines = s["lines"]
            deva = [to_devanagari(l) for l in lines]
            deva = [l + ("॥" if i == len(deva) - 1 else "।") for i, l in enumerate(deva)]
            verses.append({
                "id": f"gita-{ch}-{v}",
                "chapter": ch,
                "verse": v,
                "reference": f"Chapter {ch}, Verse {v}",
                "speaker": s["speaker"],
                "sanskrit": "\n".join(deva),
                "transliteration": "\n".join(lines),
                "translation": {"en": english[b]},
                "translation_ref": f"Besant {b[0]}.{b[1]}",
            })

    if len(verses) != 700:
        raise SystemExit(f"Expected 700 verses, got {len(verses)}")
    data = {
        "scripture": "bhagavad-gita",
        "sanskrit_source": "gretil-bhg-ce",
        "translation_source": {"en": "besant-1922"},
        "notes": "Generated by scripts/import/gita.py. Do not edit by hand; fix the script or the source and re-run.",
        "verses": verses,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Wrote {os.path.relpath(OUT, ROOT)}: {len(verses)} verses")


if __name__ == "__main__":
    main()
