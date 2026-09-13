# Contributing to grid-iq

GridIQ is an evidence-driven national energy-planning prototype. Contributions
are welcome — but they must not weaken the evidence model.

## Non-negotiable evidence rules

1. **Unknowns stay unknown.** Never fabricate operational grid values (loading,
   congestion, condition, hourly demand, dispatch) to make a screen look complete.
2. **Label every number** with its evidence class: `observed`, `derived`,
   `benchmark`, `unknown`, or `model_output`.
3. **No synthetic hourly demand/solar series.** If a time series has no defensible
   source, it does not exist in the product.
4. **No claim without data.** Do not call benchmark results BPC measurements, and
   do not claim OPF/predictive maintenance without the required inputs.
5. **Degraded, not invented.** If an external API fails, show a degraded state or
   a labelled stale cache — never a substitute value.

See `.ai/CONVENTIONS.md` and `.ai/DECISIONS.md` for the full record.

## Workflow

- `main` is the shared branch: **all changes land through a pull request with a
  green CI run**. (GitHub branch protection is unavailable for private repos on
  the org's free plan, so this is enforced by team process and review until the
  repo is upgraded or made public.)
- Keep branches short-lived and scoped to one concern.
- After every change the repository must stay green:

  ```bash
  make test          # pytest + py_compile + node --check
  make run           # app still starts
  ```

- Update `.ai/CURRENT_STATE.md`, `.ai/DECISIONS.md` (for architectural decisions)
  and `.ai/CHANGELOG.md` in the same PR.
- Prefer **additive** API changes. Do not break existing endpoints.

## Repository layout

```
app/        FastAPI app (+ stdlib compatibility runtime)
engines/    E1 optimisation, E2 flow/losses, E3 criticality, E4 siting
data/       evidence substrate: official/ derived/ benchmarks/ reference/ grid/
docs/       problem statement, solutions report, provenance, reconciliation
scripts/    fetch/verify utilities
tests/      pytest suite
web/        browser UI (vanilla JS)
.ai/        agent/human working memory (state, decisions, issues, sessions)
```

## Data policy

- Small evidence snapshots (JSON, the Botswana grid GeoJSON, the techno-economic
  workbook) are committed.
- Large layers (Africa grid, rasters) are fetched via `scripts/fetch_data.sh` and
  never committed. Run `make verify` to check committed checksums.
- Every committed data file has a SHA-256 entry in a manifest under `data/`.

## Commit style

Short imperative subjects, e.g. `engines: add E2 loss reconciliation endpoint`.
Reference the issue where one exists.

## Licensing

Code is Apache-2.0. Data is CC-BY-4.0 unless a dataset states otherwise; keep
attribution and source URLs with every dataset you add.
