import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from estima_backend.api.providers.quota import (
    DailyQuotaExceededError,
    DailyRequestCounter,
)
from estima_backend.config import YANDEX_QUOTA_TIMEZONE


def make_counter(
    storage_path: Path,
    limit: int = 2,
) -> DailyRequestCounter:
    return DailyRequestCounter(
        storage_path=storage_path,
        limits={"geocoder": limit, "geosuggest": limit},
        tz=YANDEX_QUOTA_TIMEZONE,
    )


def test_acquire_counts_requests_per_api(
    tmp_path: Path,
) -> None:
    counter = make_counter(tmp_path / "usage.json")

    asyncio.run(counter.acquire("geocoder"))
    asyncio.run(counter.acquire("geocoder"))
    asyncio.run(counter.acquire("geosuggest"))

    assert counter.usage() == {
        "geocoder": {"used": 2, "limit": 2},
        "geosuggest": {"used": 1, "limit": 2},
    }


def test_acquire_raises_when_limit_is_exhausted(
    tmp_path: Path,
) -> None:
    counter = make_counter(tmp_path / "usage.json", limit=1)

    asyncio.run(counter.acquire("geocoder"))

    with pytest.raises(DailyQuotaExceededError) as exc_info:
        asyncio.run(counter.acquire("geocoder"))

    assert 0 < exc_info.value.retry_after <= 24 * 60 * 60
    assert counter.usage()["geocoder"]["used"] == 1


def test_counter_is_persisted(
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / "usage.json"

    asyncio.run(make_counter(storage_path).acquire("geocoder"))

    assert make_counter(storage_path).usage()["geocoder"]["used"] == 1


def test_counter_resets_on_new_day(
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / "usage.json"
    old_day = date.today() - timedelta(days=2)
    storage_path.write_text(
        json.dumps({"date": old_day.isoformat(), "counts": {"geocoder": 2}}),
        encoding="utf-8",
    )

    counter = make_counter(storage_path)

    assert counter.usage()["geocoder"]["used"] == 0
    asyncio.run(counter.acquire("geocoder"))


def test_counter_resets_at_midnight_while_running(
    tmp_path: Path,
) -> None:
    counter = make_counter(tmp_path / "usage.json", limit=1)

    asyncio.run(counter.acquire("geocoder"))
    counter._day -= timedelta(days=1)

    asyncio.run(counter.acquire("geocoder"))

    assert counter.usage()["geocoder"]["used"] == 1


def test_corrupted_file_starts_from_zero(
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / "usage.json"
    storage_path.write_text("{not json", encoding="utf-8")

    assert make_counter(storage_path).usage()["geocoder"]["used"] == 0
