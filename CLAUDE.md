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
- `6-cs1-extractscripts-database.py` — Trails of Cold Steel
- `7-cs2-extractscripts-database.py` — Trails of Cold Steel II
- `8-cs3-extractscripts-database.py` — Trails of Cold Steel III
- `9-sen4-extractscripts-database.py` — Trails of Cold Steel IV

Each script expects the game's data files at hardcoded paths near the top (e.g. `psp_eng_path`, `vita_jpn_path`) — update these to match your local dump before running. There is no shared library; changes to parsing logic must be ported across scripts as needed.

## Running

```bash
cd extract
python 3-sky3rd-extractscripts-database.py   # pick the script for the game you're extracting
```

No requirements file, no tests, no build. Stdlib only (`re`, `struct`, `csv`, `json`, `html`, etc.).
