from ...config import CityConfig
from ..providers.yandex import Suggestion, YandexSuggest
from ..schemas.address import AddressSuggestion
from .city_service import CityService

MAX_SUGGESTIONS = 7


class AddressService:
    def __init__(
        self,
        *,
        suggest: YandexSuggest,
        cities: CityService,
    ) -> None:
        self.suggest = suggest
        self.cities = cities

    async def search(
        self,
        *,
        city_id: int,
        query: str,
    ) -> list[AddressSuggestion]:
        city = self.cities.get_city(city_id)

        radius_km = self.cities.search_radius_km(
            city,
        )

        suggestions = await self._suggest_within_radius(
            text=query,
            city=city,
            radius_km=radius_km,
        )

        if not suggestions and city.name.casefold() not in query.casefold():
            suggestions = await self._suggest_within_radius(
                text=f"{city.name} {query}",
                city=city,
                radius_km=radius_km,
            )

        return [AddressSuggestion.model_validate(suggestion) for suggestion in suggestions][
            :MAX_SUGGESTIONS
        ]

    async def _suggest_within_radius(
        self,
        *,
        text: str,
        city: CityConfig,
        radius_km: float,
    ) -> list[Suggestion]:
        suggestions = await self.suggest.suggest(
            text=text,
            lat=city.lat,
            lon=city.lon,
            radius_km=radius_km,
        )

        return [
            suggestion
            for suggestion in suggestions
            if suggestion.distance_km is None or suggestion.distance_km <= radius_km
        ]
