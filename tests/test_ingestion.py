import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from estima_backend.database.repositories import SaveResult
from estima_backend.ingestion.importer import import_path
from estima_backend.ingestion.models import (
    ApartmentData,
    HouseData,
    LandData,
    ListingType,
    SkipRecord,
)
from estima_backend.ingestion.normalizer import build_url, normalize
from estima_backend.ingestion.reader import collect_json_files, extract_records
from estima_backend.ingestion.validator import validate_record

ALMETYEVSK_ID = 650210


def raw_record(
    **overrides: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": 1001,
        "title": "2-к. квартира, 50,3 м², 4/9 эт.",
        "description": "Продаётся квартира",
        "category": {"id": 24, "name": "Квартиры"},
        "location": {"id": ALMETYEVSK_ID, "name": "Альметьевск"},
        "priceDetailed": {"value": 6_500_000},
        "geo": {"formattedAddress": "ул. Тельмана, 62"},
        "coords": {"lat": "54.9097", "lng": "52.3267"},
        "urlPath": "/almetevsk/kvartiry/2-k._kvartira_1001?context=abc",
        "parsed_at": "2026-09-07T15:51:28.518803",
    }
    record.update(overrides)

    return record


# NORMALIZER


def test_normalize_apartment() -> None:
    result = normalize(validate_record(raw_record()))

    assert result.listing.id == 1001
    assert result.listing.city_id == ALMETYEVSK_ID
    assert result.listing.property_type is ListingType.APARTMENT
    assert result.listing.price == 6_500_000
    assert result.listing.lat == pytest.approx(54.9097)
    assert (
        result.listing.url
        == "https://www.avito.ru/almetevsk/kvartiry/2-k._kvartira_1001?context=abc"
    )
    assert result.details == ApartmentData(
        area_m2=50.3,
        rooms=2,
        is_studio=False,
        floor=4,
        floors_total=9,
    )


@pytest.mark.parametrize(
    ("category_id", "title", "details_type"),
    [
        (25, "Дом 120 м² на участке 6 сот.", HouseData),
        (26, "Участок 6 сот. (ИЖС)", LandData),
    ],
)
def test_normalize_house_and_land(
    category_id: int,
    title: str,
    details_type: type,
) -> None:
    result = normalize(
        validate_record(
            raw_record(
                category={"id": category_id, "name": "Категория"},
                title=title,
            )
        )
    )

    assert isinstance(result.details, details_type)


@pytest.mark.parametrize(
    "overrides",
    [
        {"location": {"id": 1, "name": "Москва"}},
        {"category": {"id": 42, "name": "Гаражи"}},
        {"geo": {"formattedAddress": "   "}},
        {"title": "Апартаменты-студия, 25 м², 3/10 эт."},
    ],
)
def test_normalize_skips_unsupported_records(
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(SkipRecord):
        normalize(validate_record(raw_record(**overrides)))


@pytest.mark.parametrize(
    "overrides",
    [
        {"priceDetailed": {"value": 0}},
        {"coords": {"lat": "95", "lng": "52"}},
        {"id": None},
    ],
)
def test_validate_record_rejects_invalid_values(
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        validate_record(raw_record(**overrides))


def test_build_url_keeps_absolute_url() -> None:
    assert build_url("https://m.avito.ru/item") == "https://m.avito.ru/item"


# READER


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([{"id": 1}, {"id": 2}], [{"id": 1}, {"id": 2}]),
        ({"items": [{"id": 1}]}, [{"id": 1}]),
        ({"id": 1}, [{"id": 1}]),
        ({"urls": ["https://www.avito.ru"]}, []),
    ],
)
def test_extract_records(
    data: Any,
    expected: list[dict],
) -> None:
    assert extract_records(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        "text",
        [{"id": 1}, "text"],
    ],
)
def test_extract_records_rejects_invalid_root(
    data: Any,
) -> None:
    with pytest.raises(ValueError):
        extract_records(data)


def test_collect_json_files_is_recursive(
    tmp_path: Path,
) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "page1.json").write_text("[]", encoding="utf-8")
    (tmp_path / "page2.json").write_text("[]", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")

    assert [path.name for path in collect_json_files(tmp_path)] == [
        "page1.json",
        "page2.json",
    ]


# IMPORTER


def write_page(
    path: Path,
    records: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(records, ensure_ascii=False),
        encoding="utf-8",
    )


def test_import_path(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "test.db"

    write_page(
        raw_dir / "2026-09-07" / "page1.json",
        [
            raw_record(id=1, parsed_at="2026-09-07T10:00:00"),
            raw_record(id=2, title="Апартаменты-студия, 25 м², 3/10 эт."),
            raw_record(id=3, priceDetailed={"value": 0}),
        ],
    )
    write_page(
        raw_dir / "2026-09-14" / "page1.json",
        [
            raw_record(id=1, priceDetailed={"value": 6_000_000}, parsed_at="2026-09-14T10:00:00"),
        ],
    )
    (raw_dir / "broken.json").write_text("{", encoding="utf-8")

    result = import_path(raw_dir, db_path)

    assert result.files == 2
    assert result.total == 4
    assert result.saved[SaveResult.INSERTED] == 1
    assert result.saved[SaveResult.UPDATED] == 1
    assert len(result.skipped) == 2
    assert len(result.skipped_files) == 1

    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT id, price, first_seen_at, last_seen_at FROM listings"
        ).fetchall()

    assert rows == [(1, 6_000_000, "2026-09-07T10:00:00", "2026-09-14T10:00:00")]


def test_import_path_is_idempotent(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "test.db"

    write_page(
        raw_dir / "page1.json",
        [raw_record(id=1), raw_record(id=2)],
    )

    import_path(raw_dir, db_path)
    import_path(raw_dir, db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM listings").fetchone() == (2,)
        assert conn.execute("SELECT COUNT(*) FROM apartments").fetchone() == (2,)


def test_import_path_rebuild_keeps_backup(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "test.db"

    write_page(raw_dir / "page1.json", [raw_record()])

    import_path(raw_dir, db_path)
    result = import_path(raw_dir, db_path, rebuild=True)

    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.saved[SaveResult.INSERTED] == 1
