from pathlib import Path
import sqlite3

from ..config import SCHEMA_PATH


def create_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")

    return connection


def apply_schema(
        conn: sqlite3.Connection,
        schema_path: Path = SCHEMA_PATH,
) -> None:
    # CREATE TABLE IF NOT EXISTS не обновляет таблицы старой схемы
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(listings)")
    }

    if columns and "property_type" not in columns:
        raise RuntimeError(
            "Database has an outdated schema, "
            "recreate it (importer --rebuild)"
        )

    conn.executescript(
        schema_path.read_text(encoding="utf-8")
    )
