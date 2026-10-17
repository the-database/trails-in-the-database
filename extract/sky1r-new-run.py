"""Re-run the Sky 1st Chapter (game 101) extractors against patched game data.

The 2026-08-18 Steam patch (buildid 24691507) rewrote script.pac / script_en.pac
and table.pac / table_en.pac. This wrapper points the existing extractors at a
freshly unpacked + decompiled copy of that data and writes to `*-new.sql`, so
the April outputs (`sky1r.sql`, `sky1r-places.sql`) survive for comparison.

Nothing in `1R-sky1r-extractscripts-database.py` or
`1R-sky1r-extractplaces-database.py` is edited. Both keep every input path and
`OUTPUT` as a module-level constant that is only read inside `main()`, so
loading the module and rebinding those attributes before calling `main()` is
enough — and `main()` does not self-fire, because importlib gives the module a
`__name__` other than `__main__`.

Staging (produced by the steps in the plan, all new directories):
  Ingert/data/sky1st-b24691507/      raw .dat, unpacked from the patched pacs
  Ingert/data/sky1st-b24691507.ing/  ingert.exe decompile output
  KuroTools/sky1_new/                patched .tbl plus en_json/ jp_json/

Run from `extract/` (the extractors write OUTPUT relative to the cwd):
    python sky1r-new-run.py                 # -> sky1r-new.sql
    python sky1r-new-run.py sky1r-ruby      # -> sky1r-ruby.sql

Pass a basename to park a run beside the previous one instead of over it, so
the already-deployed .sql stays available as a diff baseline.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.join(os.path.expanduser('~'), 'Documents', 'programming')

ING_ROOT = os.path.join(PROG, 'Ingert', 'data', 'sky1st-b24691507.ing')
TBL_ROOT = os.path.join(PROG, 'KuroTools', 'sky1_new')

SCRIPTS_MODULE = '1R-sky1r-extractscripts-database.py'
PLACES_MODULE = '1R-sky1r-extractplaces-database.py'


def load(filename):
    """Import an extractor by path without triggering its __main__ block."""
    path = os.path.join(HERE, filename)
    # The stem has a leading digit and hyphens, so it is not a legal module
    # name; importlib does not care, but keep it distinct for sys.modules.
    name = 'sky1r_' + filename.replace('-', '_').replace('.py', '')
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
    os.chdir(HERE)
    base = sys.argv[1] if len(sys.argv) > 1 else 'sky1r-new'
    if base.endswith('.sql'):
        base = base[:-4]
    script_out = base + '.sql'
    places_out = base.replace('sky1r', 'sky1r-places', 1) + '.sql' \
        if base.startswith('sky1r') else base + '-places.sql'

    en_root = os.path.join(ING_ROOT, 'script_en')
    jp_root = os.path.join(ING_ROOT, 'script')
    en_tname = os.path.join(TBL_ROOT, 'en_json', 't_name.json')
    jp_tname = os.path.join(TBL_ROOT, 'jp_json', 't_name.json')
    jp_tvoice = os.path.join(TBL_ROOT, 'jp_json', 't_voice.json')
    en_tplace = os.path.join(TBL_ROOT, 'en_json', 't_place.json')
    jp_tplace = os.path.join(TBL_ROOT, 'jp_json', 't_place.json')

    require(en_root, jp_root, en_tname, jp_tname, jp_tvoice, en_tplace, jp_tplace)

    print('=== script table -> %s ===' % script_out)
    scripts = load(SCRIPTS_MODULE)
    scripts.EN_ROOT = en_root
    scripts.JP_ROOT = jp_root
    scripts.EN_TNAME = en_tname
    scripts.JP_TNAME = jp_tname
    scripts.JP_TVOICE = jp_tvoice
    scripts.OUTPUT = script_out
    scripts.main()

    print()
    print('=== file table -> %s ===' % places_out)
    places = load(PLACES_MODULE)
    places.EN_TPLACE = en_tplace
    places.JP_TPLACE = jp_tplace
    places.OUTPUT = places_out
    places.main()


if __name__ == '__main__':
    main()
