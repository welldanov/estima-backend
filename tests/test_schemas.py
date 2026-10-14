from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from estima_backend.api.schemas.prediction import (
    ApartmentPredictionRequest,
    HousePredictionRequest,
    LandPredictionRequest,
    PredictionRequest,
)

prediction_request = TypeAdapter(PredictionRequest)


def apartment_request(
    **overrides: Any,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "property_type": "apartment",
        "city_id": 650210,
        "address": {"uri": "ymapsbm1://geo?ll=52.3,54.9"},
        "area_m2": 45,
        "rooms": 2,
        "floor": 3,
        "floors_total": 9,
    }
    data.update(overrides)

    return data


def test_apartment_request() -> None:
    request = prediction_request.validate_python(apartment_request())

    assert isinstance(request, ApartmentPredictionRequest)
    assert request.is_studio is False


def test_studio_request() -> None:
    request = prediction_request.validate_python(
        apartment_request(
            rooms=None,
            is_studio=True,
        )
    )

    assert isinstance(request, ApartmentPredictionRequest)


@pytest.mark.parametrize(
    "overrides",
    [
        {"rooms": None},
        {"rooms": 1, "is_studio": True},
        {"rooms": 0},
        {"rooms": 10, "area_m2": 200},
        {"floor": 10, "floors_total": 9},
        {"floor": 0},
        {"area_m2": 7.9},
        {"area_m2": 500.1},
        {"rooms": 3, "area_m2": 14},
        {"city_id": 0},
        {"address": {"uri": "https://example.com"}},
        {"address": {"uri": "ymapsbm1://" + "a" * 2000}},
    ],
)
def test_apartment_request_rejects_invalid_data(
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        prediction_request.validate_python(apartment_request(**overrides))


def test_house_request() -> None:
    request = prediction_request.validate_python(
        {
            "property_type": "house",
            "city_id": 650210,
            "address": {"uri": "ymapsbm1://geo"},
            "house_kind": "dacha",
            "house_area_m2": 40,
            "land_area_m2": 600,
        }
    )

    assert isinstance(request, HousePredictionRequest)


@pytest.mark.parametrize(
    "overrides",
    [
        {"house_kind": None},
        {"house_kind": "castle"},
        {"house_area_m2": 0},
        {"land_area_m2": 100_001},
    ],
)
def test_house_request_rejects_invalid_data(
    overrides: dict[str, Any],
) -> None:
    data = {
        "property_type": "house",
        "city_id": 650210,
        "address": {"uri": "ymapsbm1://geo"},
        "house_kind": "dacha",
        "house_area_m2": 40,
        "land_area_m2": 600,
    }
    data.update(overrides)

    with pytest.raises(ValidationError):
        prediction_request.validate_python(data)


def test_land_request() -> None:
    request = prediction_request.validate_python(
        {
            "property_type": "land",
            "city_id": 650210,
            "address": {"uri": "ymapsbm1://geo"},
            "land_area_m2": 600,
            "land_type": "izhs",
        }
    )

    assert isinstance(request, LandPredictionRequest)


def test_unknown_property_type() -> None:
    with pytest.raises(ValidationError):
        prediction_request.validate_python(apartment_request(property_type="garage"))
