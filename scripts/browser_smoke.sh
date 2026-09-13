#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
CHROME="${CHROME:-$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)}"
if [[ -z "$CHROME" ]]; then
  echo "SKIP: Chromium/Chrome not installed"
  exit 2
fi
OUT="${1:-reports/browser_fixture_dom.html}"
ERR="${OUT%.html}.err"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
set +e
timeout 20s "$CHROME" --headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --disable-background-networking --disable-component-update --disable-sync --metrics-recording-only \
  --user-data-dir="$TMP" --virtual-time-budget=3000 --dump-dom \
  "$BASE_URL/?fixture=1#audit" >"$OUT" 2>"$ERR"
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  echo "Browser smoke failed (rc=$rc). See $ERR"
  exit $rc
fi
grep -q "Public-data planning product" "$OUT"
grep -q "BPC operational validation" "$OUT"
grep -q "AUDIT GATES — BENCHMARK ENGINEERING" "$OUT"
! grep -q "FRONTEND BOOT FAILED" "$OUT"
echo "BROWSER_SMOKE_PASS"
