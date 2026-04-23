"""Extract Trails through Daybreak 2 (game 12) place names into db2-places.sql.

Companion to 12-db2-extractscripts-database.py. Pulls EN+JP names by matching
t_place.json entries across the two decompiles on their stable `id` field.

Output schema matches the `file` table:
  delete from file where game_id = 12;
  insert into file (game_id, fname, place_name_eng, place_name_jpn) values
    ('12', '<map>', '<en name>', '<jp name>');

Row order follows the JP file. Duplicate ids: first occurrence wins.
"""

import json
import os
import sys

DB2_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'KuroTools', 'daybreak2_extract')
EN_TPLACE = os.path.join(DB2_ROOT, 'en_json', 't_place.json')
JP_TPLACE = os.path.join(DB2_ROOT, 'jp_json', 't_place.json')
GAME_ID = 12
OUTPUT = 'db2-places.sql'


def load_tplace(path):
    """Parse t_place.json. Returns list of {'id', 'map', 'name'} in source
    order. Duplicate ids are kept in the list (first-occurrence filtering
    is done at match time, not at load time)."""
    with open(path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    out = []
    for block in doc.get('data', []):
        for entry in block.get('data', []):
            pid = entry.get('id')
            if pid is None:
                continue
            out.append({
                'id': pid,
                'map': entry.get('text') or '',
                'name': entry.get('utf8text') or '',
            })
    return out


def sql_escape(s):
    return s.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z')


def main():
    jp_entries = load_tplace(JP_TPLACE)
    en_entries = load_tplace(EN_TPLACE)
    print(f't_place entries  EN={len(en_entries)}  JP={len(jp_entries)}')

    en_by_id = {}
    for e in en_entries:
        en_by_id.setdefault(e['id'], e)

    seen_ids = set()
    missing = 0
    rows = []
    for jp in jp_entries:
        if jp['id'] in seen_ids:
            continue
        seen_ids.add(jp['id'])
        en = en_by_id.get(jp['id'])
        en_name = en['name'] if en else ''
        if en is None:
            missing += 1
            print(f'WARN: no EN entry for id={jp["id"]} map={jp["map"]!r} '
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
