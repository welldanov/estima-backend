import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import (
    YANDEX_DAILY_REQUEST_LIMIT,
    YANDEX_QUOTA_TIMEZONE,
    YANDEX_USAGE_PATH,
)
from ..ml.predictor import RealEstatePredictor
from .errors import ServiceError
from .providers.quota import (
    DailyQuotaExceededError,
    DailyRequestCounter,
)
from .providers.yandex import (
    GEOCODER_API_NAME,
    GEOSUGGEST_API_NAME,
    YandexAPIError,
    YandexGeocoder,
    YandexSuggest,
)
from .routers import (
    addresses,
    cities,
    health,
    predictions,
)
from .services.address_service import AddressService
from .services.city_service import CityService
from .services.prediction_service import PredictionService

logger = logging.getLogger(__name__)

# httpx пишет в INFO полный URL запроса, а в нём ключ Yandex.
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(
        app: FastAPI,
):
    predictor = RealEstatePredictor()
    city_service = CityService(predictor)

    yandex_quota = DailyRequestCounter(
        storage_path=YANDEX_USAGE_PATH,
        limits={
            GEOCODER_API_NAME: YANDEX_DAILY_REQUEST_LIMIT,
            GEOSUGGEST_API_NAME: YANDEX_DAILY_REQUEST_LIMIT,
        },
        tz=YANDEX_QUOTA_TIMEZONE,
    )

    async with httpx.AsyncClient() as http_client:
        app.state.yandex_quota = yandex_quota
        app.state.city_service = city_service
        app.state.address_service = AddressService(
            suggest=YandexSuggest(
                client=http_client,
                quota=yandex_quota,
            ),
            cities=city_service,
        )
        app.state.prediction_service = PredictionService(
            predictor=predictor,
            geocoder=YandexGeocoder(
                client=http_client,
                quota=yandex_quota,
            ),
            cities=city_service,
        )

        yield


app = FastAPI(
    title="Estima API",
    description="API для прогнозирования стоимости объектов недвижимости.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(ServiceError)
async def service_error_handler(
        request: Request,
        exc: ServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
        },
    )


@app.exception_handler(YandexAPIError)
async def yandex_api_error_handler(
        request: Request,
        exc: YandexAPIError,
) -> JSONResponse:
    logger.warning("Yandex API error: %s", exc)

    return JSONResponse(
        status_code=502,
        content={
            "detail": "Сервис адресов временно недоступен. Попробуйте позже.",
        },
    )


@app.exception_handler(DailyQuotaExceededError)
async def daily_quota_exceeded_handler(
        request: Request,
        exc: DailyQuotaExceededError,
) -> JSONResponse:
    logger.warning("%s", exc)

    return JSONResponse(
        status_code=503,
        content={
            "detail": "Дневной лимит запросов к сервису адресов исчерпан. Попробуйте завтра.",
        },
        headers={
            "Retry-After": str(exc.retry_after),
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(cities.router)
app.include_router(addresses.router)
app.include_router(predictions.router)
