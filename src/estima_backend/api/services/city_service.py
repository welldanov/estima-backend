from ...config import CITIES, CityConfig
from ...ml.predictor import RealEstatePredictor
from ..errors import CityNotFoundError, PropertyTypeNotSupportedError
from ..schemas.city import CityResponse


class CityService:
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
    ) -> float:
        limits = [
            limit_km
            for supported_type in self.predictor.supported_listing_types(city.id)
            if (
                limit_km := self.predictor.coverage_limit_km(
                    supported_type,
                    city.id,
                )
            )
            is not None
        ]

        if not limits:
            raise PropertyTypeNotSupportedError()

        return max(limits)
