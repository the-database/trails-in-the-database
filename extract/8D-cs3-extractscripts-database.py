"""Extract Trails of Cold Steel III (game 8) dialogue into sen3.sql.

Decompiled-source variant of the original 8-cs3 extractor, modeled on
9D-sen4. Parses Decompiler2 (ED83) Python output for both EN and JP
scripts via ast walk — no execution. Extracts ChrTalk(...) (speaker-
tagged), Talk(0xFFFF, ...) (anonymous narration), and OP_27 latched
name overrides. Animation-trigger Talk() calls are filtered. EN/JP rows
are paired by LCS on (scene, kind, char) within each file.

CS3 uses the ED83 engine. Portrait icons follow a different naming
scheme from CS4: `avf{chrId * 10:04d}.webp` rather than CS4's
`avfc<face_texture_suffix>.webp`.
"""

import ast
import os
import re
import sys

FALCOM_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'Falcom')
DATA_ROOT = os.path.join(FALCOM_ROOT, 'data', 'cs3')
SCRIPTS_ROOT = os.path.join(DATA_ROOT, 'scripts')
EN_TNAME = os.path.join(DATA_ROOT, 'text', 'dat_en', 't_name.py')
JP_TNAME = os.path.join(DATA_ROOT, 'text', 'dat', 't_name.py')
JP_TVOICE = os.path.join(DATA_ROOT, 'text', 'dat', 't_voice.py')
CHRID_TABLE_PATH = os.path.join(FALCOM_ROOT, 'Decompiler2', 'Falcom', 'ED83', 'Metadata', 'chrId_table.py')
GAME_ID = 8
OUTPUT = 'sen3.sql'

# Template/system files whose dialogue is boilerplate. Empty for now —
# add stems here if a known-bad template file is found polluting output.
SKIP_STEMS = set()

# Portrait sprites shipped at itp/8/{file}. Snapshot of
# Ingert/data/cs3/png x4 (the re-extracted set). CS3 uses
# `avf{chrId * 10:04d}.webp` keyed off chr_id alone — no costume
# variants. Only main cast / important NPCs get an avf portrait.
AVAILABLE_PORTRAITS = {
    'avf0000.webp', 'avf0010.webp', 'avf0020.webp', 'avf0030.webp',
    'avf0040.webp', 'avf0050.webp', 'avf0060.webp', 'avf0070.webp',
    'avf0080.webp', 'avf0090.webp', 'avf0100.webp', 'avf0110.webp',
    'avf0120.webp', 'avf0130.webp', 'avf0140.webp', 'avf0150.webp',
    'avf0160.webp', 'avf0170.webp', 'avf0180.webp', 'avf0190.webp',
    'avf0200.webp', 'avf0210.webp', 'avf0220.webp', 'avf0230.webp',
    'avf0240.webp', 'avf0250.webp', 'avf0260.webp',
    'avf0600.webp',
    'avf1200.webp', 'avf1210.webp', 'avf1230.webp',
    'avf1410.webp', 'avf1520.webp', 'avf1530.webp',
    'avf2010.webp', 'avf2020.webp', 'avf2030.webp', 'avf2040.webp',
    'avf2080.webp',
    'avf8000.webp',
}

# Smaller "note" icons for characters lacking a full avf portrait.
# Filenames key off the model number (C_CHR<N> -> note_chr<N>.webp).
AVAILABLE_NOTES = {
    'note_chr000.webp', 'note_chr001.webp', 'note_chr002.webp',
    'note_chr003.webp', 'note_chr004.webp', 'note_chr005.webp',
    'note_chr006.webp', 'note_chr007.webp', 'note_chr008.webp',
    'note_chr009.webp', 'note_chr010.webp', 'note_chr011.webp',
    'note_chr012.webp', 'note_chr013.webp', 'note_chr015.webp',
    'note_chr016.webp', 'note_chr017.webp', 'note_chr018.webp',
    'note_chr019.webp', 'note_chr021.webp', 'note_chr023.webp',
    'note_chr024.webp', 'note_chr025.webp', 'note_chr027.webp',
    'note_chr029.webp', 'note_chr040.webp', 'note_chr041.webp',
    'note_chr042.webp',
    'note_chr043.webp', 'note_chr043_1.webp',
    'note_chr044.webp', 'note_chr046.webp', 'note_chr050.webp',
    'note_chr058.webp', 'note_chr063.webp', 'note_chr067.webp',
    'note_chr072.webp',
    'note_chr200.webp', 'note_chr201.webp', 'note_chr202.webp',
    'note_chr203.webp', 'note_chr204.webp', 'note_chr205.webp',
    'note_chr206.webp', 'note_chr210.webp', 'note_chr211.webp',
    'note_chr212.webp', 'note_chr213.webp', 'note_chr214.webp',
    'note_chr600.webp', 'note_chr601.webp', 'note_chr602.webp',
    'note_chr603.webp', 'note_chr604.webp', 'note_chr605.webp',
    'note_chr606.webp', 'note_chr610.webp', 'note_chr611.webp',
    'note_chr612.webp', 'note_chr613.webp', 'note_chr614.webp',
    'note_chr615.webp', 'note_chr621.webp', 'note_chr628.webp',
    'note_chr955.webp',
}

CONTROL_CODE_RE = re.compile(
    r'#OT|#[A-Za-z](?:_[0-9A-Za-z]|\[[A-Za-z0-9]+\])?'
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
# Ruby (furigana) markup: `記憶結晶#8Rメモリークオーツ#` — digit before R is
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
    content tuple, or None. New code should use _extract_segments to get
    per-paragraph voice IDs instead."""
    for v, _ in _extract_segments(node):
        if v is not None:
            return v
    return None


def _extract_segments(node):
    """Walk a ChrTalk/Talk content tuple in source order and yield
    (voice_id_or_None, [text_parts]) per paragraph.

    A `(TxtCtl.Voice, N)` tuple opens a new paragraph and sets that
    paragraph's voice. `TxtCtl.Clear` ends a paragraph (the next text
    starts a new one without changing voice). String literals accumulate
    into the current paragraph. Empty/no-text paragraphs are dropped.

    Multi-paragraph dialogue with one voice per paragraph (Siegfried's
    f1000 line: 0x8EF6/7/8) becomes three segments — main() voice-wraps
    each one independently so all three audio links work."""
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
    # Drop segments that ended up empty (no text and no voice).
    return [(v, p) for v, p in segments if p or v is not None]


def _is_scena_code_decorated(func):
    for dec in func.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr == 'Code':
            return True
    return False


def is_animation_trigger(parts):
    """Talk(0xFFFF, ...) calls sometimes carry animation-engine control
    strings rather than narration. They contain literal backslash-n pairs
    or engine tokens. Filter those out."""
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
      dialogues: list of (scene_idx, char, text_parts, kind, override, voice)
        kind is 'chr' (ChrTalk) or 'anon' (Talk); override is the speaker
        name resolved from a preceding OP_27 or ''.

    OP_27 semantics:
      OP_27(name, 0xFFFF) — single-shot: applies to the next dialogue.
      OP_27(name, <real chr_id>) — latched: applies to every subsequent
        dialogue whose character resolves to the same chr_id, until
        overwritten by another OP_27 for the same chr_id within this
        function. Resets at function boundaries.

    chr_key_to_id bridges ChrTable['<name>'] keys to numeric chr_ids so
    latched names can attach to key-based ChrTalks.
    """
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        print(f'WARN: syntax error in {path}: {e}', file=sys.stderr)
        return [], {}

    dialogues = []
    createchr_names = {}
    scene_idx = -1
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and _is_scena_code_decorated(node)):
            continue
        scene_idx += 1
        latched = {}       # chr_id -> name (persists until re-overwritten)
        pending_anon = ''  # OP_27 with 0xFFFF: consumed by next dialogue
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
                # CS3 has debug ChrTalk calls whose only text is an animation
                # token (e.g. ChrTalk(0x0451, ..., ('AniEvSitSian', TxtCtl.Enter))).
                # Filter them the same way as anonymous Talk().
                if is_animation_trigger(parts):
                    pending_anon = ''
                    continue
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

    # Drop adjacent voiced duplicates: branching Jump/label structure
    # emits the same logical line N times across alternate branches (only
    # one runs at runtime). Same heuristic as Reverie — only dedup when
    # both prev and current carry voice IDs.
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
    (no extension)."""
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
        f'data-audio="talk/{GAME_ID}/{voice_file}.opus">'
        f'{html_text}</a>'
    )


def render_html_segments(segments, tvoice=None):
    """Render (voice_id, [text_parts]) segments into HTML. Each
    paragraph is independently voice-wrapped (when `tvoice` is given
    and the segment has a voice id), then paragraphs join with
    `<br/><br/>` so the rendered output mirrors the original paragraph
    breaks. Pass `tvoice=None` for sides without voice (EN)."""
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
    """Plain-text version of render_html_segments — paragraphs are
    joined with a single space so e.g. 'Sentence one.' and 'Sentence
    two.' don't get glued into 'Sentence one.Sentence two.' in the
    search-text column."""
    pieces = []
    for _vid, parts in segments:
        text = clean_text(parts, ' ')
        if text:
            pieces.append(text)
    return ' '.join(pieces)


def load_chrid_table(path):
    """Parse Decompiler2's chrId_table.py: string -> int dict
    (Chinese name -> numeric chrId)."""
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
    """Parse a t_name.py file. Returns dict chr_id ->
    {'name', 'model', 'faceTexture', 'name2'}. First entry per chr_id
    wins; outfit variants (chrId=0xFFFF) are skipped."""
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


def portrait_from_chrid(chrid):
    """Derive avf portrait filename from a chr_id. CS3 names portraits
    `avf{chrId * 10:04d}.webp` — Rean (0x0000) -> avf0000.webp,
    Patrick (0x001A=26) -> avf0260.webp."""
    if chrid is None:
        return None
    pf = f'avf{chrid * 10:04d}.webp'
    return pf if pf in AVAILABLE_PORTRAITS else None


def note_from_tname(entry):
    """Fallback note icon from a t_name entry's model field
    (C_CHR045 -> note_chr045.webp)."""
    model = entry.get('model', '')
    if not model.startswith('C_CHR'):
        return None
    suffix = model[len('C_CHR'):].lower()
    if not suffix:
        return None
    base_num = suffix.split('_')[0]
    candidates = (
        f'note_chr{base_num}.webp',
        f'note_chr{base_num}_1.webp',
    )
    for pf in candidates:
        if pf in AVAILABLE_NOTES:
            return pf
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
    # Ruby must run before LEFTOVER_CODE_RE strips the `#NR` opener
    # and orphans the reading + closing `#`.
    text = _apply_ruby(text, html=(newline == '<br/>'))
    text = CONTROL_CODE_RE.sub('', text)
    text = LEFTOVER_CODE_RE.sub('', text)
    text = strip_junk_brackets(text)
    # Stray `#` chars (e.g. the separator in `#2K##2F`) survive both
    # regexes — drop them.
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
    """List .py files under SCRIPTS_ROOT/<parts...>, returning {stem: full_path}.

    Skips Windows-rename duplicates like 'm1310 (1).py' — their identifiers
    contain spaces/parens and won't parse anyway.
    """
    d = os.path.join(SCRIPTS_ROOT, *parts)
    if not os.path.isdir(d):
        return {}
    return {
        entry[:-3]: os.path.join(d, entry)
        for entry in os.listdir(d)
        if entry.endswith('.py')
        and ' ' not in entry
        and entry[:-3] not in SKIP_STEMS
    }


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def _voice_prefix(filename):
    """Voice filenames look like `v01_s0044`, `e8v59999`. Return
    everything before the first underscore (or the whole name)."""
    if not filename:
        return ''
    us = filename.find('_')
    return filename[:us] if us > 0 else filename


def build_chr_alias(parsed_files, jp_tname, chr_key_to_id, tvoice):
    """Learn `voice_prefix -> known_chr_id` from dialogues with chr_ids
    that resolve to t_name. Used as a last-ditch speaker fallback when
    char is None or its chrId is absent from t_name."""
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
    """LCS alignment on (scene_idx, kind, char) signatures. Returns
    (a_item_or_None, b_item_or_None) pairs in original order."""
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
    """Align dialogues scene-by-scene via LCS on (scene_idx, kind, char)."""
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
    en_scena = collect_files('scena', 'dat_en')
    jp_scena = collect_files('scena', 'dat')
    en_talk = collect_files('talk', 'dat_en')
    jp_talk = collect_files('talk', 'dat')
    print(f'files  EN scena={len(en_scena)}  JP scena={len(jp_scena)}  '
          f'EN talk={len(en_talk)}  JP talk={len(jp_talk)}')

    chr_key_to_id = load_chrid_table(CHRID_TABLE_PATH)
    en_tname = load_tname(EN_TNAME)
    jp_tname = load_tname(JP_TNAME)
    tvoice = load_tvoice(JP_TVOICE)
    print(f't_voice  entries={len(tvoice)}')
    # tk_{name}.py files use placeholder chr_ids; the real speaker is the
    # file's titular character, recoverable via the t_name name2 field.
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

    # Pass 1: walk scena files to collect CreateChr display names.
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

    # Voice-prefix bridge for fallback speaker resolution.
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
        if char is None:
            return None
        if char[0] == 'id':
            cid = char[1]
            if cid in jp_tname or cid in en_tname:
                return cid
            return talk_fallback_chrid
        return chr_key_to_id.get(char[1])

    def talk_fallback(stem):
        """tk_<name2> -> chrId. e.g. tk_rean -> 0x0000."""
        if not stem.startswith('tk_'):
            return None
        return name2_to_chrid.get(stem[3:])

    def speaker_name(char, override, side_tname, side_create, talk_fb, voice_id=None):
        """Priority: OP_27 override > t_name[chrId] > CreateChr display
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
        return portrait_from_chrid(chrid)

    def row_note(char, talk_fb, voice_id=None):
        chrid = resolve_chrid(char, talk_fb)
        if chrid is None and voice_id is not None:
            prefix = _voice_prefix(tvoice.get(voice_id, ''))
            chrid = voice_prefix_to_known.get(prefix)
        if chrid is None:
            return None
        entry = jp_tname.get(chrid) or en_tname.get(chrid)
        return note_from_tname(entry) if entry else None

    # Pass 2: emit rows per (kind, stem), pairing EN/JP via LCS.
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
                en_raw = speaker_name(en_char, en_override, en_tname, eng_names, talk_fb, voice_id=vid)
                jp_raw = speaker_name(jp_char, jp_override, jp_tname, jpn_names, talk_fb, voice_id=vid)
                # Cross-side fallback when one side's char is absent.
                if en_t and jp_t:
                    if not en_raw and jp_char:
                        en_raw = speaker_name(jp_char, '', en_tname, eng_names, talk_fb, voice_id=vid)
                    if not jp_raw and en_char:
                        jp_raw = speaker_name(en_char, '', jp_tname, jpn_names, talk_fb, voice_id=vid)
                eng_chr = normalize_name(en_raw)
                jpn_chr = normalize_name(jp_raw)

                en_search = render_search_segments(en_segs) if en_segs else clean_text(en_parts, ' ')
                en_html = render_html_segments(en_segs) if en_segs else clean_text(en_parts, '<br/>')
                jp_search = render_search_segments(jp_segs) if jp_segs else clean_text(jp_parts, ' ')
                jp_html = render_html_segments(jp_segs, tvoice) if jp_segs else clean_text(jp_parts, '<br/>')

                pfile = (row_portrait(jp_char, talk_fb, voice_id=vid)
                         or row_portrait(en_char, talk_fb, voice_id=vid))
                if pfile:
                    pc_icon = f'<img class="itp-face3" src="itp/{GAME_ID}/{pfile}"/>'
                else:
                    nfile = (row_note(jp_char, talk_fb, voice_id=vid)
                             or row_note(en_char, talk_fb, voice_id=vid))
                    pc_icon = f'<img class="itp-note3" src="itp/{GAME_ID}/{nfile}"/>' if nfile else ''

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
