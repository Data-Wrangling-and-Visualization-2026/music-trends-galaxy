#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post-process cluster description JSON: ensure each cluster ``name`` is unique
within the file by appending `` 1``, `` 2``, … when a name repeats.

Reads/writes ``cluster_descriptions.json`` under STORAGE_DIR (default: repo storage/).

  python dedupe_cluster_names.py
  python dedupe_cluster_names.py --storage D:/path/to/storage
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_STAGE = Path(__file__).resolve().parent
if str(_STAGE) not in sys.path:
    sys.path.insert(0, str(_STAGE))

from common_analysis import STORAGE_DIR


def _cluster_sort_key(code: Any) -> tuple[int, int, str]:
    s = str(code).strip()
    try:
        n = int(float(s))
        return (0, n, "")
    except ValueError:
        return (1, 0, s)


def _unique_name(used: set[str], desired: str) -> str:
    base = desired.strip() or "Unnamed Cluster"
    if base not in used:
        used.add(base)
        return base
    k = 1
    while True:
        cand = f"{base} {k}"
        if cand not in used:
            used.add(cand)
            return cand
        k += 1


def _dedupe_one_file(path: Path) -> int:
    if not path.is_file():
        return 0
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    clusters = data.get("clusters")
    if not isinstance(clusters, dict):
        return 0

    used: set[str] = set()
    changed = 0
    for code in sorted(clusters.keys(), key=_cluster_sort_key):
        payload = clusters[code]
        if not isinstance(payload, dict):
            continue
        old = str(payload.get("name", "") or "").strip()
        new = _unique_name(used, old)
        if new != old:
            changed += 1
        payload["name"] = new

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[dedupe_cluster_names] {path.name}: updated {changed} name(s), {len(clusters)} clusters", flush=True)
    return changed


def main() -> None:
    p = argparse.ArgumentParser(description="Make cluster names unique within each JSON file.")
    p.add_argument(
        "--storage",
        type=Path,
        default=STORAGE_DIR,
        help="Directory containing cluster_descriptions*.json",
    )
    args = p.parse_args()
    storage = args.storage.resolve()

    candidates = [
        storage / "cluster_descriptions.json",
    ]
    seen = 0
    for path in candidates:
        if path.is_file():
            _dedupe_one_file(path)
            seen += 1
    if seen == 0:
        print(f"[dedupe_cluster_names] No cluster_descriptions*.json found under {storage}", flush=True)


if __name__ == "__main__":
    main()
