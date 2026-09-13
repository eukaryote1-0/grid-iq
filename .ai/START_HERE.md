# Start here

GridIQ Botswana v1.4 is an evidence-driven national energy-planning prototype that keeps **generation + storage + grid + demand** in one decision workflow.

Read first:
1. `.ai/CURRENT_STATE.md`
2. `.ai/ARCHITECTURE.md`
3. `docs/DATA_PROVENANCE.md`
4. `.ai/DECISIONS.md` before architectural/model changes
5. `.ai/ISSUES.md` before debugging

Current focus: public Botswana evidence + deterministic data fusion + explicitly-labelled engineering benchmarks. v1.4 adds WorldPop spatial population querying, Census×NEUS derived access context, OSM→benchmark electrical enrichment, and a single-voltage DC transfer sensitivity.

Non-negotiable boundary: benchmark electrical results are **planning sensitivities**, not measured BPC operating state. Do not reintroduce synthetic hourly demand/solar series or describe OSM geometry as a validated BPC bus/branch model.
