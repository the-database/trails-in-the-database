# Extract scripts

One standalone Python 3 script per game (stdlib only) that turns decompiled
game data into SQL for the site's Postgres database. Each script reads its
inputs from hardcoded paths near the top of the file (built from
`~/Documents/programming/...`) and writes its `.sql` output into the current
directory, so run them from `extract/`. Edit the path constants if your tools
live somewhere else.

Generated `.sql` output is not tracked in git.

## Trails in the Sky 1st Chapter / 2nd Chapter (games 101 / 102)

`1R-sky1r-*` and `2R-sky2r-*` read two kinds of input:

| Input | Made with | Used for |
|---|---|---|
| Decompiled scripts (`.ing`) | [Ingert](https://github.com/Aureole-Suite/Ingert) | dialogue |
| Tables as JSON (`t_name`, `t_voice`, `t_place`) | [KuroTools](https://github.com/nnguyen259/KuroTools) `tbl2json.py` | speaker names, voice ids, place names |

Both come out of the game's `.pac` archives, in the Steam install under
`pac/steam/`:

- `script.pac` / `script_en.pac` contain the scripts (Japanese / English).
- `table.pac` / `table_en.pac` contain the tables.

The archives are unpacked with `sky_extract_pac.py` from
[eArmada8/kuro_mdl_tool](https://github.com/eArmada8/kuro_mdl_tool). It
extracts every `*.pac` sitting next to it, into its own folder, keeping the
paths stored in the archive (`script/...`, `script_en/...`, `table/...`,
`table_en/...`), so copy it and the archives into a fresh folder and run it
there.

### 1. Scripts

1. Copy `sky_extract_pac.py`, `script.pac` and `script_en.pac` into a new folder,
   e.g. `Ingert/data/sky2nd-b25340742/`, and run `python sky_extract_pac.py`
   there. You get `script/` and `script_en/` full of `.dat` files.
2. Build Ingert (`cargo build --release`) and decompile the folder:

   ```
   ingert Ingert/data/sky2nd-b25340742
   ```

   Ingert mirrors a folder of `.dat` files into a sibling folder with `.ing`
   appended, here `Ingert/data/sky2nd-b25340742.ing/script/...` and
   `.../script_en/...`. (Dragging the folder onto `ingert.exe` does the same.)

### 2. Tables

1. Unpack `table.pac` and `table_en.pac` the same way, into e.g.
   `KuroTools/sky2_full/`, giving `table/*.tbl` and `table_en/*.tbl`.
2. From the KuroTools root (it loads `schemas/` relative to the working
   directory, and writes `<name>.json` there), convert each table the scripts
   need with the Sky schema:

   ```
   python tbl2json.py -g Sora1 sky2_full/table/t_name.tbl
   ```

3. Move the JSON into `en_json/` (from `table_en/`) and `jp_json/` (from `table/`):

   ```
   KuroTools/sky2_full/en_json/t_name.json, t_place.json
   KuroTools/sky2_full/jp_json/t_name.json, t_place.json, t_voice.json
   ```

### 3. Run

```
cd extract
python 2R-sky2r-extractscripts-database.py   # -> sky2r.sql
python 2R-sky2r-extractplaces-database.py    # -> sky2r-places.sql
```

### Where each script expects its input

| Script | Scripts root (`.ing`) | Tables root (`en_json/`, `jp_json/`) |
|---|---|---|
| `1R-sky1r-extractscripts-database.py` | `Ingert/data/sky1st` | `KuroTools/sky1_extract` |
| `1R-sky1r-extractplaces-database.py` | - | `KuroTools/sky1_extract` |
| `sky1r-new-run.py` (Sky 1st, 2026-08-18 patch) | `Ingert/data/sky1st-b24691507.ing` | `KuroTools/sky1_new` |
| `2R-sky2r-extractscripts-database.py` | `Ingert/data/sky2nd-b25340742.ing` | `KuroTools/sky2_full` |
| `2R-sky2r-extractplaces-database.py` | - | `KuroTools/sky2_demo` |

All paths are under `~/Documents/programming/`. For Sky 1st, the patched data
goes through `sky1r-new-run.py`, which points the `1R-sky1r-*` scripts at the
patched folders without editing them (see its docstring); run it as
`python sky1r-new-run.py` from `extract/`.

Furigana in the game text (`<R>base</Rreading>`) comes out as
`<ruby>base<rt>reading</rt></ruby>` in the HTML columns and as the base text
alone in the search columns.

## In-game books

`kuro-extractbooks-database.py` (Daybreak I/II, Horizon, Sky 1st/2nd) and
`ed7-extractbooks-database.py` (Zero, Azure) describe their own inputs and
staging steps in their docstrings.
