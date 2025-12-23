import sqlite3

from sitrepc2.config.paths import records_path
from sitrepc2.dom.materialize import to_dom_tree
from sitrepc2.dom.debug_dom_tree import print_dom_tree


def main():
    ingest_post_id = int(input("Ingest post ID: ").strip())

    with sqlite3.connect(records_path()) as con:
        con.row_factory = sqlite3.Row

        # Find latest completed LSS run
        row = con.execute(
            """
            SELECT id
            FROM lss_runs
            WHERE ingest_post_id = ?
              AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 1
            """,
            (ingest_post_id,),
        ).fetchone()

        if not row:
            raise RuntimeError("No completed LSS run found")

        lss_run_id = row["id"]

        dom_tree = to_dom_tree(
            ingest_post_id=ingest_post_id,
            lss_run_id=lss_run_id,
            con=con,
        )

    print("\nDOM TREE\n========\n")
    print_dom_tree(dom_tree)


if __name__ == "__main__":
    main()
