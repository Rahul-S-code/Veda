-- Run after the migration and seed. Fails loudly if a check does not hold.
\set ON_ERROR_STOP on
insert into auth.users (id, email) values ('11111111-1111-1111-1111-111111111111', 'a@example.com'), ('22222222-2222-2222-2222-222222222222', 'b@example.com');
insert into verses (id, scripture_id, reference, sanskrit, sort_key, status) values ('draft-test', 'bhagavad-gita', 'Draft', 'x', 999999, 'draft');

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
