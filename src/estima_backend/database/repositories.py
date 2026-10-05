import sqlite3
from datetime import datetime
from enum import StrEnum

from ..config import CityConfig
from ..ingestion.models import (
    ApartmentData,
    HouseData,
    LandData,
    NormalizedListing,
)


class SaveResult(StrEnum):
    INSERTED = "inserted"
    UPDATED = "updated"
    STALE = "stale"


def _format_timestamp(
        value: datetime,
) -> str:
    # единый формат, чтобы даты корректно сравнивались как строки
    return value.isoformat(timespec="seconds")


def upsert_city(
        conn: sqlite3.Connection,
        city: CityConfig,
) -> None:
    conn.execute(
        """
        INSERT INTO cities (id, name)
        VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name
        """,
        (
            city.id,
            city.name,
        ),
    )


def save_listing(
        conn: sqlite3.Connection,
        record: NormalizedListing,
) -> SaveResult:
    listing = record.listing
    seen_at = _format_timestamp(listing.seen_at)

    existing = conn.execute(
        """
        SELECT first_seen_at, last_seen_at
        FROM listings
        WHERE id = ?
        """,
        (listing.id,),
    ).fetchone()

    if existing is not None and existing["last_seen_at"] > seen_at:
        # запись из более старого парсинга: данные не трогаем,
        # только сдвигаем дату первого появления
        conn.execute(
            """
            UPDATE listings
            SET first_seen_at = min(first_seen_at, ?)
            WHERE id = ?
            """,
            (
                seen_at,
                listing.id,
            ),
        )

        return SaveResult.STALE

    first_seen_at = (
        seen_at
        if existing is None
        else min(existing["first_seen_at"], seen_at)
    )

    # каскад удалит строку из таблицы типа, даже если категория сменилась
    conn.execute(
        "DELETE FROM listings WHERE id = ?",
        (listing.id,),
    )

    conn.execute(
        """
        INSERT INTO listings (
            id,
            city_id,
            property_type,
            title,
            description,
            price,
            address,
            district,
            lat,
            lon,
            url,
            first_seen_at,
            last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
        """,
        (
            listing.id,
            listing.city_id,
            listing.property_type.value,
            listing.title,
            listing.description,
            listing.price,
            listing.address,
            listing.lat,
            listing.lon,
            listing.url,
            first_seen_at,
            seen_at,
        ),
    )

    match record.details:
        case ApartmentData() as apartment:
            _insert_apartment(conn, listing.id, apartment)

        case HouseData() as house:
            _insert_house(conn, listing.id, house)

        case LandData() as land:
            _insert_land(conn, listing.id, land)

        case _:
            raise TypeError(
                f"Unsupported listing details: {type(record.details)}"
            )

    return (
        SaveResult.INSERTED
        if existing is None
        else SaveResult.UPDATED
    )


def _insert_apartment(
        conn: sqlite3.Connection,
        listing_id: int,
        apartment: ApartmentData,
) -> None:
    conn.execute(
        """
        INSERT INTO apartments (
            listing_id,
            area_m2,
            rooms,
            is_studio,
            floor,
            floors_total
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            listing_id,
            apartment.area_m2,
            apartment.rooms,
            apartment.is_studio,
            apartment.floor,
            apartment.floors_total,
        ),
    )


def _insert_house(
        conn: sqlite3.Connection,
        listing_id: int,
        house: HouseData,
) -> None:
    conn.execute(
        """
        INSERT INTO houses (
            listing_id,
            house_kind,
            house_area_m2,
            land_area_m2
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            listing_id,
            house.house_kind.value,
            house.house_area_m2,
            house.land_area_m2,
        ),
    )


def _insert_land(
        conn: sqlite3.Connection,
        listing_id: int,
        land: LandData,
) -> None:
    conn.execute(
        """
        INSERT INTO lands (
            listing_id,
            land_area_m2,
            land_type
        )
        VALUES (?, ?, ?)
        """,
        (
            listing_id,
            land.land_area_m2,
            land.land_type.value,
        ),
    )
