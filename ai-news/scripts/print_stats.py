#!/usr/bin/env python3
"""Print summary of stats.json (used by GitHub Actions workflow)"""
import json, os, sys

STATS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stats.json")

try:
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        s = json.load(f)
    print(f"  Papers: {s.get('total_papers', 'N/A')}")
    print(f"  Evidence levels: {s.get('evidence_levels', {})}")
    print(f"  Avg Effectiveness: {s.get('avg_effectiveness', 'N/A')}")
    print(f"  Avg Safety: {s.get('avg_safety', 'N/A')}")
    print(f"  Avg Coupling: {s.get('avg_coupling', 'N/A')}")
    print(f"  Avg Meas. Depth: {s.get('avg_measurement_depth', 'N/A')}")
    print(f"  Updated: {s.get('updated_at_human', 'N/A')}")
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(0)
