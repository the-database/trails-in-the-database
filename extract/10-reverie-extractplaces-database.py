"""Extract Trails into Reverie (game 10) place names into reverie-places.sql.

Companion to 10-reverie-extractscripts-database.py. Unlike the prior haji
extraction which was JP-only, this pulls both EN and JP names by matching
t_place.py entries across the two decompiles on their stable `id` field.

Output schema matches the `file` table:
  delete from file where game_id = 10;
  insert into file (game_id, fname, place_name_eng, place_name_jpn) values
    ('10', '<map>', '<en name>', '<jp name>');

Row order follows the JP file to preserve chapter-list ordering used
by the UI (the first ~131 rows have fname='null' and are chapter titles,
the rest are real map -> place name mappings).
"""

import ast
import os
import sys

FALCOM_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'Falcom')
EN_TPLACE = os.path.join(FALCOM_ROOT, 'reverie_decompiled', 'data', 'text', 'dat_en', 't_place.py')
JP_TPLACE = os.path.join(FALCOM_ROOT, 'reverie_jp_decompiled', 'data', 'text', 'dat', 't_place.py')
GAME_ID = 10
OUTPUT = 'reverie-places.sql'


def load_tplace(path):
    """Parse t_place.py. Returns list of {'id', 'map', 'name'} in source
    order. A given id can appear more than once (~1 duplicate observed
    in JP), so the result is a list, not a dict keyed by id."""
    with open(path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    entries = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'PlaceTableData'):
            continue
        fields = {}
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant):
                fields[kw.arg] = kw.value.value
        pid = fields.get('id')
        if pid is None:
            continue
        entries.append({
            'id': pid,
            'map': fields.get('map') or '',
            'name': fields.get('name') or '',
        })
    return entries


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def main():
    jp_entries = load_tplace(JP_TPLACE)
    en_entries = load_tplace(EN_TPLACE)
    print(f't_place entries  EN={len(en_entries)}  JP={len(jp_entries)}')

    # Index EN by id. For the ~1 duplicate id, first occurrence wins.
    en_by_id = {}
    for e in en_entries:
        en_by_id.setdefault(e['id'], e)

    missing = 0
    rows = []
    for jp in jp_entries:
        en = en_by_id.get(jp['id'])
        en_name = en['name'] if en else ''
        if en is None:
            missing += 1
            print(f'WARN: no EN entry for id=0x{jp["id"]:08X} map={jp["map"]!r} '
                  f'jp_name={jp["name"]!r}', file=sys.stderr)
        rows.append([str(GAME_ID), jp['map'], en_name, jp['name']])
    if missing:
        print(f'missing EN entries: {missing}', file=sys.stderr)

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(f'delete from file where game_id = {GAME_ID};\n')
        for row in rows:
            f.write('insert into file (game_id, fname, place_name_eng, place_name_jpn) values\n')
            f.write("('%s');\n" % "','".join(sql_escape(c) for c in row))

    print(f'TOTAL = {len(rows)}')


if __name__ == '__main__':
    main()
