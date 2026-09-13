#!/usr/bin/env bash
# Fetch large GridIQ datasets that are intentionally not committed.
# Committed small evidence lives in data/ and is verified by verify_manifests.py.
set -euo pipefail
cd "$(dirname "$0")/.."

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
mkdir -p data/grid

fetch() {
  local name="$1" url="$2" out="data/grid/$1"
  if [[ -f "$out" ]]; then
    echo "· already present: $name"
  else
    echo "· fetching $name"
    curl -sL --max-time 180 -A "$UA" -o "$out" "$url"
    # Strip the World Bank trailing artefact if present.
    python - "$out" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8", errors="ignore").read()
i = s.rfind("}")
if i != -1 and s[i+1:].strip():
    open(p, "w", encoding="utf-8").write(s[:i+1])
PY
  fi
  sha256sum "$out" | awk '{print "  "$1"  "$2}'
}

fetch africa_grid_existing.geojson "https://datacatalogfiles.worldbank.org/ddh-published/0040465/DR0050468/africagrid20170906existing.geojson"
fetch africa_grid_planned.geojson  "https://datacatalogfiles.worldbank.org/ddh-published/0040465/DR0050469/africagrid20170906planned.geojson"

echo
echo "Cross-check the printed checksums against data/manifests/external_datasets.json."
