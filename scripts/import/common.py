"""Helpers shared by the import scripts."""

import re

from indic_transliteration import sanscript

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


def devanagari_verse(iast_lines):
    """Devanagari for a verse given as IAST lines: । after each line but the last, ॥ at the end."""
    deva = [to_devanagari(l) for l in iast_lines]
    return "\n".join(l + ("॥" if i == len(deva) - 1 else "।") for i, l in enumerate(deva))
