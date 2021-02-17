CREATE TEXT SEARCH DICTIONARY english_stem_nostop (
    Template = snowball
    , Language = english
);

CREATE TEXT SEARCH CONFIGURATION english_nostop ( COPY = pg_catalog.english );
ALTER TEXT SEARCH CONFIGURATION english_nostop
   ALTER MAPPING FOR asciiword, asciihword, hword_asciipart, hword, hword_part, word WITH english_stem_nostop;

-- ALTER TABLE script
    -- ADD COLUMN textsearchable_index_col tsvector
               -- GENERATED ALWAYS AS (to_tsvector('english', coalesce(eng_search_text, '') || ' ' || coalesce(jpn_search_text, ''))) STORED;

-- CREATE INDEX textsearch_idx ON script USING GIN (textsearchable_index_col);

-- drop index textsearch_idx;
-- alter table script drop column textsearchable_index_col;

-- drop index script_eng_search_idx;
-- drop index script_jpn_search_idx;
CREATE INDEX script_eng_search_idx ON script USING GIN (to_tsvector('english_nostop', eng_search_text));
CREATE INDEX script_eng_simple_search_idx ON script USING GIN (to_tsvector('simple', eng_search_text));
CREATE INDEX script_jpn_search_idx ON script USING GIN (to_tsvector('simple', jpn_search_text));