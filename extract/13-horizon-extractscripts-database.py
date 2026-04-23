"""Extract Trails beyond the Horizon (game 13) dialogue into horizon.sql.

Parses .ing files decompiled by Ingert. Dialogue is expressed as
`system[5,6](chrId, ..., text, ...)` calls with text lines inline;
speaker-name overrides use `chr_set_display_name(chrId, "name")`. Each
top-level `fn name()` is a scene. Line-number labels (`NNN@`) are stripped
before parsing. Each interesting call is extracted with balanced-paren
scanning and parsed via `ast.parse` (the calls themselves are valid
Python once labels are stripped).

Format is identical to game 12 (db2) — differences from db2:
  - EN/JP script roots: `horizon.ing/script_eng`, `horizon.ing/script`
  - Portrait inventory: no noteface tier (0 files in horizon itp)
  - Portrait variant priority: _c15 > _c10 > bare > other
  - Speaker names trimmed (horizon t_name has stray trailing spaces)
"""

import ast
import json
import os
import re
import sys

HORIZON_SCRIPT_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'Ingert', 'data', 'horizon.ing')
HORIZON_TBL_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'KuroTools', 'horizon_extract')
EN_ROOT = os.path.join(HORIZON_SCRIPT_ROOT, 'script_eng')
JP_ROOT = os.path.join(HORIZON_SCRIPT_ROOT, 'script')
EN_TNAME = os.path.join(HORIZON_TBL_ROOT, 'en_json', 't_name.json')
JP_TNAME = os.path.join(HORIZON_TBL_ROOT, 'jp_json', 't_name.json')
JP_TVOICE = os.path.join(HORIZON_TBL_ROOT, 'jp_json', 't_voice.json')
GAME_ID = 13
OUTPUT = 'horizon.sql'

# 0xFFFE / 0xFFFF are engine sentinels for anonymous narration. horizon's
# t_name has a stray entry mapping 65535 to "Overlord Auguste"/chr0298.
# Skip the name and portrait lookup for these; latched overrides still apply.
ANONYMOUS_CHR_IDS = frozenset({0xFFFE, 0xFFFF})

# Subdirs under each script root that contain real dialogue. `battle`,
# `obj`, `ai`, `demo` have zero `system[5,6]` calls and are skipped.
DIALOGUE_SUBDIRS = ('scena', 'cutscene', 'minigame', 'ani')

# Full face portraits (55 files in itp/*.dds — converted to webp).
AVAILABLE_PORTRAITS = {
    'avfc0000.webp', 'avfc0000_c15.webp',
    'avfc0002.webp', 'avfc0002_c15.webp',
    'avfc0004.webp', 'avfc0004_c15.webp',
    'avfc0006.webp', 'avfc0009.webp',
    'avfc0111.webp', 'avfc0112.webp', 'avfc0113.webp',
    'avfc0118.webp', 'avfc0120.webp', 'avfc0120_c03.webp',
    'avfc0123.webp', 'avfc0124.webp', 'avfc0125.webp', 'avfc0126.webp',
    'avfc0301.webp', 'avfc0303.webp', 'avfc0304.webp', 'avfc0306.webp',
    'avfc5001.webp', 'avfc5001_c03.webp', 'avfc5001_c10.webp', 'avfc5001_c15.webp',
    'avfc5003.webp', 'avfc5003_c15.webp',
    'avfc5005.webp', 'avfc5005_c15.webp',
    'avfc5007.webp', 'avfc5007_c03.webp', 'avfc5007_c15.webp',
    'avfc5008.webp', 'avfc5009.webp', 'avfc5009_00.webp',
    'avfc5110.webp', 'avfc5110_c10.webp', 'avfc5110_c15.webp',
    'avfc5112.webp', 'avfc5112_c00.webp',
    'avfc5113.webp', 'avfc5113_c00.webp',
    'avfc5114.webp', 'avfc5114_c10.webp',
    'avfc5117.webp', 'avfc5117_c10.webp',
    'avfc5118.webp', 'avfc5119.webp', 'avfc5119_c03.webp',
    'avfc5120.webp', 'avfc5121.webp', 'avfc5122.webp',
    'avfc5302.webp', 'avfc5327.webp',
}

# Battle faces (243 files) — fallback when no avfc matches.
AVAILABLE_BTLFACE = {
    'btlface0_c0000.webp', 'btlface0_c0000_c15.webp',
    'btlface0_c0002.webp', 'btlface0_c0002_1.webp', 'btlface0_c0002_c15.webp',
    'btlface0_c0004.webp', 'btlface0_c0004_c15.webp', 'btlface0_c0004_c49.webp',
    'btlface0_c0006.webp', 'btlface0_c0009.webp', 'btlface0_c0009_c00.webp',
    'btlface0_c0010.webp', 'btlface0_c0010_c00.webp', 'btlface0_c0011.webp',
    'btlface0_c0111.webp', 'btlface0_c0112.webp', 'btlface0_c0113.webp',
    'btlface0_c0114.webp', 'btlface0_c0114_c10.webp',
    'btlface0_c0115.webp', 'btlface0_c0115_c00.webp', 'btlface0_c0115_c02.webp',
    'btlface0_c0115_c10.webp', 'btlface0_c0115_c10b.webp',
    'btlface0_c0116.webp', 'btlface0_c0116_c02.webp',
    'btlface0_c0117.webp', 'btlface0_c0117_c00.webp',
    'btlface0_c0118.webp',
    'btlface0_c0120.webp', 'btlface0_c0120_c03.webp',
    'btlface0_c0121.webp', 'btlface0_c0121_c00.webp',
    'btlface0_c0122.webp', 'btlface0_c0122_c00.webp',
    'btlface0_c0122_c10.webp', 'btlface0_c0122_c11.webp',
    'btlface0_c0123.webp', 'btlface0_c0124.webp', 'btlface0_c0125.webp',
    'btlface0_c0126.webp', 'btlface0_c0127.webp', 'btlface0_c0127_1.webp',
    'btlface0_c0127_2.webp', 'btlface0_c0129.webp',
    'btlface0_c0130.webp', 'btlface0_c0130_c10.webp',
    'btlface0_c0298.webp', 'btlface0_c0299.webp',
    'btlface0_c0300.webp', 'btlface0_c0301.webp',
    'btlface0_c0302.webp', 'btlface0_c0302_1.webp',
    'btlface0_c0303.webp', 'btlface0_c0304.webp', 'btlface0_c0304_c00.webp',
    'btlface0_c0305_c00.webp', 'btlface0_c0305_c01.webp',
    'btlface0_c0306.webp',
    'btlface0_c0307.webp', 'btlface0_c0307_c99.webp',
    'btlface0_c0311_c10.webp', 'btlface0_c0314.webp',
    'btlface0_c0316.webp', 'btlface0_c0317.webp', 'btlface0_c0318.webp',
    'btlface0_c0328.webp', 'btlface0_c0329.webp',
    'btlface0_c0330_c00.webp', 'btlface0_c0334.webp', 'btlface0_c0336.webp',
    'btlface0_c0409.webp', 'btlface0_c0426.webp',
    'btlface0_c0443.webp', 'btlface0_c0446.webp', 'btlface0_c0490.webp',
    'btlface0_c0500.webp', 'btlface0_c0501.webp', 'btlface0_c0503.webp',
    'btlface0_c0510a.webp', 'btlface0_c0549.webp',
    'btlface0_c0550a.webp', 'btlface0_c0551.webp',
    'btlface0_c0660_c01a.webp', 'btlface0_c0665_c01.webp',
    'btlface0_c0668_c03.webp', 'btlface0_c0711_c01.webp',
    'btlface0_c0712.webp', 'btlface0_c0712a.webp',
    'btlface0_c0725.webp', 'btlface0_c0725_c01.webp',
    'btlface0_c0725_c02.webp', 'btlface0_c0725_c03.webp',
    'btlface0_c0726.webp', 'btlface0_c0726_40s.webp',
    'btlface0_c0726_c01.webp', 'btlface0_c0726_c01_40s.webp',
    'btlface0_c0726_c01_e.webp', 'btlface0_c0726_e.webp',
    'btlface0_c0727.webp', 'btlface0_c0727_c01.webp',
    'btlface0_c0728.webp', 'btlface0_c0728_c01.webp',
    'btlface0_c0731_c01.webp', 'btlface0_c0750.webp', 'btlface0_c0755.webp',
    'btlface0_c0757.webp',
    'btlface0_c0760.webp', 'btlface0_c0760_c01.webp',
    'btlface0_c0760a.webp', 'btlface0_c0760a_c01.webp',
    'btlface0_c0760b.webp', 'btlface0_c0760b_c01.webp',
    'btlface0_c0765.webp', 'btlface0_c0765_c01.webp',
    'btlface0_c0770.webp', 'btlface0_c0770_c01.webp',
    'btlface0_c0775.webp', 'btlface0_c0775_c01.webp',
    'btlface0_c0780.webp', 'btlface0_c0780_c01.webp',
    'btlface0_c0781.webp', 'btlface0_c0781_c01.webp',
    'btlface0_c0782.webp', 'btlface0_c0782_c01.webp',
    'btlface0_c0782_c01_e.webp', 'btlface0_c0782_c02.webp',
    'btlface0_c0782_e.webp',
    'btlface0_c0783.webp', 'btlface0_c0783_c01.webp',
    'btlface0_c0785.webp', 'btlface0_c0785_c01.webp',
    'btlface0_c0785_e.webp', 'btlface0_c0785_w2.webp',
    'btlface0_c0785a_w1.webp', 'btlface0_c0785a_w3.webp',
    'btlface0_c0786.webp', 'btlface0_c0786_e.webp',
    'btlface0_c0786_w1.webp', 'btlface0_c0786_w2.webp',
    'btlface0_c0786a.webp', 'btlface0_c0786a_w1.webp',
    'btlface0_c0786a_w3.webp',
    'btlface0_c0787.webp', 'btlface0_c0787_e.webp',
    'btlface0_c0787_w2.webp', 'btlface0_c0787a_w1.webp',
    'btlface0_c0787a_w3.webp',
    'btlface0_c0790.webp', 'btlface0_c0790_c01.webp',
    'btlface0_c0791.webp', 'btlface0_c0791_c01.webp',
    'btlface0_c0791_c01_e.webp', 'btlface0_c0791_e.webp',
    'btlface0_c0792.webp', 'btlface0_c0792_c01.webp',
    'btlface0_c0792_c01_e.webp', 'btlface0_c0792_c02.webp',
    'btlface0_c0792_e.webp',
    'btlface0_c0795.webp', 'btlface0_c0795_c01.webp',
    'btlface0_c0795_c01_e.webp', 'btlface0_c0795_e.webp',
    'btlface0_c0800.webp', 'btlface0_c0800_e.webp',
    'btlface0_c0801.webp', 'btlface0_c0801_e.webp',
    'btlface0_c0802.webp', 'btlface0_c0802_e.webp',
    'btlface0_c0831_c01.webp', 'btlface0_c0832.webp', 'btlface0_c0840.webp',
    'btlface0_c5001.webp', 'btlface0_c5001_c03.webp',
    'btlface0_c5001_c10.webp', 'btlface0_c5001_c15.webp',
    'btlface0_c5003.webp', 'btlface0_c5003_1.webp', 'btlface0_c5003_c15.webp',
    'btlface0_c5005.webp', 'btlface0_c5005_c15.webp',
    'btlface0_c5005_c15_cl.webp', 'btlface0_c5005p_cl.webp',
    'btlface0_c5007.webp', 'btlface0_c5007_c03.webp',
    'btlface0_c5007_c03_1.webp', 'btlface0_c5007_c15.webp',
    'btlface0_c5008.webp', 'btlface0_c5009.webp', 'btlface0_c5009_c00.webp',
    'btlface0_c5110.webp', 'btlface0_c5110_c10.webp', 'btlface0_c5110_c15.webp',
    'btlface0_c5112.webp', 'btlface0_c5112_c00.webp',
    'btlface0_c5113.webp', 'btlface0_c5113_c00.webp',
    'btlface0_c5114.webp', 'btlface0_c5114_1.webp', 'btlface0_c5114_c10.webp',
    'btlface0_c5115.webp', 'btlface0_c5115_c10.webp',
    'btlface0_c5116.webp',
    'btlface0_c5117.webp', 'btlface0_c5117_c10.webp', 'btlface0_c5117_c12.webp',
    'btlface0_c5118.webp', 'btlface0_c5119.webp', 'btlface0_c5119_c03.webp',
    'btlface0_c5120.webp', 'btlface0_c5120_c00.webp',
    'btlface0_c5121.webp', 'btlface0_c5122.webp', 'btlface0_c5123.webp',
    'btlface0_c5300.webp', 'btlface0_c5300_1.webp',
    'btlface0_c5301.webp', 'btlface0_c5301_c10.webp',
    'btlface0_c5302.webp',
    'btlface0_c5311.webp', 'btlface0_c5313.webp', 'btlface0_c5314.webp',
    'btlface0_c5315.webp', 'btlface0_c5316.webp',
    'btlface0_c5319.webp', 'btlface0_c5320.webp',
    'btlface0_c5322.webp', 'btlface0_c5323.webp', 'btlface0_c5323_c03.webp',
    'btlface0_c5324.webp',
    'btlface0_c5325.webp', 'btlface0_c5325_c15.webp',
    'btlface0_c5327.webp', 'btlface0_c5329.webp',
    'btlface0_c5404.webp', 'btlface0_c5490.webp',
    'btlface0_c5511b.webp', 'btlface0_c5541_c01.webp',
    'btlface0_c5680.webp', 'btlface0_c5710.webp', 'btlface0_c5711.webp',
    'btlface0_c5750.webp', 'btlface0_c5751.webp',
}

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
        # EN preferred: full_name_en. JP preferred: name. Horizon's t_name
        # has stray trailing spaces (e.g. "Van ") — strip them.
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
        if en_d and jp_d and len(en_d) != len(jp_d):
            print(f'WARN {stem}: EN={len(en_d)} JP={len(jp_d)}', file=sys.stderr)
        n = max(len(en_d), len(jp_d))
        if n == 0:
            continue
        rownum = 1
        for i in range(n):
            en_t = en_d[i] if i < len(en_d) else None
            jp_t = jp_d[i] if i < len(jp_d) else None
            en_scene, en_chr, en_lines, en_voice, en_override = (
                en_t if en_t else (0, None, [], None, '')
            )
            jp_scene, jp_chr, jp_lines, jp_voice, jp_override = (
                jp_t if jp_t else (0, None, [], None, '')
            )
            scene = jp_scene if jp_t else en_scene
            chr_id = jp_chr if jp_chr is not None else en_chr

            eng_chr = speaker(en_chr if en_t else chr_id, en_override,
                              en_tname, 'full_name_en')
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
