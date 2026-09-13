# AGENTS.md — working rules for coding agents

This repository is built by humans **and** coding agents in short, incremental
steps. Every change must leave the system working.

## Before you start

1. Read `.ai/START_HERE.md`, `.ai/CONVENTIONS.md`, `.ai/DECISIONS.md` and the
   relevant section of `.ai/CURRENT_STATE.md`.
2. Read `CONTRIBUTING.md` — the evidence rules are absolute.

## Definition of done (every task)

- `make test` passes (pytest + `py_compile` + `node --check`).
- `./run.sh` still starts and `/api/health` responds.
- New behaviour has a test. New outputs carry evidence labels and a `not` field.
- No existing endpoint is broken or renamed.
- `.ai/CHANGELOG.md` and (if behaviour changed) `.ai/CURRENT_STATE.md` updated.

## Scoped tasks

- Work only on the files listed in your task. Do **not** edit `app/main.py`,
  `app/logic.py`, `app/compat_server.py`, `web/index.html` or
  `web/js/app.bundle.js` unless your task explicitly names them.
- New engines go in their own package under `engines/<name>/` and expose pure
  functions that take plain dicts/lists and return plain dicts. Keep them
  importable without the web server.
- New HTTP routes go in `app/engines_router.py` (or a new `app/routers/*.py`);
  only the integration owner wires them into `main.py`.
- Never edit `data/official/*` snapshots. Add new evidence as new files plus a
  manifest entry.

## Evidence boundary (do not cross)

- Do not create synthetic operational demand, solar, dispatch or congestion data.
- Do not present benchmark or model outputs as measured BPC values.
- Keep the BPC operational-validation audit gate `false` until real utility data
  arrives.

## Reporting back

Finish with: what changed, the exact verification commands you ran, and any
assumption you introduced (with the file and line where it is labelled).
