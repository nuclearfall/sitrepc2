from review.db import connect

def set_enabled(table: str, id_col: str, entity_id: str, enabled: bool):
    with connect() as con:
        con.execute(
            f"UPDATE {table} SET enabled=? WHERE {id_col}=?",
            (1 if enabled else 0, entity_id),
        )
