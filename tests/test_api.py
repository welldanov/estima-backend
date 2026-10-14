from typing import Any

import pytest
from conftest import FakeGeocoder, FakeSuggest
from fastapi.testclient import TestClient

from estima_backend.api.providers.quota import DailyQuotaExceededError
from estima_backend.api.providers.yandex import (
    GeocodedAddress,
    Suggestion,
    YandexAPIError,
)
from estima_backend.config import CITIES

ALMETYEVSK = CITIES[650210]
KAZAN = CITIES[650400]


def suggestion(
    title: str,
    distance_km: float | None = 1.0,
) -> Suggestion:
    return Suggestion(
        title=title,
        subtitle="Альметьевск",
        formatted_address=f"Россия, Альметьевск, {title}",
        uri=f"ymapsbm1://geo?text={title}",
        kind="house",
        distance_km=distance_km,
    )


def address(
    lat: float = 54.91,
    lon: float = 52.33,
    kind: str = "house",
) -> GeocodedAddress:
    return GeocodedAddress(
        formatted_address="Россия, Альметьевск, улица Ленина, 1",
        kind=kind,
        lat=lat,
        lon=lon,
    )


def apartment_request(
    **overrides: Any,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "property_type": "apartment",
        "city_id": ALMETYEVSK.id,
        "address": {"uri": "ymapsbm1://geo?ll=52.33,54.91"},
        "area_m2": 45,
        "rooms": 2,
        "floor": 3,
        "floors_total": 9,
    }
    data.update(overrides)

    return data


HOUSE_REQUEST = {
    "property_type": "house",
    "city_id": ALMETYEVSK.id,
    "address": {"uri": "ymapsbm1://geo?ll=52.33,54.91"},
    "house_kind": "house",
    "house_area_m2": 120,
    "land_area_m2": 800,
}


# HEALTH AND CITIES


def test_health(
    client: TestClient,
) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "yandex_usage": {
            "geocoder": {"used": 0, "limit": 5},
            "geosuggest": {"used": 0, "limit": 5},
        },
    }


def test_health_supports_head(
    client: TestClient,
) -> None:
    assert client.head("/api/health").status_code == 200


def test_cities(
    client: TestClient,
) -> None:
    response = client.get("/api/cities")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": ALMETYEVSK.id,
            "name": "Альметьевск",
            "property_types": ["apartment", "house", "land"],
        },
        {
            "id": KAZAN.id,
            "name": "Казань",
            "property_types": ["apartment"],
        },
    ]


# ADDRESSES


def test_search_filters_far_suggestions(
    client: TestClient,
    suggest: FakeSuggest,
) -> None:
    suggest.responses["Ленина 1"] = [
        suggestion("улица Ленина, 1"),
        suggestion("улица Ленина, 1, Москва", distance_km=1000),
        suggestion("улица Ленина, 1А", distance_km=None),
    ]

    response = client.get(
        "/api/addresses/search",
        params={"city_id": ALMETYEVSK.id, "query": "Ленина 1"},
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == [
        "улица Ленина, 1",
        "улица Ленина, 1А",
    ]
    assert suggest.calls == ["Ленина 1"]


def test_search_retries_with_city_name(
    client: TestClient,
    suggest: FakeSuggest,
) -> None:
    suggest.responses["Альметьевск Ленина 1"] = [suggestion("улица Ленина, 1")]

    response = client.get(
        "/api/addresses/search",
        params={"city_id": ALMETYEVSK.id, "query": "Ленина 1"},
    )

    assert len(response.json()["items"]) == 1
    assert suggest.calls == ["Ленина 1", "Альметьевск Ленина 1"]


def test_search_does_not_repeat_city_name(
    client: TestClient,
    suggest: FakeSuggest,
) -> None:
    response = client.get(
        "/api/addresses/search",
        params={"city_id": ALMETYEVSK.id, "query": "альметьевск Ленина 1"},
    )

    assert response.json() == {"items": []}
    assert suggest.calls == ["альметьевск Ленина 1"]


def test_search_limits_suggestions(
    client: TestClient,
    suggest: FakeSuggest,
) -> None:
    suggest.responses["Ленина"] = [suggestion(f"улица Ленина, {number}") for number in range(10)]

    response = client.get(
        "/api/addresses/search",
        params={"city_id": ALMETYEVSK.id, "query": "Ленина"},
    )

    assert len(response.json()["items"]) == 7


@pytest.mark.parametrize(
    ("params", "status_code"),
    [
        ({"city_id": 1, "query": "Ленина"}, 404),
        ({"city_id": ALMETYEVSK.id, "query": " a "}, 422),
        ({"city_id": ALMETYEVSK.id}, 422),
    ],
)
def test_search_rejects_bad_request(
    client: TestClient,
    suggest: FakeSuggest,
    params: dict[str, Any],
    status_code: int,
) -> None:
    response = client.get(
        "/api/addresses/search",
        params=params,
    )

    assert response.status_code == status_code
    assert suggest.calls == []


# PREDICTION


def test_predict_apartment(
    client: TestClient,
    geocoder: FakeGeocoder,
) -> None:
    geocoder.address = address()

    response = client.post("/api/predict", json=apartment_request())

    assert response.status_code == 200

    body = response.json()

    assert body["property_type"] == "apartment"
    assert 1_000_000 < body["predicted_price"] < 50_000_000
    assert body["approximate_reasons"] == []
    assert body["address"]["kind"] == "house"
    assert body["address"]["distance_to_center_km"] == pytest.approx(2.2, abs=0.2)
    assert geocoder.calls == ["ymapsbm1://geo?ll=52.33,54.91"]


def test_predict_far_from_center_is_approximate(
    client: TestClient,
    geocoder: FakeGeocoder,
) -> None:
    # ~7.8 км: дальше радиуса квартир Альметьевска (6 км), но в мягкой зоне (11 км).
    geocoder.address = address(lat=54.97, lon=52.3)

    response = client.post("/api/predict", json=apartment_request())

    assert response.status_code == 200
    assert response.json()["approximate_reasons"] == ["far_from_center"]


def test_predict_house_without_house_number_is_approximate(
    client: TestClient,
    geocoder: FakeGeocoder,
) -> None:
    geocoder.address = address(kind="street")

    response = client.post("/api/predict", json=HOUSE_REQUEST)

    assert response.status_code == 200
    assert response.json()["approximate_reasons"] == ["address_without_house"]


@pytest.mark.parametrize(
    ("request_data", "geocoded", "status_code"),
    [
        (apartment_request(city_id=1), address(), 404),
        ({**HOUSE_REQUEST, "city_id": KAZAN.id}, address(), 422),
        (apartment_request(), None, 422),
        (apartment_request(), address(kind="street"), 422),
        ({**HOUSE_REQUEST}, address(kind="province"), 422),
        (apartment_request(), address(lat=55.05, lon=52.3), 422),
        (apartment_request(rooms=None), address(), 422),
    ],
)
def test_predict_rejects_request(
    client: TestClient,
    geocoder: FakeGeocoder,
    request_data: dict[str, Any],
    geocoded: GeocodedAddress | None,
    status_code: int,
) -> None:
    geocoder.address = geocoded

    response = client.post("/api/predict", json=request_data)

    assert response.status_code == status_code
    assert isinstance(response.json()["detail"], str | list)


def test_predict_does_not_geocode_unsupported_type(
    client: TestClient,
    geocoder: FakeGeocoder,
) -> None:
    client.post("/api/predict", json={**HOUSE_REQUEST, "city_id": KAZAN.id})

    assert geocoder.calls == []


def test_yandex_error_returns_502(
    client: TestClient,
    geocoder: FakeGeocoder,
) -> None:
    geocoder.error = YandexAPIError("Yandex geocoder returned HTTP 500")

    response = client.post("/api/predict", json=apartment_request())

    assert response.status_code == 502
    assert "Yandex" not in response.json()["detail"]


def test_exhausted_quota_returns_503(
    client: TestClient,
    suggest: FakeSuggest,
) -> None:
    suggest.error = DailyQuotaExceededError(
        api_name="geosuggest",
        limit=900,
        retry_after=120,
    )

    response = client.get(
        "/api/addresses/search",
        params={"city_id": ALMETYEVSK.id, "query": "Ленина"},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "120"
