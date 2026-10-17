# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope

**Only `extract/` is maintained in this repo.** The `api/` (Spring Boot backend) and `frontend/` (Create React App) directories are outdated and will not be updated here — their modern versions live in a different repository. Do not edit, refactor, or add features to `api/` or `frontend/`; if a task implies changes there, stop and ask the user for the current repo.

## Project

Python 3 extract scripts that parse data files from the Trails (Kiseki) game series and emit SQL/CSV output for loading into a Postgres database downstream.

## Layout

`extract/` contains nine standalone scripts, one per game, run independently:

- `1-skyfc-extractscripts-database.py` — Trails in the Sky FC
- `2-skysc-extractscripts-database.py` — Trails in the Sky SC
- `3-sky3rd-extractscripts-database.py` — Trails in the Sky the 3rd
- `4-zero-extractscripts-database.py` — Trails from Zero
- `5-azure-extractscripts-database.py` — Trails to Azure
- `6D-cs1-extractscripts-database.py` — Trails of Cold Steel
- `7D-cs2-extractscripts-database.py` — Trails of Cold Steel II
- `8D-cs3-extractscripts-database.py` — Trails of Cold Steel III
- `9D-sen4-extractscripts-database.py` — Trails of Cold Steel IV

For cs1–cs4, only the `D`-suffix scripts are canonical — they parse Decompiler2 output (XLSX bytecode for cs1/cs2, Python AST for cs3/cs4). The unsuffixed `6/7/8/9` byte-level extractors that previously existed have been deleted; do not recreate them.

Each script expects the game's data files at hardcoded paths near the top (e.g. `psp_eng_path`, `vita_jpn_path`, `~/Documents/programming/Falcom/data/cs[1-4]/`) — update these to match your local dump before running. There is no shared library; changes to parsing logic must be ported across scripts as needed.

## Running

```bash
cd extract
python 3-sky3rd-extractscripts-database.py   # pick the script for the game you're extracting
```

No requirements file, no tests, no build. Stdlib only (`re`, `struct`, `csv`, `json`, `html`, etc.).

## Maintenance workflow

When fixing an extraction bug (junk control codes, leaked tokens, mis-parsed text), follow this loop:

1. **Survey the live db.** SSH in (`ssh hetzner`, then `sudo -u postgres psql -d trails` — peer auth, so `-U postgres` as your own user fails) and search the `script` table for the offending pattern across `jpn_search_text` / `eng_search_text`. Group by `game_id` to scope which extractors are affected, and by `regexp_matches(...)` to enumerate variant forms — patterns rarely come in just one shape.
2. **Find the root cause in raw data, not just symptoms in db.** Open the raw game data (e.g. `~/Documents/programming/Falcom/data/cs<n>/scripts/scena/dat/<file>.xlsx` for cs1/cs2, `.py` for cs3/cs4) and grep the offending pattern. Confirm whether it's an extractor bug (regex misses a control code) or content the extractor is correctly emitting from a dev/test scene.
3. **Fix the extractor.** Edit the relevant D-suffix script(s). Most text cleanup lives in `CONTROL_CODE_RE`, `LEFTOVER_CODE_RE`, `JUNK_BRACKET_SUBS`, and `clean_text()`. Port the change to all affected scripts — there is no shared library.
4. **Check for regressions before deploy.** Two questions: (a) does the new regex over-eat real content? Inspect the raw-data context around the matched pattern to confirm it's always followed by control characters or other markers, never user-visible text. (b) does the row count or average char-length shift unexpectedly? A safe fix removes a few chars per affected row, not entire rows.
5. **Re-extract** by running `python <N>D-...py` from `extract/`. Output is `sen2.sql` / `sen3.sql` / `sen4.sql` / etc. — diff against the old SQL or grep the new file to confirm the leak is gone before shipping.
6. **Deploy.** `scp` the SQL to `hetzner:/tmp/`, then on the box run `sudo -u postgres psql -d trails -1 -v ON_ERROR_STOP=1 -f /tmp/<file>.sql` per game (the dumps are a bare delete + inserts with no transaction, so `-1` keeps a failure from leaving the game half-deleted), `REFRESH MATERIALIZED VIEW <mv>;` (plain, not concurrent) on each of the four MVs (`\dm` confirms the live list — don't trust migrations), then `rm` the `/tmp/` files.
7. **Verify in db.** Re-run the original survey query — expect 0 rows for the offending pattern. Spot-check a row that was previously broken to confirm it now reads cleanly without losing real text.
