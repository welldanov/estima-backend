from dataclasses import dataclass
from math import cos, radians
from typing import Any

import httpx

from ...config import YANDEX_GEOCODER_API_KEY, YANDEX_GEOSUGGEST_API_KEY
from .quota import DailyRequestCounter

GEOCODER_API_NAME = "geocoder"
GEOSUGGEST_API_NAME = "geosuggest"

KM_PER_DEGREE_LAT = 111.32

# Без стран, регионов, водоёмов, дорог и т.п.: по ним нельзя оценить объект.
SUGGEST_KINDS = (
    "house",
    "street",
    "district",
    "locality",
)
SUGGEST_TYPES = ",".join(SUGGEST_KINDS)


class YandexAPIError(Exception):
    """Ошибка взаимодействия с Yandex Maps API."""


@dataclass(frozen=True)
class GeocodedAddress:
    formatted_address: str
    # house, street, district, locality, ...
    kind: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Suggestion:
    title: str
    subtitle: str | None
    formatted_address: str | None
    uri: str
    # Тип объекта из tags: house, street, district, locality
    kind: str | None
    # Расстояние от точки ul (центр города) по данным Yandex
    distance_km: float | None


class _YandexClient:
    def __init__(
            self,
            *,
            api_name: str,
            url: str,
            timeout: float,
            client: httpx.AsyncClient,
            quota: DailyRequestCounter,
            api_key: str | None,
    ) -> None:
        self.api_name = api_name
        self.url = url
        self.timeout = timeout
        self.client = client
        self.quota = quota
        self.api_key = api_key

    async def get_json(
            self,
            params: dict[str, str | int],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise YandexAPIError(
                f"API key for Yandex {self.api_name} is not configured"
            )

        await self.quota.acquire(self.api_name)

        try:
            response = await self.client.get(
                self.url,
                params={
                    "apikey": self.api_key,
                    **params,
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            # str(exc) не выводится: в нём может оказаться URL с ключом.
            raise YandexAPIError(
                f"Failed to connect to Yandex {self.api_name}: "
                f"{type(exc).__name__}"
            ) from exc

        if response.is_error:
            raise YandexAPIError(
                f"Yandex {self.api_name} returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise YandexAPIError(
                f"Yandex {self.api_name} returned invalid JSON"
            ) from exc

        if not isinstance(data, dict):
            raise YandexAPIError(
                f"Yandex {self.api_name} returned unexpected JSON"
            )

        return data


def _extract(
        data: Any,
        *path: str | int,
) -> Any:
    try:
        for key in path:
            data = data[key]
    except (KeyError, IndexError, TypeError) as exc:
        raise YandexAPIError(
            f"Unexpected Yandex response: missing {'/'.join(map(str, path))}"
        ) from exc

    return data


class YandexGeocoder:
    def __init__(
            self,
            *,
            client: httpx.AsyncClient,
            quota: DailyRequestCounter,
            api_key: str | None = YANDEX_GEOCODER_API_KEY,
    ) -> None:
        self._client = _YandexClient(
            api_name=GEOCODER_API_NAME,
            url="https://geocode-maps.yandex.ru/v1/",
            timeout=10.0,
            client=client,
            quota=quota,
            api_key=api_key,
        )

    async def geocode_uri(
            self,
            uri: str,
    ) -> GeocodedAddress | None:
        data = await self._client.get_json({
            "uri": uri,
            "format": "json",
            "lang": "ru_RU",
        })

        members = _extract(
            data,
            "response",
            "GeoObjectCollection",
            "featureMember",
        )

        if not members:
            return None

        geo_object = _extract(members, 0, "GeoObject")
        metadata = _extract(geo_object, "metaDataProperty", "GeocoderMetaData")
        position = _extract(geo_object, "Point", "pos")

        try:
            lon, lat = map(float, position.split())
        except (AttributeError, ValueError) as exc:
            raise YandexAPIError(
                "Invalid coordinates in Yandex geocoder response"
            ) from exc

        return GeocodedAddress(
            formatted_address=str(_extract(metadata, "Address", "formatted")),
            kind=str(_extract(metadata, "kind")),
            lat=lat,
            lon=lon,
        )


class YandexSuggest:
    def __init__(
            self,
            *,
            client: httpx.AsyncClient,
            quota: DailyRequestCounter,
            api_key: str | None = YANDEX_GEOSUGGEST_API_KEY,
    ) -> None:
        self._client = _YandexClient(
            api_name=GEOSUGGEST_API_NAME,
            url="https://suggest-maps.yandex.ru/v1/suggest",
            timeout=5.0,
            client=client,
            quota=quota,
            api_key=api_key,
        )

    async def suggest(
            self,
            *,
            text: str,
            lat: float,
            lon: float,
            radius_km: float,
            results: int = 10,
    ) -> list[Suggestion]:
        lat_span = 2 * radius_km / KM_PER_DEGREE_LAT
        lon_span = lat_span / cos(radians(lat))

        data = await self._client.get_json({
            "text": text,
            "lang": "ru",
            "types": SUGGEST_TYPES,
            "attrs": "uri",
            "print_address": 1,
            "results": min(results, 10),
            "ll": f"{lon},{lat}",
            "spn": f"{lon_span:.4f},{lat_span:.4f}",
            # Окно Yandex соблюдает нестрого: если внутри ничего не нашлось,
            # отдаёт результаты из других городов. Поэтому дополнительно
            # фильтруем по distance, которое считается от ul.
            "strict_bounds": 1,
            "ul": f"{lon},{lat}",
            "countries": "ru",
            "highlight": 0,
        })

        # Если ничего не найдено, Yandex не возвращает results.
        items = data.get("results", [])

        if not isinstance(items, list):
            raise YandexAPIError(
                "Unexpected Yandex geosuggest response: results is not a list"
            )

        return [
            suggestion
            for item in items
            if (suggestion := _parse_suggestion(item)) is not None
        ]


def _text(
        value: Any,
) -> str | None:
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return value["text"].strip() or None

    return None


def _parse_suggestion(
        item: Any,
) -> Suggestion | None:
    if not isinstance(item, dict):
        return None

    title = _text(item.get("title"))
    uri = item.get("uri")

    if title is None or not isinstance(uri, str) or not uri:
        return None

    address = item.get("address")
    formatted_address = (
        address.get("formatted_address")
        if isinstance(address, dict)
        else None
    )

    distance = item.get("distance")
    distance_m = (
        distance.get("value")
        if isinstance(distance, dict)
        else None
    )

    tags = item.get("tags")
    kinds = [
        tag
        for tag in (tags if isinstance(tags, list) else [])
        if tag in SUGGEST_KINDS
    ]

    return Suggestion(
        title=title,
        subtitle=_text(item.get("subtitle")),
        formatted_address=(
            formatted_address
            if isinstance(formatted_address, str)
            else None
        ),
        uri=uri,
        kind=kinds[0] if kinds else None,
        distance_km=(
            distance_m / 1000
            if isinstance(distance_m, int | float)
            else None
        ),
    )
