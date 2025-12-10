import csv
import sys
from collections import defaultdict

# Usage:
#   python find_duplicate_wikidata.py ua_settlements.csv

path = sys.argv[1]

duplicates = defaultdict(list)

with open(path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        qid = row.get("wikidata")
        if qid and qid.strip():
            duplicates[qid].append(row)

print("\n=== DUPLICATE WIKIDATA ENTRIES ===\n")

for qid, rows in duplicates.items():
    if len(rows) > 1:
        print(f"--- {qid} appears {len(rows)} times ---")
        for r in rows:
            print(f"  {r['osm_type']},{r['osm_id']},{r.get('name')},{r.get('name:uk')},{r.get('lat')},{r.get('lon')}")
        print()
