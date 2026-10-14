import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from estima_backend.api.providers.quota import DailyQuotaExceededError, DailyRequestCounter
from estima_backend.api.providers.yandex import (
    GeocodedAddress,
    Suggestion,
    YandexAPIError,
    YandexGeocoder,
    YandexSuggest,
)

API_KEY = "test-key"

Handler = Callable[[httpx.Request], httpx.Response]


def geocode(
    handler: Handler,
    quota: DailyRequestCounter,
    api_key: str | None = API_KEY,
) -> GeocodedAddress | None:
    async def run() -> GeocodedAddress | None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            geocoder = YandexGeocoder(
                client=client,
                quota=quota,
                api_key=api_key,
            )

            return await geocoder.geocode_uri("ymapsbm1://geo?ll=52.3,54.9")

    return asyncio.run(run())


def suggest(
    handler: Handler,
    quota: DailyRequestCounter,
) -> list[Suggestion]:
    async def run() -> list[Suggestion]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = YandexSuggest(
                client=client,
                quota=quota,
                api_key=API_KEY,
            )

            return await provider.suggest(
                text="Ленина 1",
                lat=54.9,
                lon=52.3,
                radius_km=10,
            )

    return asyncio.run(run())


def json_response(
    data: Any,
) -> Handler:
    return lambda request: httpx.Response(200, json=data)


def geocoder_response(
    *members: dict[str, Any],
) -> dict[str, Any]:
    return {
        "response": {
            "GeoObjectCollection": {
                "featureMember": list(members),
            },
        },
    }


GEO_OBJECT = {
    "GeoObject": {
        "metaDataProperty": {
            "GeocoderMetaData": {
                "kind": "house",
                "Address": {"formatted": "Россия, Альметьевск, улица Ленина, 1"},
            },
        },
        "Point": {"pos": "52.3 54.9"},
    },
}


# GEOCODER


def test_geocode_uri(
    quota: DailyRequestCounter,
) -> None:
    requests: list[httpx.Request] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        requests.append(request)

        return httpx.Response(200, json=geocoder_response(GEO_OBJECT))

    address = geocode(handler, quota)

    assert address == GeocodedAddress(
        formatted_address="Россия, Альметьевск, улица Ленина, 1",
        kind="house",
        lat=54.9,
        lon=52.3,
    )
    assert requests[0].url.params["apikey"] == API_KEY
    assert requests[0].url.params["uri"] == "ymapsbm1://geo?ll=52.3,54.9"
    assert quota.usage()["geocoder"]["used"] == 1


def test_geocode_uri_not_found(
    quota: DailyRequestCounter,
) -> None:
    assert geocode(json_response(geocoder_response()), quota) is None


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500),
        lambda request: httpx.Response(200, text="not json"),
        json_response([]),
        json_response({"response": {}}),
        json_response(
            geocoder_response({"GeoObject": {**GEO_OBJECT["GeoObject"], "Point": {"pos": "bad"}}})
        ),
    ],
)
def test_geocode_uri_rejects_bad_response(
    quota: DailyRequestCounter,
    handler: Handler,
) -> None:
    with pytest.raises(YandexAPIError):
        geocode(handler, quota)


def test_connection_error_does_not_leak_api_key(
    quota: DailyRequestCounter,
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect to {request.url}")

    with pytest.raises(YandexAPIError) as exc_info:
        geocode(handler, quota)

    assert API_KEY not in str(exc_info.value)


def test_missing_api_key_does_not_use_quota(
    quota: DailyRequestCounter,
) -> None:
    with pytest.raises(YandexAPIError):
        geocode(json_response(geocoder_response()), quota, api_key=None)

    assert quota.usage()["geocoder"]["used"] == 0


def test_exhausted_quota_blocks_request(
    quota: DailyRequestCounter,
) -> None:
    requests: list[httpx.Request] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        requests.append(request)

        return httpx.Response(200, json=geocoder_response())

    for _ in range(quota.limits["geocoder"]):
        geocode(handler, quota)

    with pytest.raises(DailyQuotaExceededError):
        geocode(handler, quota)

    assert len(requests) == quota.limits["geocoder"]


# GEOSUGGEST


def test_suggest_parses_results(
    quota: DailyRequestCounter,
) -> None:
    data = {
        "results": [
            {
                "title": {"text": "улица Ленина, 1"},
                "subtitle": {"text": "Альметьевск"},
                "address": {"formatted_address": "Россия, Альметьевск, улица Ленина, 1"},
                "uri": "ymapsbm1://geo?id=1",
                "tags": ["business", "house"],
                "distance": {"value": 1500},
            },
            {
                "title": {"text": "Альметьевск"},
                "uri": "ymapsbm1://geo?id=2",
            },
            {"title": {"text": "без uri"}},
            "not an object",
        ],
    }

    assert suggest(json_response(data), quota) == [
        Suggestion(
            title="улица Ленина, 1",
            subtitle="Альметьевск",
            formatted_address="Россия, Альметьевск, улица Ленина, 1",
            uri="ymapsbm1://geo?id=1",
            kind="house",
            distance_km=1.5,
        ),
        Suggestion(
            title="Альметьевск",
            subtitle=None,
            formatted_address=None,
            uri="ymapsbm1://geo?id=2",
            kind=None,
            distance_km=None,
        ),
    ]


def test_suggest_without_results(
    quota: DailyRequestCounter,
) -> None:
    assert suggest(json_response({}), quota) == []


def test_suggest_sends_search_window(
    quota: DailyRequestCounter,
) -> None:
    requests: list[httpx.Request] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        requests.append(request)

        return httpx.Response(200, json={})

    suggest(handler, quota)

    params = requests[0].url.params

    assert params["text"] == "Ленина 1"
    assert params["ll"] == "52.3,54.9"
    assert params["ull"] == "52.3,54.9"
    assert params["strict_bounds"] == "1"
    assert params["types"] == "house,street,district,locality"


def test_suggest_rejects_bad_results(
    quota: DailyRequestCounter,
) -> None:
    with pytest.raises(YandexAPIError):
        suggest(json_response({"results": "oops"}), quota)
