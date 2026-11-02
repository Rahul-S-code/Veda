# Data model and the road to 10,000+ shlokas

The app's content and each reader's progress live in Supabase (Postgres). The schema is in `supabase/migrations/`, and `supabase/seed.sql` is generated from `content/` by `node scripts/build-seed.mjs`.

## Tables

| Group | Table | What it holds |
|---|---|---|
| Catalogue | `scriptures` | One row per text (Rig Veda, Bhagavad Gita, Isha Upanishad...), its category, parent text, level names and traditional verse count. |
| | `sections` | Chapters, kandas, mandalas, hymns, nested as deep as needed. |
| | `sources` | Where every text and translation came from, with its licence. |
| Card | `verses` | Sanskrit, transliteration, reference, reading order, `draft` / `reviewed` / `published` status. |
| | `translations` | One or more per verse and language; one is marked primary. Full-text searchable. |
| | `explanations` | "What it means", the longer explanation and key words. |
| | `stories`, `verse_stories` | Story moments, shareable between verses (one battlefield scene can serve many Gita verses). |
| | `teachings` | The daily practice. |
| | `quiz_questions` | Gentle test questions. |
| | `audio_clips` | Recitation or generated audio, with word start times for highlighting. |
| | `tags`, `verse_tags` | Themes such as patience, dharma, devotion. |
| | `daily_verses` | The verse of the day, the same for every reader. |
| Readers | `profiles` | Created automatically at sign-up. Name, language, music preference. |
| | `verse_progress` | Which verses a reader has read or listened to, and favourites. |
| | `quiz_attempts` | Answers, checked on the server by `answer_question()` so they cannot be faked. |
| | `practice_days` | One row per day of practice, for streaks (`my_streak()`). |

Views: `scripture_coverage` (how far each text is towards its full count) and `my_progress`.

**Security:** anyone can read published content; drafts are hidden. Readers can only read and change their own progress. Content is written only by import scripts using the service key.

**Testing:** `supabase/tests/` runs the migration, seed and security checks on plain Postgres:

```sh
createdb veda_test
cat supabase/tests/local-stubs.sql supabase/migrations/*.sql supabase/seed.sql supabase/tests/rls-checks.sql | psql -v ON_ERROR_STOP=1 -d veda_test
```

## Traditional verse counts

| Text | Shlokas / mantras |
|---|---|
| Rig Veda | about 10,552 |
| Sama Veda | about 1,875 |
| Shukla Yajur Veda | about 1,975 |
| Atharva Veda | about 5,977 |
| Principal Upanishads (13) | a few thousand verses and prose passages |
| Bhagavad Gita | 700 |
| Valmiki Ramayana | about 24,000 |
| Mahabharata | about 100,000 by tradition, about 75,000 in the critical edition |
| Bhagavata Purana | about 18,000 |

Counts vary slightly between editions (for example, Gita chapter 13 has 34 or 35 verses).

## Road to 10,000+

| Phase | Scope | Running total (approx.) |
|---|---|---|
| 0 (done) | 30 featured cards | 30 |
| 1 (imported, in review) | Complete Bhagavad Gita | 700 |
| 2 (imported, in review) | Principal Upanishads (verse texts first: Isha, Kena, Katha, Prashna, Mundaka, Mandukya, Shvetashvatara) | about 1,100 |
| 3 (imported, in review) | Valmiki Ramayana, all seven kandas (critical edition, 18,761 verses) | about 20,900 |
| 4 | Rig Veda, Atharva Veda, then the rest | 20,000+ |

### Phase 1: the Bhagavad Gita import

`scripts/import/gita.py` builds `content/import/gita.json`, which `build-seed.mjs` loads:

- **Sanskrit:** all 700 verses from GRETIL's text of the Poona critical edition (IAST). Devanagari is generated from the IAST by rule, joining words the way printed editions do; nothing is typed by hand. 14 of our 20 hand-checked cards match it letter for letter, and the other 6 differ only in spelling conventions (for example संभवामि for सम्भवामि) or one critical-edition reading (18.66 त्वा for त्वां).
- **English:** Annie Besant's translation (4th edition, 1922, public domain), from the proofread scan on English Wikisource. We use it instead of Telang (1882) because Telang's translation is running prose without verse numbers, so it cannot be matched to verses reliably; Besant numbers every verse.
- **Speaker** (Dhritarashtra, Sanjaya, Arjuna, Krishna) comes from the "uvāca" lines in the Sanskrit.
- The 20 featured cards keep their reviewed content and gain Besant as a second translation. The other 680 verses are `draft`, with Besant as their primary translation, until someone reviews them.
- **Numbering:** we follow the critical edition, where chapter 13 has 34 verses. Some printed editions add an extra opening verse to chapter 13 (701 in all); Besant's edition does, so her 13.2 is our 13.1.

To re-run: `pip install indic_transliteration && python3 scripts/import/gita.py && node scripts/build-seed.mjs`. The script fails if any verse is missing, duplicated or left with markup.

### Phases 2 and 3: Upanishads and Ramayana

- `scripts/import/ramayana.py` loads all 18,761 verses of the Ramayana critical edition from GRETIL, in seven kandas and 606 sargas (`content/import/ramayana-<kanda>.json`). Printed popular editions have about 24,000 verses; the critical edition leaves out passages found in only some manuscripts.
- `scripts/import/upanishads.py` loads 1,418 verses of eight principal Upanishads from GRETIL: Isha, Katha, Prashna, Mandukya, Shvetashvatara, Aitareya, Chandogya and Brihadaranyaka. Where a file carries Shankara's commentary, only the Upanishad's own text is taken. Kena and Mundaka are not openly downloadable from GRETIL, and Taittiriya's file does not mark its own text, so those three are still to do. Five verses are missing because of gaps in GRETIL's markup (Chandogya 3.15.5 and 4.7.1-2, Brihadaranyaka 4.4.19 and 6.5.2).
- These are **Sanskrit only** for now: no public-domain English translation numbers individual verses in a way that matches these editions. Our own plain-English translation is the next step (step 2 below).
- **Licence:** GRETIL distributes its e-texts, including the Gita above, under CC BY-NC-SA 4.0. The app must credit GRETIL and the inputters, stay non-commercial, and share the texts under the same licence. Replacing the Sanskrit with another edition later only changes the `sanskrit` field; verse ids and reader progress stay the same.
- Sections nest (Kanda > Sarga, Chapter > Section). Sort keys are `kanda * 1,000,000 + sarga * 1,000 + verse`.

### How each phase is built

1. **Import the Sanskrit** from a digitised public-domain edition into `verses` as `draft`, with the edition recorded in `sources`. Typing 10,000 verses from memory is not reliable, so this step must use a real source text.
2. **Import a public-domain translation** (Telang, Griffith, Müller, or for the Ramayana, Griffith's verse translation) into `translations`, and generate our own plain-English translation alongside it.
3. **Draft the card content** (meaning, explanation, key words, teaching, two questions) in batches with an AI model, saved as `draft`.
4. **Review:** a Sanskrit-literate reviewer checks the text and a sample of the drafts, then flips them to `published`. `scripture_coverage` shows progress.
5. **Stories** are written once per episode and linked to every verse in that episode, not one per verse.
6. **Audio** is added later by a reciter or a high-quality voice service, filling `audio_clips`.
