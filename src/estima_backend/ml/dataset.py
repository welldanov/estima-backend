import sqlite3

import pandas as pd


LISTING_COLUMNS = """
            l.id AS listing_id,
            l.price,
            l.url,
            l.address,
            l.city_id,
            l.lat,
            l.lon,
            l.last_seen_at
"""


def _load(
        conn: sqlite3.Connection,
        columns: str,
        join: str,
) -> pd.DataFrame:
    query = f"""
        SELECT
            {LISTING_COLUMNS},
            {columns}

        FROM listings l
        {join}

        ORDER BY l.id
    """

    return pd.read_sql_query(query, conn)


def load_apartments(
        conn: sqlite3.Connection,
) -> pd.DataFrame:
    return _load(
        conn,
        columns="""
            a.area_m2,
            a.rooms,
            a.is_studio,
            a.floor,
            a.floors_total
        """,
        join="""
        JOIN apartments a
            ON a.listing_id = l.id
        """,
    )


def load_houses(
        conn: sqlite3.Connection,
) -> pd.DataFrame:
    return _load(
        conn,
        columns="""
            h.house_kind,
            h.house_area_m2,
            h.land_area_m2
        """,
        join="""
        JOIN houses h
            ON h.listing_id = l.id
        """,
    )


def load_lands(
        conn: sqlite3.Connection,
) -> pd.DataFrame:
    return _load(
        conn,
        columns="""
            ld.land_area_m2,
            ld.land_type
        """,
        join="""
        JOIN lands ld
            ON ld.listing_id = l.id
        """,
    )
