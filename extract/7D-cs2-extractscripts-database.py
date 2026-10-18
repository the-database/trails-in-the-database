"""Extract Trails of Cold Steel II (game 7) dialogue into sen2.sql.

Decompiled-source variant of the original 7-cs2 extractor, modeled
architecturally on 9D-sen4. The CS2 decompile output differs from
CS3/CS4: dialogue lives in XLSX bytecode tables rather than Python
files, and per-language metadata (NameTableData, voice) lives in
SQLite (cs2_jp.sqlite / cs2_en.sqlite) rather than t_name.py / t_voice.py.

Each XLSX row is one bytecode opcode: [Location, OP_Code, params...].
Dialogue opcodes match the original .dat IDs:
  26 (0x1A) ChrTalk        — char_id + text(s)
  24 (0x18) AnonymousTalk  — text(s)
  29 (0x1D) SetChrName     — name str + target chr_id (one-shot if 0xFFFF)

The `Location` rows preceding each data row carry the cell-type schema
(e.g. ['Location', 'OP Code', 'short', 'dialog', 'byte', 'byte', ...]).
We use that header to identify which cells are dialog text vs. control
bytes vs. char ids.

Active voice (the party banter that plays on the field) comes from
t_active.tbl and goes in as one more file, `active_voice`; see
active_voice_exchanges.
"""

import ast
import html
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile

FALCOM_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'Falcom')
DATA_ROOT = os.path.join(FALCOM_ROOT, 'data', 'cs2')
SCRIPTS_ROOT = os.path.join(DATA_ROOT, 'scripts')
JP_SQLITE = os.path.join(DATA_ROOT, 'cs2_jp.sqlite')
EN_SQLITE = os.path.join(DATA_ROOT, 'cs2_en.sqlite')
GAME_ID = 7
OUTPUT = 'sen2.sql'

# t_active.tbl from the Steam release, staged with the books (see
# ed8-extractbooks-database.py) and converted with tocs' sqlite_conv
# (`--game CS2` for dat_us, `--game CS2Jp` for dat).
ACTIVE_VOICE_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'books_raw', 'cs2', 'text')
EN_ACTIVE = os.path.join(ACTIVE_VOICE_ROOT, 'dat_us', 't_active.sqlite')
JP_ACTIVE = os.path.join(ACTIVE_VOICE_ROOT, 'dat', 't_active.sqlite')
ACTIVE_VOICE_FNAME = 'active_voice'

# CS2 stems whose dialogue is boilerplate. Empty for now.
SKIP_STEMS = set()

# Portrait sprites shipped at itp/7/{file}. Snapshot of
# Ingert/data/cs2/. Naming follows CS3-style chrId scheme:
# avf{chrId * 10:04d}.webp (Rean 0 -> avf0000, Alisa 1 -> avf0010).
# `_1` style variants (avf0001 etc.) are alternate expressions and
# aren't used in v1.
AVAILABLE_PORTRAITS = {
    'avf0000.webp', 'avf0001.webp', 'avf0010.webp', 'avf0011.webp',
    'avf0020.webp', 'avf0021.webp', 'avf0030.webp', 'avf0031.webp',
    'avf0040.webp', 'avf0041.webp', 'avf0050.webp', 'avf0051.webp',
    'avf0060.webp', 'avf0061.webp', 'avf0070.webp', 'avf0071.webp',
    'avf0080.webp', 'avf0081.webp', 'avf0090.webp', 'avf0091.webp',
    'avf0110.webp', 'avf0119.webp',
    'avf0120.webp', 'avf0121.webp', 'avf0122.webp',
    'avf0130.webp', 'avf0140.webp', 'avf0150.webp', 'avf0160.webp',
    'avf0170.webp', 'avf0180.webp', 'avf0190.webp', 'avf0200.webp',
    'avf0210.webp', 'avf0220.webp', 'avf0230.webp',
    'avf0700.webp', 'avf1220.webp', 'avf9999.webp',
}

AVAILABLE_NOTES = {
    'note_chr000.webp', 'note_chr001.webp', 'note_chr002.webp',
    'note_chr003.webp', 'note_chr004.webp', 'note_chr005.webp',
    'note_chr006.webp', 'note_chr007.webp', 'note_chr008.webp',
    'note_chr009.webp', 'note_chr010.webp', 'note_chr011.webp',
    'note_chr012.webp', 'note_chr013.webp', 'note_chr014.webp',
    'note_chr015.webp', 'note_chr016.webp', 'note_chr017.webp',
    'note_chr018.webp', 'note_chr023.webp', 'note_chr030.webp',
    'note_chr047.webp', 'note_chr080.webp', 'note_chr081.webp',
    'note_chr082.webp', 'note_chr083.webp', 'note_chr084.webp',
    'note_chr085.webp', 'note_chr086.webp', 'note_chr087.webp',
    'note_chr088.webp', 'note_chr089.webp', 'note_chr090.webp',
    'note_chr091.webp', 'note_chr092.webp', 'note_chr093.webp',
    'note_chr094.webp', 'note_chr095.webp', 'note_chr096.webp',
    'note_chr097.webp', 'note_chr098.webp', 'note_chr099.webp',
    'note_chr100.webp', 'note_chr101.webp', 'note_chr102.webp',
    'note_chr103.webp', 'note_chr104.webp', 'note_chr105.webp',
    'note_chr106.webp', 'note_chr107.webp', 'note_chr108.webp',
    'note_chr109.webp', 'note_chr110.webp', 'note_chr111.webp',
    'note_chr112.webp', 'note_chr113.webp', 'note_chr114.webp',
    'note_chr115.webp', 'note_chr116.webp', 'note_chr117.webp',
    'note_chr118.webp', 'note_chr119.webp', 'note_chr120.webp',
    'note_chr121.webp', 'note_chr122.webp', 'note_chr125.webp',
}

CONTROL_CODE_RE = re.compile(r'#OT|#[A-Za-z](?:_[0-9A-Za-z]|\[[A-Za-z0-9]+\]|[0-9])?')
LEFTOVER_CODE_RE = re.compile(r'#\d+[A-Za-z]?')
# Bracket-only control tokens that survive CONTROL_CODE_RE because they
# lack the `#` prefix. Preserves quest/skill names like `[Wandering Sheep]`,
# `[Slash]`, `[CRITICAL]`, full-width labels like `[ＮＯＴＥ]`.
JUNK_BRACKET_SUBS = [
    re.compile(r'\[auto[A-Z][A-Z0-9]{0,3}\]'),     # [autoM0] [autoMA] [autoE8] [autoB0]
    re.compile(r'\[CHR_[A-Z_]+\]'),                # [CHR_FLAG_NOATARI]
    re.compile(r'\[\d+(?:_\d+)+\]'),               # [04_32_05]
    re.compile(r'\[[\d,]+\]'),                     # [1] [28] [1,111,2,222,3,333]
    re.compile(r'\[[A-Z]\d{1,5}\]'),               # [J232] [E4] [A3]
    re.compile(r'\[\d+[A-Za-z][A-Za-z0-9]*\]'),    # [9K] [3F] [1LK] [76E] [100s]
    re.compile(r'\[[A-Z]{1,3}\]'),                 # [J] [K] [BK] [KL] [PM] [ST]
    re.compile(r'\[[A-Z]+,\]'),                    # [N,]
    re.compile(r'\[\?+\]'),                        # [???]
    re.compile(r'\[([A-Z0-9])\1{3,}[A-Z0-9]*\]'),  # [HHHH] [88888888] [KKKKK5] [111111118]
    re.compile(r'\[\]'),                           # empty brackets
]
LEADING_DIGITS_RE = re.compile(r'^\d+')
WHITESPACE_RE = re.compile(r'[ \t]+')
# Ruby (furigana) markup: `蒼の歌姫#4Rディーヴァ#` — digit before R says
# how many preceding characters get the reading; bare `#` closes.
RUBY_RE = re.compile(r'#(\d*)R([^#]*)#')

NS = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
NS_URI = NS['a']
TAG_SI = f'{{{NS_URI}}}si'
TAG_T = f'{{{NS_URI}}}t'
TAG_SHEETDATA = f'{{{NS_URI}}}sheetData'
TAG_ROW = f'{{{NS_URI}}}row'
TAG_C = f'{{{NS_URI}}}c'
TAG_V = f'{{{NS_URI}}}v'


def is_animation_trigger(parts):
    """Same heuristic as 9D-sen4 — text consisting of literal animation
    engine tokens isn't real dialogue."""
    text = ''.join(parts)
    if not text:
        return True
    if '\\n' in text:
        return True
    if 'WK_TEMP' in text or 'AniEv' in text or 'ChrSet' in text:
        return True
    return False


def _cell_val(c, strs):
    t = c.get('t')
    v = None
    for child in c:
        if child.tag == TAG_V:
            v = child
            break
    if v is None or v.text is None:
        return ''
    if t == 's':
        return strs[int(v.text)]
    return v.text


def _xlsx_rows(path):
    """Yield rows from sheet1 as lists of strings. Read both XML payloads
    fully into memory and iterate directly over the parsed tree (no
    ET.findall path expressions — those exhibit a 'generator already
    executing' bug under Python 3.13 when nested across two trees)."""
    with zipfile.ZipFile(path) as z:
        try:
            ss_xml = z.read('xl/sharedStrings.xml')
        except KeyError:
            ss_xml = b''
        sheet_xml = z.read('xl/worksheets/sheet1.xml')

    strs = []
    if ss_xml:
        ss_root = ET.fromstring(ss_xml)
        for si in ss_root:
            if si.tag != TAG_SI:
                continue
            buf = []
            for el in si.iter(TAG_T):
                if el.text:
                    buf.append(el.text)
            strs.append(''.join(buf))

    root = ET.fromstring(sheet_xml)
    sheet_data = None
    for child in root:
        if child.tag == TAG_SHEETDATA:
            sheet_data = child
            break
    if sheet_data is None:
        return
    rows_out = []
    for r in sheet_data:
        if r.tag != TAG_ROW:
            continue
        rows_out.append([_cell_val(c, strs) for c in r if c.tag == TAG_C])
    for row in rows_out:
        yield row


def _strip_trailing_garbage(s):
    """The XLSX export sometimes truncates strings with a trailing 0xFFFD
    (Unicode replacement char) where the original had a non-UTF-8 byte.
    Drop those for cleaner names."""
    return s.rstrip('�').rstrip('\x00').strip()


def _xlsx_segments(cells, header, want_chrid):
    """Walk an op-26/op-24 row's cells in order, segmenting by paragraph.

    CS2 op 26 schema (per paragraph):
      [byte=17, int=voice_id,] dialog [, byte=2 (Enter), byte=2|3 (continue|Clear)]

    A `byte=17` (0x11 — voice opcode) flags the next `int` cell as a
    voice id. A `byte=3` (TxtCtl.Clear) flushes the current paragraph;
    subsequent dialog starts a new paragraph (with no voice unless
    another byte=17/int pair appears).

    Returns {'chrid': int|None (first 'short' cell when want_chrid),
             'segments': [(voice_id_or_None, [text_parts]), ...]}
    """
    chrid = None
    segments = []
    cur_voice = None
    cur_parts = []
    expect_voice_int = False

    def flush():
        if cur_parts or cur_voice is not None:
            segments.append((cur_voice, list(cur_parts)))

    for i in range(2, len(cells)):
        if i >= len(header):
            break
        htype = header[i]
        val = cells[i]
        if htype == 'short' and want_chrid and chrid is None:
            try:
                chrid = int(val)
            except ValueError:
                pass
            continue
        if htype == 'byte':
            if val == '17':
                # Next 'int' is a voice id — start a new paragraph.
                flush()
                cur_voice = None
                cur_parts = []
                expect_voice_int = True
            elif val == '3':
                # End of paragraph.
                flush()
                cur_voice = None
                cur_parts = []
                expect_voice_int = False
            # byte=2 (Enter), byte=0 (end) ignored.
            continue
        if htype == 'int':
            if expect_voice_int:
                try:
                    v = int(val)
                    if v:
                        cur_voice = v
                except ValueError:
                    pass
                expect_voice_int = False
            continue
        if htype == 'dialog':
            if val:
                cur_parts.append(val)
            continue
    flush()
    segments = [(v, p) for v, p in segments if p or v is not None]
    return {'chrid': chrid, 'segments': segments}


def parse_xlsx(path, name2_to_chrid):
    """Walk one CS2 XLSX file. Returns dialogue tuples in the shape:
        (scene_idx, char, parts, kind, override, voice, segments)
    where segments is a list of (voice_id_or_None, [text_parts]) per
    paragraph. CS2's op 26 carries voice IDs in `byte=17 + int=voice`
    cell pairs (same as CS1) — voiced rows have an 8-cell header,
    unvoiced rows have a 6-cell header.

    name2_to_chrid is the global name2 -> chr_id map for the TK_<name>
    function-name fallback when ChrTalk uses 0xFFFD/E/F.
    """
    dialogues = []
    scene_idx = -1
    header = None
    pending_anon = ''
    latched = {}
    current_func = ''

    for cells in _xlsx_rows(path):
        if not cells:
            continue
        first = cells[0]
        if first == 'FUNCTION':
            scene_idx += 1
            latched = {}
            pending_anon = ''
            header = None
            current_func = cells[1] if len(cells) > 1 else ''
            continue
        if first == 'Location':
            header = cells
            continue
        if header is None or len(cells) < 2 or not first.isdigit() or not cells[1].isdigit():
            continue
        op = int(cells[1])

        if op == 26:  # ChrTalk
            seg_info = _xlsx_segments(cells, header, want_chrid=True)
            char_id = seg_info['chrid']
            seg_list = seg_info['segments']
            parts = [s for _, ps in seg_list for s in ps]
            if not parts:
                continue
            if is_animation_trigger(parts):
                pending_anon = ''
                continue
            voice = next((v for v, _ in seg_list if v is not None), None)
            # Function-name fallback: 0xFFFD/E/F (the "use enclosing
            # context" markers) in a TK_<name2> function means "use that
            # name's chr_id".
            if char_id in (0xFFFD, 0xFFFE, 0xFFFF) and current_func.startswith('TK_'):
                n2 = current_func[3:].lower()
                resolved = name2_to_chrid.get(n2)
                if resolved is not None:
                    char_id = resolved
            override = pending_anon
            if not override and char_id is not None:
                override = latched.get(char_id, '')
            pending_anon = ''
            char = ('id', char_id) if char_id is not None else None
            dialogues.append((scene_idx, char, parts, 'chr', override, voice, seg_list))

        elif op == 24:  # AnonymousTalk
            seg_info = _xlsx_segments(cells, header, want_chrid=False)
            seg_list = seg_info['segments']
            parts = [s for _, ps in seg_list for s in ps]
            if not parts:
                continue
            if is_animation_trigger(parts):
                pending_anon = ''
                continue
            voice = next((v for v, _ in seg_list if v is not None), None)
            override = pending_anon
            pending_anon = ''
            dialogues.append((scene_idx, None, parts, 'anon', override, voice, seg_list))

        elif op == 29:  # SetChrName
            name = ''
            target_id = None
            for i in range(2, len(cells)):
                if i >= len(header):
                    break
                htype = header[i]
                if htype == 'string' and not name:
                    name = _strip_trailing_garbage(cells[i])
                elif htype == 'short' and target_id is None:
                    try:
                        target_id = int(cells[i])
                    except ValueError:
                        pass
            if not name:
                continue
            if target_id in (0xFFFF, 0xFFFE, 0xFFFD):
                pending_anon = name
            elif target_id is not None:
                latched[target_id] = name

    # Drop adjacent voiced duplicates (same logic as 9D-sen4). Voice is
    # currently None for everything so this no-ops, but keep the block
    # so it activates once voice extraction is added.
    deduped = []
    prev_sig = None
    prev_voiced = False
    for d in dialogues:
        scene, char, parts, dkind, override, voice, _segs = d
        is_voiced = voice is not None
        if char is not None and parts and is_voiced:
            sig = (scene, char, tuple(parts), dkind)
            if sig == prev_sig and prev_voiced:
                continue
            prev_sig = sig
            prev_voiced = True
        else:
            prev_sig = None
            prev_voiced = False
        deduped.append(d)
    return deduped


def normalize_name(raw):
    if not raw:
        return ''
    return LEADING_DIGITS_RE.sub('', raw).strip()


def load_tname_from_sqlite(db_path):
    """Returns dict chr_id -> {'name', 'model', 'faceTexture', 'name2'}.
    First entry per chr_id wins. Source: NameTableData rows from
    t_name.tbl; column 5 (`unknown_string_5`) is the name2 key (e.g.
    'rean', 'alisa') used for tk_<name2>.xlsx fallback."""
    c = sqlite3.connect(db_path)
    cur = c.execute(
        "SELECT character, name, model, unknown_string_3, unknown_string_5 "
        "FROM NameTableData WHERE file = 't_name.tbl'"
    )
    out = {}
    for chr_id, name, model, face_tex, name2 in cur:
        if chr_id is None or chr_id in out:
            continue
        out[chr_id] = {
            'name': name or '',
            'model': model or '',
            'faceTexture': face_tex or '',
            'name2': name2 or '',
        }
    c.close()
    return out


def load_tvoice_from_sqlite(db_path):
    """Returns dict voice_id -> clip filename stem (no .opus extension)."""
    c = sqlite3.connect(db_path)
    cur = c.execute("SELECT id, clip FROM voice")
    out = {}
    for vid, clip in cur:
        if vid is None or not clip:
            continue
        out.setdefault(vid, clip)
    c.close()
    return out


def voice_wrap(html_text, voice_file):
    return (
        f'<a href="javascript:void(0)" class="dialogue-line" '
        f'data-audio="talk/{GAME_ID}/{voice_file}.ogg">'
        f'{html_text}</a>'
    )


def render_html_segments(segments, tvoice=None):
    """Render (voice_id, [parts]) segments into HTML. Each paragraph
    is independently voice-wrapped (when `tvoice` is given and the
    segment has a voice id), then joined with `<br/><br/>` to mirror
    the original paragraph breaks."""
    pieces = []
    for vid, parts in segments:
        text = clean_text(parts, '<br/>')
        if not text:
            continue
        if tvoice is not None and vid is not None:
            vfile = tvoice.get(vid)
            if vfile:
                text = voice_wrap(text, vfile)
        pieces.append(text)
    return '<br/><br/>'.join(pieces)


def render_search_segments(segments):
    """Plain-text version: paragraphs joined with a single space so
    'Sentence one.' and 'Sentence two.' don't get glued together."""
    pieces = []
    for _vid, parts in segments:
        text = clean_text(parts, ' ')
        if text:
            pieces.append(text)
    return ' '.join(pieces)


def portrait_from_chrid(chrid):
    """CS2 portraits use the chr_id * 10 scheme but prefer the `_1`
    variant where it exists — for the original Class VII (chr_ids 0-9)
    those are the timeskip outfits worn through CS2. For everyone else
    only the base variant ships, so we fall back to chr_id * 10.
    Rean (0) -> avf0001, Alisa (1) -> avf0011, Sara (11) -> avf0110."""
    if chrid is None:
        return None
    variant = f'avf{chrid * 10 + 1:04d}.webp'
    if variant in AVAILABLE_PORTRAITS:
        return variant
    base = f'avf{chrid * 10:04d}.webp'
    return base if base in AVAILABLE_PORTRAITS else None


def note_from_chrid(chrid):
    """CS2 note icons are keyed by chr_id (Patrick chrId 30 -> note_chr030,
    Vivi chrId 108 -> note_chr108) — NOT by the trailing number in the
    model name (Vivi's model is C_NPC188 but her note is note_chr108).
    Synthetic chr_ids assigned to outfit-variant entries (chr_id < 0)
    skip the lookup."""
    if chrid is None or chrid < 0 or chrid >= 1000:
        return None
    pf = f'note_chr{chrid:03d}.webp'
    return pf if pf in AVAILABLE_NOTES else None


def _ruby_base_start(text, end_pos, byte_count):
    """Walk backward from `end_pos` consuming Shift-JIS bytes until we
    hit `byte_count`. CS-era ruby `#NR...#` encodes N as the byte length
    of the preceding text in Shift-JIS (each Japanese char = 2 bytes)."""
    consumed = 0
    i = end_pos
    while i > 0 and consumed < byte_count:
        ch = text[i - 1]
        try:
            consumed += len(ch.encode('cp932'))
        except UnicodeEncodeError:
            consumed += 2
        i -= 1
    return i


def _apply_ruby(text, html):
    """Resolve `<base>#NR<reading>#` ruby markup. For HTML output, wrap
    base+reading in `<ruby>` tags. For plain text, drop the marker — the
    base remains because it's written before the marker."""
    while True:
        m = RUBY_RE.search(text)
        if not m:
            return text
        # Empty digit count (`#R<reading>#`) appears rarely and isn't true
        # ruby — treat as count=0 so both markers + reading are dropped.
        count = int(m.group(1)) if m.group(1) else 0
        reading = m.group(2)
        if count == 0:
            text = text[:m.start()] + text[m.end():]
            continue
        base_start = _ruby_base_start(text, m.start(), count)
        if html and reading:
            base = text[base_start:m.start()]
            repl = f'<ruby>{base}<rt>{reading}</rt></ruby>'
            text = text[:base_start] + repl + text[m.end():]
        else:
            text = text[:m.start()] + text[m.end():]


def strip_junk_brackets(text):
    """Iteratively strip bracket-only control tokens (loop handles nested
    forms like `[HHHH[autoM0]]` and `[8[autoE8]]` — first pass removes the
    inner `[autoXX]`, leaving `[HHHH]`/`[8]` for the next pass)."""
    prev = None
    while prev != text:
        prev = text
        for pat in JUNK_BRACKET_SUBS:
            text = pat.sub('', text)
    return text


def clean_text(parts, newline):
    text = ''.join(parts)
    text = _apply_ruby(text, html=(newline == '<br/>'))
    text = CONTROL_CODE_RE.sub('', text)
    text = LEFTOVER_CODE_RE.sub('', text)
    text = strip_junk_brackets(text)
    # Stray `#` chars (separators between codes, ruby closers without a
    # paired opener) survive both regexes — drop them.
    text = text.replace('#', '')
    text = text.replace('\n', newline)
    if newline == ' ':
        text = WHITESPACE_RE.sub(' ', text)
    # Decompiler mismaps Shift-JIS NEC `♥` (0x87 0x9D) onto `㈱`
    # (0x87 0x9F) — both bytes are CP932 NEC special chars and the
    # lookup is off by one. Patch back here before emit.
    text = text.replace('㈱', '♥')
    return text.strip()


def collect_files(*parts):
    """List .xlsx files under SCRIPTS_ROOT/<parts...>, returning
    {stem: full_path}."""
    d = os.path.join(SCRIPTS_ROOT, *parts)
    if not os.path.isdir(d):
        return {}
    return {
        entry[:-5]: os.path.join(d, entry)
        for entry in os.listdir(d)
        if entry.endswith('.xlsx')
        and ' ' not in entry
        and entry[:-5] not in SKIP_STEMS
    }


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def _voice_prefix(filename):
    if not filename:
        return ''
    us = filename.find('_')
    return filename[:us] if us > 0 else filename


def build_chr_alias(parsed_files, jp_tname, tvoice):
    """Same shape as 9D-sen4 — learns voice_prefix -> chr_id from voiced
    dialogues whose chr_id is in t_name. CS2 voice extraction isn't wired
    yet so this map will be empty until that's added; harmless."""
    from collections import Counter
    prefix_known = {}
    for parsed in parsed_files:
        for d in parsed:
            scene, char, parts, dkind, override, voice, _segs = d
            if voice is None or char is None:
                continue
            if char[0] != 'id':
                continue
            cid = char[1]
            if cid not in jp_tname:
                continue
            fn = tvoice.get(voice) or ''
            prefix = _voice_prefix(fn)
            if not prefix:
                continue
            prefix_known.setdefault(prefix, Counter())[cid] += 1
    return {p: cnt.most_common(1)[0][0] for p, cnt in prefix_known.items()}


def _lcs_pairs(a, b):
    def sig(d):
        return (d[0], d[3], d[1])
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n):
        ai = sig(a[i])
        for j in range(m):
            if ai == sig(b[j]):
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])
    out = []
    i, j = n, m
    while i > 0 and j > 0:
        if sig(a[i - 1]) == sig(b[j - 1]):
            out.append((a[i - 1], b[j - 1]))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            out.append((a[i - 1], None))
            i -= 1
        else:
            out.append((None, b[j - 1]))
            j -= 1
    while i > 0:
        out.append((a[i - 1], None))
        i -= 1
    while j > 0:
        out.append((None, b[j - 1]))
        j -= 1
    out.reverse()
    return out


def align_scenes(en_d, jp_d):
    en_by = {}
    jp_by = {}
    for d in en_d:
        en_by.setdefault(d[0], []).append(d)
    for d in jp_d:
        jp_by.setdefault(d[0], []).append(d)
    aligned = []
    for scene in sorted(set(en_by) | set(jp_by)):
        aligned.extend(_lcs_pairs(en_by.get(scene, []), jp_by.get(scene, [])))
    return aligned


def load_active_voice(db_path):
    """ActiveVoiceTableData rows in table order, as
    (group, row, line, portrait, voice_id, chr_id, text)."""
    c = sqlite3.connect(db_path)
    cur = c.execute(
        "SELECT unknown_short_1, unknown_short_2, unknown_short_3, portrait, id, character, text "
        "FROM ActiveVoiceTableData ORDER BY rowid"
    )
    out = cur.fetchall()
    c.close()
    return out


def active_voice_exchanges():
    """Pair EN/JP active voice rows and group them into exchanges.

    The table lists each exchange as (group, row, line) entries. A row --
    one voiced line -- can be listed under several groups (the same
    banter triggered from different spots) or twice in one, so each row
    is emitted once, in the first exchange that plays it. Exchanges keep
    the table's order, which follows the story; group numbers don't.
    `◆` / `◆st` / `◆end` rows are markers with no text."""
    en = load_active_voice(EN_ACTIVE)
    jp = load_active_voice(JP_ACTIVE)
    assert [r[:6] for r in en] == [r[:6] for r in jp], 'EN/JP active voice tables differ'
    groups = {}
    for e, j in zip(en, jp):
        groups.setdefault(e[0], []).append((e, j))
    exchanges = []
    seen = set()
    for entries in groups.values():
        exchange = []
        for e, j in sorted(entries, key=lambda p: p[0][2]):
            if e[1] in seen or e[6].startswith('◆'):
                continue
            seen.add(e[1])
            exchange.append((e, j))
        if exchange:
            exchanges.append(exchange)
    return exchanges


def main():
    en_scena = collect_files('scena', 'dat_us')
    jp_scena = collect_files('scena', 'dat')
    en_talk = collect_files('talk', 'dat_us')
    jp_talk = collect_files('talk', 'dat')
    print(f'files  EN scena={len(en_scena)}  JP scena={len(jp_scena)}  '
          f'EN talk={len(en_talk)}  JP talk={len(jp_talk)}')

    en_tname = load_tname_from_sqlite(EN_SQLITE)
    jp_tname = load_tname_from_sqlite(JP_SQLITE)
    tvoice = load_tvoice_from_sqlite(JP_SQLITE)
    print(f't_voice  entries={len(tvoice)}')
    name2_to_chrid = {}
    for cid, e in jp_tname.items():
        n2 = e.get('name2')
        if n2 and n2 not in name2_to_chrid:
            name2_to_chrid[n2] = cid
    # Reverse map display-name -> chr_id for both languages. Used to
    # recover an icon when the speaker came from an OP_27 override (the
    # original chr_id may be a placeholder like 0xFFFD that doesn't
    # resolve, but the override name does match a t_name entry).
    name_to_chrid = {}
    for tname in (jp_tname, en_tname):
        for cid, e in tname.items():
            n = e.get('name', '')
            if n:
                name_to_chrid.setdefault(n, cid)
    print(f'en t_name={len(en_tname)}  jp t_name={len(jp_tname)}  '
          f'name2={len(name2_to_chrid)}  name_idx={len(name_to_chrid)}')

    cache = {}

    def get(path):
        if path is None:
            return []
        hit = cache.get(path)
        if hit is None:
            try:
                hit = parse_xlsx(path, name2_to_chrid)
            except Exception as e:
                print(f'WARN: failed to parse {path}: {e}', file=sys.stderr)
                hit = []
            cache[path] = hit
        return hit

    # Voice-prefix bridge — placeholder until voice extraction is added.
    all_jp_dialogues = []
    for path in list(jp_scena.values()) + list(jp_talk.values()):
        all_jp_dialogues.append(get(path))
    voice_prefix_to_known = build_chr_alias(all_jp_dialogues, jp_tname, tvoice)
    print(f'voice prefix -> chr_id map: {len(voice_prefix_to_known)} entries')

    def resolve_via_voice(voice_id, side_tname):
        if voice_id is None:
            return ''
        prefix = _voice_prefix(tvoice.get(voice_id, ''))
        if not prefix:
            return ''
        cid = voice_prefix_to_known.get(prefix)
        if cid is None or cid not in side_tname:
            return ''
        return side_tname[cid].get('name', '')

    def resolve_chrid(char, talk_fallback_chrid=None):
        if char is None:
            return None
        if char[0] == 'id':
            cid = char[1]
            if cid in jp_tname or cid in en_tname:
                return cid
            return talk_fallback_chrid
        return None

    def talk_fallback(stem):
        if not stem.startswith('tk_'):
            return None
        return name2_to_chrid.get(stem[3:])

    def speaker_name(char, override, side_tname, talk_fb, voice_id=None):
        if override:
            return override
        chrid = resolve_chrid(char, talk_fb)
        if chrid is not None and chrid in side_tname:
            return side_tname[chrid]['name']
        return resolve_via_voice(voice_id, side_tname)

    def candidate_chrids(char, override, side_speaker, talk_fb, voice_id=None):
        """Yield chr_ids worth trying for portrait/note lookup, in order:
        the resolved char chr_id, then the chr_id matching the OP_27
        override, then the chr_id matching the resolved speaker name,
        then voice-prefix bridge. Some characters have multiple t_name
        entries (e.g. Celine has chr_ids 122 and 7032) — only one of
        which has a portrait; trying name-based lookup as a fallback
        recovers the right one."""
        seen = set()
        chrid = resolve_chrid(char, talk_fb)
        if chrid is not None and chrid not in seen:
            seen.add(chrid); yield chrid
        for nm in (override, side_speaker):
            if nm:
                cid = name_to_chrid.get(nm)
                if cid is not None and cid not in seen:
                    seen.add(cid); yield cid
        if voice_id is not None:
            prefix = _voice_prefix(tvoice.get(voice_id, ''))
            cid = voice_prefix_to_known.get(prefix)
            if cid is not None and cid not in seen:
                seen.add(cid); yield cid

    def row_portrait(char, override, side_speaker, talk_fb, voice_id=None):
        for cid in candidate_chrids(char, override, side_speaker, talk_fb, voice_id):
            pf = portrait_from_chrid(cid)
            if pf:
                return pf
        return None

    def row_note(char, override, side_speaker, talk_fb, voice_id=None):
        for cid in candidate_chrids(char, override, side_speaker, talk_fb, voice_id):
            nf = note_from_chrid(cid)
            if nf:
                return nf
        return None

    rows = []
    for kind, en_map, jp_map in (('scena', en_scena, jp_scena),
                                  ('talk', en_talk, jp_talk)):
        stems = sorted(set(en_map) | set(jp_map))
        for stem in stems:
            rownum = 1
            en_d = get(en_map.get(stem))
            jp_d = get(jp_map.get(stem))
            talk_fb = talk_fallback(stem) if kind == 'talk' else None

            pairs = align_scenes(en_d, jp_d)
            unpaired = sum(1 for e, j in pairs if e is None or j is None)
            if unpaired:
                print(f'WARN {kind}/{stem}: {unpaired} unpaired rows '
                      f'(EN={len(en_d)} JP={len(jp_d)})', file=sys.stderr)

            for en_t, jp_t in pairs:
                if en_t:
                    en_scene, en_char, en_parts, _, en_override, en_voice, en_segs = en_t
                else:
                    en_scene, en_char, en_parts, en_override, en_voice, en_segs = None, None, [], '', None, []
                if jp_t:
                    jp_scene, jp_char, jp_parts, _, jp_override, jp_voice, jp_segs = jp_t
                else:
                    jp_scene, jp_char, jp_parts, jp_override, jp_voice, jp_segs = None, None, [], '', None, []
                scene = jp_scene if jp_scene is not None else (en_scene if en_scene is not None else 0)

                # JP-only voice: EN audio files don't ship for CS2, so
                # never fall back to en_voice for voice-prefix lookup or
                # html wrapping.
                vid = jp_voice
                en_raw = speaker_name(en_char, en_override, en_tname, talk_fb, voice_id=vid)
                jp_raw = speaker_name(jp_char, jp_override, jp_tname, talk_fb, voice_id=vid)
                if en_t and jp_t:
                    if not en_raw and jp_char:
                        en_raw = speaker_name(jp_char, '', en_tname, talk_fb, voice_id=vid)
                    if not jp_raw and en_char:
                        jp_raw = speaker_name(en_char, '', jp_tname, talk_fb, voice_id=vid)
                eng_chr = normalize_name(en_raw)
                jpn_chr = normalize_name(jp_raw)

                # Pass override + resolved speaker name (JP first, then
                # EN) so the portrait can recover from speaker-name match
                # when the chr_id either is a placeholder (0xFFFD etc.)
                # or maps to a t_name entry without a shipped portrait.
                ovr = jp_override or en_override
                pfile = (row_portrait(jp_char, ovr, jp_raw, talk_fb, voice_id=vid)
                         or row_portrait(en_char, ovr, en_raw, talk_fb, voice_id=vid))
                if pfile:
                    pc_icon = f'<img class="itp-face" src="itp/{GAME_ID}/{pfile}"/>'
                else:
                    nfile = (row_note(jp_char, ovr, jp_raw, talk_fb, voice_id=vid)
                             or row_note(en_char, ovr, en_raw, talk_fb, voice_id=vid))
                    pc_icon = f'<img class="itp-note" src="itp/{GAME_ID}/{nfile}"/>' if nfile else ''

                en_search = render_search_segments(en_segs) if en_segs else clean_text(en_parts, ' ')
                en_html = render_html_segments(en_segs) if en_segs else clean_text(en_parts, '<br/>')
                jp_search = render_search_segments(jp_segs) if jp_segs else clean_text(jp_parts, ' ')
                jp_html = render_html_segments(jp_segs, tvoice) if jp_segs else clean_text(jp_parts, '<br/>')

                rows.append([
                    str(GAME_ID), stem, str(scene), str(rownum),
                    eng_chr,
                    en_search,
                    en_html,
                    jpn_chr,
                    jp_search,
                    jp_html,
                    '', pc_icon,
                ])
                rownum += 1
        print(f'done {kind}  rows={len(rows)}')

    # Active voice: one exchange per scene. The row's own portrait
    # (I_AVF0011 -> avf0011.webp) is what the game shows beside the line.
    rownum = 1
    for scene, exchange in enumerate(active_voice_exchanges(), start=1):
        for en_av, jp_av in exchange:
            _, _, _, portrait, vid, cid, en_text = en_av
            jp_text = jp_av[6]
            # chr_id < 0 is a group line ('Right!'), not a speaker; t_name's
            # negative keys are the synthetic outfit-variant ids.
            if cid < 0:
                cid = None
            char = ('id', cid)
            eng_chr = normalize_name(en_tname.get(cid, {}).get('name', ''))
            jpn_chr = normalize_name(jp_tname.get(cid, {}).get('name', ''))
            jp_html = clean_text([jp_text], '<br/>')
            vfile = tvoice.get(vid)
            if vfile:
                jp_html = voice_wrap(jp_html, vfile)
            pfile = portrait[len('I_'):].lower() + '.webp'
            if pfile not in AVAILABLE_PORTRAITS:
                pfile = row_portrait(char, '', '', None)
            if pfile:
                pc_icon = f'<img class="itp-face" src="itp/{GAME_ID}/{pfile}"/>'
            else:
                nfile = row_note(char, '', '', None)
                pc_icon = f'<img class="itp-note" src="itp/{GAME_ID}/{nfile}"/>' if nfile else ''
            rows.append([
                str(GAME_ID), ACTIVE_VOICE_FNAME, str(scene), str(rownum),
                eng_chr,
                clean_text([en_text], ' '),
                clean_text([en_text], '<br/>'),
                jpn_chr,
                clean_text([jp_text], ' '),
                jp_html,
                '', pc_icon,
            ])
            rownum += 1
    print(f'done active voice  rows={rownum - 1}')

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(f'delete from script where game_id = {GAME_ID};\n')
        for row in rows:
            f.write('insert into script (game_id, fname, scene, row, eng_chr_name, eng_search_text, '
                    'eng_html_text, jpn_chr_name, jpn_search_text, jpn_html_text, op_name, pc_icon_html) values\n')
            f.write("('%s');\n" % "','".join(sql_escape(c) for c in row))

    print(f'TOTAL = {len(rows)}')


if __name__ == '__main__':
    main()
