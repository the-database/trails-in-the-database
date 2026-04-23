"""Extract Trails through Daybreak 2 (game 12) dialogue into db2.sql.

Parses KuroTools' ED9 assembly-style Python output for EN + JP scripts.
Unlike Decompiler2's high-level ChrTalk() AST (used by the Reverie extractor),
KuroTools emits low-level bytecode: PUSHSTRING/PUSHINTEGER pushes args onto
a stack, then RUNCMD(N, "Cmd_text_06") consumes the last N pushes as a
dialogue call. This script walks each function's statement list linearly,
tracking push state, and decodes dialogues at each RUNCMD site.
"""

import ast
import json
import os
import re
import sys

DB2_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'KuroTools', 'daybreak2_extract')
EN_ROOT = os.path.join(DB2_ROOT, 'en_py')
JP_ROOT = os.path.join(DB2_ROOT, 'jp_py')
EN_TNAME = os.path.join(DB2_ROOT, 'en_json', 't_name.json')
JP_TNAME = os.path.join(DB2_ROOT, 'jp_json', 't_name.json')
JP_TVOICE = os.path.join(DB2_ROOT, 'jp_json', 't_voice.json')
GAME_ID = 12
OUTPUT = 'db2.sql'

# Boilerplate/helper stems with no field dialogue. `m0000` is the shared
# `mes_message_close`/`wait_prompt` helper library (not a scene).
# AI stems (`ai_*`) and monster stems (`mon*`) are enemy-behavior scripts.
SKIP_STEMS = {
    'personaltemplate', 'personaltemplate2',
    'system', 'system2', 'sys_event', 'sys_fdungeon',
    'debug', 'sound_ani', 'btlmagic', 'common', 'chrx000',
    'm0000',
}
SKIP_PREFIXES = ('ai_', 'mon', 'btl_')

# Full face portraits (39 files in image_portraits/*.dds — converted to webp).
AVAILABLE_PORTRAITS = {
    'avfc0000.webp', 'avfc0002.webp', 'avfc0004.webp', 'avfc0006.webp',
    'avfc0009.webp', 'avfc0111.webp', 'avfc0112.webp', 'avfc0113.webp',
    'avfc0120.webp', 'avfc0120_c03.webp',
    'avfc0301.webp', 'avfc0303.webp', 'avfc0304.webp', 'avfc0306.webp',
    'avfc5001.webp', 'avfc5001_c03.webp', 'avfc5001_c10.webp',
    'avfc5003.webp', 'avfc5005.webp',
    'avfc5007.webp', 'avfc5007_c03.webp', 'avfc5008.webp',
    'avfc5009_00.webp',
    'avfc5110.webp', 'avfc5110_c10.webp', 'avfc5112.webp', 'avfc5113.webp',
    'avfc5113_c00.webp',
    'avfc5114.webp', 'avfc5114_c10.webp',
    'avfc5117.webp', 'avfc5117_c10.webp',
    'avfc5118.webp', 'avfc5119.webp', 'avfc5119_c03.webp',
    'avfc5302.webp',
    'avfcamio.webp', 'avfcarabia.webp', 'avfcelis.webp',
}

# Small note icons (19 base files; _s shadow companions are not speaker icons).
AVAILABLE_NOTES = {
    'noteface_c0000.webp', 'noteface_c0002.webp', 'noteface_c0004.webp',
    'noteface_c0112.webp', 'noteface_c0120.webp', 'noteface_c0306.webp',
    'noteface_c5001.webp', 'noteface_c5003.webp', 'noteface_c5005.webp',
    'noteface_c5007.webp', 'noteface_c5110.webp', 'noteface_c5114.webp',
    'noteface_c5117.webp', 'noteface_c5119.webp', 'noteface_c5302.webp',
    'noteface_c5311.webp', 'noteface_c5313.webp', 'noteface_c5315.webp',
    'noteface_c5324.webp',
}

# Battle faces (159 files) — last-resort fallback.
AVAILABLE_BTLFACE = {
    'btlface0_c0000.webp', 'btlface0_c0002.webp', 'btlface0_c0002_1.webp',
    'btlface0_c0004.webp', 'btlface0_c0004_c49.webp',
    'btlface0_c0006.webp', 'btlface0_c0009.webp', 'btlface0_c0009_c00.webp',
    'btlface0_c0010.webp', 'btlface0_c0111.webp', 'btlface0_c0112.webp',
    'btlface0_c0113.webp', 'btlface0_c0114.webp',
    'btlface0_c0115.webp', 'btlface0_c0115_c00.webp', 'btlface0_c0115_c02.webp',
    'btlface0_c0116.webp', 'btlface0_c0116_c02.webp',
    'btlface0_c0117.webp', 'btlface0_c0117_c00.webp',
    'btlface0_c0118.webp',
    'btlface0_c0120.webp', 'btlface0_c0120_c03.webp',
    'btlface0_c0121.webp', 'btlface0_c0121_c00.webp',
    'btlface0_c0122.webp', 'btlface0_c0122_c00.webp',
    'btlface0_c0298.webp', 'btlface0_c0299.webp',
    'btlface0_c0300.webp', 'btlface0_c0301.webp',
    'btlface0_c0302.webp', 'btlface0_c0302_1.webp',
    'btlface0_c0303.webp', 'btlface0_c0304.webp',
    'btlface0_c0305_c00.webp', 'btlface0_c0305_c01.webp',
    'btlface0_c0306.webp', 'btlface0_c0316.webp', 'btlface0_c0317.webp',
    'btlface0_c0318.webp', 'btlface0_c0328.webp', 'btlface0_c0329.webp',
    'btlface0_c0330_c00.webp',
    'btlface0_c0334.webp', 'btlface0_c0409.webp',
    'btlface0_c0490.webp', 'btlface0_c0500.webp', 'btlface0_c0501.webp',
    'btlface0_c0503.webp', 'btlface0_c0510a.webp', 'btlface0_c0550a.webp',
    'btlface0_c0551.webp',
    'btlface0_c0660_c01a.webp', 'btlface0_c0665_c01.webp',
    'btlface0_c0711_c01.webp', 'btlface0_c0712.webp', 'btlface0_c0712a.webp',
    'btlface0_c0725.webp', 'btlface0_c0725_c01.webp',
    'btlface0_c0725_c02.webp', 'btlface0_c0725_c03.webp',
    'btlface0_c0726.webp', 'btlface0_c0726_c01.webp',
    'btlface0_c0727.webp', 'btlface0_c0727_c01.webp',
    'btlface0_c0731_c01.webp', 'btlface0_c0750.webp', 'btlface0_c0755.webp',
    'btlface0_c0757.webp',
    'btlface0_c0760.webp', 'btlface0_c0760a.webp', 'btlface0_c0760b.webp',
    'btlface0_c0765.webp', 'btlface0_c0765_c01.webp',
    'btlface0_c0770.webp', 'btlface0_c0770_c01.webp',
    'btlface0_c0780.webp', 'btlface0_c0780_c01.webp',
    'btlface0_c0781.webp', 'btlface0_c0781_c01.webp',
    'btlface0_c0783.webp', 'btlface0_c0783_c01.webp',
    'btlface0_c0785.webp', 'btlface0_c0785_c01.webp',
    'btlface0_c0785_w2.webp', 'btlface0_c0785a_w1.webp',
    'btlface0_c0785a_w3.webp',
    'btlface0_c0786.webp', 'btlface0_c0786_w1.webp', 'btlface0_c0786_w2.webp',
    'btlface0_c0786a.webp', 'btlface0_c0786a_w1.webp',
    'btlface0_c0786a_w3.webp',
    'btlface0_c0787.webp', 'btlface0_c0787_w2.webp',
    'btlface0_c0787a_w1.webp', 'btlface0_c0787a_w3.webp',
    'btlface0_c0790.webp', 'btlface0_c0790_c01.webp',
    'btlface0_c0791.webp', 'btlface0_c0791_c01.webp',
    'btlface0_c0792.webp', 'btlface0_c0792_c01.webp',
    'btlface0_c0792_c02.webp',
    'btlface0_c0795.webp', 'btlface0_c0795_c01.webp',
    'btlface0_c0800.webp', 'btlface0_c0801.webp',
    'btlface0_c0831_c01.webp', 'btlface0_c0832.webp', 'btlface0_c0840.webp',
    'btlface0_c5001.webp', 'btlface0_c5001_c03.webp', 'btlface0_c5001_c10.webp',
    'btlface0_c5003.webp', 'btlface0_c5003_1.webp',
    'btlface0_c5005.webp', 'btlface0_c5005p_cl.webp',
    'btlface0_c5007.webp', 'btlface0_c5007_c03.webp',
    'btlface0_c5007_c03_1.webp',
    'btlface0_c5110.webp', 'btlface0_c5110_c10.webp',
    'btlface0_c5112.webp', 'btlface0_c5113.webp', 'btlface0_c5113_c00.webp',
    'btlface0_c5114.webp', 'btlface0_c5114_1.webp', 'btlface0_c5114_c10.webp',
    'btlface0_c5115.webp', 'btlface0_c5116.webp',
    'btlface0_c5117.webp', 'btlface0_c5117_c10.webp',
    'btlface0_c5118.webp', 'btlface0_c5119.webp', 'btlface0_c5119_c03.webp',
    'btlface0_c5120.webp', 'btlface0_c5120_c00.webp',
    'btlface0_c5300.webp', 'btlface0_c5300_1.webp',
    'btlface0_c5301.webp', 'btlface0_c5302.webp',
    'btlface0_c5311.webp', 'btlface0_c5313.webp', 'btlface0_c5314.webp',
    'btlface0_c5315.webp', 'btlface0_c5319.webp', 'btlface0_c5320.webp',
    'btlface0_c5322.webp', 'btlface0_c5324.webp', 'btlface0_c5327.webp',
    'btlface0_c5490.webp',
    'btlface0_c5511b.webp', 'btlface0_c5541_c01.webp',
    'btlface0_c5680.webp', 'btlface0_c5710.webp', 'btlface0_c5711.webp',
    'btlface0_c5751.webp',
}

# Any <tag> (angle-bracketed control code). Handles <k>, <#E..>, <#M..>,
# <#B..> etc. all in one pass.
ANGLE_TAG_RE = re.compile(r'<[^>]*>')
# Reverie-style #X[...] fallback (rare in db2 but harmless if absent).
HASH_CODE_RE = re.compile(r'#[A-Za-z](?:_[A-Za-z0-9]+|\[[A-Za-z0-9]+\])?')
WHITESPACE_RE = re.compile(r'[ \t]+')

# Pushes we treat as stack-relevant. PUSHCALLER/PUSHRETURN are CALL-frame
# setup, not data args — skip them so the effective stack is data-only.
STACK_PUSH_NAMES = {
    'PUSHSTRING', 'PUSHINTEGER', 'PUSHFLOAT', 'PUSHUNDEFINED', 'PUSHBOOLEAN',
}


def _const_value(node):
    """ast.Constant → its python value, else None."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant):
            return -node.operand.value
    return None


def _call_info(call):
    """Return (func_name, [positional arg values]) or None if not a Call we
    can reason about. Values are unwrapped constants; non-constant args
    become None."""
    if not isinstance(call, ast.Call):
        return None
    if isinstance(call.func, ast.Name):
        name = call.func.id
    elif isinstance(call.func, ast.Attribute):
        name = call.func.attr
    else:
        return None
    args = [_const_value(a) for a in call.args]
    return name, args


def parse_script(path):
    """Parse one KuroTools-decompiled script file.

    Returns list of (scene_idx, chr_id, lines, voice_id, override). Rows
    follow file order. OP-27 equivalent is CALL(chr_set_display_name)
    which latches a display name per chrId until overwritten (or scene end).
    """
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        print(f'WARN: syntax error in {path}: {e}', file=sys.stderr)
        return []

    # Find top-level `def script():`. Everything dialogue-related is inside.
    script_body = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'script':
            script_body = node.body
            break
    if script_body is None:
        return []

    dialogues = []
    scene_idx = -1
    stack = []         # list of (kind, value) for recent data pushes
    latched = {}       # chrId -> display-name override (OP-27 equivalent)

    for stmt in script_body:
        # Only care about expression statements wrapping a Call.
        if not isinstance(stmt, ast.Expr):
            continue
        info = _call_info(stmt.value)
        if info is None:
            continue
        fname, args = info

        if fname == 'set_current_function':
            scene_idx += 1
            stack = []
            latched = {}
            continue

        if fname in STACK_PUSH_NAMES:
            val = args[0] if args else None
            kind = (
                'str' if isinstance(val, str)
                else 'int' if isinstance(val, int) and not isinstance(val, bool)
                else 'float' if isinstance(val, float)
                else 'other'
            )
            stack.append((kind, val))
            continue

        if fname in ('Label', 'POP'):
            stack = []
            continue

        if fname == 'RUNCMD':
            # RUNCMD(n_args, "Cmd_name")
            if len(args) >= 2 and isinstance(args[0], int) and args[1] == 'Cmd_text_06':
                n = args[0]
                if scene_idx >= 0 and n >= 3 and len(stack) >= n:
                    frame = stack[-n:]
                    decoded = _decode_dialogue(frame)
                    if decoded:
                        chr_id, lines, voice_id = decoded
                        override = latched.get(chr_id, '')
                        dialogues.append(
                            (scene_idx, chr_id, lines, voice_id, override)
                        )
            stack = []
            continue

        if fname == 'CALL':
            target = args[0] if args else None
            if target == 'chr_set_display_name' and len(stack) >= 2:
                # Args pushed just before CALL: ..., PUSHSTRING(name), PUSHINTEGER(chrId)
                top = stack[-1]
                prev = stack[-2]
                if top[0] == 'int' and prev[0] == 'str':
                    latched[top[1]] = prev[1]
            stack = []
            continue

        if fname == 'CALLFROMANOTHERSCRIPT':
            stack = []
            continue

        # Any other instruction: assume it doesn't touch the stack for our
        # purposes. (SAVERESULT, EXIT, JUMP*, etc.) We could be paranoid and
        # reset, but that would lose Cmd_text_06 arg setup in rare cases.

    return dialogues


def _decode_dialogue(frame):
    """Decode last-N pushes into (chrId, [lines], voice_id or None).
    frame[-1] = top of stack = chrId.
    frame[-2] = control string (emote/mouth/body tag).
    If frame[-2] is int(11): voice present, frame[-3]=voice_id, rest are
      alternating text + int(10) separators.
    Otherwise: no voice, remaining frame is alternating text + int(10).
    Returns None if structure doesn't parse (malformed stack).
    """
    if len(frame) < 3:
        return None
    top = frame[-1]
    ctl = frame[-2]
    if top[0] != 'int':
        return None
    chr_id = top[1]

    voice_id = None
    # Walk downward from -2. control string is expected; some rare dialogues
    # may have an integer there instead — tolerate either.
    idx = len(frame) - 2
    # Skip control string slot if it's a string.
    if idx >= 0 and frame[idx][0] == 'str':
        idx -= 1
    # Voice marker: int 11 → voice present. Below it: voice_id int.
    if idx >= 0 and frame[idx] == ('int', 11):
        idx -= 1
        if idx >= 0 and frame[idx][0] == 'int':
            voice_id = frame[idx][1]
            idx -= 1

    # Remaining frame[0..idx] should be strings separated by int(10).
    lines = []
    # Walk from idx down to 0, collecting strings and skipping int(10).
    j = idx
    while j >= 0:
        item = frame[j]
        if item[0] == 'str':
            lines.append(item[1])
        elif item == ('int', 10):
            pass  # separator
        else:
            # Unexpected value — skip; don't crash.
            pass
        j -= 1

    if not lines:
        # No actual text — skip (likely some non-dialogue use of Cmd_text_06).
        return None
    return chr_id, lines, voice_id


def load_tname(path):
    """Parse t_name.json. Returns dict chrId -> {name, full_name_en, model}.
    First entry per chrId wins (outfit-variant rows come later and are
    skipped, matching Reverie's `first wins` rule)."""
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


def portrait_for(entry):
    """Resolve portrait filename for a t_name entry following the priority
    ladder. Returns (filename, tier) where tier in {'face','note','btl'} or
    (None, None) if no match. `_c10` is db2's canonical variant and beats
    bare + other variants."""
    if not entry:
        return None, None
    model = entry.get('model') or ''
    if not model.startswith('chr'):
        return None, None
    suffix = model[len('chr'):]        # e.g. '0306_c02' or '0306'
    if not suffix:
        return None, None
    stem = suffix.split('_')[0]        # e.g. '0306'

    # Tier 1: avfc
    candidates = [
        f'avfc{suffix}.webp',
        f'avfc{stem}_c10.webp',
        f'avfc{stem}.webp',
    ]
    for c in candidates:
        if c in AVAILABLE_PORTRAITS:
            return c, 'face'
    # Any remaining variant, lowest suffix wins.
    variants = sorted(p for p in AVAILABLE_PORTRAITS
                      if p.startswith(f'avfc{stem}_') and p not in candidates)
    if variants:
        return variants[0], 'face'

    # Tier 2: noteface (no variant suffix)
    n = f'noteface_c{stem}.webp'
    if n in AVAILABLE_NOTES:
        return n, 'note'

    # Tier 3: btlface
    candidates = [
        f'btlface0_c{suffix}.webp',
        f'btlface0_c{stem}_c10.webp',
        f'btlface0_c{stem}.webp',
    ]
    for c in candidates:
        if c in AVAILABLE_BTLFACE:
            return c, 'btl'
    variants = sorted(p for p in AVAILABLE_BTLFACE
                      if p.startswith(f'btlface0_c{stem}_') and p not in candidates)
    if variants:
        return variants[0], 'btl'

    return None, None


def pc_icon_html(filename, tier):
    if not filename:
        return ''
    cls = {'face': 'itp-kuro', 'note': 'itp-noteface', 'btl': 'itp-btlface'}[tier]
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
    """Join dialogue lines. Strip <...> control tags and leftover #-codes."""
    text = ('\n'.join(lines)).strip()
    text = ANGLE_TAG_RE.sub('', text)
    text = HASH_CODE_RE.sub('', text)
    text = text.replace('\n', joiner)
    if joiner == ' ':
        text = WHITESPACE_RE.sub(' ', text)
    return text.strip()


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def collect_files(root):
    out = {}
    if not os.path.isdir(root):
        return out
    for entry in os.listdir(root):
        if not entry.endswith('.py'):
            continue
        stem = entry[:-3]
        if stem in SKIP_STEMS:
            continue
        if any(stem.startswith(p) for p in SKIP_PREFIXES):
            continue
        out[stem] = os.path.join(root, entry)
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
            return override
        entry = side_tname.get(chr_id)
        if not entry:
            return ''
        # EN preferred: full_name_en. JP preferred: name.
        return entry.get(side_field) or entry.get('name') or ''

    def portrait(chr_id):
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
