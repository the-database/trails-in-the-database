"""Extract Trails from Zero (game 4) dialogue into zero.sql.

Parses decompiled .py scena files from EDDecompiler. Each scena has a
`def main()` containing metadata calls (CreateScenaFile, BuildStringList,
DeclNpc, ...) followed by a sequence of placeholder `def Function_N_XXXX():
pass` declarations whose actual bodies are the calls that follow at the
same indent level. Dialogue is one of three calls:

  ChrTalk(char_id, text_or_tuple)
  NpcTalk(char_id, "speaker_name", text_or_tuple)
  AnonymousTalk(char_id, text_or_tuple)

Speaker resolution for ChrTalk follows the Falcom convention:
  - char_id >= 0x101  -> t_name[char_id - 0x101]   (party / main cast)
  - char_id == 0xFE   -> "current actor": most recent TalkBegin arg, or
                         the DeclNpc whose (talk_scena, talk_func) points
                         at this function. Resolves to BuildStringList
                         entry via DeclNpc.name_str_idx.
  - char_id 0x00-0xFD -> local DeclNpc index, resolves via BuildStringList.
SetChrName(name) latches a one-shot override for the current function.

Output schema matches games 11-13: insert into script (...) with 12
columns. op_name is populated with ChrTalk/NpcTalk/AnonymousTalk (the
old game-4 script's behavior). pc_icon_html uses the old-script format
(<img class="itp-xb" src="itp/4/ka{NNNNN}.webp"/>); voice wraps use the
newer-script .opus format.
"""

import ast
import json
import os
import re
import sys

ZERO_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'EDDecompiler', 'data', 'zero_batch')
JP_SCENA_ROOT = os.path.join(ZERO_ROOT, 'jp', 'scena')
EN_SCENA_ROOT = os.path.join(ZERO_ROOT, 'en', 'scena')
JP_TNAME = os.path.join(ZERO_ROOT, 'jp', 'text', 't_name._dt.json')
EN_TNAME = os.path.join(ZERO_ROOT, 'en', 'text', 't_name._dt.json')
GAME_ID = 4
OUTPUT = 'zero.sql'

# ChrTalk(0x101) -> t_name[0] (Lloyd), 0x102 -> t_name[1] (Elie), ...
PARTY_OFFSET = 0x101

DIALOGUE_OPS = ('ChrTalk', 'NpcTalk', 'AnonymousTalk')

WHITESPACE_RE = re.compile(r'[ \t]+')
VOICE_RE = re.compile(r'#(\d+)V')
FACE_RE = re.compile(r'#(\d+)F')
RUBY_RE = re.compile(r'#(\d+)R(.+?)#')
RESIDUAL_TAG_RE = re.compile(r'#\d+[A-Z]|#N')
# Color/format bytes that survive AST decoding but shouldn't be in output:
# \x00 NUL, \x05 (?), \x07 green color start, \x0c red color start, plus
# anything else under 0x20 except the meaningful \x01 (line break) /
# \x02 (terminator) / \x03 (page break with \x02). These three are handled
# explicitly in render_dialogue.
STRIP_CONTROL_RE = re.compile(r'[\x00\x04-\x06\x07\x08\x0b-\x1f]')


def _const_value(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
            return -node.operand.value
    return None


def _const_seq(node):
    if isinstance(node, (ast.Tuple, ast.List)):
        out = []
        for el in node.elts:
            v = _const_value(el)
            if v is None:
                return None
            out.append(v)
        return out
    return None


def _scpstr_placeholder(node):
    """Convert any `scpstr(...)` call inside a dialogue tuple to a string
    so the dialogue isn't dropped. Forms seen:
      scpstr(SCPSTR_CODE_ITEM, N)   -> '[item:N]'
      scpstr(SCPSTR_CODE_COLOR, N)  -> ''      (color codes have no text)
      scpstr(SCPSTR_CODE_X)         -> ''      (formatting/control)
      scpstr(0xD)                   -> ''      (raw numeric format code)
    Item/color tables are only available as binary in this dataset; the
    item-N form preserves the index for downstream lookup."""
    if not isinstance(node, ast.Call):
        return None
    fname = None
    if isinstance(node.func, ast.Name):
        fname = node.func.id
    elif isinstance(node.func, ast.Attribute):
        fname = node.func.attr
    if fname != 'scpstr':
        return None
    if not node.args:
        return ''
    tag = node.args[0]
    tag_name = tag.id if isinstance(tag, ast.Name) else None
    if tag_name == 'SCPSTR_CODE_ITEM' and len(node.args) >= 2:
        idx = _const_value(node.args[1])
        if isinstance(idx, int):
            return f'[item:{idx}]'
    return ''


def _string_lines(node):
    """Single string literal -> [s]. Tuple/list of string literals (with
    scpstr item-refs substituted as placeholders) -> [...]. Else None."""
    v = _const_value(node)
    if isinstance(v, str):
        return [v]
    if isinstance(node, (ast.Tuple, ast.List)):
        out = []
        for el in node.elts:
            ev = _const_value(el)
            if isinstance(ev, str):
                out.append(ev)
                continue
            ph = _scpstr_placeholder(el)
            if ph is not None:
                out.append(ph)
                continue
            return None
        return out
    return None


def _call_name(node):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
    return None


def load_tname(path):
    """Zero t_name._dt.json is a flat array: [{index, name, ...}]."""
    with open(path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    out = {}
    for entry in doc:
        idx = entry.get('index')
        if idx is None or idx in out:
            continue
        out[idx] = (entry.get('name') or '').strip()
    return out


def parse_scena(path):
    """Returns (ctx, dialogues).
      ctx = {'string_list': [...], 'npcs': [(name_str_idx, talk_scena, talk_func), ...]}
      dialogues = [(fn_idx, op_name, char_id, npc_inline, lines, talk_actor, latched), ...]
    """
    with open(path, 'r', encoding='utf-8-sig') as f:
        src = f.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f'WARN parse failed for {path}: {e}', file=sys.stderr)
        return {'string_list': [], 'npcs': []}, []

    main_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'main':
            main_fn = node
            break
    if main_fn is None:
        return {'string_list': [], 'npcs': []}, []

    string_list = []
    npcs = []
    dialogues = []

    fn_idx = -1
    talk_actor = None
    latched_name = ''

    for stmt in main_fn.body:
        if isinstance(stmt, ast.FunctionDef):
            fn_idx += 1
            talk_actor = None
            latched_name = ''
            continue

        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        name = _call_name(call)
        if name is None:
            continue

        if name == 'BuildStringList' and not string_list and call.args:
            seq = _const_seq(call.args[0])
            if seq is not None:
                string_list = [s if isinstance(s, str) else '' for s in seq]
            continue

        if name == 'DeclNpc' and fn_idx == -1:
            # BuildStringList layout is [scena_name, npc_0_name, npc_1_name, ...],
            # so DeclNpc position i picks BuildStringList[i + 1]. The NpcIndex
            # field in DeclNpc args is something else (animation/chip-related).
            args = [_const_value(a) for a in call.args]
            name_str_idx = len(npcs) + 1
            if len(args) >= 13:
                talk_scena = args[11] if isinstance(args[11], int) else None
                talk_func = args[12] if isinstance(args[12], int) else None
            else:
                talk_scena = talk_func = None
            npcs.append((name_str_idx, talk_scena, talk_func))
            continue

        if fn_idx < 0:
            continue

        if name == 'TalkBegin' and call.args:
            v = _const_value(call.args[0])
            if isinstance(v, int):
                talk_actor = v
            continue

        if name == 'SetChrName' and call.args:
            v = _const_value(call.args[0])
            if isinstance(v, str):
                latched_name = v
            continue

        if name in DIALOGUE_OPS:
            decoded = _decode_dialogue(name, call.args)
            if decoded is not None:
                char_id, npc_inline, lines = decoded
                dialogues.append((fn_idx, name, char_id, npc_inline, lines,
                                  talk_actor, latched_name))

    return {'string_list': string_list, 'npcs': npcs}, dialogues


def _decode_dialogue(op_name, args):
    if not args:
        return None
    char_id = _const_value(args[0])
    if not isinstance(char_id, int):
        return None
    npc_inline = None
    text_idx = 1
    if op_name == 'NpcTalk':
        if len(args) < 3:
            return None
        npc_inline = _const_value(args[1])
        if not isinstance(npc_inline, str):
            npc_inline = None
        text_idx = 2
    if text_idx >= len(args):
        return None
    lines = _string_lines(args[text_idx])
    if lines is None:
        return None
    return char_id, npc_inline, lines


def scena_num_for(stem):
    """'cXXXX' -> 0; 'cXXXX_N' -> N."""
    if '_' in stem:
        try:
            return int(stem.rsplit('_', 1)[1])
        except ValueError:
            return 0
    return 0


def resolve_speaker(char_id, op_name, npc_inline, latched, talk_actor,
                    ctx, fn_idx, scena_num, side_tname):
    if op_name == 'NpcTalk':
        return (npc_inline or '').strip()
    if latched:
        return latched.strip()
    if op_name == 'AnonymousTalk':
        return ''

    npcs = ctx['npcs']
    sl = ctx['string_list']

    def _from_tname(cid):
        return side_tname.get(cid - PARTY_OFFSET, '')

    def _from_npc_idx(idx):
        if idx is None or idx < 0 or idx >= len(npcs):
            return ''
        nsi = npcs[idx][0]
        if nsi is None or nsi < 0 or nsi >= len(sl):
            return ''
        return sl[nsi].strip()

    if char_id >= PARTY_OFFSET:
        return _from_tname(char_id)

    if char_id == 0xFE:
        eff = talk_actor if talk_actor not in (None, 0xFE) else 0xFE
        if eff != 0xFE and eff >= PARTY_OFFSET:
            return _from_tname(eff)
        if eff != 0xFE and 0 <= eff < 0xFE:
            return _from_npc_idx(eff)
        for i, (_, ts, tf) in enumerate(npcs):
            if ts == scena_num and tf == fn_idx:
                return _from_npc_idx(i)
        return ''

    return _from_npc_idx(char_id)


VOICE_CODE_LEN = 8


def _normalize_voice_id(digits):
    """Source codes are VOICE_CODE_LEN digits with a leading '1' (language/
    region prefix); the on-disk filename strips the leading digit — e.g.
    source #10100762V -> file v0100762.opus for Zero (8-digit codes)."""
    if digits.startswith('1') and len(digits) == VOICE_CODE_LEN:
        return digits[1:]
    return digits


def _split_voice_segments(text):
    """Split raw dialogue text on #NV voice markers. Returns a list of
    (voice_id_or_None, segment_text). Any leading text before the first
    voice marker is emitted as a segment with voice_id=None."""
    segments = []
    last = 0
    current_vid = None
    for m in VOICE_RE.finditer(text):
        segments.append((current_vid, text[last:m.start()]))
        current_vid = _normalize_voice_id(m.group(1))
        last = m.end()
    segments.append((current_vid, text[last:]))
    return [(vid, seg) for vid, seg in segments if seg]


def _extract_faces(text):
    faces = []

    def _sub(m):
        code = m.group(1)
        if len(code) < 5:
            code = '0' * (5 - len(code)) + code
        faces.append(f'<img class="itp-xb" src="itp/{GAME_ID}/ka{code}.webp"/>')
        return ''

    stripped = FACE_RE.sub(_sub, text)
    return ''.join(faces), stripped


_RUBY_STOP_CHARS = '\x01\x02\x03'


def _convert_ruby(text, html):
    """#NRfurigana#: the N is the count of preceding chars that form the
    ruby base. For HTML emit <ruby>base<rt>furigana</rt></ruby>; for
    search text drop the furigana annotation. The base never spans across
    a control-code boundary (line break / page break)."""
    out = []
    i = 0
    while True:
        m = RUBY_RE.search(text, i)
        if not m:
            out.append(text[i:])
            break
        prefix = text[i:m.start()]
        try:
            count = int(m.group(1))
        except ValueError:
            out.append(text[i:m.end()])
            i = m.end()
            continue
        # Don't let the ruby base swallow line/page breaks.
        max_back = len(prefix)
        for stop_ch in _RUBY_STOP_CHARS:
            cut = prefix.rfind(stop_ch)
            if cut != -1:
                max_back = min(max_back, len(prefix) - cut - 1)
        if count > max_back:
            count = max_back
        split = len(prefix) - count
        before = prefix[:split]
        base = prefix[split:]
        extra = m.group(2)
        out.append(before)
        if html:
            out.append(f'<ruby>{base}<rt>{extra}</rt></ruby>')
        else:
            out.append(base)
        i = m.end()
    return ''.join(out)


def _render_segment(seg_text, html):
    """Run a single voice-segment through the cleanup pipeline."""
    seg_text = STRIP_CONTROL_RE.sub('', seg_text)
    text = _convert_ruby(seg_text, html=html)
    text = RESIDUAL_TAG_RE.sub('', text)
    if html:
        text = text.replace('\x02\x03', '<br/><br/>').replace('\x01', '<br/>')
    else:
        text = text.replace('\x02\x03', ' ').replace('\x01', ' ')
        text = WHITESPACE_RE.sub(' ', text)
    text = text.replace('\x02', '').replace('\x03', '')
    return text.strip()


def render_dialogue(lines, wrap_voice):
    """Returns dict with html, search, faces_html. When wrap_voice is True,
    each #NV voice segment in the html is wrapped in its own <audio> link;
    when False, voice markers are stripped."""
    raw = ''.join(lines)
    faces_html, raw = _extract_faces(raw)
    segments = _split_voice_segments(raw)

    html_parts = []
    search_parts = []
    for vid, seg in segments:
        h = _render_segment(seg, html=True)
        s = _render_segment(seg, html=False)
        if wrap_voice and vid and h:
            h = voice_wrap(h, vid)
        if h:
            html_parts.append(h)
        if s:
            search_parts.append(s)

    return {
        'html': ''.join(html_parts),
        'search': ' '.join(search_parts),
        'faces_html': faces_html,
    }


def voice_wrap(html_text, voice_id):
    return (
        f'<audio id="v{voice_id}">'
        f'<source src="talk/{GAME_ID}/v{voice_id}.opus" type="audio/ogg; codecs=opus">'
        f'</audio>'
        f'<a href="javascript:void(0)" '
        f'onclick="document.getElementById(\'v{voice_id}\').play()">'
        f'{html_text}</a>'
    )


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def collect_files(root):
    out = {}
    if not os.path.isdir(root):
        return out
    for entry in os.listdir(root):
        if not entry.endswith('.py'):
            continue
        out[entry[:-3]] = os.path.join(root, entry)
    return out


def main():
    en_files = collect_files(EN_SCENA_ROOT)
    jp_files = collect_files(JP_SCENA_ROOT)
    print(f'files  EN={len(en_files)}  JP={len(jp_files)}')

    en_tname = load_tname(EN_TNAME)
    jp_tname = load_tname(JP_TNAME)
    print(f't_name  EN={len(en_tname)}  JP={len(jp_tname)}')

    empty_ctx = {'string_list': [], 'npcs': []}
    rows = []
    stems = sorted(set(en_files) | set(jp_files))
    for stem in stems:
        scena_num = scena_num_for(stem)
        en_ctx, en_d = parse_scena(en_files[stem]) if stem in en_files else (empty_ctx, [])
        jp_ctx, jp_d = parse_scena(jp_files[stem]) if stem in jp_files else (empty_ctx, [])
        if en_d and jp_d and len(en_d) != len(jp_d):
            print(f'WARN {stem}: EN={len(en_d)} JP={len(jp_d)}', file=sys.stderr)
        n = max(len(en_d), len(jp_d))
        if n == 0:
            continue
        rownum = 1
        for i in range(n):
            jp_t = jp_d[i] if i < len(jp_d) else None
            en_t = en_d[i] if i < len(en_d) else None
            canon = jp_t or en_t
            scene_idx, op_name, char_id, _, _, _, _ = canon

            jp_lines = jp_t[4] if jp_t else []
            en_lines = en_t[4] if en_t else []

            jpn_chr = resolve_speaker(
                char_id, op_name,
                jp_t[3] if jp_t else None,
                jp_t[6] if jp_t else '',
                jp_t[5] if jp_t else None,
                jp_ctx, scene_idx, scena_num, jp_tname,
            )
            eng_chr = resolve_speaker(
                char_id, op_name,
                en_t[3] if en_t else None,
                en_t[6] if en_t else '',
                en_t[5] if en_t else None,
                en_ctx, scene_idx, scena_num, en_tname,
            )

            jp_r = render_dialogue(jp_lines, wrap_voice=True) if jp_lines else None
            en_r = render_dialogue(en_lines, wrap_voice=False) if en_lines else None

            jp_html = jp_r['html'] if jp_r else ''
            en_html = en_r['html'] if en_r else ''
            jp_search = jp_r['search'] if jp_r else ''
            en_search = en_r['search'] if en_r else ''

            pc_icon = (jp_r and jp_r['faces_html']) or (en_r and en_r['faces_html']) or ''

            rows.append([
                str(GAME_ID), stem, str(scene_idx), str(rownum),
                eng_chr, en_search, en_html,
                jpn_chr, jp_search, jp_html,
                op_name, pc_icon,
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
