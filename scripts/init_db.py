import sqlite3

from estima_backend.config import DB_PATH, SCHEMA_PATH


def init_database() -> None:
    print(f"Database: {DB_PATH}")
    print(f"Schema:   {SCHEMA_PATH}")

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Schema not found: {SCHEMA_PATH}"
        )

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    schema = SCHEMA_PATH.read_text(
        encoding="utf-8"
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.executescript(schema)

    print("Database initialized successfully.")


if __name__ == "__main__":
    init_database()
