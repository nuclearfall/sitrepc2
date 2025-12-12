import csv
import sys

# Usage:
#   python compare_qids.py file1.csv file2.csv

file1 = sys.argv[1]
file2 = sys.argv[2]

def load_qids(path):
    qids = set()
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = row.get("qid") or row.get("wikidata") or row.get("wikidata_id")
            if q and q.strip():
                qids.add(q.strip())
    return qids

qids1 = load_qids(file1)
qids2 = load_qids(file2)

missing_in_file2 = qids1 - qids2
missing_in_file1 = qids2 - qids1

print(f"\nQIDs in {file1} but missing in {file2}:")
for q in sorted(missing_in_file2):
    print(" ", q)

print(f"\nQIDs in {file2} but missing in {file1}:")
for q in sorted(missing_in_file1):
    print(" ", q)

print("\nDone.")
