-- Returns distinct dates with idea counts, newest first
create or replace function get_macro_idea_dates()
returns table(date date, count bigint)
language sql stable
as $$
  select date, count(*) as count
  from macro_ideas
  group by date
  order by date desc;
$$;
