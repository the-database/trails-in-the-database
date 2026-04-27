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
      scpstr(SCPSTR_CODE_COLOR, N)  -> ' '     (color/formatting toggle)
      scpstr(SCPSTR_CODE_X)         -> ' '     (control codes like LINE_FEED,
                                                ENTER, etc.)
      scpstr(0xD)                   -> ' '     (raw CR / line break)
    A space is emitted instead of '' so that text on either side of the
    scpstr doesn't get word-joined (e.g. 'that Get' + scpstr(0xD) + 'Out of
    Jail Free' becoming 'GetOut of Jail Free')."""
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
        return ' '
    tag = node.args[0]
    tag_name = tag.id if isinstance(tag, ast.Name) else None
    if tag_name == 'SCPSTR_CODE_ITEM' and len(node.args) >= 2:
        idx = _const_value(node.args[1])
        if isinstance(idx, int):
            return f'[item:{idx}]'
    return ' '


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
            # Phantom NPC: position (0,0,0,0), no talk binding (255/255). The
            # writers declare these to reserve a BuildStringList name slot
            # without instantiating a real NPC — used as a scene-level
            # identity hint for chr_ids that get reused across identities.
            is_phantom = (
                len(args) >= 13
                and all(isinstance(args[i], int) and args[i] == 0 for i in range(4))
                and talk_scena == 255 and talk_func == 255
            )
            npcs.append((name_str_idx, talk_scena, talk_func, is_phantom))
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

    addressed = {char_id for (_fn, _op, char_id, _ni, _ln, _ta, _l) in dialogues
                 if isinstance(char_id, int)}
    chr_id_faces = {}
    for (_fn, _op, char_id, _ni, lines, _ta, _l) in dialogues:
        if not isinstance(char_id, int):
            continue
        fc = _face_char_for(lines)
        if fc is None:
            continue
        chr_id_faces.setdefault(char_id, set()).add(fc)
    return {'string_list': string_list, 'npcs': npcs,
            'addressed_chr_ids': addressed,
            'chr_id_faces': chr_id_faces}, dialogues


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
                    ctx, fn_idx, scena_num, side_tname,
                    face_char=None, face_to_known=None,
                    bsl_face_to_known=None):
    if op_name == 'NpcTalk':
        return (npc_inline or '').strip()

    npcs = ctx['npcs']
    sl = ctx['string_list']

    def _from_tname(cid):
        return side_tname.get(cid - PARTY_OFFSET, '')

    # t_name lookup for party / named cast (chr_id 0x101+) takes priority
    # over `latched`. SetChrName(name) is used to label AnonymousTalk(0xFF,
    # ...) narrator lines — not to relabel a real character whose chr_id
    # already identifies them via t_name. (Without this priority, a
    # `SetChrName("Tio")` upstream incorrectly relabels every party
    # member's subsequent dialogue as "Tio".)
    if isinstance(char_id, int) and char_id >= PARTY_OFFSET:
        name = _from_tname(char_id)
        # Identity-alias override via global BSL-face map (see Azure
        # extractor for full rationale). Only fire when the resolved
        # name is a singleton in t_name — protects main-cast slots
        # with chip variants (Lloyd/Elie/Tio/Randy/Wazy) from noisy
        # face-sharing in BSL signals.
        name_freq = ctx.get('tname_name_freq') or {}
        if (face_char and bsl_face_to_known
                and name_freq.get(name, 0) == 1):
            bsl_idx = bsl_face_to_known.get(face_char)
            if bsl_idx is not None:
                bsl_name = side_tname.get(bsl_idx, '')
                if bsl_name and bsl_name != name:
                    return bsl_name
        return name

    def _from_npc_idx(idx):
        if idx is None or idx < 0 or idx >= len(npcs):
            return ''
        nsi = npcs[idx][0]
        if nsi is None or nsi < 0 or nsi >= len(sl):
            return ''
        return sl[nsi].strip()

    # Falcom engine convention: char_ids 0x00-0x07 are the 8 active-party
    # slots (Lloyd/Elie/Tio/Randy/... whoever is in slot N at runtime). We
    # can't resolve these without simulating party state; return empty.
    # char_ids 0x08-0xFD are local NPCs indexed from DeclNpc[char_id-8],
    # mapping to BuildStringList via the position+1 rule.
    PARTY_SLOT_COUNT = 8

    def _from_local_npc(cid):
        return _from_npc_idx(cid - PARTY_SLOT_COUNT)

    def _from_face(side):
        """Face-code fallback: prefers BSL-derived face → t_name_idx
        map over chr_id-derived (BSL signals are more reliable for
        shared faces; see Azure extractor for full rationale)."""
        if face_char is None:
            return ''
        if bsl_face_to_known:
            bsl_idx = bsl_face_to_known.get(face_char)
            if bsl_idx is not None:
                return side.get(bsl_idx, '')
        if face_to_known:
            cid = face_to_known.get(face_char)
            if cid is not None:
                return side.get(cid, '')
        return ''

    # Precedence ladder (after the chr_id ≥ PARTY_OFFSET check above):
    #   1. latched in t_name — source explicitly labeled this line with a
    #      real character name (e.g. SetChrName("リーシャ") for Rixia).
    #      Wins over face because Rixia/Yin share faces but the source's
    #      scene label is canonical.
    #   2. local NPC via BuildStringList for chr_id 0x08-0xFD — the
    #      source's per-scene slot label. Wins over face for the same
    #      reason as #1.
    #   3. face — fallback when source has no specific label (typically
    #      0xFE with no DeclNpc match, party slot, or generic narrator).
    #   4. latched as-is — last-ditch even if not a known character.
    latched_clean = latched.strip() if latched else ''
    if latched_clean and latched_clean in side_tname.values():
        return latched_clean

    if isinstance(char_id, int) and PARTY_SLOT_COUNT <= char_id < 0xFE:
        local = _from_local_npc(char_id)
        if local:
            return local

    face = _from_face(side_tname)
    if face:
        return face

    if latched_clean:
        return latched_clean
    if op_name == 'AnonymousTalk':
        return ''

    if char_id == 0xFE:
        eff = talk_actor if talk_actor not in (None, 0xFE) else 0xFE
        if eff != 0xFE and eff >= PARTY_OFFSET:
            return _from_tname(eff)
        if eff != 0xFE and PARTY_SLOT_COUNT <= eff < 0xFE:
            return _from_local_npc(eff)
        for i, n in enumerate(npcs):
            ts, tf = n[1], n[2]
            if ts == scena_num and tf == fn_idx:
                return _from_npc_idx(i)
        return ''

    if 0 <= char_id < PARTY_SLOT_COUNT:
        return ''

    return _from_local_npc(char_id) if isinstance(char_id, int) else ''


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


def _lcs_pairs(a, b):
    """Longest common subsequence pairing on (op_name, char_id) signatures.
    Returns a list of (a_item_or_None, b_item_or_None) where matched items
    come as a pair and insertions/deletions come as one-sided entries."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n):
        ai = (a[i][1], a[i][2])
        for j in range(m):
            if ai == (b[j][1], b[j][2]):
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])
    out = []
    i, j = n, m
    while i > 0 and j > 0:
        if (a[i - 1][1], a[i - 1][2]) == (b[j - 1][1], b[j - 1][2]):
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
    """Align EN and JP dialogues scene-by-scene via LCS on (op_name, char_id).
    Function (scene) counts match across EN/JP in both Zero and Azure, so
    grouping by scene_idx gives safe reset boundaries. Within a scene, LCS
    tolerates translator-added/removed lines (Azure has ~72 such files)."""
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


def _face_char_for(lines):
    """Extract first face code's 3-digit char prefix from joined lines."""
    if not lines:
        return None
    text = ''.join(lines)
    m = FACE_RE.search(text)
    if not m:
        return None
    code = m.group(1)
    if len(code) < 5:
        code = '0' * (5 - len(code)) + code
    return code[:3]


def _name_freq(tname):
    """Count how many t_name entries share each name. Singletons may be
    aliased identities; multi-entry names are main-cast slots with
    chip variants and shouldn't be redirected by phantom overrides."""
    from collections import Counter
    return Counter(v for v in tname.values() if v)


def compute_phantom_overrides(ctx, tname):
    """Collect (bsl_name, face_set) for BSL slots named after a t_name
    character. Used as scene-level identity hints (see Azure extractor
    for full rationale)."""
    name_set = {v for v in tname.values() if v}
    sl = ctx.get('string_list') or []
    chr_id_faces = ctx.get('chr_id_faces') or {}
    out = []
    seen = set()
    for npc_idx, n in enumerate(ctx.get('npcs') or []):
        nsi = n[0]
        if nsi is None or not (0 <= nsi < len(sl)):
            continue
        bsl_name = sl[nsi].strip()
        if not bsl_name or bsl_name not in name_set or bsl_name in seen:
            continue
        chr_id = npc_idx + 8
        face_set = chr_id_faces.get(chr_id) or set()
        out.append((bsl_name, face_set))
        seen.add(bsl_name)
    return out


def build_bsl_face_to_known(parsed_files, jp_tname):
    """Global face_char → t_name_idx map learned from local NPCs whose
    BSL name matches a t_name entry (see Azure extractor for full
    rationale). Requires ≥ 90% purity and ≥ 2 supporting samples."""
    from collections import Counter
    name_to_idx = {}
    for idx, nm in jp_tname.items():
        if nm and nm not in name_to_idx:
            name_to_idx[nm] = idx
    face_votes = {}
    for ctx, _ in parsed_files:
        sl = ctx.get('string_list') or []
        chr_id_faces = ctx.get('chr_id_faces') or {}
        for npc_idx, n in enumerate(ctx.get('npcs') or []):
            nsi = n[0]
            if nsi is None or not (0 <= nsi < len(sl)):
                continue
            bsl_name = sl[nsi].strip()
            if not bsl_name or bsl_name not in name_to_idx:
                continue
            tname_idx = name_to_idx[bsl_name]
            chr_id = npc_idx + 8
            for fc in chr_id_faces.get(chr_id, ()):
                face_votes.setdefault(fc, Counter())[tname_idx] += 1
    out = {}
    for fc, cnt in face_votes.items():
        top, top_n = cnt.most_common(1)[0]
        total = sum(cnt.values())
        if top_n / total >= 0.9 and total >= 2:
            out[fc] = top
    return out


def build_face_to_known(parsed_files, jp_tname):
    """Learn `face_char (3-digit prefix) -> known_chr_id` from dialogues
    where chr_id resolves to a t_name main-cast entry. Used as a fallback
    speaker resolution for chr_id 0xFE / party-slot dialogues where the
    chr_id alone doesn't identify the character. Only emits mappings with
    >= 90% purity and >= 3 supporting samples."""
    from collections import Counter
    face_to_chrid = {}
    for parsed in parsed_files:
        for d in parsed:
            scene, op, char_id, npc_inline, lines, talk_actor, latched = d
            if not (isinstance(char_id, int) and char_id >= PARTY_OFFSET):
                continue
            cid = char_id - PARTY_OFFSET
            if cid not in jp_tname:
                continue
            face_char = _face_char_for(lines)
            if face_char is None:
                continue
            face_to_chrid.setdefault(face_char, Counter())[cid] += 1
    out = {}
    for fc, cnt in face_to_chrid.items():
        top, top_n = cnt.most_common(1)[0]
        total = sum(cnt.values())
        if top_n / total >= 0.9 and total >= 3:
            out[fc] = top
    return out


def main():
    en_files = collect_files(EN_SCENA_ROOT)
    jp_files = collect_files(JP_SCENA_ROOT)
    print(f'files  EN={len(en_files)}  JP={len(jp_files)}')

    en_tname = load_tname(EN_TNAME)
    jp_tname = load_tname(JP_TNAME)
    print(f't_name  EN={len(en_tname)}  JP={len(jp_tname)}')

    empty_ctx = {'string_list': [], 'npcs': [], 'addressed_chr_ids': set()}
    en_name_freq = _name_freq(en_tname)
    jp_name_freq = _name_freq(jp_tname)
    print('Pre-pass: building face_char -> chr_id map...', file=sys.stderr)
    parsed_jp = {stem: parse_scena(jp_files[stem]) for stem in jp_files}
    face_to_known = build_face_to_known(
        (dlg for _ctx, dlg in parsed_jp.values()), jp_tname,
    )
    print(f'  resolved {len(face_to_known)} face_char -> chr_id mappings', file=sys.stderr)
    bsl_face_to_known = build_bsl_face_to_known(parsed_jp.values(), jp_tname)
    print(f'  resolved {len(bsl_face_to_known)} BSL-confirmed face_char -> chr_id mappings', file=sys.stderr)

    rows = []
    stems = sorted(set(en_files) | set(jp_files))
    for stem in stems:
        scena_num = scena_num_for(stem)
        en_ctx, en_d = parse_scena(en_files[stem]) if stem in en_files else (empty_ctx, [])
        jp_ctx, jp_d = parsed_jp.get(stem, (empty_ctx, []))
        en_ctx['phantom_overrides'] = compute_phantom_overrides(en_ctx, en_tname)
        en_ctx['tname_name_freq'] = en_name_freq
        jp_ctx['phantom_overrides'] = compute_phantom_overrides(jp_ctx, jp_tname)
        jp_ctx['tname_name_freq'] = jp_name_freq
        pairs = align_scenes(en_d, jp_d)
        if not pairs:
            continue
        unpaired = sum(1 for e, j in pairs if e is None or j is None)
        if unpaired:
            print(f'WARN {stem}: {unpaired} unpaired rows '
                  f'(EN={len(en_d)} JP={len(jp_d)})', file=sys.stderr)
        rownum = 1
        for en_t, jp_t in pairs:
            canon = jp_t or en_t
            scene_idx, op_name, char_id, _, _, _, _ = canon

            jp_lines = jp_t[4] if jp_t else []
            en_lines = en_t[4] if en_t else []

            face_char = _face_char_for(jp_lines) or _face_char_for(en_lines)

            jpn_chr = resolve_speaker(
                char_id, op_name,
                jp_t[3] if jp_t else None,
                jp_t[6] if jp_t else '',
                jp_t[5] if jp_t else None,
                jp_ctx, scene_idx, scena_num, jp_tname,
                face_char=face_char, face_to_known=face_to_known,
                bsl_face_to_known=bsl_face_to_known,
            )
            eng_chr = resolve_speaker(
                char_id, op_name,
                en_t[3] if en_t else None,
                en_t[6] if en_t else '',
                en_t[5] if en_t else None,
                en_ctx, scene_idx, scena_num, en_tname,
                face_char=face_char, face_to_known=face_to_known,
                bsl_face_to_known=bsl_face_to_known,
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
