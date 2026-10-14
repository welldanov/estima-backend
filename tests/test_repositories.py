import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from estima_backend.config import CITIES
from estima_backend.database.connection import apply_schema, create_connection
from estima_backend.database.repositories import SaveResult, save_listing, upsert_city
from estima_backend.ingestion.models import (
    ApartmentData,
    LandData,
    LandType,
    ListingData,
    ListingDetails,
    ListingType,
    NormalizedListing,
)

ALMETYEVSK_ID = 650210

APARTMENT = ApartmentData(
    area_m2=45.0,
    rooms=2,
    is_studio=False,
    floor=3,
    floors_total=9,
)


def make_listing(
    *,
    seen_at: str,
    price: int = 5_000_000,
    details: ListingDetails = APARTMENT,
    property_type: ListingType = ListingType.APARTMENT,
) -> NormalizedListing:
    return NormalizedListing(
        listing=ListingData(
            id=1,
            city_id=ALMETYEVSK_ID,
            property_type=property_type,
            title="2-к. квартира, 45 м², 3/9 эт.",
            description="",
            price=price,
            address="ул. Ленина, 1",
            lat=54.9,
            lon=52.3,
            url="https://www.avito.ru/1",
            seen_at=datetime.fromisoformat(seen_at),
        ),
        details=details,
    )


@pytest.fixture
def conn(
    tmp_path: Path,
) -> Iterator[sqlite3.Connection]:
    connection = create_connection(tmp_path / "test.db")
    apply_schema(connection)

    for city in CITIES.values():
        upsert_city(connection, city)

    yield connection

    connection.close()


def listing_row(
    conn: sqlite3.Connection,
) -> sqlite3.Row:
    return conn.execute(
        "SELECT price, first_seen_at, last_seen_at FROM listings WHERE id = 1"
    ).fetchone()


def test_save_listing_inserts_new_listing(
    conn: sqlite3.Connection,
) -> None:
    assert (
        save_listing(conn, make_listing(seen_at="2026-09-07T10:00:00.123456"))
        is SaveResult.INSERTED
    )

    row = listing_row(conn)

    assert row["first_seen_at"] == "2026-09-07T10:00:00"
    assert row["last_seen_at"] == "2026-09-07T10:00:00"
    assert (
        conn.execute("SELECT rooms FROM apartments WHERE listing_id = 1").fetchone()["rooms"] == 2
    )


def test_save_listing_updates_with_newer_data(
    conn: sqlite3.Connection,
) -> None:
    save_listing(conn, make_listing(seen_at="2026-09-07T10:00:00"))

    result = save_listing(
        conn,
        make_listing(
            seen_at="2026-09-14T10:00:00",
            price=4_500_000,
        ),
    )

    assert result is SaveResult.UPDATED
    assert tuple(listing_row(conn)) == (4_500_000, "2026-09-07T10:00:00", "2026-09-14T10:00:00")


def test_save_listing_keeps_newer_data_from_stale_record(
    conn: sqlite3.Connection,
) -> None:
    save_listing(conn, make_listing(seen_at="2026-09-14T10:00:00"))

    result = save_listing(
        conn,
        make_listing(
            seen_at="2026-09-07T10:00:00",
            price=9_999_999,
        ),
    )

    assert result is SaveResult.STALE
    assert tuple(listing_row(conn)) == (5_000_000, "2026-09-07T10:00:00", "2026-09-14T10:00:00")


def test_save_listing_replaces_details_when_category_changes(
    conn: sqlite3.Connection,
) -> None:
    save_listing(conn, make_listing(seen_at="2026-09-07T10:00:00"))
    save_listing(
        conn,
        make_listing(
            seen_at="2026-09-14T10:00:00",
            property_type=ListingType.LAND,
            details=LandData(
                land_area_m2=600.0,
                land_type=LandType.IZHS,
            ),
        ),
    )

    assert conn.execute("SELECT COUNT(*) FROM apartments").fetchone()[0] == 0
    assert conn.execute("SELECT land_type FROM lands").fetchone()[0] == "izhs"


def test_apply_schema_rejects_outdated_database(
    tmp_path: Path,
) -> None:
    connection = create_connection(tmp_path / "old.db")
    connection.execute("CREATE TABLE listings (id INTEGER PRIMARY KEY)")

    with pytest.raises(RuntimeError):
        apply_schema(connection)

    connection.close()
