"""Extract Trails in the Sky 1st Chapter remake (game 101) into sky1r.sql.

Same Ingert .ing format as games 11-13 (Kuro engine): dialogue expressed
as `system[5,6](chrId, ..., text, ...)` calls, speaker overrides via
`chr_set_display_name(chrId, "name")`. See 13-horizon for the detailed
format notes.

Game 101 is the 2025 Sky 1st Chapter remake — distinct from the PSP
original (game 1, binary format, handled by 1-skyfc-extractscripts...).

Differences from horizon:
  - EN/JP script roots: `sky1st/script_en`, `sky1st/script`
    (note: `script_en`, not `script_eng`)
  - DIALOGUE_SUBDIRS drops `cutscene` (0 files)
  - Portrait inventory: 13 base avfc files, no tier variants, no btlface
"""

import ast
import json
import os
import re
import sys

SKY1R_SCRIPT_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'Ingert', 'data', 'sky1st')
SKY1R_TBL_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'KuroTools', 'sky1_extract')
EN_ROOT = os.path.join(SKY1R_SCRIPT_ROOT, 'script_en')
JP_ROOT = os.path.join(SKY1R_SCRIPT_ROOT, 'script')
EN_TNAME = os.path.join(SKY1R_TBL_ROOT, 'en_json', 't_name.json')
JP_TNAME = os.path.join(SKY1R_TBL_ROOT, 'jp_json', 't_name.json')
JP_TVOICE = os.path.join(SKY1R_TBL_ROOT, 'jp_json', 't_voice.json')
GAME_ID = 101
OUTPUT = 'sky1r.sql'

# 0xFFFE / 0xFFFF are engine sentinels for anonymous narration.
ANONYMOUS_CHR_IDS = frozenset({0xFFFE, 0xFFFF})

# Subdirs under each script root that contain dialogue. Sky 1st has no
# cutscene files; battle/obj/ai/demo have zero `system[5,6]` calls.
DIALOGUE_SUBDIRS = ('scena', 'minigame', 'ani')

# Full face portraits — 13 base avfc files in icon/*.dds, converted to
# webp. No `_c10`/`_c15`/`_c03` variants in the Sky 1st remake inventory.
AVAILABLE_PORTRAITS = {
    'avfc0001.webp', 'avfc0003.webp', 'avfc0005.webp', 'avfc0007.webp',
    'avfc0117.webp', 'avfc0307.webp', 'avfc0316.webp',
    'avfc5000.webp', 'avfc5002.webp', 'avfc5004.webp', 'avfc5006.webp',
    'avfc5308.webp', 'avfc5311.webp',
}

# No battle faces exist for Sky 1st remake (no btlface assets in the
# decompile). Kept as an empty set so portrait_for() cleanly falls through.
AVAILABLE_BTLFACE = set()

# Any <tag> (angle-bracketed control code). Handles <k>, <#E..>, <#M..>,
# <#B..>, <S5>, <K>, <c888>, <W500> etc. all in one pass.
ANGLE_TAG_RE = re.compile(r'<[^>]*>')
WHITESPACE_RE = re.compile(r'[ \t]+')

# `NNN@` line-number labels are sprinkled before statements and inside
# argument lists. They're not part of the logic — strip before parsing.
LABEL_RE = re.compile(r'\d+@')

# Top-level scene function. `prelude fn ...` (system opcode alias) starts
# with 'prelude' so `(?m)^fn` excludes preludes.
FN_HEADER_RE = re.compile(r'(?m)^fn\s+(\w+)\s*\(')

# Dialogue opcode: system[5,6](chrId, ...args...)
DIALOGUE_CALL_RE = re.compile(r'\bsystem\s*\[\s*5\s*,\s*6\s*\]\s*\(')

# OP-27 equivalent: chr_set_display_name(chrId, "name")
DISPLAY_NAME_CALL_RE = re.compile(r'\bchr_set_display_name\s*\(')


def _find_balanced(s, open_paren_idx):
    """Given position of an opening '(' in s, return index AFTER the
    matching ')'. String literals are respected so parens inside strings
    don't count. Returns -1 if unmatched."""
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
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return -1


def _const_value(node):
    """ast.Constant → python value; handle unary minus on ints/floats;
    reject anything else."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
            return -node.operand.value
    return None


def _parse_call_args(call_text):
    """`call_text` is a single Python call like `system[5,6]("a", 10, "b")`.
    Return the list of argument AST nodes, or None on parse failure."""
    try:
        tree = ast.parse(call_text, mode='eval')
    except SyntaxError:
        return None
    if not isinstance(tree.body, ast.Call):
        return None
    return tree.body.args


def parse_script(path):
    """Parse one .ing file and return a list of dialogue tuples:
      (scene_idx, chr_id, lines, voice_id, override)

    Scenes are top-level `fn` declarations. `chr_set_display_name(chrId,
    "name")` latches a display name per chrId until overwritten; the
    latch resets at scene (function) boundaries.
    """
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    src = LABEL_RE.sub('', src)

    # Collect events (scene boundaries + dialogue calls + name-overrides)
    # in source order, keyed by their character offset.
    events = []

    for m in FN_HEADER_RE.finditer(src):
        events.append((m.start(), 'fn', None))

    for m in DIALOGUE_CALL_RE.finditer(src):
        open_paren = m.end() - 1
        end = _find_balanced(src, open_paren)
        if end == -1:
            continue
        events.append((m.start(), 'dialogue', src[m.start():end]))

    for m in DISPLAY_NAME_CALL_RE.finditer(src):
        open_paren = m.end() - 1
        end = _find_balanced(src, open_paren)
        if end == -1:
            continue
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
                if isinstance(cid, int) and isinstance(nm, str) and nm:
                    latched[cid] = nm
            continue

        if kind == 'dialogue':
            decoded = _decode_dialogue(args)
            if decoded:
                chr_id, lines, voice_id = decoded
                override = latched.get(chr_id, '')
                dialogues.append((scene_idx, chr_id, lines, voice_id, override))

    return dialogues


def _decode_dialogue(args):
    """Decode the arg list of a `system[5,6](...)` call.

    Layout: first arg is chrId. Remaining args are a mix of:
      - strings: text lines (in reading order) and/or pure-control tags
        like `"<#E[5]#M_0#B_0>"` (dropped after tag-stripping leaves them
        empty);
      - int 11 followed by an int: voice marker + voice_id;
      - int 10: line separator (ignored; string order is preserved in the
        arg list);
      - other ints: rare per-call flags (ignored).

    Returns (chrId, [lines], voice_id or None), or None if the call had
    no usable text.
    """
    if not args:
        return None
    chr_id = _const_value(args[0])
    if not isinstance(chr_id, int):
        return None

    lines = []
    voice_id = None
    i = 1
    while i < len(args):
        v = _const_value(args[i])
        if isinstance(v, str):
            cleaned = ANGLE_TAG_RE.sub('', v).strip()
            if cleaned:
                lines.append(cleaned)
        elif isinstance(v, int) and v == 11 and i + 1 < len(args):
            nxt = _const_value(args[i + 1])
            if isinstance(nxt, int):
                voice_id = nxt
                i += 1  # consume the voice_id slot
        # Other ints (10 = separator; rare flags in ani files)
        # are ignored; string order is preserved so we don't need them.
        i += 1

    if not lines:
        return None
    return chr_id, lines, voice_id


def load_tname(path):
    """Parse t_name.json. Returns dict chrId -> {name, full_name_en, model}.
    First entry per chrId wins (outfit-variant rows come later and are
    skipped)."""
    with open(path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    out = {}
    for block in doc.get('data', []):
        for entry in block.get('data', []):
            cid = entry.get('character_id')
            if cid is None or cid in out:
                continue
            # Skip variant-tag placeholders like "Leon_Towel".
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
    """Parse t_voice.json. Returns dict id -> filename stem."""
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
    """Priority ladder within a single tier (avfc or btlface).
      1. {prefix}{stem}_c15 — horizon canonical variant
      2. {prefix}{stem}_c10
      3. {prefix}{stem}    — bare
      4. {prefix}{suffix}  — exact model match (when suffix differs)
      5. Any other {prefix}{stem}_c## — lowest sorts first
    Returns the filename or None."""
    tried = [
        f'{prefix}{stem}_c15.webp',
        f'{prefix}{stem}_c10.webp',
        f'{prefix}{stem}.webp',
        f'{prefix}{suffix}.webp',
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
    """Resolve portrait filename for a t_name entry.
    Tier order: avfc → btlface. No noteface tier in horizon.
    Within each tier, _c15 wins over _c10 wins over bare."""
    if not entry:
        return None, None
    model = entry.get('model') or ''
    if not model.startswith('chr'):
        return None, None
    suffix = model[len('chr'):]        # e.g. '0000_c15' or '0000'
    if not suffix:
        return None, None
    stem = suffix.split('_')[0]        # e.g. '0000'

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
        f'<audio id="{voice_file}">'
        f'<source src="talk/{GAME_ID}/{voice_file}.opus" type="audio/ogg; codecs=opus">'
        f'</audio>'
        f'<a href="javascript:void(0)" '
        f'onclick="document.getElementById(\'{voice_file}\').play()">'
        f'{html_text}</a>'
    )


def clean_text(lines, joiner):
    """Join dialogue lines. `_decode_dialogue` already strips <...> tags;
    this just joins + collapses whitespace for the search column."""
    text = joiner.join(line.strip() for line in lines if line.strip())
    if joiner == ' ':
        text = WHITESPACE_RE.sub(' ', text)
    return text.strip()


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def collect_files(root):
    """Scan DIALOGUE_SUBDIRS under `root` and return {stem: full_path}.
    Stems are unique across subdirs, so a flat dict is safe."""
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


def main():
    en_files = collect_files(EN_ROOT)
    jp_files = collect_files(JP_ROOT)
    print(f'files  EN={len(en_files)}  JP={len(jp_files)}')

    en_tname = load_tname(EN_TNAME)
    jp_tname = load_tname(JP_TNAME)
    tvoice = load_tvoice(JP_TVOICE)
    print(f't_name  EN={len(en_tname)}  JP={len(jp_tname)}  t_voice={len(tvoice)}')

    def speaker(chr_id, override, side_tname, side_field):
        if override:
            return override.strip()
        if chr_id in ANONYMOUS_CHR_IDS:
            return ''
        entry = side_tname.get(chr_id)
        if not entry:
            return ''
        val = entry.get(side_field) or entry.get('name') or ''
        return val.strip()

    def portrait(chr_id):
        if chr_id in ANONYMOUS_CHR_IDS:
            return None, None
        entry = jp_tname.get(chr_id) or en_tname.get(chr_id)
        return portrait_for(entry)

    rows = []
    stems = sorted(set(en_files) | set(jp_files))
    for stem in stems:
        en_d = parse_script(en_files[stem]) if stem in en_files else []
        jp_d = parse_script(jp_files[stem]) if stem in jp_files else []
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

            eng_chr = speaker(en_chr if en_t else chr_id, en_override,
                              en_tname, 'name')
            jpn_chr = speaker(jp_chr if jp_t else chr_id, jp_override,
                              jp_tname, 'name')

            pfile, tier = portrait(chr_id) if chr_id is not None else (None, None)
            pc_icon = pc_icon_html(pfile, tier)

            jp_html = clean_text(jp_lines, '<br/>')
            vid = jp_voice or en_voice
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
