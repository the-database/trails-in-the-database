"""Extract Trails into Reverie (game 10) dialogue into reverie.sql.

Parses Decompiler2's Python output for EN + JP scripts (no execution — ast
walk only). Extracts both ChrTalk(...) (speaker-tagged) and Talk(0xFFFF, ...)
(anonymous narration) opcodes. Animation-trigger Talk() calls are filtered.
EN and JP rows are paired by position within each file. Character display
names come from CreateChr calls in scena files, keyed by the Chinese
ChrTable key shared between EN and JP decompiles.

Active voice (the party banter that plays on the field) comes from
t_active.tbl and goes in as one more file, `active_voice`; see
active_voice_exchanges.
"""

import ast
import os
import re
import sqlite3
import sys

FALCOM_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'Falcom')
DATA_ROOT = os.path.join(FALCOM_ROOT, 'data')
EN_ROOT = os.path.join(DATA_ROOT, 'reverie_decompiled', 'data', 'scripts')
JP_ROOT = os.path.join(DATA_ROOT, 'reverie_jp_decompiled', 'scripts')
EN_TNAME = os.path.join(DATA_ROOT, 'reverie_decompiled', 'data', 'text', 'dat_en', 't_name.py')
JP_TNAME = os.path.join(DATA_ROOT, 'reverie_jp_decompiled', 'data', 'text', 'dat', 't_name.py')
JP_TVOICE = os.path.join(DATA_ROOT, 'reverie_jp_decompiled', 'data', 'text', 'dat', 't_voice.py')
CHRID_TABLE_PATH = os.path.join(FALCOM_ROOT, 'Decompiler2', 'Falcom', 'ED85', 'Metadata', 'chrId_table.py')
GAME_ID = 10
OUTPUT = 'reverie.sql'

# t_active.tbl, staged with the books (see ed8-extractbooks-database.py):
# EN from the Steam release, JP from Hajimari no Kiseki v1.0, CLE-decrypted
# into text/decrypted/dat. Converted with tocs' sqlite_conv (`--game CS5`).
ACTIVE_VOICE_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'books_raw', 'reverie', 'text')
EN_ACTIVE = os.path.join(ACTIVE_VOICE_ROOT, 'dat_en', 't_active.sqlite')
JP_ACTIVE = os.path.join(ACTIVE_VOICE_ROOT, 'decrypted', 'dat', 't_active.sqlite')
ACTIVE_VOICE_FNAME = 'active_voice'
# Groups from here up are test entries after the game's own, never played:
# a line per portrait that only reads the character's name (JP with dev
# notes such as 「本校制服、ユウナの夢で使用」), and placeholder lines
# (「ほげほげ」).
ACTIVE_VOICE_TEST_GROUPS = 9990

# Template/system files that haji omitted. Their ChrTalks are boilerplate.
SKIP_STEMS = {'PersonalTemplate', 'be0000', 'infsys'}

# JP-side filename overrides for cases where the canonical .py was
# overwritten by a dev/test artifact and the real version was preserved
# as a Windows "copy of" file. Keyed by stem.
JP_FILE_OVERRIDES = {'h0000': 'h0000 - コピー.py'}

# Broken `import <stem with dashes>_hook` line introduced by Windows-style
# rename of files in the override set. Patched out before `ast.parse`.
HOOK_PATCH_RE = re.compile(
    r'^(\s*)import\s+\S+\s*-\s*コピー_hook\s*$', re.MULTILINE)

# The 71 face-portrait files shipped at itp/10/{file}. Used to filter
# the filename derived from t_name.py's faceTexture/model fields (which
# can reference sprites that weren't shipped). Snapshot of the
# authoritative face-sprite directory — only files listed here actually
# ship.
AVAILABLE_PORTRAITS = {
    'avfc000.webp', 'avfc000_c09.webp', 'avfc000_c64.webp', 'avfc000_fc57.webp',
    'avfc001.webp', 'avfc001_c64.webp', 'avfc002.webp', 'avfc003.webp',
    'avfc004.webp', 'avfc005_c10.webp', 'avfc006.webp', 'avfc007.webp',
    'avfc008.webp', 'avfc009.webp', 'avfc010.webp', 'avfc010_c10.webp',
    'avfc011.webp', 'avfc011_c10.webp', 'avfc011_c64.webp',
    'avfc012.webp', 'avfc012_c10.webp',
    'avfc013.webp', 'avfc013_c10.webp', 'avfc013_c64.webp',
    'avfc015.webp', 'avfc015_c10.webp', 'avfc015_c60.webp',
    'avfc016.webp', 'avfc017.webp', 'avfc018_c03.webp', 'avfc019.webp',
    'avfc021.webp', 'avfc023_c00.webp', 'avfc024.webp', 'avfc025.webp',
    'avfc026.webp', 'avfc027.webp', 'avfc028_c10.webp', 'avfc029.webp',
    'avfc034.webp', 'avfc035.webp', 'avfc035_c10.webp',
    'avfc041.webp', 'avfc042.webp', 'avfc043.webp', 'avfc044.webp',
    'avfc045.webp', 'avfc046.webp', 'avfc063.webp', 'avfc067.webp',
    'avfc072.webp', 'avfc080.webp', 'avfc081.webp', 'avfc083.webp',
    'avfc087.webp', 'avfc088.webp', 'avfc089.webp', 'avfc091.webp',
    'avfc097.webp', 'avfc105.webp', 'avfc106.webp', 'avfc107.webp',
    'avfc108.webp', 'avfc110.webp', 'avfc111.webp',
    'avfc112.webp', 'avfc112_c00.webp',
    'avfc113.webp', 'avfc202.webp', 'avfc955.webp', 'avfc972.webp',
}

# 129 smaller "note" icons for characters without a full avfc portrait
# (minor NPCs, battle-only chars, etc.). Filenames are keyed by chrId
# directly: note_chr{chrid:03d}.webp, sometimes with a _N variant suffix.
# Frontend renders these with CSS class `itp-note3`.
AVAILABLE_NOTES = {
    'note_chr000.webp', 'note_chr000_1.webp', 'note_chr001.webp',
    'note_chr002.webp', 'note_chr003.webp', 'note_chr004.webp',
    'note_chr005.webp', 'note_chr006.webp', 'note_chr007.webp',
    'note_chr008.webp', 'note_chr009.webp',
    'note_chr010.webp', 'note_chr010_1.webp',
    'note_chr011.webp', 'note_chr011_1.webp',
    'note_chr012.webp', 'note_chr012_1.webp',
    'note_chr013.webp', 'note_chr013_1.webp',
    'note_chr015.webp', 'note_chr015_1.webp',
    'note_chr016.webp', 'note_chr017.webp', 'note_chr018.webp',
    'note_chr019.webp', 'note_chr020.webp', 'note_chr021.webp',
    'note_chr023.webp', 'note_chr024.webp', 'note_chr025.webp',
    'note_chr026.webp', 'note_chr027.webp', 'note_chr028.webp',
    'note_chr029.webp', 'note_chr034.webp', 'note_chr035.webp',
    'note_chr040.webp', 'note_chr041.webp', 'note_chr042.webp',
    'note_chr043.webp', 'note_chr044.webp', 'note_chr045.webp',
    'note_chr046.webp', 'note_chr050.webp', 'note_chr058.webp',
    'note_chr063.webp', 'note_chr067.webp', 'note_chr072.webp',
    'note_chr078.webp', 'note_chr080.webp', 'note_chr081.webp',
    'note_chr083.webp', 'note_chr085.webp', 'note_chr087.webp',
    'note_chr088.webp', 'note_chr089.webp', 'note_chr091.webp',
    'note_chr094.webp', 'note_chr102.webp', 'note_chr105.webp',
    'note_chr106.webp', 'note_chr107.webp', 'note_chr108.webp',
    'note_chr109.webp', 'note_chr109_1.webp',
    'note_chr110.webp', 'note_chr111.webp',
    'note_chr112.webp', 'note_chr112_1.webp',
    'note_chr113.webp', 'note_chr114.webp', 'note_chr124.webp',
    'note_chr200.webp', 'note_chr201.webp', 'note_chr202.webp',
    'note_chr203.webp', 'note_chr204.webp', 'note_chr205.webp',
    'note_chr206.webp', 'note_chr210.webp', 'note_chr211.webp',
    'note_chr212.webp', 'note_chr213.webp', 'note_chr215.webp',
    'note_chr411.webp', 'note_chr412.webp', 'note_chr413.webp',
    'note_chr414.webp', 'note_chr505.webp', 'note_chr506.webp',
    'note_chr507.webp', 'note_chr512.webp', 'note_chr516.webp',
    'note_chr600.webp', 'note_chr601.webp', 'note_chr602.webp',
    'note_chr603.webp', 'note_chr604.webp', 'note_chr605.webp',
    'note_chr606.webp', 'note_chr610.webp', 'note_chr611.webp',
    'note_chr612.webp', 'note_chr613.webp', 'note_chr614.webp',
    'note_chr615.webp', 'note_chr616.webp', 'note_chr617.webp',
    'note_chr621.webp', 'note_chr731.webp', 'note_chr732.webp',
    'note_chr733.webp', 'note_chr735.webp', 'note_chr736.webp',
    'note_chr737.webp', 'note_chr738.webp', 'note_chr739.webp',
    'note_chr740.webp', 'note_chr741.webp', 'note_chr744.webp',
    'note_chr805.webp', 'note_chr806.webp', 'note_chr807.webp',
    'note_chr808.webp', 'note_chr809.webp', 'note_chr813.webp',
    'note_chr815.webp', 'note_chr955_1.webp', 'note_chr972.webp',
}

CONTROL_CODE_RE = re.compile(r'#[A-Za-z](?:_[A-Za-z0-9]+|\[[A-Za-z0-9]+\])?')
LEFTOVER_CODE_RE = re.compile(r'#\d+[A-Za-z]?')
LEADING_DIGITS_RE = re.compile(r'^\d+')
WHITESPACE_RE = re.compile(r'[ \t]+')
# Ruby (furigana) markup: `Ⅶの輪#6RROUND OF SEVEN#` — digit before R is
# the byte length of the preceding base text in Shift-JIS (each Japanese
# char = 2 bytes); reading runs to the closing bare `#`.
RUBY_RE = re.compile(r'#(\d+)R([^#]*)#')


def _subscript_slice(node):
    inner = node.slice
    if hasattr(ast, 'Index') and isinstance(inner, ast.Index):
        inner = inner.value
    return inner


def _parse_char_arg(node):
    """ChrTable['key'] -> ('key', str); integer literal -> ('id', int); else None."""
    if isinstance(node, ast.Subscript):
        if isinstance(node.value, ast.Name) and node.value.id == 'ChrTable':
            inner = _subscript_slice(node)
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                return ('key', inner.value)
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return ('id', node.value)
    return None


def _string_parts(node):
    """Extract string constants from a Tuple/List literal."""
    if not isinstance(node, (ast.Tuple, ast.List)):
        return []
    out = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
    return out


def _extract_voice_id(node):
    """Backwards-compatible accessor: returns the first voice id in the
    content tuple, or None. New code should use _extract_segments."""
    for v, _ in _extract_segments(node):
        if v is not None:
            return v
    return None


def _extract_segments(node):
    """Walk a ChrTalk/Talk content tuple in source order and yield
    (voice_id_or_None, [text_parts]) per paragraph. `(TxtCtl.Voice, N)`
    opens a paragraph and sets its voice; `TxtCtl.Clear` ends one;
    string literals accumulate into the current paragraph.

    Multi-paragraph dialogue with one voice per paragraph (e.g. boss
    speeches with three sequential voice IDs) becomes three segments —
    main() voice-wraps each one independently so all audio links work
    instead of only the first one playing."""
    if not isinstance(node, (ast.Tuple, ast.List)):
        return []
    segments = []
    cur_voice = None
    cur_parts = []

    def flush():
        if cur_parts or cur_voice is not None:
            segments.append((cur_voice, list(cur_parts)))

    for elt in node.elts:
        if isinstance(elt, ast.Tuple) and len(elt.elts) >= 2:
            head, val = elt.elts[0], elt.elts[1]
            if (isinstance(head, ast.Attribute) and head.attr == 'Voice'
                    and isinstance(val, ast.Constant) and isinstance(val.value, int)):
                flush()
                cur_voice = val.value
                cur_parts = []
                continue
        if isinstance(elt, ast.Attribute) and elt.attr == 'Clear':
            flush()
            cur_voice = None
            cur_parts = []
            continue
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            cur_parts.append(elt.value)
    flush()
    return [(v, p) for v, p in segments if p or v is not None]


def _is_scena_code_decorated(func):
    for dec in func.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr == 'Code':
            return True
    return False


def is_animation_trigger(parts):
    """Some Talk(0xFFFF, ...) calls carry animation-engine control strings
    rather than narration, e.g. 'chr001\\nAniEvAseNugui \\nWK_TEMP:0'. These
    contain literal backslash-n pairs (never present in real dialogue, which
    uses actual newlines) and/or engine tokens. Filter them out."""
    text = ''.join(parts)
    if not text:
        return True
    if '\\n' in text:
        return True
    if 'WK_TEMP' in text or 'AniEv' in text or 'ChrSet' in text:
        return True
    return False


def _iter_calls_in_order(node):
    """Yield Call nodes from an AST subtree in source (depth-first) order.
    Preserves source order so OP_27 overrides attach to the next dialogue."""
    if isinstance(node, ast.Call):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _iter_calls_in_order(child)


def parse_script(path, chr_key_to_id):
    """Parse one decompiled .py file.

    Returns (dialogues, createchr_names).
      dialogues: list of (scene_idx, char, text_parts, kind, override) where
        kind is 'chr' (ChrTalk) or 'anon' (Talk); override is the JP
        speaker name resolved for this dialogue or ''.

    OP_27 semantics (per observation):
      OP_27(name, 0xFFFF)       — single-shot: applies to the next dialogue.
      OP_27(name, <real chr_id>) — latched: applies to every subsequent
        dialogue whose character resolves to the same chr_id, until
        overwritten by another OP_27 for the same chr_id within this
        function. The latch resets at function boundaries.

    chr_key_to_id bridges ChrTable['<name>'] keys to numeric chr_ids so
    latched names can attach to key-based ChrTalks.
    """
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    # Patch the broken `import <stem>_hook` line in JP_FILE_OVERRIDES files
    # (the one コピー file has a Windows-rename artifact in its hook import).
    src = HOOK_PATCH_RE.sub(r'\1pass  # patched (broken hook import)', src)
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        print(f'WARN: syntax error in {path}: {e}', file=sys.stderr)
        return [], {}

    dialogues = []
    createchr_names = {}
    scene_idx = -1
    # Latched OP_27 overrides persist ACROSS functions within a scena —
    # this matches the game runtime, which holds these aliases until
    # explicitly reassigned or the scena unloads. The clearest example
    # is w1410: `OP_27('《Ｃ》', 0x002C)` in EV_C1_01_01 makes Rufus's
    # chr_id render as "《Ｃ》" for the rest of the scena (including
    # subsequent functions like EV_C2_00_01). Resetting per-function
    # would lose that masked-identity alias on every line outside the
    # function it was first set in.
    latched = {}
    pending_anon = ''      # OP_27 with 0xFFFF: consumed by next dialogue
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and _is_scena_code_decorated(node)):
            continue
        scene_idx += 1
        # New function: clear the single-shot pending_anon (a one-shot
        # bound to the very next dialogue can't survive a function
        # boundary) but preserve the persistent latched dict.
        pending_anon = ''
        for call in _iter_calls_in_order(node):
            if not isinstance(call.func, ast.Name):
                continue
            name = call.func.id
            if name == 'OP_27' and len(call.args) >= 2:
                n_arg, id_arg = call.args[0], call.args[1]
                if not (isinstance(n_arg, ast.Constant) and isinstance(n_arg.value, str)):
                    continue
                sval = n_arg.value
                if isinstance(id_arg, ast.Constant) and isinstance(id_arg.value, int):
                    if id_arg.value in (0xFFFF, 0xFFFE):
                        # Single-shot anonymous label; an empty name is a
                        # no-op (pending_anon is cleared by the next line).
                        if sval.strip():
                            pending_anon = sval
                    elif sval.strip():
                        latched[id_arg.value] = sval
                    else:
                        # Empty name = reset this chr_id's latch to the
                        # real t_name; clear it instead of ignoring it.
                        latched.pop(id_arg.value, None)
            elif name == 'ChrTalk' and len(call.args) >= 3:
                char = _parse_char_arg(call.args[0])
                segments = _extract_segments(call.args[2])
                parts = [s for _, ps in segments for s in ps]
                voice = next((v for v, _ in segments if v is not None), None)
                override = pending_anon
                if not override and char is not None:
                    chrid = char[1] if char[0] == 'id' else chr_key_to_id.get(char[1])
                    if chrid is not None:
                        override = latched.get(chrid, '')
                pending_anon = ''
                dialogues.append((scene_idx, char, parts, 'chr', override, voice, segments))
            elif name == 'Talk' and len(call.args) >= 2:
                segments = _extract_segments(call.args[1])
                parts = [s for _, ps in segments for s in ps]
                if is_animation_trigger(parts):
                    pending_anon = ''
                    continue
                voice = next((v for v, _ in segments if v is not None), None)
                override = pending_anon
                pending_anon = ''
                dialogues.append((scene_idx, None, parts, 'anon', override, voice, segments))
            elif name == 'CreateChr' and len(call.args) >= 3:
                char = _parse_char_arg(call.args[0])
                if char is None:
                    continue
                name_node = call.args[2]
                if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
                    display = name_node.value
                    if display:
                        createchr_names.setdefault(char, display)
    # Drop adjacent duplicates: source uses Jump/label branching where the
    # same logical line is emitted N times across alternate branches (only
    # one runs at runtime). Two patterns:
    #   - exact dup (h2600): same (char, voice, text) — branch A and B
    #     both reference the same recorded VA line.
    #   - alternate-VA (d7010): same (char, text) with DIFFERENT voice IDs
    #     — speaker slot can be one of N party members, each with their
    #     own VA recording for the same line; cascading If/Jump picks one.
    # Both have voices on every branch — only dedup when prev AND current
    # both carry non-None voice IDs. Unvoiced same-text adjacent dialogues
    # (d8071 pattern) are slight particle variants in JP that translated to
    # identical EN; deduping there causes EN<JP imbalance.
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
    return deduped, createchr_names


def normalize_name(raw):
    if not raw:
        return ''
    return LEADING_DIGITS_RE.sub('', raw).strip()


def load_tvoice(path):
    """Parse t_voice.py. Returns dict voice_id (int) -> filename stem
    ('v163_00004'). The `file` field omits the .opus extension."""
    with open(path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    result = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'VoiceTableData'):
            continue
        fields = {}
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant):
                fields[kw.arg] = kw.value.value
        vid = fields.get('id')
        fn = fields.get('file')
        if vid is None or not fn:
            continue
        result.setdefault(vid, fn)
    return result


def voice_wrap(html_text, voice_file):
    return (
        f'<a href="javascript:void(0)" class="dialogue-line" '
        f'data-audio="talk/10/{voice_file}.opus">'
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
    'Sentence one.' and 'Sentence two.' don't get glued together."""
    pieces = []
    for _vid, parts in segments:
        text = clean_text(parts, ' ')
        if text:
            pieces.append(text)
    return ' '.join(pieces)


def load_chrid_table(path):
    """Parse Decompiler2's chrId_table.py and extract string-keyed entries
    (Chinese name -> numeric chr_id). The file also has the reverse
    mapping (id -> name) which we ignore."""
    with open(path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and isinstance(k.value, str)
                        and isinstance(v, ast.Constant) and isinstance(v.value, int)):
                    result[k.value] = v.value
    return result


def load_tname(path):
    """Parse a t_name.py file (EN or JP). Returns dict chr_id ->
    {'name', 'model', 'faceTexture', 'name2'}. First entry per chr_id
    wins; outfit variants (which use chrId=0xFFFF) are skipped."""
    with open(path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    result = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'NameTableData'):
            continue
        fields = {}
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant):
                fields[kw.arg] = kw.value.value
        cid = fields.get('chrId')
        if cid is None or cid == 0xFFFF or cid in result:
            continue
        result[cid] = {
            'name': fields.get('chrName') or '',
            'model': fields.get('model') or '',
            'faceTexture': fields.get('faceTexture') or '',
            'name2': fields.get('name2') or '',
        }
    return result


def portrait_from_tname(entry):
    """Derive the portrait filename from a t_name entry.

    Resolution order:
      1. faceTexture field (Rufus: FC_CHR112_C00 -> avfc112_c00.webp).
      2. model field (Clotilde: model=C_CHR045 when faceTexture=FC_CHR998
         points at a shared fallback texture not shipped as a sprite).
      3. If neither points at a shipped file, but a variant of the base
         id IS shipped (Claire: plain avfc023.webp isn't shipped but
         avfc023_c00.webp is), use the lowest-suffixed variant. This
         mirrors how the game swaps to a variant face when the default
         model lacks its own portrait sprite.
    """
    def strip(s):
        for prefix in ('FC_CHR', 'C_CHR'):
            if s.startswith(prefix):
                suffix = s[len(prefix):].lower()
                return f'avfc{suffix}.webp' if suffix else None
        return None

    for field in ('faceTexture', 'model'):
        pf = strip(entry.get(field, ''))
        if pf in AVAILABLE_PORTRAITS:
            return pf

    # Variant-suffix fallback: 'avfc023.webp' -> try 'avfc023_c##.webp'.
    for field in ('faceTexture', 'model'):
        pf = strip(entry.get(field, ''))
        if not pf:
            continue
        base = pf[:-len('.webp')]  # 'avfc023'
        variants = sorted(p for p in AVAILABLE_PORTRAITS
                          if p.startswith(base + '_c'))
        if variants:
            return variants[0]
    return None


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
        count = int(m.group(1))
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


def clean_text(parts, newline):
    text = ''.join(parts)
    # Ruby must run before LEFTOVER_CODE_RE strips the `#NR` opener and
    # orphans the reading + closing `#`.
    text = _apply_ruby(text, html=(newline == '<br/>'))
    text = CONTROL_CODE_RE.sub('', text)
    text = LEFTOVER_CODE_RE.sub('', text)
    text = text.replace('\n', newline)
    if newline == ' ':
        text = WHITESPACE_RE.sub(' ', text)
    # Decompiler mismaps Shift-JIS NEC `♥` (0x87 0x9D) onto `㈱`
    # (0x87 0x9F) — both bytes are CP932 NEC special chars and the
    # lookup is off by one. Patch back here before emit.
    text = text.replace('㈱', '♥')
    return text.strip()


def collect_files(root, *parts):
    d = os.path.join(root, *parts)
    if not os.path.isdir(d):
        return {}
    # Files used as override targets — exclude their natural stems so we
    # don't emit a phantom JP-only entry for the override file itself.
    override_targets = (
        {v[:-3] for v in JP_FILE_OVERRIDES.values()} if root == JP_ROOT else set()
    )
    out = {
        entry[:-3]: os.path.join(d, entry)
        for entry in os.listdir(d)
        if entry.endswith('.py')
        and entry[:-3] not in SKIP_STEMS
        and entry[:-3] not in override_targets
    }
    # JP-side: redirect specific stems to their override file (e.g. the
    # real h0000 lives at "h0000 - コピー.py" — see JP_FILE_OVERRIDES).
    if root == JP_ROOT:
        for stem, override_name in JP_FILE_OVERRIDES.items():
            override_path = os.path.join(d, override_name)
            if os.path.exists(override_path):
                out[stem] = override_path
    return out


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def _voice_prefix(filename):
    """Reverie voice filenames look like `v10_1_1234`, `v16_c_0058` — the
    character identity lives in the leading `v##` portion (everything up
    to the first underscore)."""
    if not filename or not filename.startswith('v'):
        return ''
    us = filename.find('_')
    return filename[:us] if us > 0 else filename


def build_chr_alias(parsed_files, jp_tname, chr_key_to_id, tvoice):
    """Learn `voice_prefix -> known_chr_id` from dialogues with chr_ids that
    resolve to a t_name entry. Used as a last-ditch speaker fallback for
    chr_ids absent from t_name OR when chr_id couldn't be parsed at all
    (variable expression — `char` is None)."""
    from collections import Counter
    prefix_known = {}
    for parsed in parsed_files:
        for d in parsed:
            scene, char, parts, dkind, override, voice, _segs = d
            if voice is None or char is None:
                continue
            if char[0] == 'id':
                cid = char[1]
            else:
                cid = chr_key_to_id.get(char[1])
            if cid is None or cid not in jp_tname:
                continue
            fn = tvoice.get(voice) or ''
            prefix = _voice_prefix(fn)
            if not prefix:
                continue
            prefix_known.setdefault(prefix, Counter())[cid] += 1
    return {prefix: cnt.most_common(1)[0][0]
            for prefix, cnt in prefix_known.items()}


def _lcs_pairs(a, b):
    """LCS alignment on (scene_idx, kind, char) signatures. Returns a list
    of (a_item_or_None, b_item_or_None) — matched items paired, EN/JP-only
    insertions emitted as singletons. char tuples are hashable."""
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
    """Align dialogues scene-by-scene via LCS on (scene_idx, kind, char).
    Scene counts match across EN/JP, so grouping by scene_idx is a safe
    reset boundary."""
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
        if e[0] >= ACTIVE_VOICE_TEST_GROUPS:
            continue
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
    en_scena = collect_files(EN_ROOT, 'scena', 'dat_en')
    jp_scena = collect_files(JP_ROOT, 'scena', 'dat')
    en_talk = collect_files(EN_ROOT, 'talk', 'dat_en')
    jp_talk = collect_files(JP_ROOT, 'talk', 'dat')
    print(f'files  EN scena={len(en_scena)}  JP scena={len(jp_scena)}  '
          f'EN talk={len(en_talk)}  JP talk={len(jp_talk)}')

    # Authoritative name/portrait tables from the game's own data files.
    # These supersede any CreateChr display-name heuristics — they are
    # what the game UI actually shows and what haji was mining.
    chr_key_to_id = load_chrid_table(CHRID_TABLE_PATH)
    en_tname = load_tname(EN_TNAME)
    jp_tname = load_tname(JP_TNAME)
    tvoice = load_tvoice(JP_TVOICE)
    print(f't_voice  entries={len(tvoice)}')
    # tk_{name}.py talk files use placeholder chr_ids like 0x1AC3 that
    # aren't in t_name; the real speaker is the file's titular character,
    # recoverable via the name2 field (e.g. 'tovar' -> chrId 0x0019).
    name2_to_chrid = {}
    for cid, e in jp_tname.items():
        n2 = e.get('name2')
        if n2 and n2 not in name2_to_chrid:
            name2_to_chrid[n2] = cid
    print(f'chrId_table  keys={len(chr_key_to_id)}  '
          f'en t_name={len(en_tname)}  jp t_name={len(jp_tname)}  '
          f'name2={len(name2_to_chrid)}')

    cache = {}

    def get(path):
        if path is None:
            return ([], {})
        hit = cache.get(path)
        if hit is None:
            hit = parse_script(path, chr_key_to_id)
            cache[path] = hit
        return hit

    # Pass 1: walk all scena files to prime the cache. CreateChr maps are
    # used only as a fallback for ('id', N) chrIds absent from t_name.
    eng_names, jpn_names = {}, {}
    for path in en_scena.values():
        _, creates = get(path)
        for k, v in creates.items():
            eng_names.setdefault(k, v)
    for path in jp_scena.values():
        _, creates = get(path)
        for k, v in creates.items():
            jpn_names.setdefault(k, v)
    print(f'createchr names  EN={len(eng_names)}  JP={len(jpn_names)}')

    # Voice-prefix bridge: learn `voice_prefix -> known_chr_id` from
    # dialogues with chr_ids that resolve to t_name. Used as a fallback for
    # speakers when char is None (variable expression) or chr_id isn't in
    # t_name. JP scena+talk dialogues are the source — voice_id is
    # language-independent.
    all_jp_dialogues = []
    for path in list(jp_scena.values()) + list(jp_talk.values()):
        d, _ = get(path)
        all_jp_dialogues.append(d)
    voice_prefix_to_known = build_chr_alias(all_jp_dialogues, jp_tname,
                                             chr_key_to_id, tvoice)
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
        """Map a ChrTalk char arg to a numeric chr_id. Talk files use
        placeholder ids (0x1AC3 etc.) for the file's titular speaker;
        when talk_fallback_chrid is set, any chr_id not found in t_name
        falls back to it."""
        if char is None:
            return None
        if char[0] == 'id':
            cid = char[1]
            if cid in jp_tname or cid in en_tname:
                return cid
            # Placeholder like 0x1AC3 — use the talk-file fallback.
            return talk_fallback_chrid
        return chr_key_to_id.get(char[1])

    def talk_fallback(stem):
        """tk_tovar -> chr_id for Toval via name2='tovar'."""
        if not stem.startswith('tk_'):
            return None
        return name2_to_chrid.get(stem[3:])

    def speaker_name(char, override, side_tname, side_create, talk_fb, voice_id=None):
        """Resolve the speaker display name for one side (EN or JP).
        Priority: OP_27 override > t_name[chrId] > CreateChr display
                > voice-prefix bridge > ''."""
        if override:
            return override
        chrid = resolve_chrid(char, talk_fb)
        if chrid is not None and chrid in side_tname:
            return side_tname[chrid]['name']
        if char in side_create:
            return side_create[char]
        return resolve_via_voice(voice_id, side_tname)

    def row_portrait(char, talk_fb, voice_id=None):
        chrid = resolve_chrid(char, talk_fb)
        if chrid is None and voice_id is not None:
            prefix = _voice_prefix(tvoice.get(voice_id, ''))
            chrid = voice_prefix_to_known.get(prefix)
        if chrid is None:
            return None
        entry = jp_tname.get(chrid) or en_tname.get(chrid)
        return portrait_from_tname(entry) if entry else None

    def row_note(char, talk_fb, voice_id=None):
        """Fallback icon for characters without a shipped avfc portrait.
        Note filenames are keyed by model number (same as avfc), not by
        chrId — e.g. Illia has chrId 0x0107 but model C_CHR109, giving
        note_chr109.webp. Strip the C_CHR prefix off the t_name entry's
        model field to build the filename."""
        chrid = resolve_chrid(char, talk_fb)
        if chrid is None and voice_id is not None:
            prefix = _voice_prefix(tvoice.get(voice_id, ''))
            chrid = voice_prefix_to_known.get(prefix)
        if chrid is None:
            return None
        entry = jp_tname.get(chrid) or en_tname.get(chrid)
        if not entry:
            return None
        model = entry.get('model', '')
        if not model.startswith('C_CHR'):
            return None
        suffix = model[len('C_CHR'):].lower()
        if not suffix:
            return None
        # Strip any trailing _c## variant — notes don't carry the outfit
        # suffix that models do; only a base number (plus optional _1).
        base_num = suffix.split('_')[0]
        candidates = (
            f'note_chr{base_num}.webp',
            f'note_chr{base_num}_1.webp',
        )
        for pf in candidates:
            if pf in AVAILABLE_NOTES:
                return pf
        return None

    # Pass 2: emit rows per (kind, stem), pairing EN/JP by position.
    # The `row` column resets to 1 at each new fname (matches haji).
    rows = []
    for kind, en_map, jp_map in (('scena', en_scena, jp_scena),
                                  ('talk', en_talk, jp_talk)):
        stems = sorted(set(en_map) | set(jp_map))
        for stem in stems:
            rownum = 1
            en_d, _ = get(en_map.get(stem))
            jp_d, _ = get(jp_map.get(stem))
            talk_fb = talk_fallback(stem) if kind == 'talk' else None

            pairs = align_scenes(en_d, jp_d)
            unpaired = sum(1 for e, j in pairs if e is None or j is None)
            if unpaired:
                print(f'WARN {kind}/{stem}: {unpaired} unpaired rows '
                      f'(EN={len(en_d)} JP={len(jp_d)})', file=sys.stderr)

            for en_t, jp_t in pairs:
                if en_t:
                    en_scene, en_char, en_parts, _en_kind, en_override, en_voice, en_segs = en_t
                else:
                    en_scene, en_char, en_parts, en_override, en_voice, en_segs = None, None, [], '', None, []
                if jp_t:
                    jp_scene, jp_char, jp_parts, _jp_kind, jp_override, jp_voice, jp_segs = jp_t
                else:
                    jp_scene, jp_char, jp_parts, jp_override, jp_voice, jp_segs = None, None, [], '', None, []
                scene = jp_scene if jp_scene is not None else (en_scene if en_scene is not None else 0)

                vid = jp_voice or en_voice
                # Speakers: t_name[chrId] is authoritative; OP_27 overrides
                # it for context-specific labels (e.g. '《Ｃ》', '謎の声').
                en_raw = speaker_name(en_char, en_override, en_tname, eng_names, talk_fb, voice_id=vid)
                jp_raw = speaker_name(jp_char, jp_override, jp_tname, jpn_names, talk_fb, voice_id=vid)
                # Cross-side fallback when one side's char is absent (only
                # when both sides actually have dialogue — don't synthesize
                # a name on a side that has no text).
                if en_t and jp_t:
                    if not en_raw and jp_char:
                        en_raw = speaker_name(jp_char, '', en_tname, eng_names, talk_fb, voice_id=vid)
                    if not jp_raw and en_char:
                        jp_raw = speaker_name(en_char, '', jp_tname, jpn_names, talk_fb, voice_id=vid)
                eng_chr = normalize_name(en_raw)
                jpn_chr = normalize_name(jp_raw)

                pfile = (row_portrait(jp_char, talk_fb, voice_id=vid)
                         or row_portrait(en_char, talk_fb, voice_id=vid))
                # Masked-Rufus override: when an OP_27 latch has aliased
                # Rufus (chr_id 0x002C) to '《Ｃ》' / 'C', use the masked
                # face sprite (avfc112.webp) instead of his unmasked one
                # (avfc112_c00.webp). Reverie ships only those two
                # Rufus-related sprites so this is a hard mapping.
                if pfile == 'avfc112_c00.webp' and (jp_raw == '《Ｃ》' or en_raw == 'C'):
                    pfile = 'avfc112.webp'
                if pfile:
                    pc_icon = f'<img class="itp-face3" src="itp/10/{pfile}"/>'
                else:
                    nfile = (row_note(jp_char, talk_fb, voice_id=vid)
                             or row_note(en_char, talk_fb, voice_id=vid))
                    pc_icon = f'<img class="itp-note3" src="itp/10/{nfile}"/>' if nfile else ''

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
    # (I_AVFC042 -> avfc042.webp) is what the game shows beside the line.
    rownum = 1
    for scene, exchange in enumerate(active_voice_exchanges(), start=1):
        for en_av, jp_av in exchange:
            _, _, _, portrait, vid, cid, en_text = en_av
            jp_text = jp_av[6]
            char = ('id', cid)
            eng_chr = normalize_name(en_tname.get(cid, {}).get('name', ''))
            jpn_chr = normalize_name(jp_tname.get(cid, {}).get('name', ''))
            jp_html = clean_text([jp_text], '<br/>')
            vfile = tvoice.get(vid)
            if vfile:
                jp_html = voice_wrap(jp_html, vfile)
            pfile = portrait[len('I_'):].lower() + '.webp'
            if pfile not in AVAILABLE_PORTRAITS:
                pfile = row_portrait(char, None)
            if pfile:
                pc_icon = f'<img class="itp-face3" src="itp/10/{pfile}"/>'
            else:
                nfile = row_note(char, None)
                pc_icon = f'<img class="itp-note3" src="itp/10/{nfile}"/>' if nfile else ''
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
