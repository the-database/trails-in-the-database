"""Extract Trails to Azure (game 5) place names into azure-places.sql.

Companion to 5-azure-extractscripts-database.py. Same shape as the game-4
places extractor; see 4-zero-extractplaces-database.py for the details.
"""

import ast
import json
import os
import sys

AZURE_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'EDDecompiler', 'data', 'azure')
JP_SCENA_ROOT = os.path.join(AZURE_ROOT, 'jp', 'scena')
JP_TTOWN = os.path.join(AZURE_ROOT, 'jp', 'text', 't_town._dt.json')
EN_TTOWN = os.path.join(AZURE_ROOT, 'en', 'text', 't_town._dt.json')
GAME_ID = 5
OUTPUT = 'azure-places.sql'

# t_town index 0 is a 4-wide-space placeholder; treat as "no place".
PLACEHOLDER_TOWN = '　　　　'


def _const_value(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
            return -node.operand.value
    return None


def load_ttown(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def map_index_for(path):
    """Parse scena .py, return MapIndex (int) from first CreateScenaFile call,
    or None if absent."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        src = f.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f'WARN parse failed for {path}: {e}', file=sys.stderr)
        return None

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != 'main':
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
                continue
            call = stmt.value
            fn = call.func
            fname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
            if fname != 'CreateScenaFile':
                continue
            if len(call.args) < 4:
                return None
            v = _const_value(call.args[3])
            return v if isinstance(v, int) else None
    return None


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def main():
    jp_town = load_ttown(JP_TTOWN)
    en_town = load_ttown(EN_TTOWN)
    print(f't_town  EN={len(en_town)}  JP={len(jp_town)}')

    if not os.path.isdir(JP_SCENA_ROOT):
        print(f'no JP scena dir: {JP_SCENA_ROOT}', file=sys.stderr)
        return

    rows = []
    skipped = 0
    for entry in sorted(os.listdir(JP_SCENA_ROOT)):
        if not entry.endswith('.py'):
            continue
        stem = entry[:-3]
        path = os.path.join(JP_SCENA_ROOT, entry)
        idx = map_index_for(path)
        if idx is None:
            print(f'WARN {stem}: no MapIndex', file=sys.stderr)
            skipped += 1
            continue
        if idx < 0 or idx >= len(jp_town):
            print(f'WARN {stem}: MapIndex {idx} out of range (jp_town size {len(jp_town)})', file=sys.stderr)
            skipped += 1
            continue
        jp_name = (jp_town[idx] or '').strip()
        en_name = (en_town[idx] if 0 <= idx < len(en_town) else '').strip()
        if jp_name in ('', PLACEHOLDER_TOWN):
            skipped += 1
            continue
        rows.append([str(GAME_ID), stem, en_name, jp_name])

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(f'delete from file where game_id = {GAME_ID};\n')
        for row in rows:
            f.write('insert into file (game_id, fname, place_name_eng, place_name_jpn) values\n')
            f.write("('%s');\n" % "','".join(sql_escape(c) for c in row))

    print(f'TOTAL = {len(rows)}  SKIPPED = {skipped}')


if __name__ == '__main__':
    main()
