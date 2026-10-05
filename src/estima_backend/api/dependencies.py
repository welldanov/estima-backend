from typing import Annotated

from fastapi import Depends, Request

from .providers.quota import DailyRequestCounter
from .services.address_service import AddressService
from .services.city_service import CityService
from .services.prediction_service import PredictionService


def get_city_service(
        request: Request,
) -> CityService:
    return request.app.state.city_service


def get_address_service(
        request: Request,
) -> AddressService:
    return request.app.state.address_service


def get_prediction_service(
        request: Request,
) -> PredictionService:
    return request.app.state.prediction_service


def get_yandex_quota(
        request: Request,
) -> DailyRequestCounter:
    return request.app.state.yandex_quota


CityServiceDep = Annotated[CityService, Depends(get_city_service)]
AddressServiceDep = Annotated[AddressService, Depends(get_address_service)]
PredictionServiceDep = Annotated[PredictionService, Depends(get_prediction_service)]
YandexQuotaDep = Annotated[DailyRequestCounter, Depends(get_yandex_quota)]
