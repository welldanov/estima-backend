from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PriceDetailedSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: int = Field(gt=0)


class CategorySchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = Field(min_length=1)


class LocationSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = Field(min_length=1)


class CoordsSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class GeoSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    formattedAddress: str


class AvitoListingSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)

    title: str = Field(min_length=1)

    description: str

    category: CategorySchema
    location: LocationSchema

    priceDetailed: PriceDetailedSchema

    geo: GeoSchema
    coords: CoordsSchema

    urlPath: str = Field(min_length=1)

    parsed_at: datetime


def validate_record(
        record: dict,
) -> AvitoListingSchema:
    return AvitoListingSchema.model_validate(record)


def validate_records(
        records: list[dict],
) -> list[AvitoListingSchema]:
    return [
        validate_record(record)
        for record in records
    ]
