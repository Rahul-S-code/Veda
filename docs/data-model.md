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
| 1 | Complete Bhagavad Gita | 700 |
| 2 | Principal Upanishads (verse texts first: Isha, Kena, Katha, Prashna, Mundaka, Mandukya, Shvetashvatara) | about 1,100 |
| 3 | Valmiki Ramayana, kanda by kanda | 10,000+ partway through |
| 4 | Rig Veda, Atharva Veda, then the rest | 20,000+ |

### How each phase is built

1. **Import the Sanskrit** from a digitised public-domain edition into `verses` as `draft`, with the edition recorded in `sources`. Typing 10,000 verses from memory is not reliable, so this step must use a real source text.
2. **Import a public-domain translation** (Telang, Griffith, Müller, or for the Ramayana, Griffith's verse translation) into `translations`, and generate our own plain-English translation alongside it.
3. **Draft the card content** (meaning, explanation, key words, teaching, two questions) in batches with an AI model, saved as `draft`.
4. **Review:** a Sanskrit-literate reviewer checks the text and a sample of the drafts, then flips them to `published`. `scripture_coverage` shows progress.
5. **Stories** are written once per episode and linked to every verse in that episode, not one per verse.
6. **Audio** is added later by a reciter or a high-quality voice service, filling `audio_clips`.
