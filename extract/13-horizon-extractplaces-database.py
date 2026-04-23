"""Extract Trails beyond the Horizon (game 13) place names into horizon-places.sql.

Companion to 13-horizon-extractscripts-database.py. Same structure as db2's
places extractor — only difference is the display-name field in t_place.json
moved from `utf8text` (db2) to `text4` (horizon).

Output schema matches the `file` table:
  delete from file where game_id = 13;
  insert into file (game_id, fname, place_name_eng, place_name_jpn) values
    ('13', '<map>', '<en name>', '<jp name>');

Row order follows the JP file. Duplicate ids: first occurrence wins.
"""

import json
import os
import sys

HORIZON_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'KuroTools', 'horizon_extract')
EN_TPLACE = os.path.join(HORIZON_ROOT, 'en_json', 't_place.json')
JP_TPLACE = os.path.join(HORIZON_ROOT, 'jp_json', 't_place.json')
GAME_ID = 13
OUTPUT = 'horizon-places.sql'


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
                'name': entry.get('text4') or '',
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
