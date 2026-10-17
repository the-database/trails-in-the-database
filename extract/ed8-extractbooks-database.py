"""Extract Trails of Cold Steel I-IV and Trails into Reverie (games 6-10)
in-game books into sen1-books.sql ... sen4-books.sql, reverie-books.sql.

    python ed8-extractbooks-database.py cs1     # also cs2, cs3, cs4, reverie

Source, staged under books_raw/<game>/ in the game's own data/ layout (EN dir
dat_us for CS1/CS2, dat_en for CS3/CS4; JP dir dat):

  text/<dir>/t_book.tbl (CS1/CS2) or t_notebook.tbl (CS3/CS4)
  text/<dir>/<same name>.sqlite
      the tbl converted with tocs' sqlite_conv:
          sqlite_conv tbl-to-sql --tbl-path <dir> --db-path <dir>/<name>.sqlite
              --game CS1 | CS1Jp | CS2 | CS2Jp | CS3 | CS4
      (CS1Jp / CS2Jp decode those games' Shift-JIS JP tables; CS3+ are UTF-8)
  scripts/book/<dir>/book*.dat
  scripts/book/xlsx/<dir>/book*.xlsx
      the .dat decompiled with SenScriptsDecompiler
      (`SenScriptsDecompiler.exe CS1 <dat> <outdir>`; config.ini
      InputDatFileEncoding Windows-31J for CS1/CS2 JP, UTF-8 otherwise)

CS1-CS4 come from the Steam release (CS1/CS2 byte-identical to the latest
GOG builds, 1.6 / 1.4.1). Reverie: EN from the Steam release; the western
release has no JP text, so JP comes from the Japanese PC Hajimari no Kiseki
(the "Game v1.0" install the dialogue extractor also uses), whose files are
CLE-encrypted: they are copied as-is to scripts/book/dat and text/dat and
decrypted copies made in scripts/book/decrypted/dat and text/decrypted/dat
with Falcom/bin/tools/cle_decrypt.exe; the sqlite and xlsx are built from
those (SenScriptsDecompiler game name `reverie`, sqlite_conv `--game CS5`).

The tbl's QSBook records are the game's book list, in its own order:
(category, item id, title, script file, function prefix). QSChapter names
the categories. A book's pages are the script functions <prefix>_01,
<prefix>_02, ... (op 270, text in the last cell; <prefix>_99 holds the page
count). EN and JP agree on the book list but not on page counts, so pages are
stored per language and books pair by (script file, prefix).

Quirks:
  - A book listed under two categories (CS2's Crossbell Times SP) is one book
    and is emitted once, under its first listing.
  - Black Records volumes are also listed in a partly deciphered state: same
    category and title, text with most characters blanked out (■ / ┃). Those
    stages are dropped in favour of the complete text (CS2 BookDataNNA/NNB,
    CS3 BookData13).
  - CS4 and Reverie list earlier games' books under those games' category
    ids without defining them in their own QSChapter; their names come from
    the earlier game's table.
  - Scripts the list never points at (CS2's copy of CS1's book00-03, the
    synpNN notebook synopses) are not books of that game and are skipped.

Output schema: the `book` / `book_page` tables (see the Go API repo's
migrations/20261017_books.sql).
"""

import html
import importlib.util
import os
import re
import sqlite3
import sys

RAW = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'books_raw')
HERE = os.path.dirname(os.path.abspath(__file__))

GAMES = {
    # game: (game_id, table, EN dir, output, games whose QSChapter fill in
    #        category ids missing from this one's, nearest first)
    'cs1': (6, 't_book', 'dat_us', 'sen1-books.sql', ()),
    'cs2': (7, 't_book', 'dat_us', 'sen2-books.sql', ()),
    'cs3': (8, 't_notebook', 'dat_en', 'sen3-books.sql', ()),
    'cs4': (9, 't_notebook', 'dat_en', 'sen4-books.sql', ('cs3',)),
    'reverie': (10, 't_notebook', 'dat_en', 'reverie-books.sql', ('cs4', 'cs3')),
}

# The decompiled-xlsx reader lives in the CS1 dialogue extractor; load it from
# there rather than carry a third copy.
_spec = importlib.util.spec_from_file_location('cs1_extract', os.path.join(HERE, '6D-cs1-extractscripts-database.py'))
_cs1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cs1)
xlsx_rows = _cs1._xlsx_rows

BLANKED_RE = re.compile('[■┃]')
RUBY_RE = re.compile(r'#(\d*)R([^#]*)#')
# Layout / colour codes: #000c, #-570y, #3S, ... (offsets can be negative).
CODE_RE = re.compile(r'#-?\d*[A-Za-z]')
# Runs of full-width spaces pad lines out to the page width; mid-line they
# pad a title out to a right-aligned date.
WRAP_GAP_RE = re.compile(r'(?<=\S)　{2,}')
WHITESPACE_RE = re.compile(r'[ \t　]+')
RUBY_OPEN, RUBY_SEP, RUBY_CLOSE = '\x11', '\x12', '\x13'
RUBY_MARK_RE = re.compile('\x11([^\x11-\x13]*)\x12([^\x11-\x13]*)\x13')


def load_books(db_path):
    con = sqlite3.connect(db_path)
    chapter_cols = [r[1] for r in con.execute('pragma table_info(QSChapter)')]
    # The id / name columns are named differently in the CS1 and CS2+ schemas.
    id_col, name_col = chapter_cols[1], chapter_cols[2]
    chapters = dict(con.execute(f'select {id_col}, {name_col} from QSChapter'))
    books = list(con.execute(
        'select unknown_short_1, title, unknown_text_1, unknown_text_2 from QSBook order by rowid'))
    return chapters, books


def book_pages(xlsx_path):
    """-> {prefix: (declared page count, [page text, ...])} in function order."""
    pages = {}
    fn = None
    for row in xlsx_rows(xlsx_path):
        if row and row[0] == 'FUNCTION':
            fn = row[1]
            continue
        if not fn or len(row) < 4:
            continue
        prefix, _, num = fn.rpartition('_')
        count, texts = pages.setdefault(prefix, (None, []))
        if num == '99' and row[1] == '269':
            pages[prefix] = (int(row[2]), texts)
        elif num != '99' and row[1] == '270':
            texts.append(row[-1])
    return pages


def park_ruby(line):
    """`base#NRreading#`, N being the cp932 byte length of the base."""
    out = []
    i = 0
    for m in RUBY_RE.finditer(line):
        prefix = line[i:m.start()]
        count = int(m.group(1) or 0)
        start = len(prefix)
        used = 0
        while start > 0 and used < count:
            start -= 1
            used += len(prefix[start].encode('cp932', errors='replace'))
        out.append(prefix[:start])
        if count and m.group(2):
            out.append(RUBY_OPEN + prefix[start:] + RUBY_SEP + m.group(2) + RUBY_CLOSE)
        else:
            out.append(prefix[start:])
        i = m.end()
    out.append(line[i:])
    return ''.join(out)


def tidy_page(text, lang):
    lines = []
    for line in text.replace('\\n', '\n').split('\n'):
        line = CODE_RE.sub('', park_ruby(line))
        # Same NEC off-by-one as the dialogue extractors.
        line = line.replace('㈱', '♥').rstrip(' \t　')
        line = WRAP_GAP_RE.sub(' ' if lang == 'eng' else '　', line)
        lines.append(line)
    while lines and not lines[0].strip():
        lines.pop(0)
    out = []
    for line in lines:
        if not line.strip() and (not out or not out[-1].strip()):
            continue
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


def render(lines, lang):
    """-> (search_text, html_text)"""
    html_text = '<br/>'.join(
        RUBY_MARK_RE.sub(r'<ruby>\1<rt>\2</rt></ruby>', html.escape(l, quote=False)) for l in lines)
    plain = [RUBY_MARK_RE.sub(r'\1', l) for l in lines]
    # JP lines break mid-word, so they join without a space.
    search = (' ' if lang == 'eng' else '').join(plain)
    return WHITESPACE_RE.sub(' ', search).strip(), html_text


def plain(text):
    return WHITESPACE_RE.sub(' ', RUBY_MARK_RE.sub(r'\1', CODE_RE.sub('', park_ruby(text)))).strip()


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def sql_value(v):
    if v is None:
        return 'NULL'
    if isinstance(v, int):
        return str(v)
    return "'%s'" % sql_escape(v)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in GAMES:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    game_id, table, en_dir, output, fallback = GAMES[sys.argv[1]]
    root = os.path.join(RAW, sys.argv[1])
    dirs = {'eng': en_dir, 'jpn': 'dat'}

    def table_path(game, lang):
        _, tbl, en, *_ = GAMES[game]
        return os.path.join(RAW, game, 'text', en if lang == 'eng' else 'dat', tbl + '.sqlite')

    chapters, en_books = load_books(table_path(sys.argv[1], 'eng'))
    jp_chapters, jp_books = load_books(table_path(sys.argv[1], 'jpn'))
    assert [b[2:] for b in en_books] == [b[2:] for b in jp_books], 'EN/JP QSBook lists differ'
    for previous in fallback:
        for lang, names in (('eng', chapters), ('jpn', jp_chapters)):
            for cat, name in load_books(table_path(previous, lang))[0].items():
                names.setdefault(cat, name)

    cache = {}

    def pages_for(lang, script, prefix):
        key = (lang, script)
        if key not in cache:
            cache[key] = book_pages(os.path.join(root, 'scripts', 'book', 'xlsx', dirs[lang], script + '.xlsx'))
        declared, texts = cache[key].get(prefix, (None, []))
        # The game shows <prefix>_99's page count; a few books carry blank
        # page functions past it (Reverie JP book02 BookData06: 16 + 3).
        assert declared is not None and declared <= len(texts), (lang, script, prefix, declared, len(texts))
        assert not any(tidy_page(t, lang) for t in texts[declared:]), (lang, script, prefix, 'text past page count')
        return texts[:declared]

    candidates = []
    seen = set()
    for (cat, title, script, prefix), (_, title_jp, _, _) in zip(en_books, jp_books):
        if (script, prefix) in seen:
            continue
        seen.add((script, prefix))
        texts = {lang: pages_for(lang, script, prefix) for lang in ('eng', 'jpn')}
        candidates.append((cat, title, title_jp, script, prefix, texts))

    def blanked(texts):
        return any(BLANKED_RE.search(t) for t in texts['eng'] + texts['jpn'])

    complete = {(c[0], c[1]) for c in candidates if not blanked(c[5])}
    books = []
    for cat, title, title_jp, script, prefix, texts in candidates:
        if blanked(texts) and (cat, title) in complete:
            continue
        pages = {}
        for lang in ('eng', 'jpn'):
            rendered = [render(tidy_page(t, lang), lang) for t in texts[lang]]
            pages[lang] = [r for r in rendered if r[0]]
        assert pages['eng'] and pages['jpn'], (script, prefix)
        assert cat in chapters and cat in jp_chapters, (script, prefix, cat)
        books.append({
            'key': f'{script}:{prefix}',
            'series_eng': chapters[cat], 'series_jpn': jp_chapters[cat],
            'title_eng': plain(title), 'title_jpn': plain(title_jp),
            'pages': pages,
        })

    write_sql(output, game_id, books)


def write_sql(output, game_id, books):
    n_pages = 0
    with open(output, 'w', encoding='utf-8') as f:
        # Upsert on (game_id, book_key) rather than delete + insert, so book
        # ids -- and with them the site's /books/<id> links -- survive a
        # re-extract. Books that disappeared are dropped at the end.
        f.write(f'delete from book_page where book_id in (select id from book where game_id = {game_id});\n')
        for order, b in enumerate(books, start=1):
            f.write(
                'insert into book (game_id, book_key, sort_order, series_eng, series_jpn, '
                'title_eng, title_jpn, eng_page_count, jpn_page_count) values\n(%s)\n'
                'on conflict (game_id, book_key) do update set sort_order = excluded.sort_order, '
                'series_eng = excluded.series_eng, series_jpn = excluded.series_jpn, '
                'title_eng = excluded.title_eng, title_jpn = excluded.title_jpn, '
                'eng_page_count = excluded.eng_page_count, jpn_page_count = excluded.jpn_page_count;\n' % ', '.join(
                    sql_value(v) for v in (
                        game_id, b['key'], order, b['series_eng'], b['series_jpn'],
                        b['title_eng'], b['title_jpn'],
                        len(b['pages']['eng']), len(b['pages']['jpn']),
                    )))
            for lang in ('eng', 'jpn'):
                for page, (search, html_text) in enumerate(b['pages'][lang], start=1):
                    f.write(
                        'insert into book_page (book_id, lang, page, search_text, html_text) values\n'
                        "((select id from book where game_id = %d and book_key = %s), '%s', %d, %s, %s);\n"
                        % (game_id, sql_value(b['key']), lang, page, sql_value(search), sql_value(html_text)))
                    n_pages += 1
        keys = ', '.join(sql_value(b['key']) for b in books)
        f.write(f'delete from book where game_id = {game_id} and book_key not in ({keys});\n')
    print(f'{output}: {len(books)} books, {n_pages} pages')


if __name__ == '__main__':
    main()
