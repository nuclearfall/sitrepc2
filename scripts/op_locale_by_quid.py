import overpy
import csv
import time

QIDS = [
    "Q4025836",
    "Q4153016",
    "Q4173796",
    "Q4230435",
    "Q4230441",
    "Q4230442",
    "Q4272128",
    "Q4294214",
    "Q4334273",
    "Q4336734",
    "Q4392577",
    "Q44279",
    "Q757912",
    "Q2064567",
    "Q4442207"
]

api = overpy.Overpass()

def fetch_osm_elements_for_qid(qid):
    query = f"""
    [out:json][timeout:60];
    (
      node["wikidata"="{qid}"];
      way["wikidata"="{qid}"];
      relation["wikidata"="{qid}"];
    );
    out body center tags;
    """
    return api.query(query)


def extract_fields(osm_type, element, qid):
    """
    Convert Overpy element to the ua_settlements CSV schema.
    """
    tags = element.tags

    # OSM type + ID
    osm_id = element.id

    # Tags
    place = tags.get("place")

    name_en = tags.get("name:en")      # becomes "name"
    name_uk = tags.get("name")         # becomes "name:uk"

    # Coordinates:
    # nodes → lat/lon are direct
    # ways/relations → Overpass returns "center" in element.center_lat/lon
    if osm_type == "node":
        lat = element.lat
        lon = element.lon
    else:
        lat = getattr(element, "center_lat", None)
        lon = getattr(element, "center_lon", None)

    return {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "place": place,
        "name": name_en,
        "name:uk": name_uk,
        "wikidata": qid,
        "lat": lat,
        "lon": lon,
    }


if __name__ == "__main__":

    # CSV output
    with open("qid_osm_results.csv", "w", encoding="utf-8", newline="") as f_out:
        fieldnames = ["osm_type","osm_id","place","name","name:uk","wikidata","lat","lon"]
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for qid in QIDS:
            print(f"\n=== Fetching {qid} ===")

            try:
                result = fetch_osm_elements_for_qid(qid)

                # Nodes
                for node in result.nodes:
                    row = extract_fields("node", node, qid)
                    writer.writerow(row)
                    print(" node", row)

                # Ways
                for way in result.ways:
                    row = extract_fields("way", way, qid)
                    writer.writerow(row)
                    print(" way", row)

                # Relations
                for rel in result.relations:
                    row = extract_fields("relation", rel, qid)
                    writer.writerow(row)
                    print(" relation", row)

            except Exception as e:
                print(f"ERROR fetching {qid}: {e}")

            time.sleep(1)  # avoid rate-limit
