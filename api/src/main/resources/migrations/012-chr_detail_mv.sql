drop materialized view chr_detail_mv;
create materialized view chr_detail_mv as
SELECT array_agg(distinct s.game_id) as game_id, s.eng_chr_name, s.jpn_chr_name, count(*) as rows FROM script s 
WHERE fname NOT LIKE 'a%' AND (game_id, fname) NOT IN (SELECT game_id, fname FROM file WHERE place_name_eng LIKE 'map%') 
GROUP BY s.eng_chr_name, s.jpn_chr_name ORDER BY rows desc;