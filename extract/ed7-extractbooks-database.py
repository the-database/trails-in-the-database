"""Extract Trails from Zero (game 4) / Trails to Azure (game 5) in-game books
into zero-books.sql / azure-books.sql.

    python ed7-extractbooks-database.py zero
    python ed7-extractbooks-database.py azure

Source: EDDecompiler/data/<snapshot>/{en,jp}/text/t_bookNN._dt, the same
post-2026-09-10-patch snapshots zero-azure-new-run.py reads. No decompiler
handles these files; the format is simple enough to read directly:

  u16 offset table (the first offset doubles as the table size), offsets in
  (title, body) pairs, one pair per issue / chapter. Each string is
  NUL-terminated cp932. Body control codes:
    \\x01          line break
    \\x02\\x03      page break
    \\x07 NN       colour (two bytes)
    #NR...#       furigana; N is the byte length (cp932) of the base
    #Nx #Ny #NF   layout position / inline picture
    #NS #F #Z     font size / layout resets
  Every page ends with a right-aligned "N/M" (EN) / "Ｎ／Ｍ" (JP) page counter,
  which is dropped since the site paginates on its own.

EN and JP share entry counts per file (asserted) but not page counts, so
books pair by (file, entry index) and pages are stored per language.

Azure ships Zero's t_book00-05 again (the carried-over Zero library, retouched
by a few bytes) ahead of its own t_book06-09. All of them are emitted, so each
game's book list matches what that game actually contains.

Output schema: the `book` / `book_page` tables (see the app repo's
api/src/main/resources/migrations/20261017_books.sql).
"""

import html
import os
import re
import struct
import sys

DATA = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'EDDecompiler', 'data')

GAMES = {
    # game: (game_id, snapshot, files, output)
    'zero': (4, 'zero20261017', [f't_book{n:02d}' for n in range(0, 6)], 'zero-books.sql'),
    'azure': (5, 'azure20261017', [f't_book{n:02d}' for n in range(0, 10)], 'azure-books.sql'),
}

# Series by EN title prefix; anything else is a standalone book (series NULL,
# shown under "Other" by the site).
SERIES = [
    ('Tomb of Secrets', 'Tomb of Secrets', '秘伝書'),
    ('Crossbell Times', 'Crossbell Times', 'クロスベルタイムズ'),
    ('Back Alley Doctor Glenn', 'Back Alley Doctor Glenn', '闇医者グレン'),
    ('Mark and the Witch', 'Mark and the Witch', 'マルクと深き森の魔女'),
    # The EN patch titles volume 2 "The Saint and the White Witch".
    ('The Saint and the White', 'The Saint and the White Wolf', '聖女と白い狼'),
    ('Sunshine Agnès', 'Sunshine Agnès', '陽溜りのアニエス'),
]

CODE_RE = re.compile(rb'#(\d*)([A-Za-z])')
# Sentinels for parked furigana; control bytes never survive into page text.
RUBY_OPEN, RUBY_SEP, RUBY_CLOSE = '\x11', '\x12', '\x13'
RUBY_MARK_RE = re.compile('\x11([^\x11-\x13]*)\x12([^\x11-\x13]*)\x13')
PAGE_COUNTER_RE = re.compile(r'^[\s　]*[0-9０-９]+[\s　]*[/／][\s　]*[0-9０-９]+[\s　]*$')
# Runs of full-width spaces at line start wrap text around a picture the site
# doesn't show; a single one is a JP paragraph indent and stays. Mid-line runs
# pad a picture caption out to the wrapped text that follows it.
WRAP_INDENT_RE = re.compile(r'^　{2,}')
WRAP_GAP_RE = re.compile(r'(?<=\S)　{2,}')
WHITESPACE_RE = re.compile(r'[ \t　]+')


def is_sjis_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def read_entries(path):
    with open(path, 'rb') as f:
        data = f.read()
    size = struct.unpack_from('<H', data, 0)[0]
    offsets = [struct.unpack_from('<H', data, i)[0] for i in range(0, size, 2)]
    return [data[o:data.index(b'\0', o)] for o in offsets]


def split_pages(body):
    """Body bytes -> list of pages, each a list of lines (str). Codes are
    stripped; furigana is parked behind sentinels."""
    pages = []
    lines = []
    line = bytearray()
    i = 0
    n = len(body)
    while i < n:
        b = body[i]
        if b == 0x02 and i + 1 < n and body[i + 1] == 0x03:
            lines.append(bytes(line))
            pages.append(lines)
            lines, line = [], bytearray()
            i += 2
        elif b == 0x01:
            lines.append(bytes(line))
            line = bytearray()
            i += 1
        elif b == 0x07:
            i += 2
        elif b < 0x20:
            i += 1
        elif b == 0x23:  # '#'
            m = CODE_RE.match(body, i)
            if not m:
                line.append(b)
                i += 1
                continue
            if m.group(2) == b'R':
                end = body.index(b'#', m.end())
                reading = body[m.end():end]
                count = min(int(m.group(1) or 0), len(line))
                base = bytes(line[len(line) - count:])
                del line[len(line) - count:]
                line += (RUBY_OPEN.encode() + base + RUBY_SEP.encode()
                         + reading + RUBY_CLOSE.encode())
                i = end + 1
            else:
                i = m.end()
        elif is_sjis_lead(b) and i + 1 < n:
            line += body[i:i + 2]
            i += 2
        else:
            line.append(b)
            i += 1
    lines.append(bytes(line))
    pages.append(lines)
    return [[l.decode('cp932') for l in page] for page in pages]


def tidy_page(lines, lang):
    out = []
    for line in lines:
        if lang == 'eng':
            # EN patch puts è at cp932 0x875F, which decodes as ㍉.
            line = line.replace('㍉', 'è')
        # Same NEC off-by-one as the dialogue extractors.
        line = line.replace('㈱', '♥')
        line = WRAP_INDENT_RE.sub('', line.rstrip(' \t　'))
        line = WRAP_GAP_RE.sub(' ' if lang == 'eng' else '　', line)
        out.append(line)
    # Drop the page counter, then blank padding around / runs inside the page.
    while out and not out[-1].strip():
        out.pop()
    if out and PAGE_COUNTER_RE.match(out[-1]):
        out.pop()
    collapsed = []
    for line in out:
        if not line.strip() and (not collapsed or not collapsed[-1].strip()):
            continue
        collapsed.append(line)
    while collapsed and not collapsed[-1].strip():
        collapsed.pop()
    return collapsed


def render(lines, lang):
    """-> (search_text, html_text)"""
    html_lines = []
    for line in lines:
        h = html.escape(line, quote=False)
        h = RUBY_MARK_RE.sub(r'<ruby>\1<rt>\2</rt></ruby>', h)
        html_lines.append(h)
    plain = [RUBY_MARK_RE.sub(r'\1', line) for line in lines]
    # JP lines break mid-word, so they join without a space.
    search = (' ' if lang == 'eng' else '').join(plain)
    search = WHITESPACE_RE.sub(' ', search).strip()
    return search, '<br/>'.join(html_lines)


def plain_title(raw, lang):
    pages = split_pages(raw)
    text = RUBY_MARK_RE.sub(r'\1', ' '.join(l for p in pages for l in p))
    if lang == 'eng':
        text = text.replace('㍉', 'è')
    return WHITESPACE_RE.sub(' ', text).strip()


def series_for(title_eng):
    for prefix, eng, jpn in SERIES:
        if title_eng.startswith(prefix):
            return eng, jpn
    return None, None


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
    game_id, snapshot, files, output = GAMES[sys.argv[1]]
    root = os.path.join(DATA, snapshot)

    books = []
    for fname in files:
        en = read_entries(os.path.join(root, 'en', 'text', fname + '._dt'))
        jp = read_entries(os.path.join(root, 'jp', 'text', fname + '._dt'))
        assert len(en) == len(jp) and len(en) % 2 == 0, (fname, len(en), len(jp))
        for k in range(0, len(en), 2):
            title_eng = plain_title(en[k], 'eng')
            title_jpn = plain_title(jp[k], 'jpn')
            series_eng, series_jpn = series_for(title_eng)
            pages = {}
            for lang, raw in (('eng', en[k + 1]), ('jpn', jp[k + 1])):
                rendered = [render(tidy_page(p, lang), lang) for p in split_pages(raw)]
                pages[lang] = [r for r in rendered if r[0]]
            books.append({
                'key': f'{fname}:{k // 2}',
                'series_eng': series_eng, 'series_jpn': series_jpn,
                'title_eng': title_eng, 'title_jpn': title_jpn,
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
