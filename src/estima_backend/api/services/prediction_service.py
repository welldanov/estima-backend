from typing import assert_never

from ...ingestion.models import ListingType
from ...ml.predictor import RealEstatePredictor
from ...utils.geo import calculate_distance_km
from ..errors import (
    AddressNotFoundError,
    AddressNotPreciseError,
    AddressOutOfCoverageError,
    PropertyTypeNotSupportedError,
)
from ..providers.yandex import GeocodedAddress, YandexGeocoder
from ..schemas.prediction import (
    ApartmentPredictionRequest,
    ApproximateReason,
    HousePredictionRequest,
    LandPredictionRequest,
    PredictionAddress,
    PredictionRequest,
    PredictionResponse,
)
from .city_service import CityService

# У домов и участков в сёлах и СНТ часто нет номера,
# поэтому для них хватает улицы или населённого пункта.
SETTLEMENT_ADDRESS_KINDS = frozenset({
    "house",
    "street",
    "district",
    "locality",
})


class PredictionService:
    def __init__(
            self,
            *,
            predictor: RealEstatePredictor,
            geocoder: YandexGeocoder,
            cities: CityService,
    ) -> None:
        self.predictor = predictor
        self.geocoder = geocoder
        self.cities = cities

    async def predict(
            self,
            request: PredictionRequest,
    ) -> PredictionResponse:
        city = self.cities.get_city(request.city_id)

        radius_km = self.predictor.coverage_radius_km(
            request.property_type,
            city.id,
        )
        limit_km = self.predictor.coverage_limit_km(
            request.property_type,
            city.id,
        )

        if radius_km is None or limit_km is None:
            raise PropertyTypeNotSupportedError()

        address = await self.geocoder.geocode_uri(
            request.address.uri,
        )

        if address is None:
            raise AddressNotFoundError()

        check_address_kind(
            request.property_type,
            address.kind,
        )

        distance_to_center_km = float(
            calculate_distance_km(
                lat1=city.lat,
                lon1=city.lon,
                lat2=address.lat,
                lon2=address.lon,
            )
        )

        if distance_to_center_km > limit_km:
            raise AddressOutOfCoverageError()

        approximate_reasons: list[ApproximateReason] = []

        if distance_to_center_km > radius_km:
            approximate_reasons.append(ApproximateReason.FAR_FROM_CENTER)

        # Для квартиры адрес без дома отклоняется в check_address_kind.
        if address.kind != "house":
            approximate_reasons.append(ApproximateReason.ADDRESS_WITHOUT_HOUSE)

        return PredictionResponse(
            property_type=request.property_type,
            predicted_price=self._predict_price(
                request,
                address,
            ),
            approximate_reasons=approximate_reasons,
            address=PredictionAddress(
                formatted_address=address.formatted_address,
                kind=address.kind,
                lat=address.lat,
                lon=address.lon,
                distance_to_center_km=round(distance_to_center_km, 2),
            ),
        )

    def _predict_price(
            self,
            request: PredictionRequest,
            address: GeocodedAddress,
    ) -> float:
        match request:
            case ApartmentPredictionRequest():
                return self.predictor.predict_apartment(
                    city_id=request.city_id,
                    lat=address.lat,
                    lon=address.lon,
                    area_m2=request.area_m2,
                    rooms=request.rooms,
                    is_studio=request.is_studio,
                    floor=request.floor,
                    floors_total=request.floors_total,
                )

            case HousePredictionRequest():
                return self.predictor.predict_house(
                    city_id=request.city_id,
                    lat=address.lat,
                    lon=address.lon,
                    house_kind=request.house_kind,
                    house_area_m2=request.house_area_m2,
                    land_area_m2=request.land_area_m2,
                )

            case LandPredictionRequest():
                return self.predictor.predict_land(
                    city_id=request.city_id,
                    lat=address.lat,
                    lon=address.lon,
                    land_area_m2=request.land_area_m2,
                    land_type=request.land_type,
                )

            case _:
                assert_never(request)


def check_address_kind(
        property_type: ListingType,
        kind: str,
) -> None:
    match property_type:
        case ListingType.APARTMENT if kind != "house":
            raise AddressNotPreciseError(
                "Для квартиры выберите адрес с номером дома."
            )

        case ListingType.HOUSE | ListingType.LAND if kind not in SETTLEMENT_ADDRESS_KINDS:
            raise AddressNotPreciseError(
                "Выберите дом, улицу или населённый пункт."
            )
