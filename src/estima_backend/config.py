from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parents[2]

DB_PATH = ROOT_DIR / "data" / "real_estate.db"
SCHEMA_PATH = ROOT_DIR / "sql" / "schema.sql"
MODELS_DIR = ROOT_DIR / "models"
ANALYSIS_DIR = ROOT_DIR / "analysis"

BASE_URL = "https://www.avito.ru"

load_dotenv(ROOT_DIR / ".env")

YANDEX_GEOSUGGEST_API_KEY = os.getenv(
    "YANDEX_GEOSUGGEST_API_KEY"
)

YANDEX_GEOCODER_API_KEY = os.getenv(
    "YANDEX_GEOCODER_API_KEY"
)

YANDEX_DAILY_REQUEST_LIMIT = 900
YANDEX_QUOTA_TIMEZONE = timezone(timedelta(hours=3))

YANDEX_USAGE_PATH = ROOT_DIR / "data" / "yandex_usage.json"

# Мягкая граница покрытия: за coverage_radius_km модели прогноз ещё даётся,
# но помечается приблизительным; дальше предельного радиуса — отказ.
# Предельный радиус = max(радиус × FACTOR, радиус + MIN_EXTRA_KM).
COVERAGE_SOFT_FACTOR = 1.5
COVERAGE_SOFT_MIN_EXTRA_KM = 5.0


@dataclass(frozen=True)
class MetroStation:
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class CityConfig:
    id: int
    name: str
    lat: float
    lon: float
    metro_stations: tuple[MetroStation, ...] = ()


KAZAN_METRO_STATIONS = (
    MetroStation("Авиастроительная", 55.855852, 49.084498),
    MetroStation("Северный вокзал", 55.841886, 49.081986),
    MetroStation("Яшьлек", 55.828039, 49.082482),
    MetroStation("Козья слобода", 55.817470, 49.098104),
    MetroStation("Кремлёвская", 55.795225, 49.107002),
    MetroStation("Площадь Габдуллы Тукая", 55.785765, 49.124655),
    MetroStation("Суконная слобода", 55.777100, 49.142282),
    MetroStation("Аметьево", 55.765171, 49.166507),
    MetroStation("Горки", 55.760219, 49.190880),
    MetroStation("Проспект Победы", 55.749883, 49.208445),
    MetroStation("Дубравная", 55.743721, 49.218991),
)

CITIES: dict[int, CityConfig] = {
    650210: CityConfig(
        id=650210,
        name="Альметьевск",
        lat=54.900000,
        lon=52.300000,
    ),
    650400: CityConfig(
        id=650400,
        name="Казань",
        lat=55.787000,
        lon=49.122200,
        metro_stations=KAZAN_METRO_STATIONS,
    ),
}

CATEGORY_TYPES: dict[int, str] = {
    24: "apartment",
    25: "house",
    26: "land",
}
