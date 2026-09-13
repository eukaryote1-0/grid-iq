#!/usr/bin/env python3
"""Verify committed datasets against their SHA-256 manifests.

Checks:
  - data/manifests/external_datasets.json  (committed files + fetched-file expectations)
  - data/evidence_manifest.json            (the app's bundled evidence)

Exit code 0 if every *existing* committed file matches; non-zero on mismatch.
Fetched-not-committed files are reported but do not fail the check when absent.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(manifest_path: Path, *, required: bool) -> list[str]:
    problems: list[str] = []
    if not manifest_path.exists():
        return [f"missing manifest: {manifest_path.relative_to(ROOT)}"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("status") != "generated":
        problems.append(f"{manifest_path.name}: status is not 'generated'")
    for entry in data.get("files", []):
        path = ROOT / entry["path"]
        if not path.exists():
            problems.append(f"missing file: {entry['path']}")
            continue
        actual = sha256(path)
        if actual != entry["sha256"]:
            problems.append(f"checksum mismatch: {entry['path']}\n  expected {entry['sha256']}\n  actual   {actual}")
        if entry.get("bytes") and path.stat().st_size != entry["bytes"]:
            problems.append(f"size mismatch: {entry['path']}")
    return problems


def report_fetched(manifest_path: Path) -> None:
    if not manifest_path.exists():
        return
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in data.get("fetched_not_committed", []):
        path = ROOT / entry["path"]
        status = "present" if path.exists() else "not fetched"
        print(f"  fetched dataset: {entry['path']} — {status}")


def main() -> int:
    problems = check(ROOT / "data" / "manifests" / "external_datasets.json", required=True)
    problems += check(ROOT / "data" / "evidence_manifest.json", required=True)
    report_fetched(ROOT / "data" / "manifests" / "external_datasets.json")
    if problems:
        print("Manifest verification FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Manifest verification OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
