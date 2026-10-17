"""Extract Trails in the Sky FC / SC / the 3rd (games 1 / 2 / 3) in-game books
into skyfc-books.sql / skysc-books.sql / sky3rd-books.sql.

    python ed6-extractbooks-database.py fc
    python ed6-extractbooks-database.py sc
    python ed6-extractbooks-database.py 3rd

English comes from the current Steam PC release, Japanese from the PS Vita
Evolution release (the same pairing the dialogue extractors use).

English: the T_BOOK*._DT tables in the PC archives, ED6_DT02 (FC) and
ED6_DT22 (SC, the 3rd), unpacked with Falcom/ED6/ED6DatCreator/ED6Unpacker.exe
into books_raw/<game>/<archive>/:

    copy ED6_DT22.dir + ED6_DT22.dat into books_raw/skysc/
    ED6Unpacker.exe books_raw/skysc/ED6_DT22.dat   -> books_raw/skysc/ED6_DT22/
    (T_BOOK entries of size 0 in the .dir report "failed"; they are empty)

Japanese: DATA/TEXT (FC), DATA_SC/TEXT (SC) or DATA_3RD/TEXT (the 3rd)
T_BOOK*._DT from the decrypted Evolution dump's gamedata/data.psarc
(PCSG00488 FC, PCSG00489 SC, PCSG00490 the 3rd), unpacked with UnPSARC,
copied into books_raw/<game>/evo_jp/. Evolution
keeps the PC file and entry layout exactly -- same T_BOOK00 index, same entry
per (file, index) -- so EN and JP pair by (file, entry); this is asserted.

T_BOOK00 is an index, not a book: 12-byte records (u32 item id, u16 file
index into the archive's .dir listing, u16 archive number, u32 entry), one
per book item, in in-game order, terminated by an all-0xFF record. It is
what makes a book exist in the game, so it drives the list and order here:
unreferenced entries (the "ダミー" filler) are skipped, and so is anything
whose text is still placeholder ("まだダミーデータです。").

T_BOOK01+ use the same layout and codes as Zero/Azure (see
ed7-extractbooks-database.py): u16 offset table, (title, body) pairs of
NUL-terminated cp932. One difference: the 3rd puts a colour code between the
page-break bytes (\\x02 \\x07\\t \\x03), so \\x02 alone marks the break here and
\\x03 is dropped.

SC and the 3rd carry earlier books over (SC re-ships FC's library, the 3rd
both), and they are emitted like any other book so each game's list is what
it ships.

Output schema: the `book` / `book_page` tables (see the Go API repo's
migrations/20261017_books.sql).
"""

import html
import os
import re
import struct
import sys

RAW = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'books_raw')

GAMES = {
    # game: (game_id, folder, archive, Japanese folder or None, output)
    'fc': (1, 'skyfc', 'ED6_DT02', 'evo_jp', 'skyfc-books.sql'),
    'sc': (2, 'skysc', 'ED6_DT22', 'evo_jp', 'skysc-books.sql'),
    '3rd': (3, 'sky3rd', 'ED6_DT22', 'evo_jp', 'sky3rd-books.sql'),
}

# Series by EN title prefix; anything else is a standalone book (series NULL,
# shown under "Other" by the site). JP names are the ones the Sky remakes'
# t_books tables use for the same series.
SERIES = [
    ('Liberl News', 'Liberl News', 'リベール通信'),
    ('Carnelia', 'Carnelia', 'カーネリア'),
    ('Gambler Jack', 'Gambler Jack', '賭博師ジャック'),
    ('The Doll Knight', 'The Doll Knight', '人形の騎士'),
]

PLACEHOLDER_RE = re.compile('ダミー')

# Layout offsets can be negative (`#-23x`).
CODE_RE = re.compile(rb'#(-?\d*)([A-Za-z])')
# Sentinels for parked furigana; control bytes never survive into page text.
RUBY_OPEN, RUBY_SEP, RUBY_CLOSE = '\x11', '\x12', '\x13'
RUBY_MARK_RE = re.compile('\x11([^\x11-\x13]*)\x12([^\x11-\x13]*)\x13')
PAGE_COUNTER_RE = re.compile(r'^[\s　]*[0-9０-９]+[\s　]*[/／][\s　]*[0-9０-９]+[\s　]*$')
# Runs of full-width spaces at line start wrap text around a picture the site
# doesn't show. Mid-line runs pad a picture caption out to the wrapped text
# that follows it.
WRAP_INDENT_RE = re.compile(r'^　{2,}')
WRAP_GAP_RE = re.compile(r'(?<=\S)　{2,}')
WHITESPACE_RE = re.compile(r'[ \t　]+')


def is_sjis_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def char_boundary(line, start):
    """First cp932 character boundary at or after byte `start` of `line`.
    A furigana base is given as a byte count, which can land inside a
    double-byte character when the base mixes in half-width spaces."""
    i = 0
    while i < max(start, 0):
        i += 2 if is_sjis_lead(line[i]) and i + 1 < len(line) else 1
    return i


def read_entries(path):
    with open(path, 'rb') as f:
        data = f.read()
    size = struct.unpack_from('<H', data, 0)[0]
    offsets = [struct.unpack_from('<H', data, i)[0] for i in range(0, size, 2)]
    out = []
    for o in offsets:
        end = data.find(b'\0', o)  # the last string may run to EOF unterminated
        out.append(data[o:end if end >= 0 else len(data)])
    return out


def dir_names(path):
    """Archive .dir -> file names, in the order T_BOOK00's file index uses."""
    with open(path, 'rb') as f:
        data = f.read()
    assert data[:8] == b'LB DIR\x1a\x00', path
    names = []
    for i in range(16, len(data) - 0x23, 0x24):
        name = data[i:i + 16].split(b'\0')[0].decode('ascii')
        if not name.startswith('/'):
            names.append(name)
    return names


def read_index(path, names):
    with open(path, 'rb') as f:
        data = f.read()
    refs = []
    for i in range(0, len(data) - 11, 12):
        _item, file_idx, archive, entry = struct.unpack_from('<IHHI', data, i)
        if archive == 0xFFFF:
            break
        refs.append((names[file_idx], entry))
    return refs


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
        if b == 0x02:
            lines.append(bytes(line))
            pages.append(lines)
            lines, line = [], bytearray()
            i += 1
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
                start = char_boundary(line, len(line) - int(m.group(1) or 0))
                base = bytes(line[start:])
                del line[start:]
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


def render_body(raw, lang):
    rendered = [render(tidy_page(p, lang), lang) for p in split_pages(raw)]
    return [r for r in rendered if r[0]]


def plain_title(raw):
    text = RUBY_MARK_RE.sub(r'\1', ' '.join(l for p in split_pages(raw) for l in p))
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
    game_id, folder, archive, jp_folder, output = GAMES[sys.argv[1]]
    root = os.path.join(RAW, folder)
    en_tables = os.path.join(root, archive)
    jp_tables = os.path.join(root, jp_folder) if jp_folder else None

    names = dir_names(os.path.join(root, archive + '.dir'))
    refs = read_index(os.path.join(en_tables, 'T_BOOK00._DT'), names)
    if jp_tables:
        jp_refs = read_index(os.path.join(jp_tables, 'T_BOOK00._DT'), names)
        assert refs == jp_refs, 'PC and Evolution T_BOOK00 indexes differ'

    cache = {}

    def strings(tables, fname):
        if (tables, fname) not in cache:
            cache[tables, fname] = read_entries(os.path.join(tables, fname))
        return cache[tables, fname]

    books = []
    for fname, entry in refs:
        en = strings(en_tables, fname)
        title = plain_title(en[2 * entry])
        pages = {'eng': render_body(en[2 * entry + 1], 'eng'), 'jpn': []}
        if PLACEHOLDER_RE.search(title) or any(PLACEHOLDER_RE.search(s) for s, _ in pages['eng']):
            print(f'skip placeholder {fname}:{entry}', file=sys.stderr)
            continue
        title_jpn = None
        if jp_tables:
            jp = strings(jp_tables, fname)
            assert len(jp) == len(en), (fname, len(en), len(jp))
            title_jpn = plain_title(jp[2 * entry])
            pages['jpn'] = render_body(jp[2 * entry + 1], 'jpn')
        series_eng, series_jpn = series_for(title)
        books.append({
            'key': f'{os.path.splitext(fname)[0].lower()}:{entry}',
            'series_eng': series_eng, 'series_jpn': series_jpn,
            'title_eng': title, 'title_jpn': title_jpn,
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
