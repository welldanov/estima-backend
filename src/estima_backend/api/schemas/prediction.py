from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...ingestion.models import HouseKind, LandType, ListingType
from ...ingestion.titles import (
    MAX_APARTMENT_AREA_M2,
    MIN_APARTMENT_AREA_M2,
    MIN_AREA_PER_ROOM_M2,
)


class AddressSelection(BaseModel):
    uri: str = Field(
        max_length=2000,
        pattern=r"^ymapsbm1://",
        description="uri из подсказки /api/addresses/search",
    )


class BasePredictionRequest(BaseModel):
    city_id: int = Field(
        gt=0,
    )

    address: AddressSelection


class ApartmentPredictionRequest(
    BasePredictionRequest
):
    property_type: Literal[ListingType.APARTMENT]

    area_m2: float = Field(
        ge=MIN_APARTMENT_AREA_M2,
        le=MAX_APARTMENT_AREA_M2,
    )

    rooms: int | None = Field(
        default=None,
        ge=1,
        le=9,
        description="Не указывается для студий",
    )

    is_studio: bool = False

    floor: int = Field(
        ge=1,
        le=100,
    )

    floors_total: int = Field(
        ge=1,
        le=100,
    )

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        if self.is_studio != (self.rooms is None):
            raise ValueError(
                "Число комнат указывается для всех квартир, кроме студий."
            )

        if self.floor > self.floors_total:
            raise ValueError(
                "Этаж не может быть больше этажности дома."
            )

        if (
                self.rooms is not None
                and self.area_m2 / self.rooms < MIN_AREA_PER_ROOM_M2
        ):
            raise ValueError(
                "Площадь слишком мала для такого числа комнат."
            )

        return self


class HousePredictionRequest(
    BasePredictionRequest
):
    property_type: Literal[ListingType.HOUSE]

    house_kind: HouseKind

    house_area_m2: float = Field(
        gt=0,
        le=5000,
    )

    land_area_m2: float = Field(
        gt=0,
        le=100000,
    )


class LandPredictionRequest(
    BasePredictionRequest
):
    property_type: Literal[ListingType.LAND]

    land_area_m2: float = Field(
        gt=0,
        le=100000,
    )

    land_type: LandType


PredictionRequest = Annotated[
    (
            ApartmentPredictionRequest
            | HousePredictionRequest
            | LandPredictionRequest
    ),
    Field(
        discriminator="property_type",
    ),
]


class PredictionAddress(BaseModel):
    formatted_address: str

    kind: str = Field(
        description="Точность адреса по Yandex: house, street, district, locality",
    )

    lat: float
    lon: float

    distance_to_center_km: float


class PredictionResponse(BaseModel):
    property_type: ListingType

    predicted_price: float

    address: PredictionAddress
