from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ListingType(StrEnum):
    APARTMENT = "apartment"
    HOUSE = "house"
    LAND = "land"


class HouseKind(StrEnum):
    HOUSE = "house"
    DACHA = "dacha"
    COTTAGE = "cottage"
    TOWNHOUSE = "townhouse"


class LandType(StrEnum):
    IZHS = "izhs"
    SNT_DNP = "snt_dnp"
    LPH = "lph"
    INDUSTRIAL = "industrial"


class SkipRecord(Exception):
    """Запись не подходит для импорта (не ошибка кода)."""


@dataclass(frozen=True)
class ListingData:
    id: int
    city_id: int
    property_type: ListingType

    title: str
    description: str
    price: int

    address: str

    lat: float
    lon: float

    url: str
    seen_at: datetime


@dataclass(frozen=True)
class ApartmentData:
    area_m2: float
    rooms: int | None
    is_studio: bool
    floor: int
    floors_total: int


@dataclass(frozen=True)
class HouseData:
    house_kind: HouseKind
    house_area_m2: float
    land_area_m2: float


@dataclass(frozen=True)
class LandData:
    land_area_m2: float
    land_type: LandType


@dataclass(frozen=True)
class NormalizedListing:
    listing: ListingData
    details: ApartmentData | HouseData | LandData
