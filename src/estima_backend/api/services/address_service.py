from ...ingestion.models import ListingType
from ..providers.yandex import YandexSuggest
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
            listing_type: ListingType | None = None,
    ) -> list[AddressSuggestion]:
        city = self.cities.get_city(city_id)

        radius_km = self.cities.search_radius_km(
            city,
            listing_type,
        )

        suggestions = await self.suggest.suggest(
            text=query,
            lat=city.lat,
            lon=city.lon,
            radius_km=radius_km,
        )

        # Без distance подсказку не отбрасываем: дальность всё равно проверит прогноз.
        return [
            AddressSuggestion.model_validate(suggestion)
            for suggestion in suggestions
            if suggestion.distance_km is None or suggestion.distance_km <= radius_km
        ][:MAX_SUGGESTIONS]
