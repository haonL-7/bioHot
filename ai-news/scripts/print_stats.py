#!/usr/bin/env python3
"""Print summary stats from stats.json (called by GitHub Actions workflow)"""
import json, os, sys

STATS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stats.json")

try:
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        s = json.load(f)
    print(f"  Articles: {s.get('total_articles', 'N/A')}")
    print(f"  Avg Authority: {s.get('avg_authority', 'N/A')}")
    print(f"  Avg Novelty: {s.get('avg_novelty', 'N/A')}")
    print(f"  Avg Value: {s.get('avg_value', 'N/A')}")
    print(f"  Updated: {s.get('updated_at_human', 'N/A')}")
except Exception as e:
    print(f"  ERROR reading stats: {e}")
    sys.exit(0)
