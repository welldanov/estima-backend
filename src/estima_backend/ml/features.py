from collections.abc import Callable, Iterable

import numpy as np
import pandas as pd

from ..config import CITIES
from ..ingestion.models import HouseKind, LandType
from ..utils.geo import calculate_distance_km


APARTMENT_FEATURES = [
    "city_id",
    "lat",
    "lon",
    "distance_to_center_km",
    "distance_to_metro_km",
    "area_m2",
    "rooms",
    "is_studio",
    "floor",
    "floors_total",
    "floor_ratio",
    "area_per_room",
    "is_top_floor",
    "is_first_floor",
]

APARTMENT_CATEGORICAL_FEATURES = [
    "city_id",
]

HOUSE_FEATURES = [
    "city_id",
    "lat",
    "lon",
    "distance_to_center_km",
    "distance_to_metro_km",
    "house_kind",
    "house_area_m2",
    "land_area_m2",
    "land_to_house_ratio",
]

HOUSE_CATEGORICAL_FEATURES = [
    "city_id",
    "house_kind",
]

LAND_FEATURES = [
    "city_id",
    "lat",
    "lon",
    "distance_to_center_km",
    "distance_to_metro_km",
    "land_area_m2",
    "land_type",
]

LAND_CATEGORICAL_FEATURES = [
    "city_id",
    "land_type",
]


# COMMON

def _to_frame(
        data: dict | pd.DataFrame,
) -> pd.DataFrame:
    match data:
        case dict():
            return pd.DataFrame([data])
        case pd.DataFrame():
            return data.copy()
        case _:
            raise TypeError(
                "data must be a dict or pandas DataFrame"
            )


def _check_values(
        series: pd.Series,
        allowed: Iterable,
) -> None:
    unknown = set(series) - set(allowed)

    if unknown:
        raise ValueError(
            f"Unknown {series.name} values: {sorted(map(str, unknown))}"
        )


def _add_city_features(
        data: pd.DataFrame,
) -> None:
    _check_values(
        data["city_id"],
        CITIES,
    )

    center_lat = data["city_id"].map(
        {city_id: city.lat for city_id, city in CITIES.items()}
    )
    center_lon = data["city_id"].map(
        {city_id: city.lon for city_id, city in CITIES.items()}
    )

    data["distance_to_center_km"] = calculate_distance_km(
        lat1=data["lat"],
        lon1=data["lon"],
        lat2=center_lat,
        lon2=center_lon,
    )

    data["distance_to_metro_km"] = _nearest_metro_km(data)


def _nearest_metro_km(
        data: pd.DataFrame,
) -> pd.Series:
    result = pd.Series(
        np.nan,
        index=data.index,
    )

    for city_id, city in CITIES.items():
        mask = data["city_id"] == city_id

        if not city.metro_stations or not mask.any():
            continue

        lat = data.loc[mask, "lat"].to_numpy()
        lon = data.loc[mask, "lon"].to_numpy()

        distances = [
            calculate_distance_km(
                lat1=lat,
                lon1=lon,
                lat2=station.lat,
                lon2=station.lon,
            )
            for station in city.metro_stations
        ]

        result[mask] = np.min(
            distances,
            axis=0,
        )

    return result


def _select_features(
        data: pd.DataFrame,
        features: list[str],
        categorical_features: list[str],
) -> pd.DataFrame:
    result = data[features].copy()

    for column in categorical_features:
        result[column] = result[column].astype(str)

    return result


def _prepare(
        df: pd.DataFrame,
        build: Callable[[pd.DataFrame], pd.DataFrame],
) -> tuple[pd.DataFrame, pd.Series]:
    if "price" not in df.columns:
        raise ValueError(
            "Training dataset must contain 'price' column"
        )

    return build(df.copy()), df["price"].copy()


# APARTMENTS

def _build_apartment_features(
        data: pd.DataFrame,
) -> pd.DataFrame:
    _add_city_features(data)

    data["rooms"] = pd.to_numeric(data["rooms"])
    data["is_studio"] = data["is_studio"].astype(int)

    # Те же правила, что CHECK в схеме apartments.
    if (data["is_studio"].astype(bool) != data["rooms"].isna()).any():
        raise ValueError(
            "is_studio must be set exactly when rooms is missing"
        )

    if (data["rooms"] <= 0).any():
        raise ValueError(
            "rooms must be positive"
        )

    data["floor_ratio"] = data["floor"] / data["floors_total"]

    data["area_per_room"] = (
            data["area_m2"]
            / data["rooms"].fillna(1)
    )

    data["is_top_floor"] = (
            data["floor"] == data["floors_total"]
    ).astype(int)

    data["is_first_floor"] = (
            data["floor"] == 1
    ).astype(int)

    return _select_features(
        data,
        APARTMENT_FEATURES,
        APARTMENT_CATEGORICAL_FEATURES,
    )


def prepare_apartment_features(
        df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    return _prepare(
        df,
        _build_apartment_features,
    )


def build_apartment_features(
        data: dict | pd.DataFrame,
) -> pd.DataFrame:
    return _build_apartment_features(
        _to_frame(data)
    )


# HOUSES

def _build_house_features(
        data: pd.DataFrame,
) -> pd.DataFrame:
    _add_city_features(data)

    _check_values(
        data["house_kind"],
        HouseKind,
    )

    data["land_to_house_ratio"] = (
            data["land_area_m2"]
            / data["house_area_m2"]
    )

    return _select_features(
        data,
        HOUSE_FEATURES,
        HOUSE_CATEGORICAL_FEATURES,
    )


def prepare_house_features(
        df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    return _prepare(
        df,
        _build_house_features,
    )


def build_house_features(
        data: dict | pd.DataFrame,
) -> pd.DataFrame:
    return _build_house_features(
        _to_frame(data)
    )


# LANDS

def _build_land_features(
        data: pd.DataFrame,
) -> pd.DataFrame:
    _add_city_features(data)

    _check_values(
        data["land_type"],
        LandType,
    )

    return _select_features(
        data,
        LAND_FEATURES,
        LAND_CATEGORICAL_FEATURES,
    )


def prepare_land_features(
        df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    return _prepare(
        df,
        _build_land_features,
    )


def build_land_features(
        data: dict | pd.DataFrame,
) -> pd.DataFrame:
    return _build_land_features(
        _to_frame(data)
    )
