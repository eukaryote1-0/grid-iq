# Data reconciliation register

Conflicts found while merging the OIC2 dataset pull with the existing GridIQ
baseline. **Rule: prefer the ingested dataset where one exists; otherwise prefer
the official primary source and label its vintage.** Each row is open for team
decision; nothing here is silently overwritten.

| # | Quantity | Baseline (`botswana_energy_baseline.json`) | Ingested dataset / other source | Proposed resolution | Status |
|---|---|---|---|---|---|
| R1 | System losses | 14.35% of dispatched (Compact) | BPC Integrated Report 2023: **642 GWh, 14.51%**; AFREC 2025: **~630 GWh, 13.8%** (54.20 ktoe) | Keep **BPC 642 GWh / 14.51%** as the reconciliation anchor (utility's own dataset), AFREC as the independent cross-check. Strict dataset-first would make AFREC primary. **Team to decide.** | Open |
| R2 | Transmission km by voltage | 1,027 / 1,784.5 / 1,833.1 (Compact, Mar 2025) | BPC site: 1,246 / 2,200 / 2,162; AICD/BPA 2006 layer: 198.6 / 836.8 / 1,209.3 (existing) | No dataset is current. Keep Compact and BPC figures side by side, labelled by source/date; use the 2006 layer only as a geometry cross-check. | Open |
| R3 | Installed capacity | 927 MW (SAPP) | Compact July 2025: **913 MW**; earlier draft: 892 MW | Store all three with source + date; show SAPP as current operating snapshot, Compact as sector baseline. | Open |
| R4 | National access | 76.6% (Compact, Mar 2025) | NEUS 2022/23: **73.9%** (468,344 / 634,076 households) | Dataset-first: NEUS primary, Compact shown with vintage. Both to be displayed. | Open |
| R5 | Renewable target | 50% by 2030 (Compact domestic case, 475 MW) | Africa Energy Portal: 15% / 36% / 50% by 2030 / 2036 / 2040 | National plan (Compact) takes precedence for the pitch; note the AEP trajectory when citing 2040. | Open |
| R6 | Operational interconnectors | 4 named (Francistown–Marvel 220 kV; Segoditshane–Spitskop 3×132 kV; Phokoje–Insukamini 400 kV; Phokoje–Matimba 400 kV) | Earlier draft had none | Adopt the baseline list. **Resolves a former open gap.** | Adopted |
| R7 | Losses scope | Compact/BPC figures are T&D | The DC model is transmission-level | Report the model's transmission bracket against BPC's T&D total and explain the scope. | Adopted |

Sources for the ingested side: `docs/PROVENANCE_EXTERNAL_DATASETS.md`,
`data/manifests/external_datasets.json`.
