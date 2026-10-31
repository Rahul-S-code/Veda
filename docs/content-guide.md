# Content guide

Cards live in `content/cards.*.json` (one file per scripture group). Run `node scripts/validate-content.mjs` after any edit.

## Card fields

| Field | What it holds |
|---|---|
| `id` | Stable unique id, e.g. `gita-2-47`. Progress is saved against this, so never change it after launch. |
| `scripture` | Shown at the top of the card, e.g. "Bhagavad Gita". |
| `reference` | Exact location, e.g. "Chapter 2, Verse 47". |
| `sanskrit` | Devanagari text. `\n` separates lines. |
| `transliteration` | IAST romanisation, same line breaks. |
| `translation` | Plain-English translation. |
| `meaning` | One or two sentences on what it means for daily life. |
| `explanation` | A fuller paragraph (about 80 to 100 words): context in the scripture, what the key words mean, and how to read it today. |
| `keywords` | Three key Sanskrit words or phrases, each with `word` (IAST) and `meaning`. |
| `story` | Button A: `title`, `text`, and `illustration` (`status` + an `idea` for the artwork). |
| `teaching` | Button B: `title` and a `practice` the reader can do today. |
| `test` | At least 2 gentle multiple-choice questions. `answer` is the index of the correct option. The app should shuffle options when showing them. |
| `tags` | Themes for filtering and "more like this". |

## Sources and copyright

- The Sanskrit texts are ancient and in the public domain.
- Translations, meanings, stories and teachings are original plain-English writing for this project, so there are no third-party copyright issues. They follow the standard readings found in public-domain translations such as K. T. Telang's Bhagavad Gita (1882), R. T. H. Griffith's Rig Veda (1896) and Atharva Veda (1895–96), and Max Müller's Upanishads (1879–84).
- Stories marked as traditional (for example Shankara in Kashi, Valmiki as Ratnakara, Markandeya) come from later tradition and Puranas rather than the verse's own text.

## Before launch

- Have someone fluent in Sanskrit proofread every `sanskrit` and `transliteration` field against a printed edition.
- Replace each `illustration.status: "needed"` with a real image.
