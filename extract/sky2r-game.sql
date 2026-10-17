-- Upsert rather than delete+insert: once `script` / `file` rows exist for
-- this game, a delete trips file_game_id_fkey / script_game_id_fkey.
insert into game (id, title_eng, title_jpn_roman, title_jpn) values
('102','Trails in the Sky 2nd Chapter','Sora no Kiseki the 2nd','空の軌跡 the 2nd')
on conflict (id) do update set
  title_eng = excluded.title_eng,
  title_jpn_roman = excluded.title_jpn_roman,
  title_jpn = excluded.title_jpn;
