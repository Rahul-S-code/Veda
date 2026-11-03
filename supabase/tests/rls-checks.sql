-- Run after the migration and seed. Fails loudly if a check does not hold.
\set ON_ERROR_STOP on
insert into auth.users (id, email) values ('11111111-1111-1111-1111-111111111111', 'a@example.com'), ('22222222-2222-2222-2222-222222222222', 'b@example.com');
insert into verses (id, scripture_id, reference, sanskrit, sort_key, status) values ('draft-test', 'bhagavad-gita', 'Draft', 'x', 999999, 'draft');

-- The full Gita is imported: 700 verses, 20 published cards plus 680 drafts, each with a primary English translation.
do $$ begin
  assert (select count(*) from verses where scripture_id = 'bhagavad-gita' and id <> 'draft-test') = 700, 'Gita should have 700 verses';
  assert (select count(*) from verses where scripture_id = 'bhagavad-gita' and status = 'draft' and id <> 'draft-test') = 680, 'Gita should have 680 drafts';
  assert (select count(*) from translations t join verses v on v.id = t.verse_id where v.scripture_id = 'bhagavad-gita' and t.is_primary) = 700, 'every Gita verse needs one primary translation';
  assert (select count(*) from verses where scripture_id = 'bhagavad-gita' and speaker is null and id <> 'draft-test') = 0, 'every Gita verse needs a speaker';
  assert (select count(*) from verses v join sections s on s.id = v.section_id where v.scripture_id = 'bhagavad-gita') = 700, 'every Gita verse sits in its chapter';
  assert not exists (select 1 from sections s where s.scripture_id = 'bhagavad-gita' and s.expected_verses <> (select count(*) from verses v where v.section_id = s.id)), 'chapter counts should match';
end $$;

-- The Ramayana critical edition is imported in full: 7 kandas, 606 sargas, 18,761 draft verses, each in its sarga.
do $$ begin
  assert (select count(*) from verses where scripture_id = 'valmiki-ramayana' and status = 'draft') = 18761, 'Ramayana should have 18,761 drafts';
  assert (select count(*) from sections where scripture_id = 'valmiki-ramayana' and level = 1) = 7, 'Ramayana should have 7 kandas';
  assert (select count(*) from sections where scripture_id = 'valmiki-ramayana' and level = 2) = 606, 'Ramayana should have 606 sargas';
  assert (select count(*) from verses v join sections s on s.id = v.section_id where v.scripture_id = 'valmiki-ramayana' and s.level = 2) = 18761, 'every Ramayana verse sits in its sarga';
  assert not exists (select 1 from sections s where s.scripture_id = 'valmiki-ramayana' and s.level = 2 and s.expected_verses <> (select count(*) from verses v where v.section_id = s.id)), 'sarga counts should match';
end $$;

-- Eight principal Upanishads are imported; featured cards keep their content and move into their nested section.
do $$ begin
  assert (select count(*) from verses v join scriptures s on s.id = v.scripture_id where s.category = 'upanishad') = 1419, 'Upanishads should have 1,419 verses (1,418 imported + Taittiriya card)';
  assert (select s.level from verses v join sections s on s.id = v.section_id where v.id = 'brihadaranyaka-1-3-28') = 2, 'featured BAU verse should sit in its section';
  assert (select status from verses where id = 'isha-1') = 'published', 'featured card stays published';
  assert (select count(*) from verses where id <> 'draft-test') = 20887, 'all imported and featured verses should be present';
end $$;

-- Drafted meanings: a verse with one gets our plain-English translation as primary, Besant's kept as secondary.
do $$ begin
  assert (select t.source_id from translations t where t.verse_id = 'gita-12-2' and t.is_primary) = 'veda-app-ai-draft', 'drafted translation should be primary';
  assert exists (select 1 from translations where verse_id = 'gita-12-2' and source_id = 'besant-1922' and not is_primary), 'Besant kept as secondary';
  assert (select status from explanations where verse_id = 'gita-12-2') = 'draft', 'drafted meaning stays a draft';
  assert (select source_id from explanations where verse_id = 'gita-12-13') = 'veda-app-original', 'featured card keeps its own meaning';
  assert (select count(distinct e.verse_id) from explanations e join verses v on v.id = e.verse_id where v.scripture_id = 'bhagavad-gita') = 700, 'every Gita verse has a meaning';
  assert (select count(distinct e.verse_id) from explanations e join verses v on v.id = e.verse_id where v.scripture_id = 'chandogya-upanishad') = 623, 'every Chandogya verse has a meaning';
  assert (select count(distinct e.verse_id) from explanations e join verses v on v.id = e.verse_id where v.scripture_id = 'brihadaranyaka-upanishad') = 433, 'every Brihadaranyaka verse (432 imported + 1 featured card) has a meaning';
  assert (select count(distinct e.verse_id) from explanations e where e.verse_id like 'ramayana-1-%') = 1941, 'every Bala Kanda verse has a meaning';
  assert (select count(distinct e.verse_id) from explanations e where e.verse_id like 'ramayana-2-%') = 3160, 'every Ayodhya Kanda verse has a meaning';
  assert (select count(distinct e.verse_id) from explanations e where e.verse_id like 'ramayana-3-%') = 2060, 'every Aranya Kanda verse has a meaning';
  assert (select count(distinct e.verse_id) from explanations e where e.verse_id like 'ramayana-4-%') = 1987, 'every Kishkindha Kanda verse has a meaning';
end $$;

-- Anonymous visitors see published verses only.
set role anon;
do $$ begin
  assert (select count(*) from verses) = 30, 'anon should see 30 published verses';
  assert (select count(*) from quiz_questions) = 60, 'anon should see 60 questions';
  assert (select count(*) from profiles) = 0, 'anon should see no profiles';
end $$;
reset role;

-- Reader A records progress and answers a question.
set role authenticated;
set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
select mark_verse_read('gita-2-47', true);
select mark_verse_read('gita-2-47');
select answer_question((select min(id) from quiz_questions where verse_id = 'gita-2-47'), 1::smallint);
do $$ begin
  assert (select read_count from verse_progress where verse_id = 'gita-2-47') = 2, 'read count should be 2';
  assert (select listened from verse_progress where verse_id = 'gita-2-47'), 'listened should stay true';
  assert (select is_correct from quiz_attempts limit 1), 'answer 1 should be correct';
  assert my_streak() = 1, 'streak should be 1';
  assert (select count(*) from profiles) = 1, 'A should see own profile';
end $$;

-- Reader B cannot see A's progress or forge an attempt.
set request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';
do $$ begin
  assert (select count(*) from verse_progress) = 0, 'B must not see A''s progress';
  assert (select count(*) from quiz_attempts) = 0, 'B must not see A''s attempts';
end $$;
do $$ begin
  begin
    insert into quiz_attempts (user_id, question_id, chosen_index, is_correct) values (auth.uid(), 1, 0, true);
    raise exception 'direct insert into quiz_attempts should be blocked';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;

select id, verses_imported, verses_published, expected_verses, percent_published from scripture_coverage where verses_imported > 0;
\echo 'All checks passed'
