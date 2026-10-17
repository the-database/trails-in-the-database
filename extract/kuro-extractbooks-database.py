"""Extract in-game books for the Kuro-engine games into <game>-books.sql.

    python kuro-extractbooks-database.py daybreak    # game 11 -> daybreak-books.sql
    python kuro-extractbooks-database.py db2         # game 12 -> db2-books.sql
    python kuro-extractbooks-database.py horizon     # game 13 -> horizon-books.sql
    python kuro-extractbooks-database.py sky1r       # game 101 -> sky1r-books.sql
    python kuro-extractbooks-database.py sky2r       # game 102 -> sky2r-books.sql

Source: KuroTools/books_20261017/<game>/{en,jp}/, staged from the Steam
installs on 2026-10-17 (all confirmed on the latest patch):
  daybreak, horizon  table{,_en,_eng}/*.tbl copied as-is
  db2                script{,_en}.p3a via daybreak2_extract/p3a_extract_filter.py
  sky1, sky2         pac/steam/table{,_en}.pac (FPAC, same layout as
                     sky*/sky_extract_pac.py). Not the loose table*/ dirs in
                     the installs, which are stale copies.
then `python tbl2json.py [-g Sora1] t_books.tbl` (and t_notemenu.tbl for the
three Kuro games) from the KuroTools root.

t_books.tbl:
  BooksTitle  {id, int1 = category, title, ...}
  BooksText   {book_id = BooksTitle.id, line_id = page, book_text}
  Category names: BooksCategory {id, category_name} in the Sky remakes;
  t_notemenu.tbl NoteBooksMenu {note_text, long1 = category} in the others.
EN and JP share BooksTitle but not page counts, so pages are stored per
language. Every BooksTitle row is emitted, including the Sky 1st library that
Sky 2nd carries over, so each game's list is what that game ships; those
carried-over books keep their Sky 1st category (see PREVIOUS).
Daybreak II's BooksTitleReplace only swaps a texture for book 106 and is
ignored.

Output schema: the `book` / `book_page` tables (see the app repo's
api/src/main/resources/migrations/20261017_books.sql).
"""

import html
import json
import os
import re
import sys

ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'KuroTools', 'books_20261017')

GAMES = {
    # game: (game_id, staged dir, output)
    'daybreak': (11, 'daybreak', 'daybreak-books.sql'),
    'db2': (12, 'daybreak2', 'db2-books.sql'),
    'horizon': (13, 'horizon', 'horizon-books.sql'),
    'sky1r': (101, 'sky1', 'sky1r-books.sql'),
    'sky2r': (102, 'sky2', 'sky2r-books.sql'),
}

# Sky 2nd files its carried-over Sky 1st books under category 2, which its own
# BooksCategory doesn't define. Those books take the category Sky 1st gives the
# same book id; where that name is also one of the game's own categories (Liberl
# News), the suffix keeps the carried-over issues from merging into the game's
# own run of the same series. Books in an undefined category with no
# counterpart get FALLBACK_CATEGORY (Sky 1st's name for category 2).
PREVIOUS = {
    # game: (staged dir of the game it carries books over from, EN suffix, JP suffix)
    'sky2r': ('sky1', ' (1st Chapter)', '（the 1st）'),
}
FALLBACK_CATEGORY = ('Other', 'その他')

# Furigana: `<R>base</Rreading>`. Same handling as the dialogue extractors
# (1R-sky1r-extractscripts-database.py): a reading-less `<R>x</R>` is
# emphasis, not furigana.
RUBY_RE = re.compile(r'<R>([^<>]*)</R([^<>]*)>')
RUBY_OPEN, RUBY_SEP, RUBY_CLOSE = '\x01', '\x02', '\x03'
RUBY_MARK_RE = re.compile('\x01([^\x01-\x03]*)\x02([^\x01-\x03]*)\x03')
ANGLE_TAG_RE = re.compile(r'<[^>]*>')
WHITESPACE_RE = re.compile(r'[ \t　]+')


def load_tables(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return {t['name']: t['data'] for t in data['data']}


def mark_ruby(text):
    def park(m):
        base, reading = m.group(1).strip(), m.group(2).strip()
        if not reading or not base:
            return m.group(1)
        return RUBY_OPEN + base + RUBY_SEP + reading + RUBY_CLOSE
    return ANGLE_TAG_RE.sub('', RUBY_RE.sub(park, text))


def tidy_lines(text):
    lines = [l.replace('\t', ' ').rstrip(' 　') for l in mark_ruby(text).split('\n')]
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


def render(text, lang):
    """-> (search_text, html_text)"""
    lines = tidy_lines(text)
    html_text = '<br/>'.join(
        RUBY_MARK_RE.sub(r'<ruby>\1<rt>\2</rt></ruby>', html.escape(l, quote=False)) for l in lines)
    plain = [RUBY_MARK_RE.sub(r'\1', l) for l in lines]
    # JP lines break mid-word, so they join without a space.
    search = (' ' if lang == 'eng' else '').join(plain)
    return WHITESPACE_RE.sub(' ', search).strip(), html_text


def plain(text):
    return WHITESPACE_RE.sub(' ', RUBY_MARK_RE.sub(r'\1', mark_ruby(text))).strip()


def categories(game_dir, lang, tables):
    if 'BooksCategory' in tables:
        return {r['id']: plain(r['category_name']) for r in tables['BooksCategory']}
    menu = load_tables(os.path.join(game_dir, lang, 't_notemenu.json'))['NoteBooksMenu']
    return {r['long1']: plain(r['note_text']) for r in menu}


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
    game_id, staged, output = GAMES[sys.argv[1]]
    game_dir = os.path.join(ROOT, staged)

    per_lang = {}
    for lang, sub in (('eng', 'en'), ('jpn', 'jp')):
        tables = load_tables(os.path.join(game_dir, sub, 't_books.json'))
        pages = {}
        for r in sorted(tables['BooksText'], key=lambda r: (r['book_id'], r['line_id'])):
            rendered = render(r['book_text'], lang)
            if rendered[0]:
                pages.setdefault(r['book_id'], []).append(rendered)
        per_lang[lang] = {
            'titles': tables['BooksTitle'],
            'categories': categories(game_dir, sub, tables),
            'pages': pages,
        }

    eng, jpn = per_lang['eng'], per_lang['jpn']
    assert [t['id'] for t in eng['titles']] == [t['id'] for t in jpn['titles']], 'EN/JP BooksTitle differ'
    jpn_titles = {t['id']: t for t in jpn['titles']}

    previous = {}
    suffix_eng = suffix_jpn = ''
    if sys.argv[1] in PREVIOUS:
        prev_staged, suffix_eng, suffix_jpn = PREVIOUS[sys.argv[1]]
        prev_dir = os.path.join(ROOT, prev_staged)
        for lang, sub in (('eng', 'en'), ('jpn', 'jp')):
            tables = load_tables(os.path.join(prev_dir, sub, 't_books.json'))
            previous[lang] = ({t['id']: t['int1'] for t in tables['BooksTitle']},
                              categories(prev_dir, sub, tables))

    books = []
    for t in eng['titles']:
        jt = jpn_titles[t['id']]
        cat = t['int1']
        if cat in eng['categories']:
            series_eng, series_jpn = eng['categories'][cat], jpn['categories'].get(cat)
        elif previous and t['id'] in previous['eng'][0]:
            prev_cat = previous['eng'][0][t['id']]
            series_eng = previous['eng'][1][prev_cat]
            series_jpn = previous['jpn'][1][prev_cat]
            if series_eng in eng['categories'].values():
                series_eng += suffix_eng
                series_jpn += suffix_jpn
        else:
            series_eng, series_jpn = FALLBACK_CATEGORY
        books.append({
            'key': str(t['id']),
            'series_eng': series_eng, 'series_jpn': series_jpn,
            'title_eng': plain(t['title']), 'title_jpn': plain(jt['title']),
            'pages': {'eng': eng['pages'].get(t['id'], []), 'jpn': jpn['pages'].get(t['id'], [])},
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
