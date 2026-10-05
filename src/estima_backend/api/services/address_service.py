from ..providers.yandex import YandexSuggest
from ..schemas.address import AddressSuggestion
from .city_service import CityService


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

        suggestions = await self.suggest.suggest(
            text=query,
            lat=city.lat,
            lon=city.lon,
            radius_km=self.cities.search_radius_km(city),
        )

        return [
            AddressSuggestion.model_validate(suggestion)
            for suggestion in suggestions
        ]
