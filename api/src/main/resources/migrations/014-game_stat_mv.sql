drop materialized view game_stat_mv;
create materialized view game_stat_mv as
SELECT g.id, title_eng, title_jpn_roman, title_jpn, count(*) as rows
from script s 
left join game g on s.game_id = g.id
group by g.id;