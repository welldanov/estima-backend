from ...config import CITIES, CityConfig
from ...ingestion.models import ListingType
from ...ml.predictor import RealEstatePredictor
from ..errors import CityNotFoundError, PropertyTypeNotSupportedError
from ..schemas.city import CityResponse


class CityService:
    """Города, для которых есть хотя бы одна модель."""

    def __init__(
            self,
            predictor: RealEstatePredictor,
    ) -> None:
        self.predictor = predictor

    def list_cities(self) -> list[CityResponse]:
        return [
            CityResponse(
                id=city.id,
                name=city.name,
                property_types=property_types,
            )
            for city in CITIES.values()
            if (property_types := self.predictor.supported_listing_types(city.id))
        ]

    def get_city(
            self,
            city_id: int,
    ) -> CityConfig:
        city = CITIES.get(city_id)

        if city is None or not self.predictor.supported_listing_types(city_id):
            raise CityNotFoundError()

        return city

    def search_radius_km(
            self,
            city: CityConfig,
            listing_type: ListingType | None = None,
    ) -> float:
        """Предельный радиус покрытия для типа, без типа — максимум по моделям города."""
        if listing_type is not None:
            limit_km = self.predictor.coverage_limit_km(
                listing_type,
                city.id,
            )

            if limit_km is None:
                raise PropertyTypeNotSupportedError()

            return limit_km

        return max(
            self.predictor.coverage_limit_km(listing_type, city.id)
            for listing_type in self.predictor.supported_listing_types(city.id)
        )
