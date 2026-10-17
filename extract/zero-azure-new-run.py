"""Re-run the Zero (game 4) / Azure (game 5) extractors against patched game data.

The 2026-09-10 PC patch (Zero 1.5.5, Azure 1.2.5: "Fix various text and
localization issues") rewrote about half of the English scena files in both
games. This wrapper points the existing extractors at a freshly copied +
decompiled snapshot and writes to `<game>-new.sql` / `<game>-new-places.sql`,
so the deployed outputs (`zero.sql`, `azure.sql`, ...) survive as a diff
baseline for `diff-sky1r.py`.

Same mechanism as `sky1r-new-run.py`: nothing in the extractors is edited.
Each keeps its input paths and `OUTPUT` as module-level constants that are only
read inside `main()`, so rebinding them after import is enough.

Staging (EDDecompiler/data/<snapshot>/{en,jp}/{scena,text}):
  scena/*.py   ZeroKaiScenarioScript.py / AzureKaiScenarioScript.py, run as
               `py -3.13 <script> --cp=cp932 <dir>` with PyLibs on PYTHONPATH
               (this reproduces the April .py files byte for byte)
  text/t_name._dt.json, t_town._dt.json

Run from anywhere (outputs land in `extract/`):
    python zero-azure-new-run.py zero                     # zero20261017 -> zero-new.sql
    python zero-azure-new-run.py azure                    # azure20261017 -> azure-new.sql
    python zero-azure-new-run.py zero zero_batch zero-base  # re-extract a snapshot under any name
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.expanduser('~'), 'Documents', 'programming', 'EDDecompiler', 'data')

GAMES = {
    'zero': ('4-zero-extractscripts-database.py', '4-zero-extractplaces-database.py', 'zero20261017'),
    'azure': ('5-azure-extractscripts-database.py', '5-azure-extractplaces-database.py', 'azure20261017'),
}


def load(filename):
    """Import an extractor by path without triggering its __main__ block."""
    path = os.path.join(HERE, filename)
    name = 'za_' + filename.replace('-', '_').replace('.py', '')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(*paths):
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        for p in missing:
            print(f'MISSING INPUT: {p}', file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in GAMES:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    game = sys.argv[1]
    scripts_module, places_module, default_snapshot = GAMES[game]
    snapshot = sys.argv[2] if len(sys.argv) > 2 else default_snapshot
    base = sys.argv[3] if len(sys.argv) > 3 else game + '-new'
    if base.endswith('.sql'):
        base = base[:-4]
    # diff-sky1r.py's places_for() pairs `X.sql` with `X-places.sql`.
    script_out = base + '.sql'
    places_out = base + '-places.sql'

    os.chdir(HERE)
    root = os.path.join(DATA, snapshot)
    jp_scena = os.path.join(root, 'jp', 'scena')
    en_scena = os.path.join(root, 'en', 'scena')
    jp_tname = os.path.join(root, 'jp', 'text', 't_name._dt.json')
    en_tname = os.path.join(root, 'en', 'text', 't_name._dt.json')
    jp_ttown = os.path.join(root, 'jp', 'text', 't_town._dt.json')
    en_ttown = os.path.join(root, 'en', 'text', 't_town._dt.json')

    require(jp_scena, en_scena, jp_tname, en_tname, jp_ttown, en_ttown)

    print('=== script table (%s) -> %s ===' % (snapshot, script_out))
    scripts = load(scripts_module)
    scripts.JP_SCENA_ROOT = jp_scena
    scripts.EN_SCENA_ROOT = en_scena
    scripts.JP_TNAME = jp_tname
    scripts.EN_TNAME = en_tname
    scripts.OUTPUT = script_out
    scripts.main()

    print()
    print('=== file table (%s) -> %s ===' % (snapshot, places_out))
    places = load(places_module)
    places.JP_SCENA_ROOT = jp_scena
    places.JP_TTOWN = jp_ttown
    places.EN_TTOWN = en_ttown
    places.OUTPUT = places_out
    places.main()


if __name__ == '__main__':
    main()
