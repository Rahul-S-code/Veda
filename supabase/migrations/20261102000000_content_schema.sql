-- Veda: database for 10,000+ shlokas across many scriptures, plus each reader's progress.
--
-- Content tables are readable by everyone (only published rows).
-- Progress tables are private: each signed-in user can only see and change their own rows.
-- Writing content is done with the service role (import scripts, admin tools), never from the app.

create extension if not exists pg_trgm;

-- ============================================================
-- Reference data
-- ============================================================

create type content_status as enum ('draft', 'reviewed', 'published');

-- Where a text or translation came from, so every line can be traced and its licence checked.
create table sources (
  id          text primary key,                -- e.g. 'telang-1882', 'griffith-rv-1896', 'veda-app-original'
  title       text not null,
  author      text,
  year        int,
  url         text,
  licence     text not null,                   -- e.g. 'public-domain', 'original-work', 'cc-by-4.0'
  notes       text
);

-- One row per text: Bhagavad Gita, Rig Veda, Isha Upanishad, Valmiki Ramayana...
create table scriptures (
  id                 text primary key,         -- 'bhagavad-gita', 'rig-veda', 'isha-upanishad'
  name               text not null,            -- 'Bhagavad Gita'
  name_sanskrit      text,                     -- 'भगवद्गीता'
  category           text not null check (category in ('veda', 'upanishad', 'itihasa', 'gita', 'purana', 'sutra', 'other')),
  parent_id          text references scriptures(id),  -- Isha Upanishad -> Shukla Yajur Veda; Gita -> Mahabharata
  description        text,
  -- Names of each level of the text, top to bottom, e.g. {'Chapter','Verse'} or {'Mandala','Hymn','Verse'}.
  level_names        text[] not null,
  expected_verses    int,                      -- traditional total, used for the coverage view
  sort_order         int not null default 0,
  created_at         timestamptz not null default now()
);

-- Chapters, kandas, mandalas, hymns, sargas... Nested as deep as a text needs.
create table sections (
  id             bigint generated always as identity primary key,
  scripture_id   text not null references scriptures(id) on delete cascade,
  parent_id      bigint references sections(id) on delete cascade,
  level          smallint not null,            -- 1 = top level (e.g. Mandala), 2 = next (Hymn)...
  number         int not null,
  title          text,                         -- 'Sankhya Yoga', 'Ayodhya Kanda'
  title_sanskrit text,
  summary        text,
  expected_verses int,                         -- traditional verse count for this section, if known
  unique nulls not distinct (scripture_id, parent_id, number)
);
create index sections_scripture_idx on sections (scripture_id, level, number);

-- ============================================================
-- Verses and everything shown on a card
-- ============================================================

create table verses (
  id              text primary key,            -- stable slug, e.g. 'gita-2-47'. Progress is keyed on this; never change it.
  scripture_id    text not null references scriptures(id) on delete cascade,
  section_id      bigint references sections(id) on delete set null,
  number          int,                         -- verse number inside its section
  reference       text not null,               -- 'Chapter 2, Verse 47' as shown on the card
  sanskrit        text not null,               -- Devanagari; '\n' separates lines
  transliteration text,                        -- IAST
  speaker         text,                        -- 'Krishna', 'Arjuna', 'Sanjaya' where known
  sort_key        bigint not null,             -- global reading order within a scripture
  is_featured     boolean not null default false,  -- part of the curated "best known" set
  source_id       text references sources(id),
  status          content_status not null default 'draft',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (scripture_id, sort_key)
);
create index verses_section_idx on verses (section_id, number);
create index verses_published_idx on verses (scripture_id, sort_key) where status = 'published';
create index verses_featured_idx on verses (is_featured) where is_featured;

-- More than one translation per verse and language is allowed (e.g. a public-domain one and our own).
create table translations (
  id          bigint generated always as identity primary key,
  verse_id    text not null references verses(id) on delete cascade,
  language    text not null default 'en',      -- BCP 47: 'en', 'hi', 'mr'...
  text        text not null,
  source_id   text references sources(id),
  is_primary  boolean not null default false,  -- the one shown on the card
  search      tsvector generated always as (to_tsvector('simple', text)) stored
);
create unique index translations_one_primary on translations (verse_id, language) where is_primary;
create index translations_search_idx on translations using gin (search);

-- "What it means" plus the longer explanation and key words.
create table explanations (
  verse_id     text not null references verses(id) on delete cascade,
  language     text not null default 'en',
  meaning      text not null,                  -- one or two sentences
  explanation  text,                           -- 80 to 100 word paragraph
  keywords     jsonb not null default '[]',    -- [{"word": "karma", "meaning": "action"}]
  source_id    text references sources(id),
  status       content_status not null default 'draft',
  reviewed_by  text,
  primary key (verse_id, language)
);

-- Stories can be shared by several verses (e.g. Arjuna drops his bow).
create table stories (
  id                 text primary key,         -- 'arjuna-drops-bow'
  title              text not null,
  text               text not null,
  language           text not null default 'en',
  illustration_url   text,
  illustration_idea  text,
  illustration_credit text,
  source_ref         text                      -- e.g. 'Mahabharata, Bhishma Parva'
);
create table verse_stories (
  verse_id   text not null references verses(id) on delete cascade,
  story_id   text not null references stories(id) on delete cascade,
  primary key (verse_id, story_id)
);

-- "Daily teaching" button.
create table teachings (
  verse_id   text not null references verses(id) on delete cascade,
  language   text not null default 'en',
  title      text not null,
  practice   text not null,
  primary key (verse_id, language)
);

-- Gentle test questions.
create table quiz_questions (
  id            bigint generated always as identity primary key,
  verse_id      text not null references verses(id) on delete cascade,
  language      text not null default 'en',
  question      text not null,
  options       text[] not null check (cardinality(options) between 2 and 6),
  answer_index  smallint not null,
  difficulty    smallint not null default 1 check (difficulty between 1 and 3),
  check (answer_index >= 0 and answer_index < cardinality(options))
);
create index quiz_questions_verse_idx on quiz_questions (verse_id);

-- Recorded or generated audio, with the time each word starts (for highlighting).
create table audio_clips (
  id              bigint generated always as identity primary key,
  verse_id        text not null references verses(id) on delete cascade,
  language        text not null,               -- 'sa' for the Sanskrit, 'en' for the translation
  kind            text not null check (kind in ('recitation', 'tts')),
  url             text not null,               -- Supabase Storage path or CDN URL
  duration_ms     int,
  word_starts_ms  int[],                       -- one entry per word, same split as the displayed text
  voice           text,                        -- reciter name or TTS voice id
  source_id       text references sources(id),
  unique (verse_id, language, kind)
);

create table tags (
  id     text primary key,                      -- 'patience', 'dharma'
  label  text not null
);
create table verse_tags (
  verse_id  text not null references verses(id) on delete cascade,
  tag_id    text not null references tags(id) on delete cascade,
  primary key (verse_id, tag_id)
);
create index verse_tags_tag_idx on verse_tags (tag_id);

-- Today's verse: one row per date, picked ahead of time so every reader sees the same verse.
create table daily_verses (
  day       date primary key,
  verse_id  text not null references verses(id) on delete cascade
);

-- ============================================================
-- Readers
-- ============================================================

create table profiles (
  id               uuid primary key references auth.users(id) on delete cascade,
  display_name     text,
  preferred_lang   text not null default 'en',
  music_on         boolean not null default true,
  created_at       timestamptz not null default now()
);

create table verse_progress (
  user_id        uuid not null references auth.users(id) on delete cascade,
  verse_id       text not null references verses(id) on delete cascade,
  first_read_at  timestamptz not null default now(),
  last_read_at   timestamptz not null default now(),
  read_count     int not null default 1,
  listened       boolean not null default false,
  favourite      boolean not null default false,
  primary key (user_id, verse_id)
);
create index verse_progress_recent_idx on verse_progress (user_id, last_read_at desc);

create table quiz_attempts (
  id           bigint generated always as identity primary key,
  user_id      uuid not null references auth.users(id) on delete cascade,
  question_id  bigint not null references quiz_questions(id) on delete cascade,
  chosen_index smallint not null,
  is_correct   boolean not null,
  answered_at  timestamptz not null default now()
);
create index quiz_attempts_user_idx on quiz_attempts (user_id, answered_at desc);

-- One row per user per day they opened a card, for streaks.
create table practice_days (
  user_id  uuid not null references auth.users(id) on delete cascade,
  day      date not null,
  primary key (user_id, day)
);

-- ============================================================
-- Helpful views
-- ============================================================

-- How far we are towards each scripture's full text.
create view scripture_coverage with (security_invoker = true) as
select s.id, s.name, s.category, s.expected_verses,
       count(v.id)                                         as verses_imported,
       count(v.id) filter (where v.status = 'published')   as verses_published,
       round(100.0 * count(v.id) filter (where v.status = 'published') / nullif(s.expected_verses, 0), 1) as percent_published
from scriptures s
left join verses v on v.scripture_id = s.id
group by s.id
order by s.sort_order;

-- Per-user summary for the Progress screen.
create view my_progress with (security_invoker = true) as
select v.scripture_id,
       count(*)                          as verses_read,
       count(*) filter (where p.favourite) as favourites
from verse_progress p
join verses v on v.id = p.verse_id
where p.user_id = auth.uid()
group by v.scripture_id;

-- ============================================================
-- Row level security
-- ============================================================

alter table sources         enable row level security;
alter table scriptures      enable row level security;
alter table sections        enable row level security;
alter table verses          enable row level security;
alter table translations    enable row level security;
alter table explanations    enable row level security;
alter table stories         enable row level security;
alter table verse_stories   enable row level security;
alter table teachings       enable row level security;
alter table quiz_questions  enable row level security;
alter table audio_clips     enable row level security;
alter table tags            enable row level security;
alter table verse_tags      enable row level security;
alter table daily_verses    enable row level security;
alter table profiles        enable row level security;
alter table verse_progress  enable row level security;
alter table quiz_attempts   enable row level security;
alter table practice_days   enable row level security;

-- Anyone, signed in or not, can read reference data.
create policy "read sources"    on sources    for select using (true);
create policy "read scriptures" on scriptures for select using (true);
create policy "read sections"   on sections   for select using (true);
create policy "read stories"    on stories    for select using (true);
create policy "read tags"       on tags       for select using (true);

-- Verse content is readable only once the verse is published.
create policy "read published verses" on verses for select using (status = 'published');
create policy "read translations"  on translations  for select using (exists (select 1 from verses v where v.id = verse_id and v.status = 'published'));
create policy "read explanations"  on explanations  for select using (status = 'published' and exists (select 1 from verses v where v.id = verse_id and v.status = 'published'));
create policy "read verse stories" on verse_stories for select using (exists (select 1 from verses v where v.id = verse_id and v.status = 'published'));
create policy "read teachings"     on teachings     for select using (exists (select 1 from verses v where v.id = verse_id and v.status = 'published'));
create policy "read questions"     on quiz_questions for select using (exists (select 1 from verses v where v.id = verse_id and v.status = 'published'));
create policy "read audio"         on audio_clips   for select using (exists (select 1 from verses v where v.id = verse_id and v.status = 'published'));
create policy "read verse tags"    on verse_tags    for select using (exists (select 1 from verses v where v.id = verse_id and v.status = 'published'));
create policy "read daily verse"   on daily_verses  for select using (day <= current_date);

-- Readers own their rows.
create policy "own profile"        on profiles       for all using (id = auth.uid())      with check (id = auth.uid());
create policy "own progress"       on verse_progress for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own practice days"  on practice_days  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "read own attempts"  on quiz_attempts  for select using (user_id = auth.uid());
-- Attempts are written only through answer_question(), so a client cannot mark its own answer correct.

-- ============================================================
-- App functions
-- ============================================================

-- Record that the signed-in reader opened a verse.
create function mark_verse_read(p_verse_id text, p_listened boolean default false)
returns void language sql security invoker set search_path = public as $$
  insert into verse_progress (user_id, verse_id, listened)
  values (auth.uid(), p_verse_id, p_listened)
  on conflict (user_id, verse_id) do update
    set last_read_at = now(),
        read_count   = verse_progress.read_count + 1,
        listened     = verse_progress.listened or excluded.listened;
  insert into practice_days (user_id, day) values (auth.uid(), current_date)
  on conflict do nothing;
$$;

-- Check an answer on the server and store the attempt. Returns the correct option index.
create function answer_question(p_question_id bigint, p_chosen smallint)
returns smallint language plpgsql security definer set search_path = public as $$
declare v_answer smallint;
begin
  if auth.uid() is null then raise exception 'sign in required'; end if;
  select q.answer_index into v_answer
  from quiz_questions q join verses v on v.id = q.verse_id
  where q.id = p_question_id and v.status = 'published';
  if v_answer is null then raise exception 'question not found'; end if;
  insert into quiz_attempts (user_id, question_id, chosen_index, is_correct)
  values (auth.uid(), p_question_id, p_chosen, p_chosen = v_answer);
  return v_answer;
end $$;

-- Current streak of consecutive practice days ending today or yesterday.
create function my_streak()
returns int language sql stable security invoker set search_path = public as $$
  with d as (
    select day, day - (row_number() over (order by day))::int as grp
    from practice_days where user_id = auth.uid()
  ), runs as (
    select max(day) as last_day, count(*) as len from d group by grp
  )
  select coalesce((select len::int from runs where last_day >= current_date - 1 order by last_day desc limit 1), 0);
$$;

-- Keep updated_at fresh on verse edits.
create function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
create trigger verses_touch before update on verses for each row execute function touch_updated_at();

-- Create a profile row automatically when someone signs up.
create function handle_new_user() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, display_name) values (new.id, coalesce(new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)));
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users for each row execute function handle_new_user();
