"""Extract Trails through Daybreak (game 11) dialogue into daybreak.sql.

Parses .ing files decompiled by Ingert. Dialogue is expressed as
`system[5,6](chrId, ..., text, ...)` calls with text lines inline;
speaker-name overrides use `chr_set_display_name(chrId, "name")`. Each
top-level `fn name()` is a scene. Line-number labels (`NNN@`) are
stripped before parsing.

Differences from db2/horizon:
  - EN/JP script roots: `daybreak.ing/script_en`, `daybreak.ing/script`
  - Portrait inventory: 22 avfc + 105 btlface; no noteface, no _c15/_c10
    variants exist in the game
  - Portrait priority: exact model match → bare → any other variant

Active voice (the party banter that plays on the field) comes from
t_active_voice.tbl and goes in as one more file, `active_voice`; see
active_voice_exchanges.
"""

import ast
import json
import os
import re
import sys

DAYBREAK_SCRIPT_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'Ingert', 'data', 'daybreak.ing')
DAYBREAK_TBL_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'KuroTools', 'daybreak1_extract')
EN_ROOT = os.path.join(DAYBREAK_SCRIPT_ROOT, 'script_en')
JP_ROOT = os.path.join(DAYBREAK_SCRIPT_ROOT, 'script')
EN_TNAME = os.path.join(DAYBREAK_TBL_ROOT, 'en_json', 't_name.json')
JP_TNAME = os.path.join(DAYBREAK_TBL_ROOT, 'jp_json', 't_name.json')
JP_TVOICE = os.path.join(DAYBREAK_TBL_ROOT, 'jp_json', 't_voice.json')
GAME_ID = 11
OUTPUT = 'daybreak.sql'

# t_active_voice.tbl from the Steam release, staged with the books under
# KuroTools/books_20261017 (see kuro-extractbooks-database.py) and converted
# with `python tbl2json.py t_active_voice.tbl`.
ACTIVE_VOICE_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'KuroTools', 'books_20261017', 'daybreak')
EN_ACTIVE = os.path.join(ACTIVE_VOICE_ROOT, 'en', 't_active_voice.json')
JP_ACTIVE = os.path.join(ACTIVE_VOICE_ROOT, 'jp', 't_active_voice.json')
ACTIVE_VOICE_FNAME = 'active_voice'
# Groups from here up are test entries after the game's own, never played:
# 'Test 1' / 'Test 2' and a few sample exchanges.
ACTIVE_VOICE_TEST_GROUPS = 99990

# 0xFFFE / 0xFFFF are engine sentinels for anonymous narration. Daybreak's
# t_name has hundreds of stray entries under character_id=65535 (all outfit
# variants catalog). Skip name + portrait lookup for these; latched
# overrides still apply.
ANONYMOUS_CHR_IDS = frozenset({0xFFFE, 0xFFFF})

# Subdirs under each script root that contain real dialogue. `battle`,
# `obj`, `ai` have zero `system[5,6]` calls and are skipped.
DIALOGUE_SUBDIRS = ('scena', 'cutscene', 'minigame', 'ani')

# Full face portraits (22 files in itp x4/*.webp — already webp).
AVAILABLE_PORTRAITS = {
    'avfc0000.webp', 'avfc0002.webp', 'avfc0004.webp', 'avfc0006.webp',
    'avfc0111.webp', 'avfc0112.webp', 'avfc0113.webp',
    'avfc0301.webp', 'avfc0304.webp',
    'avfc5001.webp', 'avfc5001_c03.webp',
    'avfc5003.webp', 'avfc5005.webp',
    'avfc5007.webp', 'avfc5007_c03.webp',
    'avfc5008.webp',
    'avfc5110.webp', 'avfc5112.webp',
    'avfc5113.webp', 'avfc5113_c00.webp',
    'avfc5117.webp', 'avfc5118.webp',
}

# Battle faces (105 files) — fallback when no avfc matches.
AVAILABLE_BTLFACE = {
    'btlface0_c0000.webp', 'btlface0_c0002.webp', 'btlface0_c0002_1.webp',
    'btlface0_c0004.webp', 'btlface0_c0006.webp',
    'btlface0_c0009.webp', 'btlface0_c0009_c00.webp',
    'btlface0_c0111.webp', 'btlface0_c0112.webp', 'btlface0_c0113.webp',
    'btlface0_c0114.webp',
    'btlface0_c0115.webp', 'btlface0_c0115_c00.webp', 'btlface0_c0115_c02.webp',
    'btlface0_c0116.webp', 'btlface0_c0116_c02.webp',
    'btlface0_c0117.webp',
    'btlface0_c0299.webp',
    'btlface0_c0301.webp', 'btlface0_c0302.webp', 'btlface0_c0302_1.webp',
    'btlface0_c0304.webp', 'btlface0_c0316.webp', 'btlface0_c0318.webp',
    'btlface0_c0328.webp', 'btlface0_c0329.webp',
    'btlface0_c0500.webp', 'btlface0_c0501.webp', 'btlface0_c0503.webp',
    'btlface0_c0510a.webp', 'btlface0_c0660_c01a.webp',
    'btlface0_c0712.webp',
    'btlface0_c0725.webp', 'btlface0_c0725_c01.webp',
    'btlface0_c0725_c02.webp', 'btlface0_c0725_c03.webp',
    'btlface0_c0726.webp', 'btlface0_c0726_c01.webp',
    'btlface0_c0726_c01_p1.webp', 'btlface0_c0726_p1.webp',
    'btlface0_c0727.webp', 'btlface0_c0727_c01.webp',
    'btlface0_c0750.webp',
    'btlface0_c0765.webp', 'btlface0_c0765_c01.webp',
    'btlface0_c0770.webp', 'btlface0_c0770_c01.webp',
    'btlface0_c0785.webp', 'btlface0_c0785_c03.webp',
    'btlface0_c0785_p1.webp', 'btlface0_c0785_w2.webp',
    'btlface0_c0785a_c03.webp', 'btlface0_c0785a_p1.webp',
    'btlface0_c0785a_w1.webp', 'btlface0_c0785a_w3.webp',
    'btlface0_c0786.webp', 'btlface0_c0786_c03.webp',
    'btlface0_c0786_p1.webp', 'btlface0_c0786_w2.webp',
    'btlface0_c0786a_c03.webp', 'btlface0_c0786a_p1.webp',
    'btlface0_c0786a_w1.webp', 'btlface0_c0786a_w3.webp',
    'btlface0_c0787.webp', 'btlface0_c0787_c03.webp',
    'btlface0_c0787_p1.webp', 'btlface0_c0787_w2.webp',
    'btlface0_c0787a_p1.webp', 'btlface0_c0787a_w1.webp',
    'btlface0_c0787a_w3.webp',
    'btlface0_c0790.webp', 'btlface0_c0790_c01.webp',
    'btlface0_c0791.webp', 'btlface0_c0791_c01.webp',
    'btlface0_c0795.webp', 'btlface0_c0795_c01.webp',
    'btlface0_c0800.webp', 'btlface0_c0831_c01.webp',
    'btlface0_c0832.webp',
    'btlface0_c5001.webp', 'btlface0_c5001_c03.webp',
    'btlface0_c5003.webp', 'btlface0_c5005.webp',
    'btlface0_c5007.webp', 'btlface0_c5007_c03.webp',
    'btlface0_c5007_c03_1.webp',
    'btlface0_c5110.webp', 'btlface0_c5112.webp',
    'btlface0_c5113.webp', 'btlface0_c5113_c00.webp',
    'btlface0_c5115.webp', 'btlface0_c5116.webp',
    'btlface0_c5117.webp', 'btlface0_c5118.webp',
    'btlface0_c5300.webp', 'btlface0_c5300_1.webp',
    'btlface0_c5301.webp',
    'btlface0_c5311.webp', 'btlface0_c5313.webp', 'btlface0_c5319.webp',
    'btlface0_c5511b.webp', 'btlface0_c5541_c01.webp',
    'btlface0_c5680.webp', 'btlface0_c5710.webp', 'btlface0_c5711.webp',
}

ANGLE_TAG_RE = re.compile(r'<[^>]*>')
WHITESPACE_RE = re.compile(r'[ \t]+')

# Furigana: `<R>翠耀石</Rエスメラス>` — base between `<R>` and `</R`, reading
# before the closing `>`.
#
# Both halves are deliberately confined to one string argument (`[^"<>]`).
# `<R>` doubles as a plain formatting code, and every JP script carries a
# handful of unclosed ones (e.g. `"<C1><R>おや、村は…"`). A `.*?` match would
# sail past those into the *next* dialogue call and swallow hundreds of
# characters of unrelated text before finding some later `</R`.
RUBY_RE = re.compile(r'<R>([^"<>]*)</R([^"<>]*)>')

# Furigana has to outlive ANGLE_TAG_RE so that clean_text() can render it
# differently per column, so it is parked behind sentinels first. \x01-\x03
# occur nowhere in the game text.
RUBY_OPEN, RUBY_SEP, RUBY_CLOSE = '\x01', '\x02', '\x03'
RUBY_MARK_RE = re.compile(r'\x01([^\x01-\x03]*)\x02([^\x01-\x03]*)\x03')
LABEL_RE = re.compile(r'\d+@')
FN_HEADER_RE = re.compile(r'(?m)^fn\s+(\w+)\s*\(')
DIALOGUE_CALL_RE = re.compile(r'\bsystem\s*\[\s*5\s*,\s*(?:0|6|8)\s*\]\s*\(')
DISPLAY_NAME_CALL_RE = re.compile(r'\bchr_set_display_name\s*\(')

# EN decompile-only artifact: `if sound_get_voice_language() == 0 { A }
# else { B }` branches the unvoiced-fallback path (A) against the voiced
# path (B). Both branches often contain the same dialogue text, which
# counts as 2 dialogues to my extractor and double-counts versus the JP
# side (which has no such branching). Suppress the `== 0` branch so only
# the voiced path (else) contributes a row.
VOICE_LANG_IF_RE = re.compile(r'\bif\s+sound_get_voice_language\s*\(\s*\)\s*==\s*0\s*\{')


def _find_balanced(s, open_paren_idx, open_char='(', close_char=')'):
    """Given position of `open_char` in s, return index AFTER the matching
    `close_char`. String literals are respected. -1 if unmatched."""
    depth = 0
    i = open_paren_idx
    in_str = None
    escape = False
    n = len(s)
    while i < n:
        c = s[i]
        if in_str:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == in_str:
                in_str = None
        else:
            if c == '"' or c == "'":
                in_str = c
            elif c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return -1


def _voice_lang_suppress_ranges(src):
    """Spans to skip during event collection. Covers the body of every
    `if sound_get_voice_language() == 0 { ... }` block (the unvoiced
    fallback branch — see VOICE_LANG_IF_RE comment)."""
    ranges = []
    for m in VOICE_LANG_IF_RE.finditer(src):
        brace_open = m.end() - 1
        brace_close = _find_balanced(src, brace_open, '{', '}')
        if brace_close != -1:
            ranges.append((m.start(), brace_close))
    return ranges


def _const_value(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
            return -node.operand.value
    return None


def _parse_call_args(call_text):
    try:
        tree = ast.parse(call_text, mode='eval')
    except SyntaxError:
        return None
    if not isinstance(tree.body, ast.Call):
        return None
    return tree.body.args


def parse_script(path):
    """Parse one .ing file. Same logic as horizon's extractor."""
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    src = LABEL_RE.sub('', src)

    suppress = _voice_lang_suppress_ranges(src)

    def _in_suppress(pos):
        for s_, e_ in suppress:
            if s_ <= pos < e_:
                return True
        return False

    events = []
    for m in FN_HEADER_RE.finditer(src):
        events.append((m.start(), 'fn', None))
    for m in DIALOGUE_CALL_RE.finditer(src):
        if _in_suppress(m.start()):
            continue
        end = _find_balanced(src, m.end() - 1)
        if end != -1:
            events.append((m.start(), 'dialogue', src[m.start():end]))
    for m in DISPLAY_NAME_CALL_RE.finditer(src):
        if _in_suppress(m.start()):
            continue
        end = _find_balanced(src, m.end() - 1)
        if end != -1:
            events.append((m.start(), 'set_name', src[m.start():end]))
    events.sort(key=lambda e: e[0])

    dialogues = []
    scene_idx = -1
    latched = {}

    for _pos, kind, payload in events:
        if kind == 'fn':
            scene_idx += 1
            latched = {}
            continue
        if scene_idx < 0:
            continue
        args = _parse_call_args(payload)
        if args is None:
            continue

        if kind == 'set_name':
            if len(args) >= 2:
                cid = _const_value(args[0])
                nm = _const_value(args[1])
                if isinstance(cid, int) and isinstance(nm, str):
                    # Empty name = the game's "reset to the real name"
                    # signal; clear the latch instead of ignoring it.
                    if nm:
                        latched[cid] = nm
                    else:
                        latched.pop(cid, None)
            continue

        if kind == 'dialogue':
            decoded = _decode_dialogue(args)
            if decoded:
                chr_id, lines, voice_id = decoded
                override = latched.get(chr_id, '')
                dialogues.append((scene_idx, chr_id, lines, voice_id, override))

    return dialogues


def _decode_dialogue(args):
    """Decode system[5,6](...) args. First arg is chrId; remaining mix of
    text strings, pure control strings, `11, voice_id` voice pair, and
    integer separators."""
    if not args:
        return None
    chr_id = _const_value(args[0])
    # Variable chr_id (e.g. `var0`) — keep dialogue, resolve via voice prefix.
    if not isinstance(chr_id, int):
        chr_id = None

    lines = []
    voice_id = None
    i = 1
    while i < len(args):
        v = _const_value(args[i])
        if isinstance(v, str):
            # Park furigana first; whatever `<R>` survives that pass was a
            # formatting code, and gets stripped like any other tag.
            cleaned = ANGLE_TAG_RE.sub('', _mark_ruby(v)).strip()
            if cleaned:
                lines.append(cleaned)
        elif isinstance(v, int) and v == 11 and i + 1 < len(args):
            nxt = _const_value(args[i + 1])
            if isinstance(nxt, int):
                voice_id = nxt
                i += 1
        i += 1

    if not lines:
        return None
    return chr_id, lines, voice_id


def load_tname(path):
    with open(path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    out = {}
    for block in doc.get('data', []):
        for entry in block.get('data', []):
            cid = entry.get('character_id')
            if cid is None or cid in out:
                continue
            nm = entry.get('name', '') or ''
            if '_' in nm and ' ' not in nm:
                continue
            out[cid] = {
                'name': nm,
                'full_name': entry.get('full_name') or '',
                'full_name_en': entry.get('full_name_en') or '',
                'model': entry.get('model') or '',
                'face': entry.get('face') or '',
            }
    return out


def load_tvoice(path):
    with open(path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    out = {}
    for block in doc.get('data', []):
        for entry in block.get('data', []):
            vid = entry.get('id')
            fn = entry.get('filename')
            if vid is None or not fn or vid in out:
                continue
            out[vid] = fn
    return out


def _resolve_tier(stem, suffix, inventory, prefix):
    """Priority ladder within a single tier (avfc or btlface0_c).
      1. {prefix}{suffix} — exact model match (respects the variant the
         game says the character is wearing)
      2. {prefix}{stem}   — bare (base outfit)
      3. Any other {prefix}{stem}_* — lowest sorts first
    Daybreak has no _c15/_c10 variants, so no special outfit priority."""
    tried = [
        f'{prefix}{suffix}.webp',
        f'{prefix}{stem}.webp',
    ]
    for c in tried:
        if c in inventory:
            return c
    variants = sorted(p for p in inventory
                      if p.startswith(f'{prefix}{stem}_') and p not in tried)
    if variants:
        return variants[0]
    return None


def portrait_for(entry):
    """Tier order: avfc → btlface. No noteface tier in daybreak."""
    if not entry:
        return None, None
    model = entry.get('model') or ''
    if not model.startswith('chr'):
        return None, None
    suffix = model[len('chr'):]
    if not suffix:
        return None, None
    stem = suffix.split('_')[0]

    pf = _resolve_tier(stem, suffix, AVAILABLE_PORTRAITS, 'avfc')
    if pf:
        return pf, 'face'
    pf = _resolve_tier(stem, suffix, AVAILABLE_BTLFACE, 'btlface0_c')
    if pf:
        return pf, 'btl'
    return None, None


def pc_icon_html(filename, tier):
    if not filename:
        return ''
    cls = {'face': 'itp-kuro', 'btl': 'itp-btlface'}[tier]
    return f'<img class="{cls}" src="itp/{GAME_ID}/{filename}"/>'


def voice_wrap(html_text, voice_file):
    return (
        f'<a href="javascript:void(0)" class="dialogue-line" '
        f'data-audio="talk/{GAME_ID}/{voice_file}.opus">'
        f'{html_text}</a>'
    )


def _mark_ruby(text):
    """Park `<R>base</Rreading>` furigana behind sentinels.

    Called before the generic tag strip so ANGLE_TAG_RE cannot eat the
    reading, which lives inside the closing tag rather than between the tags.
    """
    def park(m):
        base, reading = m.group(1).strip(), m.group(2).strip()
        # `<R>本題</R>` with no reading is emphasis markup, not furigana —
        # keep the base and drop the tags rather than emit an empty <rt>.
        #
        # Trim both halves: a padded base (`<R> Ｂ Ｏ Ｅ</R…>`) used to be
        # trimmed along with the whole argument, and parking the padding
        # inside the sentinel would put it out of reach of the whitespace
        # collapse and double a space in the search column.
        if not reading or not base:
            return m.group(1)
        return RUBY_OPEN + base + RUBY_SEP + reading + RUBY_CLOSE

    return RUBY_RE.sub(park, text)


def _render_ruby(text, html):
    """Resolve parked furigana into the shape each column wants.

    HTML gets `<ruby>base<rt>reading</rt></ruby>`; the search column keeps the
    base alone, so a search for 翠耀石 still hits and the reading does not
    pollute the text. Matches what games 1-10 already emit.
    """
    if html:
        text = RUBY_MARK_RE.sub(r'<ruby>\1<rt>\2</rt></ruby>', text)
    else:
        text = RUBY_MARK_RE.sub(r'\1', text)
    # Belt and braces: a sentinel must never reach the database.
    for ch in (RUBY_OPEN, RUBY_SEP, RUBY_CLOSE):
        text = text.replace(ch, '')
    return text


def clean_text(lines, joiner):
    text = joiner.join(line.strip() for line in lines if line.strip())
    if joiner == ' ':
        text = WHITESPACE_RE.sub(' ', text)
    # Decompiler mismaps Shift-JIS NEC `♥` (0x87 0x9D) onto `㈱`
    # (0x87 0x9F) — both bytes are CP932 NEC special chars and the
    # lookup is off by one. Patch back here before emit.
    text = text.replace('㈱', '♥')
    text = _render_ruby(text, html=(joiner == '<br/>'))
    return text.strip()


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def collect_files(root):
    out = {}
    for sub in DIALOGUE_SUBDIRS:
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for entry in os.listdir(d):
            if not entry.endswith('.ing'):
                continue
            stem = entry[:-4]
            out.setdefault(stem, os.path.join(d, entry))
    return out


def _lcs_pairs(a, b):
    """LCS alignment on (scene_idx, chr_id) signatures."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n):
        ai = (a[i][0], a[i][1])
        for j in range(m):
            if ai == (b[j][0], b[j][1]):
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])
    out = []
    i, j = n, m
    while i > 0 and j > 0:
        if (a[i - 1][0], a[i - 1][1]) == (b[j - 1][0], b[j - 1][1]):
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
    """Align dialogues scene-by-scene via LCS on (scene_idx, chr_id). Scene
    (fn) counts match across EN/JP, so grouping by scene_idx is a safe
    reset boundary. Handles mid-file signature drift without cross-pairing
    unrelated characters."""
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


def build_chr_alias(parsed_files, jp_tname, tvoice):
    """Build (chr_alias, voice_prefix_to_known) maps from voice prefixes.

    Voice files are recorded one-per-VA. Two uses:
      - chr_alias[unk_chr_id] -> known_chr_id (for IDs absent from t_name)
      - voice_prefix_to_known[prefix] -> known_chr_id (for runtime variable
        chr_ids that can't be parsed at all)."""
    from collections import Counter
    prefix_known = {}
    unk_prefixes = {}
    for parsed in parsed_files:
        for d in parsed:
            chr_id, voice_id = d[1], d[3]
            if voice_id is None:
                continue
            fn = tvoice.get(voice_id) or ''
            if not fn or not fn.startswith('v'):
                continue
            prefix = fn[:4]
            # Sentinel chr_ids (0xFFFF "Overlord Dantès" etc.) appear in
            # t_name but are debug placeholders — exclude from the bridge
            # so they don't hijack voice-prefix attribution.
            if chr_id in ANONYMOUS_CHR_IDS:
                continue
            if chr_id in jp_tname:
                prefix_known.setdefault(prefix, Counter())[chr_id] += 1
            elif chr_id is not None:
                unk_prefixes.setdefault(chr_id, Counter())[prefix] += 1
    voice_prefix_to_known = {
        prefix: cnt.most_common(1)[0][0] for prefix, cnt in prefix_known.items()
    }
    alias = {}
    for unk_cid, prefixes in unk_prefixes.items():
        dominant_prefix, _ = prefixes.most_common(1)[0]
        if dominant_prefix in voice_prefix_to_known:
            alias[unk_cid] = voice_prefix_to_known[dominant_prefix]
    return alias, voice_prefix_to_known


def load_active_voice(path):
    """ActiveVoiceTableData rows in table order, as
    (group, chr_ids, voice_id, text).
    int1 is the speaker's chr_id, long2 the t_voice id (0 = unvoiced)."""
    with open(path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    out = []
    for block in doc.get('data', []):
        for r in block.get('data', []):
            out.append((r['id'], [r['int1']], r['long2'] or None, r['voice_subtitle']))
    return out


def active_voice_exchanges():
    """Pair EN/JP active voice rows and group them into exchanges (the
    table's `id`), in table order. Variants of one exchange for different
    triggers repeat its lines, so a line (speaker, voice, text) is emitted
    once, in the first exchange that plays it. Rows with no text are
    dropped, and so are the test groups (ACTIVE_VOICE_TEST_GROUPS)."""
    en = load_active_voice(EN_ACTIVE)
    jp = load_active_voice(JP_ACTIVE)
    assert [r[:3] for r in en] == [r[:3] for r in jp], 'EN/JP active voice tables differ'
    groups = {}
    seen = set()
    for e, j in zip(en, jp):
        group, chr_ids, voice_id, text = e
        if group >= ACTIVE_VOICE_TEST_GROUPS or not (text.strip() or j[3].strip()):
            continue
        key = (tuple(chr_ids), voice_id, text)
        if key in seen:
            continue
        seen.add(key)
        groups.setdefault(group, []).append((e, j))
    return list(groups.values())


def active_voice_lines(text):
    return [ANGLE_TAG_RE.sub('', _mark_ruby(line)).strip() for line in text.split('\n')]


def main():
    en_files = collect_files(EN_ROOT)
    jp_files = collect_files(JP_ROOT)
    print(f'files  EN={len(en_files)}  JP={len(jp_files)}')

    en_tname = load_tname(EN_TNAME)
    jp_tname = load_tname(JP_TNAME)
    tvoice = load_tvoice(JP_TVOICE)
    print(f't_name  EN={len(en_tname)}  JP={len(jp_tname)}  t_voice={len(tvoice)}')

    print('Pre-pass: building chr_id alias map...', file=sys.stderr)
    parsed_jp = {stem: parse_script(jp_files[stem]) for stem in jp_files}
    chr_alias, voice_prefix_to_known = build_chr_alias(parsed_jp.values(), jp_tname, tvoice)
    print(f'  resolved {len(chr_alias)} unknown chr_ids via voice-prefix bridge', file=sys.stderr)

    def _resolve_via_voice(voice_id, side_tname, side_field):
        if voice_id is None:
            return ''
        fn = tvoice.get(voice_id) or ''
        if len(fn) < 4:
            return ''
        known_cid = voice_prefix_to_known.get(fn[:4])
        if known_cid is None:
            return ''
        entry = side_tname.get(known_cid)
        if not entry:
            return ''
        return (entry.get(side_field) or entry.get('name') or '').strip()

    def speaker(chr_id, override, side_tname, side_field, voice_id=None):
        if override:
            return override.strip()
        if chr_id in ANONYMOUS_CHR_IDS:
            return ''
        if chr_id is None:
            return _resolve_via_voice(voice_id, side_tname, side_field)
        entry = side_tname.get(chr_id)
        if not entry and chr_id in chr_alias:
            entry = side_tname.get(chr_alias[chr_id])
        if not entry:
            return ''
        val = entry.get(side_field) or entry.get('name') or ''
        return val.strip()

    def _check_mask(chr_id, tier, override_en, override_jp):
        # Suppress only when chr_set_display_name masks a named character's
        # avfc face (e.g. Judith → "Police Officer"). Generic btlface
        # combat models are reused for gangster/mafioso/etc. roles and
        # match the override legitimately, so leave those alone.
        if tier != 'face':
            return False
        overrides = {(o or '').strip() for o in (override_en, override_jp)}
        overrides.discard('')
        if not overrides:
            return False
        real = set()
        for src in (en_tname.get(chr_id), jp_tname.get(chr_id)):
            if not src:
                continue
            real.add((src.get('name') or '').strip())
            real.add((src.get('full_name_en') or '').strip())
        real.discard('')
        return not (overrides & real)

    def portrait(chr_id, voice_id=None, override_en='', override_jp=''):
        if chr_id in ANONYMOUS_CHR_IDS:
            return None, None
        if chr_id is None:
            if voice_id is None:
                return None, None
            fn = tvoice.get(voice_id) or ''
            if len(fn) < 4:
                return None, None
            known_cid = voice_prefix_to_known.get(fn[:4])
            if known_cid is None:
                return None, None
            entry = jp_tname.get(known_cid) or en_tname.get(known_cid)
            pf, tier = portrait_for(entry)
            if _check_mask(known_cid, tier, override_en, override_jp):
                return None, None
            return pf, tier
        entry = jp_tname.get(chr_id) or en_tname.get(chr_id)
        if not entry and chr_id in chr_alias:
            aliased = chr_alias[chr_id]
            entry = jp_tname.get(aliased) or en_tname.get(aliased)
        pf, tier = portrait_for(entry)
        if _check_mask(chr_id, tier, override_en, override_jp):
            return None, None
        return pf, tier

    rows = []
    stems = sorted(set(en_files) | set(jp_files))
    for stem in stems:
        en_d = parse_script(en_files[stem]) if stem in en_files else []
        jp_d = parsed_jp.get(stem, []) if stem in jp_files else []
        pairs = align_scenes(en_d, jp_d)
        if not pairs:
            continue
        unpaired = sum(1 for e, j in pairs if e is None or j is None)
        if unpaired:
            print(f'WARN {stem}: {unpaired} unpaired rows '
                  f'(EN={len(en_d)} JP={len(jp_d)})', file=sys.stderr)
        rownum = 1
        for en_t, jp_t in pairs:
            en_scene, en_chr, en_lines, en_voice, en_override = (
                en_t if en_t else (0, None, [], None, '')
            )
            jp_scene, jp_chr, jp_lines, jp_voice, jp_override = (
                jp_t if jp_t else (0, None, [], None, '')
            )
            scene = jp_scene if jp_t else en_scene
            chr_id = jp_chr if jp_chr is not None else en_chr
            vid = jp_voice or en_voice

            eng_chr = speaker(en_chr if en_t else chr_id, en_override,
                              en_tname, 'name', voice_id=vid)
            jpn_chr = speaker(jp_chr if jp_t else chr_id, jp_override,
                              jp_tname, 'name', voice_id=vid)

            pfile, tier = portrait(chr_id, voice_id=vid,
                                   override_en=en_override,
                                   override_jp=jp_override)
            pc_icon = pc_icon_html(pfile, tier)

            jp_html = clean_text(jp_lines, '<br/>')
            vfile = tvoice.get(vid) if vid is not None else None
            if vfile and jp_html:
                jp_html = voice_wrap(jp_html, vfile)

            rows.append([
                str(GAME_ID), stem, str(scene), str(rownum),
                eng_chr,
                clean_text(en_lines, ' '),
                clean_text(en_lines, '<br/>'),
                jpn_chr,
                clean_text(jp_lines, ' '),
                jp_html,
                '', pc_icon,
            ])
            rownum += 1

    # Active voice: one exchange per scene, after the scripts. A single
    # speaker is named by chr_id, or -- for the anonymous ids and ids t_name
    # doesn't know (bosses) -- by the voice clip's actor prefix, as the
    # scripts do. Lines several speakers say together ('Yeah!') get the
    # scripts' joint-speaker form, 'A & B'.
    rownum = 1
    for scene, exchange in enumerate(active_voice_exchanges(), start=1):
        for (_, chr_ids, vid, en_text), (_, _, _, jp_text) in exchange:
            if len(chr_ids) == 1:
                cid = chr_ids[0]
                if cid in ANONYMOUS_CHR_IDS or not (cid in en_tname or cid in chr_alias):
                    cid = None
                eng_chr = speaker(cid, '', en_tname, 'name', voice_id=vid)
                jpn_chr = speaker(cid, '', jp_tname, 'name', voice_id=vid)
                pc_icon = pc_icon_html(*portrait(cid, voice_id=vid))
            else:
                eng_chr = ' & '.join(n for n in (speaker(c, '', en_tname, 'name') for c in chr_ids) if n)
                jpn_chr = '＆'.join(n for n in (speaker(c, '', jp_tname, 'name') for c in chr_ids) if n)
                pc_icon = ''
            en_lines = active_voice_lines(en_text)
            jp_lines = active_voice_lines(jp_text)
            jp_html = clean_text(jp_lines, '<br/>')
            vfile = tvoice.get(vid) if vid is not None else None
            if vfile and jp_html:
                jp_html = voice_wrap(jp_html, vfile)
            rows.append([
                str(GAME_ID), ACTIVE_VOICE_FNAME, str(scene), str(rownum),
                eng_chr,
                clean_text(en_lines, ' '),
                clean_text(en_lines, '<br/>'),
                jpn_chr,
                clean_text(jp_lines, ' '),
                jp_html,
                '', pc_icon,
            ])
            rownum += 1
    print(f'active voice  rows={rownum - 1}')

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(f'delete from script where game_id = {GAME_ID};\n')
        for row in rows:
            f.write(
                'insert into script (game_id, fname, scene, row, eng_chr_name, eng_search_text, '
                'eng_html_text, jpn_chr_name, jpn_search_text, jpn_html_text, op_name, pc_icon_html) values\n'
            )
            f.write("('%s');\n" % "','".join(sql_escape(c) for c in row))

    print(f'TOTAL = {len(rows)}')


if __name__ == '__main__':
    main()
