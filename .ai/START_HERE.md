# Start here

GridIQ Botswana v1.7 is an evidence-driven energy-planning prototype. Its central rule is **generation + storage + grid + demand share one substrate and one provenance model**.

Read first:
1. `.ai/CURRENT_STATE.md`
2. `.ai/ARCHITECTURE.md`
3. `docs/DATA_PROVENANCE.md`
4. `data/benchmarks/gap_resolution.json`
5. `.ai/DECISIONS.md` before changing model boundaries
6. `.ai/ISSUES.md` before debugging

Current focus: close unavailable public-data fields with named benchmark datasets/proxies where defensible, while keeping BPC operational validation separate. v1.7 adds multi-injection benchmark DC PF, benchmark chronological E1, a DRE candidate register, and benchmark boundary geometry.

Non-negotiable boundary: a benchmark closes a **planning capability**, not BPC operational truth. Never describe benchmark line utilisation, inferred transformer parameters, regional load shapes or DRE candidate status as measured BPC state.
