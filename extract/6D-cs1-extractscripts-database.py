"""Extract Trails of Cold Steel (game 6) dialogue into sen1.sql.

Decompiled-source variant of the original 6-cs1 extractor. CS1 uses
the same XLSX + SQLite decompile format as CS2, so this lifts most of
7D-cs2-extractscripts-database.py wholesale.

Differences from CS2:
- CS1 NameTableData has 8 columns (CS2 had 10). model lives in
  unknown_string_1, faceTexture in unknown_string_4, and there is no
  name2 field. Talk-file fallback lowercases the EN-side display name.
- CS1 portraits have no costume variants — simple
  avf{chrId * 10:04d}.webp lookup, no _1 / _c10 logic.
- CS1 portraits use `itp-face` / `itp-note` CSS classes (no `3` suffix).
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
DATA_ROOT = os.path.join(FALCOM_ROOT, 'data', 'cs1')
SCRIPTS_ROOT = os.path.join(DATA_ROOT, 'scripts')
JP_SQLITE = os.path.join(DATA_ROOT, 'cs1_jp.sqlite')
EN_SQLITE = os.path.join(DATA_ROOT, 'cs1_en.sqlite')
GAME_ID = 6
OUTPUT = 'sen1.sql'

SKIP_STEMS = set()

# Portrait sprites shipped at itp/6/{file}. Snapshot of
# Ingert/data/cs1/. avf{chrId * 10:04d}.webp — no costume variants in CS1.
AVAILABLE_PORTRAITS = {
    'avf0000.webp', 'avf0010.webp', 'avf0020.webp', 'avf0030.webp',
    'avf0040.webp', 'avf0050.webp', 'avf0060.webp', 'avf0070.webp',
    'avf0080.webp', 'avf0090.webp', 'avf0095.webp',
    'avf0100.webp', 'avf0110.webp', 'avf0119.webp', 'avf0120.webp',
    'avf0530.webp', 'avf0990.webp', 'avf1000.webp', 'avf1010.webp',
}

AVAILABLE_NOTES = {
    'note_chr000.webp', 'note_chr001.webp', 'note_chr002.webp',
    'note_chr003.webp', 'note_chr004.webp', 'note_chr005.webp',
    'note_chr006.webp', 'note_chr007.webp', 'note_chr008.webp',
    'note_chr009.webp', 'note_chr010.webp', 'note_chr011.webp',
    'note_chr012.webp',
    'note_chr052.webp', 'note_chr053.webp', 'note_chr056.webp',
    'note_chr057.webp', 'note_chr058.webp', 'note_chr059.webp',
    'note_chr060.webp', 'note_chr061.webp', 'note_chr062.webp',
    'note_chr063.webp', 'note_chr064.webp', 'note_chr065.webp',
    'note_chr066.webp', 'note_chr067.webp', 'note_chr068.webp',
    'note_chr069.webp', 'note_chr070.webp', 'note_chr071.webp',
    'note_chr072.webp', 'note_chr073.webp', 'note_chr074.webp',
    'note_chr075.webp', 'note_chr076.webp', 'note_chr077.webp',
    'note_chr078.webp', 'note_chr079.webp', 'note_chr080.webp',
    'note_chr081.webp', 'note_chr082.webp', 'note_chr083.webp',
    'note_chr084.webp', 'note_chr085.webp', 'note_chr086.webp',
    'note_chr087.webp', 'note_chr088.webp', 'note_chr089.webp',
    'note_chr090.webp', 'note_chr091.webp', 'note_chr092.webp',
    'note_chr093.webp', 'note_chr094.webp', 'note_chr095.webp',
    'note_chr096.webp', 'note_chr097.webp', 'note_chr098.webp',
    'note_chr102.webp', 'note_chr127.webp',
}

# Three-letter codes (#MA, #EI, etc.) must come before the single-letter
# alternative or the regex strips just `#M`/`#E` and orphans the trailing
# uppercase letter into the rendered text.
CONTROL_CODE_RE = re.compile(
    r'#(?:MA|MB|EE|EF|EH|EI|EJ)'
    r'|#[A-Za-z](?:_[0-9A-Fa-f]|\[[A-Za-z0-9]+\]|[0-9])?'
)
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
# Ruby (furigana) markup: `蒼の歌姫#4Rディーヴァ#` — the digit before R says
# how many of the preceding characters get the reading; bare `#` closes.
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

    CS1 op 26 schema (per paragraph):
      [byte=17, int=voice_id,] dialog [, byte=2 (Enter), byte=2|3 (continue|Clear)]

    A `byte` cell with value 17 (0x11) flags the next `int` cell as a
    voice id. A `byte` cell with value 3 (TxtCtl.Clear) flushes the
    current paragraph; subsequent dialog starts a new paragraph (with
    no voice unless another byte=17/int pair appears).

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
    """Walk one CS1 XLSX file. Returns (dialogues, local_npcs) where
    dialogues is the list of dialogue tuples (same shape as 9D-sen4
    parse_script: (scene_idx, char, parts, kind, override, voice))
    and local_npcs is dict[chr_id -> {'name', 'model'}] populated from
    op-19 NPC declarations in this scena.

    CS1 t_name only carries main-cast chr_ids; named NPCs (Arseid,
    Towa, George, etc.) are bound per-scena via op 19 (the same
    `\\x13` structure the binary parser used to regex-scan).

    name2_to_chrid is the global name2 -> chr_id dict, used for the
    TK_<name> function-name fallback when ChrTalk uses the special
    char_id 0xFFFE / 0xFFFF.

    Voice extraction is not yet wired; voice will be None.
    """
    dialogues = []
    local_npcs = {}
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

        if op == 19:  # CreateChr — declares a scena-local NPC
            chr_id = None
            model = ''
            name = ''
            cell_strings = []
            for i in range(2, len(cells)):
                if i >= len(header):
                    break
                htype = header[i]
                if htype == 'short' and chr_id is None:
                    try:
                        chr_id = int(cells[i])
                    except ValueError:
                        pass
                elif htype == 'string':
                    cell_strings.append(_strip_trailing_garbage(cells[i]))
            # cell_strings[0] = model (e.g. 'C_NPC027'),
            # cell_strings[1] = display name (e.g. 'Arseid'),
            # later strings include TK_<func> references.
            if cell_strings:
                model = cell_strings[0]
            if len(cell_strings) >= 2:
                name = cell_strings[1]
            if chr_id is not None and chr_id < 0xF000 and (name or model):
                # Only take the first declaration per chr_id within a file.
                local_npcs.setdefault(chr_id, {'name': name, 'model': model})
            continue

        if op == 26:  # ChrTalk
            char_id = None
            segments = _xlsx_segments(cells, header, want_chrid=True)
            char_id = segments['chrid']
            seg_list = segments['segments']
            parts = [s for _, ps in seg_list for s in ps]
            if not parts:
                continue
            if is_animation_trigger(parts):
                pending_anon = ''
                continue
            voice = next((v for v, _ in seg_list if v is not None), None)
            override = pending_anon
            if not override and char_id is not None:
                override = latched.get(char_id, '')
            pending_anon = ''
            char = ('id', char_id) if char_id is not None else None
            dialogues.append((scene_idx, char, parts, 'chr', override, voice, current_func, seg_list))

        elif op == 24:  # AnonymousTalk
            segments = _xlsx_segments(cells, header, want_chrid=False)
            seg_list = segments['segments']
            parts = [s for _, ps in seg_list for s in ps]
            voice = next((v for v, _ in seg_list if v is not None), None)
            if not parts:
                continue
            if is_animation_trigger(parts):
                pending_anon = ''
                continue
            override = pending_anon
            pending_anon = ''
            dialogues.append((scene_idx, None, parts, 'anon', override, voice, current_func, seg_list))

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
        scene, char, parts, dkind, override, voice, _func, _segs = d
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
    return deduped, local_npcs


def normalize_name(raw):
    if not raw:
        return ''
    return LEADING_DIGITS_RE.sub('', raw).strip()


SYNTHETIC_CHRID_START = 100000


def load_tname_from_sqlite(db_path):
    """Returns dict chr_id -> {'name', 'model', 'faceTexture', 'name2'}.
    Source: NameTableData rows from t_name.tbl. CS1 schema:
      - unknown_string_1 = model (e.g. 'C_PLY000')
      - unknown_string_4 = faceTexture (e.g. 'FC_PLY000')
      - no name2 column

    CS1 reserves chr_id 0xFFFF for named NPCs that have no fixed slot
    (Claire, Rufus, Arseid, etc. — 272 such entries). Each gets a
    synthetic chr_id starting at SYNTHETIC_CHRID_START so name lookups
    can succeed via the OP_27 / TK_<name> function-name fallback. EN
    and JP DBs are extracted in parallel so positional ordering aligns.
    """
    c = sqlite3.connect(db_path)
    cur = c.execute(
        "SELECT character, name, unknown_string_1, unknown_string_4 "
        "FROM NameTableData WHERE file = 't_name.tbl'"
    )
    out = {}
    synth = SYNTHETIC_CHRID_START
    for chr_id, name, model, face_tex in cur:
        if chr_id == 0xFFFF or chr_id is None:
            key = synth
            synth += 1
        elif chr_id in out:
            continue
        else:
            key = chr_id
        out[key] = {
            'name': name or '',
            'model': model or '',
            'faceTexture': face_tex or '',
            'name2': '',
        }
    c.close()
    return out


def load_tvoice_from_sqlite(db_path):
    """Returns dict voice_id -> clip filename stem (no extension).

    Skips `pc8v...` clips (CS1 voice IDs 60000-64609): these are
    PC-port placeholder references in the bytecode that don't have
    matching shipped audio files. Lines tagged with these IDs (e.g.
    parenthesised inner-thought balloons) aren't actually voiced in
    the released game, so omitting them here makes the segment
    renderer correctly emit no audio link for those rows."""
    c = sqlite3.connect(db_path)
    cur = c.execute("SELECT id, clip FROM voice")
    out = {}
    for vid, clip in cur:
        if vid is None or not clip:
            continue
        if clip.startswith('pc'):
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
    the original paragraph breaks. Pass `tvoice=None` for sides without
    voice (EN)."""
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
    'Sentence one.' and 'Sentence two.' don't get glued into
    'Sentence one.Sentence two.' in the search-text column."""
    pieces = []
    for _vid, parts in segments:
        text = clean_text(parts, ' ')
        if text:
            pieces.append(text)
    return ' '.join(pieces)


def portrait_from_chrid(chrid):
    """CS1 has no costume variants — straight chr_id*10 scheme.
    Rean (0) -> avf0000, Alisa (1) -> avf0010, Sara (11) -> avf0110.
    Synthetic chr_ids assigned to 0xFFFF NPC entries skip the avf
    lookup (their note_chr fallback handles them via model field)."""
    if chrid is None or chrid >= SYNTHETIC_CHRID_START:
        return None
    pf = f'avf{chrid * 10:04d}.webp'
    return pf if pf in AVAILABLE_PORTRAITS else None


def note_from_chrid(chrid):
    """CS1 note icons are keyed by chr_id (Vivi chrId 85 -> note_chr085,
    Towa chrId 52 -> note_chr052) — NOT by the trailing number in the
    model name (Vivi's model is C_NPC188 but her note is note_chr085).
    Synthetic chr_ids assigned to 0xFFFF entries are above
    SYNTHETIC_CHRID_START and skip the lookup."""
    if chrid is None or chrid >= SYNTHETIC_CHRID_START or chrid >= 1000:
        return None
    pf = f'note_chr{chrid:03d}.webp'
    return pf if pf in AVAILABLE_NOTES else None


def _ruby_base_start(text, end_pos, byte_count):
    """Walk backward from `end_pos` consuming Shift-JIS bytes until we
    hit `byte_count`. Returns the character index where the base text
    starts. CS1 ruby `#NR...#` encodes N as the byte length of the
    preceding text in Shift-JIS, where each Japanese char is 2 bytes."""
    consumed = 0
    i = end_pos
    while i > 0 and consumed < byte_count:
        ch = text[i - 1]
        try:
            consumed += len(ch.encode('cp932'))
        except UnicodeEncodeError:
            consumed += 2  # assume Japanese width when unencodable
        i -= 1
    return i


def _apply_ruby(text, html):
    """Resolve `<base>#NR<reading>#` ruby markup. For HTML output, wrap
    base+reading in `<ruby>` tags so the reading shows above the kanji.
    For plain text, drop the marker — the base remains because it's
    written before the marker. Iterates because a string may contain
    multiple ruby spans."""
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
    # Ruby markup needs to be resolved before LEFTOVER_CODE_RE strips
    # the `#NR` opener and orphans the reading + closing `#`.
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
    """Extract the speaker-identifying prefix from a voice clip name.

    CS1 clips look like `8v00xxx` / `c8v0xxx` (no underscores) where the
    `##` after the leading prefix encodes the speaker's chr_id. The
    first 4 characters serve as a reliable speaker bucket: '8v00' = Rean,
    '8v01' = Alisa, etc.
    """
    if not filename:
        return ''
    us = filename.find('_')
    if us > 0:
        return filename[:us]
    return filename[:4] if len(filename) >= 4 else filename


def build_chr_alias(parsed_files, jp_tname, tvoice):
    """Same shape as 9D-sen4 — learns voice_prefix -> chr_id from voiced
    dialogues whose chr_id is in t_name. CS2 voice extraction isn't wired
    yet so this map will be empty until that's added; harmless."""
    from collections import Counter
    prefix_known = {}
    for parsed in parsed_files:
        for d in parsed:
            scene, char, parts, dkind, override, voice, _func, _segs = d
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
    # CS1's NameTableData has no name2 column. Derive name2 keys from
    # the EN display names (lowercased, spaces stripped) so tk_<name>.xlsx
    # speaker fallback can match e.g. tk_alisa.xlsx -> 'Alisa' -> chr_id 1.
    # Multi-word names like 'Princess Alfin' also get a last-word key
    # ('alfin') so tk_alfin.xlsx resolves.
    name2_to_chrid = {}
    for cid, e in en_tname.items():
        n = (e.get('name') or '').strip()
        if not n:
            continue
        keys = {n.lower().replace(' ', '')}
        last = n.split()[-1].lower() if ' ' in n else None
        if last:
            keys.add(last)
        for k in keys:
            name2_to_chrid.setdefault(k, cid)
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
            return [], {}
        hit = cache.get(path)
        if hit is None:
            try:
                hit = parse_xlsx(path, name2_to_chrid)
            except Exception as e:
                print(f'WARN: failed to parse {path}: {e}', file=sys.stderr)
                hit = ([], {})
            cache[path] = hit
        return hit

    # Voice-prefix bridge — placeholder until voice extraction is added.
    all_jp_dialogues = []
    for path in list(jp_scena.values()) + list(jp_talk.values()):
        d, _ = get(path)
        all_jp_dialogues.append(d)
    voice_prefix_to_known = build_chr_alias(all_jp_dialogues, jp_tname, tvoice)
    print(f'voice prefix -> chr_id map: {len(voice_prefix_to_known)} entries')

    def resolve_via_voice(voice_id, side_tname):
        if voice_id is None:
            return ''
        cid = chrid_from_voice(voice_id)
        if cid is None:
            return ''
        if cid in side_tname:
            return side_tname[cid].get('name', '')
        return ''

    def chrid_from_voice(voice_id):
        """Map a CS1 voice id back to a chr_id via the learned
        voice-prefix bridge (builds prefix -> chr_id from voiced rows
        whose chr_id is already in t_name)."""
        if voice_id is None:
            return None
        clip = tvoice.get(voice_id, '')
        if not clip:
            return None
        return voice_prefix_to_known.get(_voice_prefix(clip))

    def resolve_chrid(char, talk_fallback_chrid=None, local_npcs=None):
        if char is None:
            return None
        if char[0] == 'id':
            cid = char[1]
            if cid in jp_tname or cid in en_tname:
                return cid
            if local_npcs and cid in local_npcs:
                return cid
            return talk_fallback_chrid
        return None

    def talk_fallback(stem):
        if not stem.startswith('tk_'):
            return None
        return name2_to_chrid.get(stem[3:])

    def local_name2_lookup(key, en_npcs, jp_npcs, global_name2):
        """Map TK_<key> function name to a chr_id. Search per-file op-19
        NPC declarations on the EN side first (their names are the
        canonical English forms that match the TK_ function names like
        TK_Gyler -> 'gyler'), then fall back to the global t_name-derived
        name2 map."""
        for npcs in (en_npcs, jp_npcs):
            if not npcs:
                continue
            for cid, e in npcs.items():
                n = (e.get('name') or '').strip()
                if not n:
                    continue
                if n.lower().replace(' ', '') == key:
                    return cid
                if ' ' in n and n.split()[-1].lower() == key:
                    return cid
        return global_name2.get(key)

    def speaker_name(char, override, side_tname, talk_fb,
                     local_npcs_jp=None, local_npcs_en=None,
                     side='jp', voice_id=None):
        if override:
            return override
        chrid = resolve_chrid(char, talk_fb, local_npcs_jp or local_npcs_en)
        if chrid is not None and chrid in side_tname:
            return side_tname[chrid]['name']
        if chrid is not None:
            local = local_npcs_en if side == 'en' else local_npcs_jp
            if local and chrid in local:
                return local[chrid].get('name', '')
        return resolve_via_voice(voice_id, side_tname)

    def candidate_chrids(char, override, side_speaker, talk_fb,
                         local_npcs=None, voice_id=None):
        """Yield chr_ids worth trying for portrait/note lookup.

        Name-based lookup goes FIRST: the original CS1 binary script
        keyed icons off the resolved speaker name (`reverse_names_eng
        [eng_chr_name]`), which is the same approach. This matters when
        OP_27 overrides change the displayed speaker — e.g.
        `ChrTalk(0=Rean, ...)` with override `'Sara'` should show Sara's
        icon, not Rean's. Falling back to the row's raw chr_id only when
        the name doesn't resolve.

        Voice-prefix bridge is intentionally NOT consulted here: CS1
        voice clips use only ~10 distinct 4-char prefixes ('e8v0',
        'e8v1', ...) so the bridge collapses thousands of speakers to a
        handful of representative chr_ids and produces wrong icons for
        op-19 scena-local NPCs (Vulcan/Scarlet/Terrorist whose voice
        prefix happens to match Patrick or Beatrix). The original binary
        script never used voice for icon lookup either."""
        seen = set()
        for nm in (override, side_speaker):
            if nm:
                cid = name_to_chrid.get(nm)
                if cid is not None and cid not in seen:
                    seen.add(cid); yield cid
        chrid = resolve_chrid(char, talk_fb, local_npcs)
        if chrid is not None and chrid not in seen:
            seen.add(chrid); yield chrid

    def row_portrait(char, override, side_speaker, talk_fb,
                     local_npcs=None, voice_id=None):
        for cid in candidate_chrids(char, override, side_speaker, talk_fb,
                                     local_npcs, voice_id):
            pf = portrait_from_chrid(cid)
            if pf:
                return pf
        return None

    def row_note(char, override, side_speaker, talk_fb,
                 local_npcs_jp=None, local_npcs_en=None, voice_id=None):
        local = local_npcs_jp or local_npcs_en
        for cid in candidate_chrids(char, override, side_speaker, talk_fb,
                                     local, voice_id):
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
            en_d, en_npcs = get(en_map.get(stem))
            jp_d, jp_npcs = get(jp_map.get(stem))
            talk_fb = talk_fallback(stem) if kind == 'talk' else None

            pairs = align_scenes(en_d, jp_d)
            unpaired = sum(1 for e, j in pairs if e is None or j is None)
            if unpaired:
                print(f'WARN {kind}/{stem}: {unpaired} unpaired rows '
                      f'(EN={len(en_d)} JP={len(jp_d)})', file=sys.stderr)

            for en_t, jp_t in pairs:
                if en_t:
                    en_scene, en_char, en_parts, _, en_override, en_voice, en_func, en_segs = en_t
                else:
                    en_scene, en_char, en_parts, en_override, en_voice, en_func, en_segs = None, None, [], '', None, '', []
                if jp_t:
                    jp_scene, jp_char, jp_parts, _, jp_override, jp_voice, jp_func, jp_segs = jp_t
                else:
                    jp_scene, jp_char, jp_parts, jp_override, jp_voice, jp_func, jp_segs = None, None, [], '', None, '', []
                scene = jp_scene if jp_scene is not None else (en_scene if en_scene is not None else 0)

                # Resolve TK_<name> function-name fallback now that we
                # have both EN and JP local_npcs in scope. Use the EN
                # function name (canonical English form like TK_Gyler).
                func = en_func or jp_func
                if func.startswith('TK_'):
                    n2 = func[3:].lower()
                    fb = local_name2_lookup(n2, en_npcs, jp_npcs, name2_to_chrid)
                    if fb is not None:
                        if en_char and en_char[0] == 'id' and en_char[1] in (0xFFFD, 0xFFFE, 0xFFFF):
                            en_char = ('id', fb)
                        if jp_char and jp_char[0] == 'id' and jp_char[1] in (0xFFFD, 0xFFFE, 0xFFFF):
                            jp_char = ('id', fb)
                # Party-leader placeholders (0xF000 / 0xF010) almost
                # always mean Rean during main-story scenes — default
                # to chr_id 0 when no override / latched name applies.
                for ch_var in ('en_char', 'jp_char'):
                    ch = locals()[ch_var]
                    if ch and ch[0] == 'id' and ch[1] in (0xF000, 0xF010):
                        if ch_var == 'en_char':
                            en_char = ('id', 0)
                        else:
                            jp_char = ('id', 0)

                vid = jp_voice or en_voice
                en_raw = speaker_name(en_char, en_override, en_tname, talk_fb,
                                      jp_npcs, en_npcs, side='en', voice_id=vid)
                jp_raw = speaker_name(jp_char, jp_override, jp_tname, talk_fb,
                                      jp_npcs, en_npcs, side='jp', voice_id=vid)
                if en_t and jp_t:
                    if not en_raw and jp_char:
                        en_raw = speaker_name(jp_char, '', en_tname, talk_fb,
                                              jp_npcs, en_npcs, side='en', voice_id=vid)
                    if not jp_raw and en_char:
                        jp_raw = speaker_name(en_char, '', jp_tname, talk_fb,
                                              jp_npcs, en_npcs, side='jp', voice_id=vid)
                eng_chr = normalize_name(en_raw)
                jpn_chr = normalize_name(jp_raw)

                en_search = render_search_segments(en_segs) if en_segs else clean_text(en_parts, ' ')
                en_html = render_html_segments(en_segs) if en_segs else clean_text(en_parts, '<br/>')
                jp_search = render_search_segments(jp_segs) if jp_segs else clean_text(jp_parts, ' ')
                jp_html = render_html_segments(jp_segs, tvoice) if jp_segs else clean_text(jp_parts, '<br/>')

                # Pass override + resolved speaker name (JP first, then
                # EN) so the portrait can recover from speaker-name match
                # when the chr_id either is a placeholder (0xFFFD etc.)
                # or maps to a t_name entry without a shipped portrait.
                ovr = jp_override or en_override
                pfile = (row_portrait(jp_char, ovr, jp_raw, talk_fb,
                                       local_npcs=jp_npcs, voice_id=vid)
                         or row_portrait(en_char, ovr, en_raw, talk_fb,
                                          local_npcs=en_npcs, voice_id=vid))
                if pfile:
                    pc_icon = f'<img class="itp-face" src="itp/{GAME_ID}/{pfile}"/>'
                else:
                    nfile = (row_note(jp_char, ovr, jp_raw, talk_fb,
                                       local_npcs_jp=jp_npcs, local_npcs_en=en_npcs, voice_id=vid)
                             or row_note(en_char, ovr, en_raw, talk_fb,
                                          local_npcs_jp=jp_npcs, local_npcs_en=en_npcs, voice_id=vid))
                    pc_icon = f'<img class="itp-note" src="itp/{GAME_ID}/{nfile}"/>' if nfile else ''

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

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(f'delete from script where game_id = {GAME_ID};\n')
        for row in rows:
            f.write('insert into script (game_id, fname, scene, row, eng_chr_name, eng_search_text, '
                    'eng_html_text, jpn_chr_name, jpn_search_text, jpn_html_text, op_name, pc_icon_html) values\n')
            f.write("('%s');\n" % "','".join(sql_escape(c) for c in row))

    print(f'TOTAL = {len(rows)}')


if __name__ == '__main__':
    main()
