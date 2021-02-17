CREATE TABLE script (
  id serial primary key,
  game_id int NOT NULL references game(id),
  fname text NOT NULL,
  scene text NULL,
  row int NOT NULL,
  eng_chr_name text NULL,
  eng_search_text text,
  eng_html_text text,
  jpn_chr_name text NULL,
  jpn_search_text text,
  jpn_html_text text,
  op_name text NULL,
  pc_icon_html text NULL,
  evo_icon_html text NULL
);