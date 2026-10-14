from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from estima_backend.api import dependencies
from estima_backend.api.main import app
from estima_backend.api.providers.quota import DailyRequestCounter
from estima_backend.api.providers.yandex import (
    GEOCODER_API_NAME,
    GEOSUGGEST_API_NAME,
    GeocodedAddress,
    Suggestion,
)
from estima_backend.api.services.address_service import AddressService
from estima_backend.api.services.city_service import CityService
from estima_backend.api.services.prediction_service import PredictionService
from estima_backend.config import YANDEX_QUOTA_TIMEZONE
from estima_backend.ml.predictor import RealEstatePredictor


class FakeGeocoder:
    def __init__(self) -> None:
        self.address: GeocodedAddress | None = None
        self.error: Exception | None = None
        self.calls: list[str] = []

    async def geocode_uri(
        self,
        uri: str,
    ) -> GeocodedAddress | None:
        self.calls.append(uri)

        if self.error is not None:
            raise self.error

        return self.address


class FakeSuggest:
    def __init__(self) -> None:
        self.responses: dict[str, list[Suggestion]] = {}
        self.error: Exception | None = None
        self.calls: list[str] = []

    async def suggest(
        self,
        *,
        text: str,
        lat: float,
        lon: float,
        radius_km: float,
        results: int = 10,
    ) -> list[Suggestion]:
        self.calls.append(text)

        if self.error is not None:
            raise self.error

        return self.responses.get(text, [])


@pytest.fixture(scope="session")
def predictor() -> RealEstatePredictor:
    return RealEstatePredictor()


@pytest.fixture
def geocoder() -> FakeGeocoder:
    return FakeGeocoder()


@pytest.fixture
def suggest() -> FakeSuggest:
    return FakeSuggest()


def make_quota(
    storage_path: Path,
    limit: int = 5,
) -> DailyRequestCounter:
    return DailyRequestCounter(
        storage_path=storage_path,
        limits={
            GEOCODER_API_NAME: limit,
            GEOSUGGEST_API_NAME: limit,
        },
        tz=YANDEX_QUOTA_TIMEZONE,
    )


@pytest.fixture
def quota(
    tmp_path: Path,
) -> DailyRequestCounter:
    return make_quota(tmp_path / "yandex_usage.json")


@pytest.fixture
def client(
    predictor: RealEstatePredictor,
    geocoder: FakeGeocoder,
    suggest: FakeSuggest,
    quota: DailyRequestCounter,
) -> Iterator[TestClient]:
    city_service = CityService(predictor)
    address_service = AddressService(
        suggest=suggest,
        cities=city_service,
    )
    prediction_service = PredictionService(
        predictor=predictor,
        geocoder=geocoder,
        cities=city_service,
    )

    app.dependency_overrides = {
        dependencies.get_city_service: lambda: city_service,
        dependencies.get_address_service: lambda: address_service,
        dependencies.get_prediction_service: lambda: prediction_service,
        dependencies.get_yandex_quota: lambda: quota,
    }

    yield TestClient(app)

    app.dependency_overrides.clear()
