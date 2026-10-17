"""Diff two Sky 1st Chapter (game 101) extractions and report what the patch changed.

    python diff-sky1r.py                       # sky1r.sql vs sky1r-new.sql
    python diff-sky1r.py OLD.sql NEW.sql       # explicit pair
    python diff-sky1r.py OLD.sql NEW.sql PREFIX  # write PREFIX.txt / PREFIX.html

Emits `<prefix>.txt` (full diff, greppable) and `<prefix>.html` (browsable
report), defaulting to `sky1r-script-diff`. The matching places pair is
derived from the script filenames and folded into the same report when both
sides exist.

A row counts as changed when its speaker or its searchable text moved:
eng_chr_name, eng_search_text, jpn_chr_name, jpn_search_text. Rows differing
only in the HTML wrapper (portrait <img>, voice <a data-audio>) are counted and
reported in the summary but kept out of the hunks, so they are never silently
dropped.

Alignment runs per fname with difflib, so an inserted line in one map does not
cascade into every row after it.

Changed lines are then split into two piles, because they want different kinds
of review:

  * **terminology** - the line changed only because a term was renamed
    (Jade Tower -> Esmelas Tower). Worth reading once as a glossary, not 26
    times as a diff.
  * **rewrites** - everything else: the line was actually reworded.

A substitution counts as terminology once it recurs across at least
MIN_TERM_CONTEXTS separate sentences; a line is terminology-only when every word-level
change in it is one of those. Punctuation-only shuffles never make a term, and
never on their own keep a line out of the rewrite pile.
"""

import difflib
import html
import os
import re
import sys
from collections import Counter, OrderedDict

SCRIPT_COLS = ['game_id', 'fname', 'scene', 'row', 'eng_chr_name',
               'eng_search_text', 'eng_html_text', 'jpn_chr_name',
               'jpn_search_text', 'jpn_html_text', 'op_name', 'pc_icon_html']
PLACE_COLS = ['game_id', 'fname', 'place_name_eng', 'place_name_jpn']

# game_id -> (short name for <title>, full name for the header). The report
# is otherwise game-agnostic, so Zero/Azure reuse it as-is.
GAME_NAMES = {
    '101': ('Sky 1st', 'Trails in the Sky 1st Chapter'),
    '4': ('Zero', 'Trails from Zero'),
    '5': ('Azure', 'Trails to Azure'),
}

# The fields that define "this line of dialogue changed".
KEY_FIELDS = ('eng_chr_name', 'eng_search_text', 'jpn_chr_name', 'jpn_search_text')

# A substitution is a renamed term once it turns up in at least this many
# *distinct sentences*. Counting distinct sentences rather than rows matters:
# the script duplicates some lines verbatim, and counting rows would promote a
# one-off rewording to a "term" purely because its line appears twice.
MIN_TERM_CONTEXTS = 2

# A term is a short noun-ish fragment. Anything longer is a reworded clause.
MAX_TERM_WORDS = 5
MAX_TERM_CHARS = 32

# Hard ceiling on hunks rendered into the HTML. Any overflow is stated in the
# report header and printed to stdout -- never a silent truncation.
MAX_HTML_HUNKS = 8000

# Whole words for Latin text, single characters for CJK: the right granularity
# for both halves of this script.
TOKEN_RE = re.compile(r"\s+|[A-Za-z0-9_']+|.", re.S)

# Any letter, digit or CJK character. A fragment without one is punctuation.
WORDY_RE = re.compile(r'[^\W_]', re.UNICODE)

# Runs of word characters, for measuring how many words a fragment holds.
WORD_RUN_RE = re.compile(r'[^\W_]+', re.UNICODE)


# ---------------------------------------------------------------- parsing

def unescape(field):
    r"""Invert the extractor's sql_escape(): \\ -> \, \Z -> \x1a, '' -> '."""
    out = []
    i = 0
    n = len(field)
    while i < n:
        c = field[i]
        if c == '\\' and i + 1 < n:
            nxt = field[i + 1]
            if nxt == '\\':
                out.append('\\')
            elif nxt == 'Z':
                out.append('\x1a')
            else:
                out.append(nxt)
            i += 2
        elif c == "'" and i + 1 < n and field[i + 1] == "'":
            out.append("'")
            i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def split_tuple(body):
    """Split the inner text of ('a','b',...) into raw, still-escaped fields."""
    # Fast path: with no doubled quotes and no backslashes anywhere, "','" can
    # only be a separator and never content.
    if "''" not in body and '\\' not in body:
        return body[1:-1].split("','")
    fields = []
    i = 0
    n = len(body)
    while i < n:
        assert body[i] == "'", 'expected quote at %d: %r' % (i, body[i:i + 20])
        i += 1
        start = i
        while True:
            c = body[i]
            if c == '\\':
                i += 2
            elif c == "'":
                if i + 1 < n and body[i + 1] == "'":
                    i += 2
                else:
                    break
            else:
                i += 1
        fields.append(body[start:i])
        i += 1
        if i < n and body[i] == ',':
            i += 1
    return fields


def load_sql(path, cols):
    """Read an extractor .sql into a list of dicts, preserving emit order."""
    rows = []
    pending = None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if pending is not None:
                pending += '\n' + line
            elif line.startswith("('"):
                pending = line
            else:
                continue
            if not pending.endswith(');'):
                continue
            raw = split_tuple(pending[1:-2])
            pending = None
            if len(raw) != len(cols):
                raise ValueError('%s: expected %d fields, got %d'
                                 % (path, len(cols), len(raw)))
            rows.append(dict(zip(cols, (unescape(v) for v in raw))))
    return rows


def by_fname(rows):
    groups = OrderedDict()
    for r in rows:
        groups.setdefault(r['fname'], []).append(r)
    return groups


# ---------------------------------------------------------------- diffing

class Hunk:
    """One aligned old/new pair, or a pure insertion / deletion."""

    __slots__ = ('old', 'new', 'sides', 'cls', 'terms', 'place')

    def __init__(self, old, new, sides, place=False):
        self.old = old
        self.new = new
        self.sides = sides          # ('en',) / ('jp',) / ('en', 'jp')
        self.place = place
        self.cls = 'rewrite'        # set by classify()
        self.terms = []             # glossary entries that explain this line

    @property
    def kind(self):
        if self.old is None:
            return 'added'
        if self.new is None:
            return 'removed'
        return 'changed'

    def field(self, name):
        return (self.new or self.old)[name]


def side_fields(side):
    """The (speaker, text) columns for one language of the script table."""
    if side == 'en':
        return 'eng_chr_name', 'eng_search_text'
    return 'jpn_chr_name', 'jpn_search_text'


def place_fields(side):
    """The single text column for one language of the file (places) table."""
    return ('place_name_eng',) if side == 'en' else ('place_name_jpn',)


def sides_changed(old, new, place=False):
    if old is None or new is None:
        return ('en', 'jp')
    out = []
    for side in ('en', 'jp'):
        fields = place_fields(side) if place else side_fields(side)
        if any(old[f] != new[f] for f in fields):
            out.append(side)
    return tuple(out)


def diff_rows(old_rows, new_rows, cols):
    """Per-fname alignment. Returns (hunks, stats)."""
    is_place = cols is PLACE_COLS
    key = (lambda r: (r['place_name_eng'], r['place_name_jpn'])) if is_place \
        else (lambda r: tuple(r[f] for f in KEY_FIELDS))
    old_g = by_fname(old_rows)
    new_g = by_fname(new_rows)
    stats = {
        'old_rows': len(old_rows), 'new_rows': len(new_rows),
        'files_old': len(old_g), 'files_new': len(new_g),
        'files_added': [], 'files_removed': [], 'files_changed': [],
        'changed': 0, 'added': 0, 'removed': 0,
        'en_changed': 0, 'jp_changed': 0, 'cosmetic_only': 0,
        'rewrites': 0, 'terminology': 0,
    }
    hunks = []

    for fname in sorted(set(old_g) | set(new_g)):
        o = old_g.get(fname, [])
        n = new_g.get(fname, [])
        if not o:
            stats['files_added'].append(fname)
        elif not n:
            stats['files_removed'].append(fname)

        sm = difflib.SequenceMatcher(None, [key(r) for r in o],
                                     [key(r) for r in n], autojunk=False)
        file_hunks = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                # Same key, but the html/icon columns may still differ.
                for oi, nj in zip(range(i1, i2), range(j1, j2)):
                    if o[oi] != n[nj]:
                        stats['cosmetic_only'] += 1
                continue
            if tag == 'replace':
                # Pair positionally; any leftover becomes an add or a remove.
                for k in range(max(i2 - i1, j2 - j1)):
                    ov = o[i1 + k] if i1 + k < i2 else None
                    nv = n[j1 + k] if j1 + k < j2 else None
                    file_hunks.append(
                        Hunk(ov, nv, sides_changed(ov, nv, is_place), is_place))
            elif tag == 'delete':
                for oi in range(i1, i2):
                    file_hunks.append(Hunk(o[oi], None, ('en', 'jp'), is_place))
            elif tag == 'insert':
                for nj in range(j1, j2):
                    file_hunks.append(Hunk(None, n[nj], ('en', 'jp'), is_place))

        if file_hunks:
            stats['files_changed'].append(fname)
            for h in file_hunks:
                stats[h.kind] += 1
                if 'en' in h.sides:
                    stats['en_changed'] += 1
                if 'jp' in h.sides:
                    stats['jp_changed'] += 1
            hunks.extend(file_hunks)

    return hunks, stats


def token_diff(a, b):
    """Word/char-level opcodes for intra-line highlighting."""
    at = TOKEN_RE.findall(a)
    bt = TOKEN_RE.findall(b)
    sm = difflib.SequenceMatcher(None, at, bt, autojunk=False)
    old_parts, new_parts = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        same = tag == 'equal'
        if i1 != i2:
            old_parts.append((same, ''.join(at[i1:i2])))
        if j1 != j2:
            new_parts.append((same, ''.join(bt[j1:j2])))
    return old_parts, new_parts


# --------------------------------------------- terminology vs real rewrites

def diff_ops(a, b):
    """Token-level (old_fragment, new_fragment) substitutions between a and b."""
    at = TOKEN_RE.findall(a)
    bt = TOKEN_RE.findall(b)
    sm = difflib.SequenceMatcher(None, at, bt, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        out.append((''.join(at[i1:i2]).strip(), ''.join(bt[j1:j2]).strip()))
    return out


def is_trivial(old, new):
    """True when neither side holds a letter, digit or CJK character."""
    return not (WORDY_RE.search(old) or WORDY_RE.search(new))


def hunk_ops(h):
    """[(side, old, new)] for this hunk, or None for a pure add/remove."""
    if h.old is None or h.new is None:
        return None
    ops = []
    for side in ('en', 'jp'):
        if h.place:
            text_field = place_fields(side)[0]
            speaker_field = None
        else:
            speaker_field, text_field = side_fields(side)
        if speaker_field and h.old[speaker_field] != h.new[speaker_field]:
            ops.append((side, h.old[speaker_field].strip(),
                        h.new[speaker_field].strip()))
        for o, n in diff_ops(h.old[text_field], h.new[text_field]):
            ops.append((side, o, n))
    return ops


def term_eligible(old, new):
    """Could this substitution be a renamed term, by shape alone?

    A rename swaps one short name for another. An insertion, a deletion, a
    punctuation shuffle, or a whole reworded clause is not a term however often
    it recurs -- two unrelated rewrites can easily share a comma-to-ellipsis
    shift, and calling that terminology would hide real rewording.
    """
    if not old or not new:
        return False
    if is_trivial(old, new):
        return False
    if len(old) > MAX_TERM_CHARS or len(new) > MAX_TERM_CHARS:
        return False
    return (len(WORD_RUN_RE.findall(old)) <= MAX_TERM_WORDS
            and len(WORD_RUN_RE.findall(new)) <= MAX_TERM_WORDS)


def op_context(h, side):
    """The old text the substitution sat in, used to tell sentences apart."""
    if h.place:
        return h.old[place_fields(side)[0]]
    return h.old[side_fields(side)[1]]


def classify(all_hunks):
    """Tag every hunk as 'term' or 'rewrite'. Returns the glossary.

    Glossary maps (side, old, new) -> number of lines the term appears on.
    Promotion to a term is decided on distinct *sentences*, though, so a line
    duplicated verbatim in the script cannot promote its own rewording.
    """
    per_hunk = [(h, hunk_ops(h)) for h in all_hunks]

    contexts = {}       # op -> set of distinct surrounding sentences
    line_count = Counter()
    for h, ops in per_hunk:
        if not ops:
            continue
        # Count each substitution once per line, not once per occurrence.
        for op in set(ops):
            if not term_eligible(op[1], op[2]):
                continue
            contexts.setdefault(op, set()).add(op_context(h, op[0]))
            line_count[op] += 1
    glossary = {op: line_count[op] for op, seen in contexts.items()
                if len(seen) >= MIN_TERM_CONTEXTS}

    for h, ops in per_hunk:
        if not ops:                       # added / removed line, or no ops
            h.cls = 'rewrite'
            h.terms = []
            continue
        terms = [op for op in ops if op in glossary]
        unexplained = [op for op in ops
                       if op not in glossary and not is_trivial(op[1], op[2])]
        h.cls = 'term' if terms and not unexplained else 'rewrite'
        # Preserve order of first appearance, without duplicates.
        h.terms = list(OrderedDict.fromkeys(terms))

    return glossary


def glossary_rows(glossary):
    """Glossary as a display-ordered list: most-used first, then alphabetical."""
    rows = [(side, old, new, count)
            for (side, old, new), count in glossary.items()]
    rows.sort(key=lambda r: (r[0] != 'en', -r[3], r[1].lower()))
    return rows


# ---------------------------------------------------------------- text out

def write_txt(path, hunks, stats, old_name, new_name, place, glossary):
    rewrites = [h for h in hunks if h.cls == 'rewrite']
    terms_only = [h for h in hunks if h.cls == 'term']
    grows = glossary_rows(glossary)

    def term_label(op):
        return '%s: %s -> %s' % (op[0].upper(), op[1] or '(nothing)',
                                 op[2] or '(nothing)')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('--- %s\n+++ %s\n' % (old_name, new_name))
        f.write('# script table: rows %d -> %d; %d changed '
                '(%d rewritten, %d terminology-only), %d added, %d removed, '
                '%d html/icon-only\n'
                % (stats['old_rows'], stats['new_rows'], stats['changed'],
                   len(rewrites), len(terms_only), stats['added'],
                   stats['removed'], stats['cosmetic_only']))
        f.write('# EN side moved on %d rows, JP side moved on %d\n'
                % (stats['en_changed'], stats['jp_changed']))
        f.write('# %d of %d files changed\n'
                % (len(stats['files_changed']), stats['files_new']))

        # ---- 1. glossary
        f.write('\n\n')
        f.write('=' * 72 + '\n')
        f.write('TERMINOLOGY  (%d renamed terms)\n' % len(grows))
        f.write('=' * 72 + '\n')
        f.write('A substitution listed here recurs on at least %d lines. Lines\n'
                'whose only changes are these terms are collected at the end of\n'
                'this file rather than shown as individual diffs.\n\n'
                % MIN_TERM_CONTEXTS)
        if grows:
            width = max(len(r[1]) for r in grows)
            for side, old, new, count in grows:
                f.write('  %s  %-*s  ->  %-*s  %4d line%s\n'
                        % (side.upper(), width, old or '(nothing)',
                           width, new or '(nothing)', count,
                           '' if count == 1 else 's'))
        else:
            f.write('  (none)\n')

        # ---- 2. real rewrites
        f.write('\n\n')
        f.write('=' * 72 + '\n')
        f.write('REWRITTEN DIALOGUE  (%d lines)\n' % len(rewrites))
        f.write('=' * 72 + '\n')
        f.write('Lines that changed beyond the terminology above.\n')

        current = None
        for h in rewrites:
            fname = h.field('fname')
            if fname != current:
                current = fname
                f.write('\n\n### %s\n' % current)
            f.write('\n@@ scene %s row %s @@ %s [%s]\n'
                    % (h.field('scene'), h.field('row'), h.kind.upper(),
                       '+'.join(s.upper() for s in h.sides)))
            for label, side in (('EN', 'en'), ('JP', 'jp')):
                cf, tf = side_fields(side)
                ov = '%s | %s' % (h.old[cf], h.old[tf]) if h.old else None
                nv = '%s | %s' % (h.new[cf], h.new[tf]) if h.new else None
                if ov == nv:
                    f.write('  %s %s\n' % (label, ov))
                    continue
                if ov is not None:
                    f.write('- %s %s\n' % (label, ov))
                if nv is not None:
                    f.write('+ %s %s\n' % (label, nv))

        # ---- 3. terminology-only lines, listed but not spelled out
        f.write('\n\n')
        f.write('=' * 72 + '\n')
        f.write('TERMINOLOGY-ONLY LINES  (%d lines)\n' % len(terms_only))
        f.write('=' * 72 + '\n')
        f.write('Nothing changed on these lines except the terms named above.\n\n')
        for h in terms_only:
            f.write('  %-16s scene %-5s row %-6s %s\n'
                    % (h.field('fname'), h.field('scene'), h.field('row'),
                       '; '.join(term_label(t) for t in h.terms)))

        # ---- 4. places
        if place is not None:
            phunks, pstats = place
            f.write('\n\n')
            f.write('=' * 72 + '\n')
            f.write('FILE TABLE / PLACE NAMES  (rows %d -> %d; %d changed, '
                    '%d added, %d removed)\n'
                    % (pstats['old_rows'], pstats['new_rows'], pstats['changed'],
                       pstats['added'], pstats['removed']))
            f.write('=' * 72 + '\n')
            for h in phunks:
                tag = 'terminology' if h.cls == 'term' else 'rewrite'
                f.write('\n@@ %s @@ %s (%s)\n'
                        % (h.field('fname'), h.kind.upper(), tag))
                for label, fld in (('EN', 'place_name_eng'),
                                   ('JP', 'place_name_jpn')):
                    ov = h.old[fld] if h.old else None
                    nv = h.new[fld] if h.new else None
                    if ov == nv:
                        f.write('  %s %s\n' % (label, ov))
                        continue
                    if ov is not None:
                        f.write('- %s %s\n' % (label, ov))
                    if nv is not None:
                        f.write('+ %s %s\n' % (label, nv))


# ---------------------------------------------------------------- html out

CSS = """
:root{
  --ground:#eef1f5; --surface:#ffffff; --surface-2:#f6f8fa;
  --ink:#141d27; --muted:#5c6a79; --faint:#8b98a6;
  --line:#d8e0e8; --line-soft:#e8edf2;
  --accent:#1f5f96; --accent-soft:#dce9f4;
  --old:#9c3a26; --old-bg:#fbe9e4; --old-mark:#f3c7ba;
  --new:#0f6a4c; --new-bg:#e4f3ec; --new-mark:#b6e2ce;
  --term:#7a4e12; --term-soft:#f6ecd9;
  --shadow:0 1px 2px rgba(20,29,39,.06),0 4px 14px rgba(20,29,39,.05);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0d141c; --surface:#141d27; --surface-2:#18222e;
    --ink:#e3eaf2; --muted:#93a2b3; --faint:#6d7d8e;
    --line:#243141; --line-soft:#1c2734;
    --accent:#74aada; --accent-soft:#1a2c3d;
    --old:#e59279; --old-bg:#2b1913; --old-mark:#5c2c1e;
    --new:#66c8a1; --new-bg:#0f2820; --new-mark:#1d4d3a;
    --term:#d8b070; --term-soft:#2a2114;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 4px 14px rgba(0,0,0,.25);
  }
}
:root[data-theme="dark"]{
  --ground:#0d141c; --surface:#141d27; --surface-2:#18222e;
  --ink:#e3eaf2; --muted:#93a2b3; --faint:#6d7d8e;
  --line:#243141; --line-soft:#1c2734;
  --accent:#74aada; --accent-soft:#1a2c3d;
  --old:#e59279; --old-bg:#2b1913; --old-mark:#5c2c1e;
  --new:#66c8a1; --new-bg:#0f2820; --new-mark:#1d4d3a;
  --term:#d8b070; --term-soft:#2a2114;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 4px 14px rgba(0,0,0,.25);
}

*{box-sizing:border-box;}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:'IBM Plex Sans',ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;
  font-size:15px; line-height:1.55;
}
.wrap{max-width:1180px; margin:0 auto; padding:0 24px 96px;}

/* ---- masthead ---- */
header.top{
  border-bottom:1px solid var(--line);
  background:linear-gradient(180deg,var(--surface),var(--surface-2));
}
.top-inner{max-width:1180px; margin:0 auto; padding:34px 24px 26px;
  display:flex; flex-direction:column; gap:6px;}
.eyebrow{
  font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:11.5px;
  letter-spacing:.14em; text-transform:uppercase; color:var(--accent);
}
h1{margin:0; font-family:'Newsreader',Georgia,serif; font-weight:500;
  font-size:clamp(28px,4vw,40px); line-height:1.12; text-wrap:balance;
  letter-spacing:-.01em;}
.sub{margin:2px 0 0; color:var(--muted); max-width:68ch;}
.sub code,.note code{font-family:'IBM Plex Mono',ui-monospace,monospace;
  font-size:.9em; background:var(--surface-2);
  border:1px solid var(--line-soft); border-radius:4px; padding:1px 5px;}

/* ---- stat tiles ---- */
.tiles{display:grid; gap:12px; margin:26px 0 0;
  grid-template-columns:repeat(auto-fit,minmax(158px,1fr));}
.tile{background:var(--surface); border:1px solid var(--line);
  border-radius:9px; padding:13px 15px; box-shadow:var(--shadow);}
.tile .n{font-family:'IBM Plex Mono',ui-monospace,monospace;
  font-size:25px; font-weight:600; line-height:1.15;
  font-variant-numeric:tabular-nums; letter-spacing:-.02em;}
.tile .l{font-size:11.5px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--muted); margin-top:3px;}
.tile.is-old .n{color:var(--old);} .tile.is-new .n{color:var(--new);}
.tile.is-accent .n{color:var(--accent);} .tile.is-term .n{color:var(--term);}

.note{margin:20px 0 0; padding:12px 15px; border-radius:8px;
  background:var(--accent-soft); border:1px solid var(--line);
  color:var(--ink); font-size:13.5px;}
.note b{font-weight:600;}

/* ---- glossary ---- */
.gloss{margin:34px 0 0;}
.gloss h2{margin:0 0 4px; font-family:'Newsreader',Georgia,serif;
  font-weight:500; font-size:25px; letter-spacing:-.01em;}
.gloss p{margin:0 0 14px; color:var(--muted); font-size:13.5px; max-width:68ch;}
.tablewrap{overflow-x:auto; background:var(--surface);
  border:1px solid var(--line); border-radius:9px; box-shadow:var(--shadow);}
table{border-collapse:collapse; width:100%; min-width:520px;}
thead th{text-align:left; font-size:11px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--muted); font-weight:500;
  padding:10px 15px; border-bottom:1px solid var(--line);
  background:var(--surface-2); position:sticky; top:0;}
tbody td{padding:9px 15px; border-bottom:1px solid var(--line-soft);
  vertical-align:baseline;}
tbody tr:last-child td{border-bottom:0;}
td.t-old,td.t-new{font-family:'Newsreader',Georgia,'Yu Mincho','Hiragino Mincho ProN',serif;
  font-size:16px; overflow-wrap:anywhere;}
td.t-old{color:var(--old);} td.t-new{color:var(--new);}
td.t-arrow{color:var(--faint); font-family:'IBM Plex Mono',ui-monospace,monospace;
  width:1px; padding:9px 4px;}
td.t-lang{width:1px; padding-right:0;}
td.t-count{text-align:right; width:1px; white-space:nowrap;
  font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:13px;
  color:var(--muted); font-variant-numeric:tabular-nums;}
.lang{font-size:10.5px; font-weight:600; letter-spacing:.07em;
  text-transform:uppercase; padding:2px 7px; border-radius:4px;
  color:var(--accent); background:var(--accent-soft);}

/* ---- controls ---- */
.controls{position:sticky; top:0; z-index:5; margin:34px 0 0;
  padding:12px 0; background:var(--ground);
  border-bottom:1px solid var(--line);
  display:flex; flex-wrap:wrap; gap:10px; align-items:center;}
input[type=search]{
  flex:1 1 220px; min-width:0; padding:8px 12px; font:inherit; font-size:14px;
  color:var(--ink); background:var(--surface);
  border:1px solid var(--line); border-radius:7px;}
input[type=search]:focus-visible,.chip:focus-visible{
  outline:2px solid var(--accent); outline-offset:2px;}
.chips{display:flex; gap:6px; flex-wrap:wrap;}
.chip{font:inherit; font-size:12.5px; padding:6px 12px; cursor:pointer;
  color:var(--muted); background:var(--surface);
  border:1px solid var(--line); border-radius:999px;}
.chip[aria-pressed=true]{color:var(--surface); background:var(--accent);
  border-color:var(--accent);}
.count{font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:12px;
  color:var(--faint); margin-left:auto; font-variant-numeric:tabular-nums;}

/* ---- file sections ---- */
h2.file{margin:34px 0 0; padding:0 0 7px; border-bottom:2px solid var(--line);
  font-family:'IBM Plex Mono',ui-monospace,monospace;
  font-size:17px; font-weight:600; letter-spacing:-.01em;
  display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;}
h2.file .place{font-family:'Newsreader',Georgia,serif; font-weight:400;
  font-size:16px; color:var(--muted);}
h2.file .n{font-family:'IBM Plex Sans',sans-serif; font-size:11.5px;
  font-weight:500; letter-spacing:.06em; text-transform:uppercase;
  color:var(--faint); margin-left:auto;}

/* ---- hunks ---- */
.hunk{margin:14px 0 0; background:var(--surface); border:1px solid var(--line);
  border-radius:9px; box-shadow:var(--shadow); overflow:hidden;}
.hunk-head{display:flex; gap:9px; align-items:center; flex-wrap:wrap;
  padding:7px 13px; background:var(--surface-2);
  border-bottom:1px solid var(--line-soft);
  font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:11.5px;
  color:var(--muted); font-variant-numeric:tabular-nums;}
.tag{font-family:'IBM Plex Sans',sans-serif; font-size:10.5px; font-weight:600;
  letter-spacing:.07em; text-transform:uppercase; padding:2px 7px;
  border-radius:4px; border:1px solid transparent;}
.tag.en,.tag.jp{color:var(--accent); background:var(--accent-soft);}
.tag.added{color:var(--new); background:var(--new-bg); border-color:var(--new-mark);}
.tag.removed{color:var(--old); background:var(--old-bg); border-color:var(--old-mark);}
.tag.term{color:var(--term); background:var(--term-soft);}
.termlist{font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:11px;
  color:var(--faint); margin-left:auto; text-align:right;}

.pair{display:grid; grid-template-columns:1fr 1fr;}
@media (max-width:760px){.pair{grid-template-columns:1fr;}}
.cell{padding:11px 14px; min-width:0;}
.cell.old{background:var(--old-bg); border-right:1px solid var(--line-soft);}
.cell.new{background:var(--new-bg);}
@media (max-width:760px){
  .cell.old{border-right:0; border-bottom:1px solid var(--line-soft);}
}
.cell .side{font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:10.5px;
  letter-spacing:.1em; text-transform:uppercase; margin-bottom:5px;}
.cell.old .side{color:var(--old);} .cell.new .side{color:var(--new);}
.speaker{font-size:12.5px; font-weight:600; color:var(--muted); margin-bottom:2px;}
.speaker:empty::before{content:'\\2014'; color:var(--faint); font-weight:400;}
.text{font-family:'Newsreader',Georgia,'Yu Mincho','Hiragino Mincho ProN',serif;
  font-size:16.5px; line-height:1.5; overflow-wrap:anywhere;}
.cell.old mark{background:var(--old-mark); color:inherit; border-radius:2px;
  padding:0 1px;}
.cell.new mark{background:var(--new-mark); color:inherit; border-radius:2px;
  padding:0 1px;}
mark{text-decoration:none;}

.context{padding:9px 14px; border-top:1px solid var(--line-soft);
  background:var(--surface);}
.context .side{font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:10.5px;
  letter-spacing:.1em; text-transform:uppercase; color:var(--faint);
  margin-bottom:4px;}
.context .speaker,.context .text{color:var(--muted);}
.context .text{font-size:15px;}

.empty{color:var(--faint); font-style:italic; font-size:14px;}
.hidden{display:none !important;}
#none{margin:40px 0; text-align:center; color:var(--muted);}

footer{margin:56px 0 0; padding:18px 0 0; border-top:1px solid var(--line);
  color:var(--faint); font-size:12.5px;}
footer code{font-family:'IBM Plex Mono',ui-monospace,monospace;}
"""

JS = """
(function(){
  var q=document.getElementById('q');
  var secs=Array.prototype.slice.call(document.querySelectorAll('section.filegroup'));
  var grows=Array.prototype.slice.call(document.querySelectorAll('tr.grow'));
  var gsec=document.getElementById('glossary');
  var out=document.getElementById('shown');
  var none=document.getElementById('none');
  var mode='rewrite', lang='all';

  function group(name){
    return Array.prototype.slice.call(
      document.querySelectorAll('.chip[data-group="'+name+'"]'));
  }

  function apply(){
    var term=q.value.trim().toLowerCase();
    var total=0;
    secs.forEach(function(sec){
      var vis=0;
      Array.prototype.forEach.call(sec.querySelectorAll('.hunk'),function(h){
        var okMode = mode==='all' || h.dataset.cls===mode;
        var okLang = lang==='all'
          || (lang==='en' && h.dataset.en==='1')
          || (lang==='jp' && h.dataset.jp==='1');
        var okTerm = !term
          || h.dataset.search.indexOf(term)>-1
          || sec.dataset.fname.indexOf(term)>-1;
        var show = okMode && okLang && okTerm;
        h.classList.toggle('hidden',!show);
        if(show){vis++;}
      });
      sec.classList.toggle('hidden',vis===0);
      // Keep the per-file tally honest while a filter is narrowing the view.
      var n=sec.querySelector('.n');
      n.textContent=vis+' '+n.dataset.noun+(vis===1?'':'s');
      total+=vis;
    });

    // The glossary answers the search box too.
    var gvis=0;
    grows.forEach(function(r){
      var show=(!term || r.dataset.search.indexOf(term)>-1)
        && (lang==='all' || r.dataset.lang===lang);
      r.classList.toggle('hidden',!show);
      if(show){gvis++;}
    });
    if(gsec){gsec.classList.toggle('hidden',gvis===0);}

    out.textContent = total.toLocaleString()+' line'+(total===1?'':'s')+' shown';
    none.classList.toggle('hidden',total>0);
  }

  q.addEventListener('input',apply);
  group('mode').forEach(function(c){
    c.addEventListener('click',function(){
      mode=c.dataset.mode;
      group('mode').forEach(function(o){
        o.setAttribute('aria-pressed',String(o===c));});
      apply();
    });
  });
  group('lang').forEach(function(c){
    c.addEventListener('click',function(){
      lang=c.dataset.lang;
      group('lang').forEach(function(o){
        o.setAttribute('aria-pressed',String(o===c));});
      apply();
    });
  });
  apply();
})();
"""


def esc(s):
    return html.escape(s, quote=False)


def render_parts(parts):
    out = []
    for same, text in parts:
        if not text:
            continue
        out.append(esc(text) if same else '<mark>%s</mark>' % esc(text))
    return ''.join(out) or '<span class="empty">(empty)</span>'


def render_cell(kind, side_label, speaker, parts):
    return (
        '<div class="cell %s"><div class="side">%s %s</div>'
        '<div class="speaker">%s</div><div class="text">%s</div></div>'
        % (kind, side_label, kind, esc(speaker), render_parts(parts))
    )


def render_pair(h, side, label):
    """Old|new columns for one language, or a muted context row if unchanged."""
    cf, tf = side_fields(side)
    o_chr = h.old[cf] if h.old else ''
    n_chr = h.new[cf] if h.new else ''
    o_txt = h.old[tf] if h.old else ''
    n_txt = h.new[tf] if h.new else ''

    if h.old is not None and h.new is not None and o_chr == n_chr and o_txt == n_txt:
        return ('<div class="context"><div class="side">%s unchanged</div>'
                '<div class="speaker">%s</div><div class="text">%s</div></div>'
                % (label, esc(o_chr), esc(o_txt) or '<span class="empty">(empty)</span>'))

    o_parts, n_parts = token_diff(o_txt, n_txt)
    cells = []
    if h.old is not None:
        cells.append(render_cell('old', label, o_chr, o_parts))
    if h.new is not None:
        cells.append(render_cell('new', label, n_chr, n_parts))
    return '<div class="pair">%s</div>' % ''.join(cells)


def hunk_search_blob(h, fields):
    bits = []
    for src in (h.old, h.new):
        if not src:
            continue
        bits.extend(src.get(f, '') for f in fields)
    return ' '.join(b for b in bits if b).lower()


def render_hunk_head(h, extra):
    out = ['<div class="hunk-head">%s' % extra]
    if h.kind != 'changed':
        out.append('<span class="tag %s">%s</span>' % (h.kind, h.kind))
    if h.cls == 'term':
        out.append('<span class="tag term">terminology</span>')
    for side in h.sides:
        out.append('<span class="tag %s">%s</span>' % (side, side.upper()))
    if h.cls == 'term' and h.terms:
        out.append('<span class="termlist">%s</span>'
                   % esc(' · '.join('%s → %s' % (t[1], t[2]) for t in h.terms[:3])))
    out.append('</div>')
    return ''.join(out)


def write_html(path, hunks, stats, old_name, new_name, place, places_by_fname,
               glossary, meta_lines, game_id='101'):
    short_name, full_name = GAME_NAMES.get(game_id, ('Game %s' % game_id, 'Game %s' % game_id))
    truncated = max(0, len(hunks) - MAX_HTML_HUNKS)
    shown = hunks[:MAX_HTML_HUNKS]
    n_rewrite = sum(1 for h in hunks if h.cls == 'rewrite')
    n_term = sum(1 for h in hunks if h.cls == 'term')
    grows = glossary_rows(glossary)

    tiles = [
        ('is-accent', format(stats['changed'], ','), 'lines changed'),
        ('is-accent', format(n_rewrite, ','), 'dialogue rewrites'),
        ('is-term', format(n_term, ','), 'terminology-only'),
        ('is-term', format(len(grows), ','), 'renamed terms'),
        ('', format(stats['en_changed'], ','), 'english moved'),
        ('', format(stats['jp_changed'], ','), 'japanese moved'),
        ('', format(len(stats['files_changed']), ','), 'files touched'),
        ('', format(stats['new_rows'], ','), 'rows in new sql'),
    ]
    if stats['added']:
        tiles.append(('is-new', format(stats['added'], ','), 'lines added'))
    if stats['removed']:
        tiles.append(('is-old', format(stats['removed'], ','), 'lines removed'))

    parts = []
    add = parts.append
    add('<title>%s Script Revision</title>' % esc(short_name))
    add('<link rel="preconnect" href="https://fonts.googleapis.com">')
    add('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    add('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600'
        '&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap">')
    add('<style>%s</style>' % CSS)

    add('<header class="top"><div class="top-inner">')
    add('<div class="eyebrow">%s &middot; game %s</div>' % (esc(full_name), esc(game_id)))
    add('<h1>What the patch rewrote</h1>')
    add('<p class="sub">%s</p>' % ' '.join(meta_lines))
    add('</div></header>')

    add('<div class="wrap">')
    add('<div class="tiles">')
    for cls, n, label in tiles:
        add('<div class="tile %s"><div class="n">%s</div><div class="l">%s</div></div>'
            % (cls, n, label))
    add('</div>')

    add('<p class="note">Changed lines are split in two. A <b>renamed term</b> '
        'is a short substitution that recurs in at least %d different '
        'sentences; a line is <b>terminology-only</b> when every word-level '
        'change in it is one of those terms, and a <b>rewrite</b> otherwise. '
        'The list below opens on rewrites &mdash; switch with the buttons.'
        % MIN_TERM_CONTEXTS)

    extra = []
    if not stats['added'] and not stats['removed']:
        extra.append('No lines were added or removed &mdash; every row lines up.')
    if stats['cosmetic_only']:
        extra.append('%d further row%s differ only in portrait or voice markup.'
                     % (stats['cosmetic_only'],
                        '' if stats['cosmetic_only'] == 1 else 's'))
    if extra:
        add(' ' + ' '.join(extra))
    add('</p>')

    if truncated:
        add('<p class="note"><b>Showing the first %s of %s changed lines.</b> '
            'The remaining %s are in the .txt diff only.</p>'
            % (format(MAX_HTML_HUNKS, ','), format(len(hunks), ','),
               format(truncated, ',')))

    # ---- glossary
    add('<section class="gloss" id="glossary">')
    add('<h2>Terminology</h2>')
    add('<p>Substitutions the patch applied across more than one sentence: '
        'renamed proper nouns, plus spelling and number conventions. '
        'Most-used first. These account for %s of the %s changed lines on '
        'their own.</p>'
        % (format(n_term, ','), format(stats['changed'], ',')))
    add('<div class="tablewrap"><table>')
    add('<thead><tr><th></th><th>Was</th><th></th><th>Now</th>'
        '<th style="text-align:right">Lines</th></tr></thead><tbody>')
    if grows:
        for side, old, new, count in grows:
            blob = html.escape(('%s %s' % (old, new)).lower(), quote=True)
            add('<tr class="grow" data-lang="%s" data-search="%s">'
                '<td class="t-lang"><span class="lang">%s</span></td>'
                '<td class="t-old">%s</td><td class="t-arrow">&rarr;</td>'
                '<td class="t-new">%s</td><td class="t-count">%s</td></tr>'
                % (side, blob, side.upper(),
                   esc(old) or '<span class="empty">(nothing)</span>',
                   esc(new) or '<span class="empty">(nothing)</span>',
                   format(count, ',')))
    else:
        add('<tr class="grow" data-lang="all" data-search="">'
            '<td colspan="5" class="empty">No term recurred on more than one '
            'line.</td></tr>')
    add('</tbody></table></div></section>')

    # ---- controls
    add('<div class="controls">')
    add('<input type="search" id="q" placeholder="Filter by text, speaker, term, '
        'or map name…" aria-label="Filter changes">')
    add('<div class="chips">')
    for mode, label, pressed in (('rewrite', 'Rewrites', True),
                                 ('term', 'Terminology', False),
                                 ('all', 'All', False)):
        add('<button class="chip" data-group="mode" data-mode="%s" '
            'aria-pressed="%s">%s</button>'
            % (mode, 'true' if pressed else 'false', label))
    add('</div><div class="chips">')
    for lang, label, pressed in (('all', 'Both', True), ('en', 'EN', False),
                                 ('jp', 'JP', False)):
        add('<button class="chip" data-group="lang" data-lang="%s" '
            'aria-pressed="%s">%s</button>'
            % (lang, 'true' if pressed else 'false', label))
    add('</div><span class="count" id="shown"></span></div>')

    # ---- hunks
    current = None
    open_section = False
    for h in shown:
        fname = h.field('fname')
        if fname != current:
            if open_section:
                add('</section>')
            current = fname
            place_name = places_by_fname.get(fname, '')
            n_here = sum(1 for x in shown if x.field('fname') == fname)
            add('<section class="filegroup" data-fname="%s">' % esc(fname.lower()))
            add('<h2 class="file">%s%s'
                '<span class="n" data-noun="line">%d line%s</span></h2>'
                % (esc(fname),
                   ('<span class="place">%s</span>' % esc(place_name)) if place_name else '',
                   n_here, '' if n_here == 1 else 's'))
            open_section = True

        blob = hunk_search_blob(h, ('eng_search_text', 'jpn_search_text',
                                    'eng_chr_name', 'jpn_chr_name'))
        add('<article class="hunk" data-en="%d" data-jp="%d" data-kind="%s" '
            'data-cls="%s" data-search="%s">'
            % (1 if 'en' in h.sides else 0, 1 if 'jp' in h.sides else 0,
               h.kind, h.cls, html.escape(blob, quote=True)))
        add(render_hunk_head(h, '<span>scene %s</span><span>row %s</span>'
                             % (esc(h.field('scene')), esc(h.field('row')))))
        add(render_pair(h, 'en', 'EN'))
        add(render_pair(h, 'jp', 'JP'))
        add('</article>')

    if open_section:
        add('</section>')

    # ---- places
    if place is not None:
        phunks = place[0]
        if phunks:
            add('<section class="filegroup" data-fname="place names">')
            add('<h2 class="file">place names<span class="place">file table</span>'
                '<span class="n" data-noun="change">%d change%s</span></h2>'
                % (len(phunks), '' if len(phunks) == 1 else 's'))
            for h in phunks:
                blob = hunk_search_blob(h, ('place_name_eng', 'place_name_jpn'))
                add('<article class="hunk" data-en="%d" data-jp="%d" '
                    'data-kind="%s" data-cls="%s" data-search="%s">'
                    % (1 if 'en' in h.sides else 0, 1 if 'jp' in h.sides else 0,
                       h.kind, h.cls, html.escape(blob, quote=True)))
                add(render_hunk_head(h, '<span>%s</span>' % esc(h.field('fname'))))
                for label, fld in (('EN', 'place_name_eng'),
                                   ('JP', 'place_name_jpn')):
                    ov = h.old[fld] if h.old else ''
                    nv = h.new[fld] if h.new else ''
                    if h.old is not None and h.new is not None and ov == nv:
                        add('<div class="context"><div class="side">%s unchanged</div>'
                            '<div class="text">%s</div></div>' % (label, esc(ov)))
                        continue
                    op, np_ = token_diff(ov, nv)
                    cells = []
                    if h.old is not None:
                        cells.append(render_cell('old', label, '', op))
                    if h.new is not None:
                        cells.append(render_cell('new', label, '', np_))
                    add('<div class="pair">%s</div>' % ''.join(cells))
                add('</article>')
            add('</section>')

    add('<p id="none" class="hidden">Nothing matches that filter.</p>')
    add('<footer>Generated by <code>diff-sky1r.py</code> from '
        '<code>%s</code> &rarr; <code>%s</code>.</footer>'
        % (esc(old_name), esc(new_name)))
    add('</div>')
    add('<script>%s</script>' % JS)

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    return truncated


# ---------------------------------------------------------------- main

def places_for(script_path):
    """`sky1r-ruby.sql` -> `sky1r-places-ruby.sql`, `sky1r.sql` -> `sky1r-places.sql`."""
    stem = script_path[:-4] if script_path.endswith('.sql') else script_path
    if stem == 'sky1r':
        return 'sky1r-places.sql'
    if stem.startswith('sky1r'):
        return stem.replace('sky1r', 'sky1r-places', 1) + '.sql'
    return stem + '-places.sql'


def main():
    args = sys.argv[1:]
    old_path = args[0] if len(args) > 0 else 'sky1r.sql'
    new_path = args[1] if len(args) > 1 else 'sky1r-new.sql'
    out_prefix = args[2] if len(args) > 2 else 'sky1r-script-diff'

    for p in (old_path, new_path):
        if not os.path.exists(p):
            print('missing: %s' % p, file=sys.stderr)
            return 1

    print('reading %s ...' % old_path)
    old_rows = load_sql(old_path, SCRIPT_COLS)
    print('reading %s ...' % new_path)
    new_rows = load_sql(new_path, SCRIPT_COLS)
    print('  %d -> %d rows' % (len(old_rows), len(new_rows)))

    hunks, stats = diff_rows(old_rows, new_rows, SCRIPT_COLS)

    # Derive the matching places pair from the script filenames rather than
    # hardcoding one: comparing an unrelated place pair would quietly seed the
    # glossary with renames that are not in the diff being asked for.
    old_places, new_places = places_for(old_path), places_for(new_path)

    place = None
    places_by_fname = {}
    if os.path.exists(old_places) and os.path.exists(new_places):
        print('places: %s vs %s' % (old_places, new_places))
        po = load_sql(old_places, PLACE_COLS)
        pn = load_sql(new_places, PLACE_COLS)
        place = diff_rows(po, pn, PLACE_COLS)
        for r in pn:
            places_by_fname.setdefault(r['fname'], r['place_name_eng'])

    # Terminology is mined across both tables: a tower renamed in dialogue is
    # the same rename as in the place list.
    glossary = classify(hunks + (place[0] if place else []))
    n_rewrite = sum(1 for h in hunks if h.cls == 'rewrite')
    n_term = sum(1 for h in hunks if h.cls == 'term')
    stats['rewrites'] = n_rewrite
    stats['terminology'] = n_term

    txt_path = out_prefix + '.txt'
    html_path = out_prefix + '.html'

    write_txt(txt_path, hunks, stats, old_path, new_path, place, glossary)

    meta = [
        '%s dialogue lines changed across %d of %d scena files between '
        '<code>%s</code> and <code>%s</code>.'
        % (format(stats['changed'], ','), len(stats['files_changed']),
           stats['files_new'], old_path, new_path),
        '%s are genuine rewrites; the other %s only carry a renamed term.'
        % (format(n_rewrite, ','), format(n_term, ',')),
    ]
    truncated = write_html(html_path, hunks, stats, old_path, new_path, place,
                           places_by_fname, glossary, meta,
                           old_rows[0]['game_id'] if old_rows else '101')

    grows = glossary_rows(glossary)
    print()
    print('script table  rows %d -> %d' % (stats['old_rows'], stats['new_rows']))
    print('  changed %d  =  %d rewrites  +  %d terminology-only'
          % (stats['changed'], n_rewrite, n_term))
    print('  added %d   removed %d   html/icon-only %d'
          % (stats['added'], stats['removed'], stats['cosmetic_only']))
    print('  EN moved %d   JP moved %d' % (stats['en_changed'], stats['jp_changed']))
    print('  files changed %d   added %s   removed %s'
          % (len(stats['files_changed']), stats['files_added'] or '[]',
             stats['files_removed'] or '[]'))
    print('  renamed terms %d (threshold: seen on >= %d lines)'
          % (len(grows), MIN_TERM_CONTEXTS))
    for side, old, new, count in grows[:15]:
        print('     %s  %-28s -> %-28s %4d' % (side.upper(), old, new, count))
    if len(grows) > 15:
        print('     ... %d more, see the report' % (len(grows) - 15))
    if place is not None:
        _, pstats = place
        print('file table    rows %d -> %d   changed %d added %d removed %d'
              % (pstats['old_rows'], pstats['new_rows'], pstats['changed'],
                 pstats['added'], pstats['removed']))
    if truncated:
        print('  NOTE: html capped at %d hunks, %d omitted (full set is in the .txt)'
              % (MAX_HTML_HUNKS, truncated))
    print()
    print('wrote %s  (%.1f KB)' % (txt_path, os.path.getsize(txt_path) / 1024))
    print('wrote %s  (%.1f KB)' % (html_path, os.path.getsize(html_path) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
