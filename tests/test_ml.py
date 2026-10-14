import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from estima_backend.config import CITIES, MODELS_DIR
from estima_backend.ingestion.models import HouseKind, LandType, ListingType
from estima_backend.ml.cleaning import drop_duplicate_listings, drop_price_outliers
from estima_backend.ml.evaluator import calculate_metrics
from estima_backend.ml.features import (
    APARTMENT_FEATURES,
    HOUSE_FEATURES,
    LAND_FEATURES,
    build_apartment_features,
    build_house_features,
    build_land_features,
    prepare_apartment_features,
)
from estima_backend.ml.predictor import RealEstatePredictor, metadata_path
from estima_backend.ml.split import building_groups, split_by_groups
from estima_backend.utils.geo import calculate_distance_km

ALMETYEVSK = CITIES[650210]
KAZAN = CITIES[650400]


def apartment(
    **overrides: object,
) -> dict[str, object]:
    data: dict[str, object] = {
        "city_id": ALMETYEVSK.id,
        "lat": 54.91,
        "lon": 52.33,
        "area_m2": 45.0,
        "rooms": 2,
        "is_studio": False,
        "floor": 3,
        "floors_total": 9,
    }
    data.update(overrides)

    return data


# GEO


def test_distance_between_same_points_is_zero() -> None:
    assert calculate_distance_km(lat1=55.0, lon1=49.0, lat2=55.0, lon2=49.0) == 0


def test_distance_one_degree_of_latitude() -> None:
    assert calculate_distance_km(lat1=55.0, lon1=49.0, lat2=56.0, lon2=49.0) == pytest.approx(
        111.2, abs=0.1
    )


def test_distance_kazan_to_almetyevsk() -> None:
    distance = calculate_distance_km(
        lat1=KAZAN.lat,
        lon1=KAZAN.lon,
        lat2=ALMETYEVSK.lat,
        lon2=ALMETYEVSK.lon,
    )

    assert distance == pytest.approx(220, abs=15)


def test_distance_is_vectorized() -> None:
    distances = calculate_distance_km(
        lat1=np.array([55.0, 55.0]),
        lon1=np.array([49.0, 49.0]),
        lat2=np.array([55.0, 56.0]),
        lon2=np.array([49.0, 49.0]),
    )

    assert distances == pytest.approx([0.0, 111.2], abs=0.1)


# FEATURES


def test_build_apartment_features() -> None:
    features = build_apartment_features(apartment(floor=9))

    assert list(features.columns) == APARTMENT_FEATURES

    row = features.iloc[0]

    assert row["city_id"] == str(ALMETYEVSK.id)
    assert row["distance_to_center_km"] == pytest.approx(2.2, abs=0.2)
    assert np.isnan(row["distance_to_metro_km"])
    assert row["floor_ratio"] == 1
    assert row["area_per_room"] == 22.5
    assert row["is_top_floor"] == 1
    assert row["is_first_floor"] == 0


def test_build_apartment_features_for_studio() -> None:
    row = build_apartment_features(apartment(rooms=None, is_studio=True, area_m2=25.0)).iloc[0]

    assert row["is_studio"] == 1
    assert row["area_per_room"] == 25.0


def test_build_apartment_features_metro_distance_in_kazan() -> None:
    tukay = next(station for station in KAZAN.metro_stations if "Тукая" in station.name)

    row = build_apartment_features(
        apartment(
            city_id=KAZAN.id,
            lat=tukay.lat,
            lon=tukay.lon,
        )
    ).iloc[0]

    assert row["distance_to_metro_km"] == pytest.approx(0, abs=0.01)


@pytest.mark.parametrize(
    "overrides",
    [
        {"city_id": 1},
        {"rooms": None, "is_studio": False},
        {"rooms": 2, "is_studio": True},
    ],
)
def test_build_apartment_features_rejects_invalid_data(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        build_apartment_features(apartment(**overrides))


def test_build_house_features() -> None:
    features = build_house_features(
        {
            "city_id": ALMETYEVSK.id,
            "lat": 54.91,
            "lon": 52.33,
            "house_kind": HouseKind.COTTAGE,
            "house_area_m2": 150.0,
            "land_area_m2": 600.0,
        }
    )

    assert list(features.columns) == HOUSE_FEATURES
    assert features.iloc[0]["land_to_house_ratio"] == 4
    assert features.iloc[0]["house_kind"] == "cottage"


def test_build_house_features_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        build_house_features(
            {
                "city_id": ALMETYEVSK.id,
                "lat": 54.91,
                "lon": 52.33,
                "house_kind": "castle",
                "house_area_m2": 150.0,
                "land_area_m2": 600.0,
            }
        )


def test_build_land_features() -> None:
    features = build_land_features(
        {
            "city_id": ALMETYEVSK.id,
            "lat": 54.91,
            "lon": 52.33,
            "land_area_m2": 600.0,
            "land_type": LandType.IZHS,
        }
    )

    assert list(features.columns) == LAND_FEATURES
    assert features.iloc[0]["land_type"] == "izhs"


def test_prepare_features_matches_inference() -> None:
    df = pd.DataFrame([apartment(price=5_000_000), apartment(price=7_000_000, area_m2=60.0)])

    X, y = prepare_apartment_features(df)

    assert list(y) == [5_000_000, 7_000_000]
    pd.testing.assert_frame_equal(
        X.iloc[[1]].reset_index(drop=True),
        build_apartment_features(apartment(area_m2=60.0)),
    )


def test_prepare_features_requires_price() -> None:
    with pytest.raises(ValueError):
        prepare_apartment_features(pd.DataFrame([apartment()]))


# CLEANING AND SPLIT


def test_drop_duplicate_listings_keeps_latest() -> None:
    df = pd.DataFrame(
        {
            "address": ["Ленина, 1", "Ленина, 1", "Мира, 2"],
            "area_m2": [45.0, 45.0, 45.0],
            "price": [5_000_000, 4_800_000, 6_000_000],
            "last_seen_at": ["2026-09-14", "2026-09-07", "2026-09-07"],
        }
    )

    result = drop_duplicate_listings(df, ["address", "area_m2"])

    assert list(result["price"]) == [5_000_000, 6_000_000]


def test_drop_price_outliers_is_per_city() -> None:
    cheap_city = [100_000 + i for i in range(100)]
    expensive_city = [1_000_000 + i for i in range(100)]
    df = pd.DataFrame(
        {
            "city_id": [1] * 100 + [2] * 100,
            "price": cheap_city + expensive_city,
            "area_m2": [1.0] * 200,
        }
    )

    result = drop_price_outliers(df, "area_m2", 0.05)

    assert len(result) == 180
    assert result.groupby("city_id").size().to_dict() == {1: 90, 2: 90}


def test_split_by_groups_keeps_building_together() -> None:
    df = pd.DataFrame(
        {
            "lat": [54.90001, 54.90002, 54.91, 54.92, 54.93, 54.94] * 5,
            "lon": [52.30001, 52.30002, 52.31, 52.32, 52.33, 52.34] * 5,
        }
    )
    groups = building_groups(df)

    train_index, test_index = split_by_groups(groups, test_size=0.4, random_state=42)

    assert set(groups[train_index]).isdisjoint(groups[test_index])
    assert len(train_index) + len(test_index) == len(df)
    assert groups.nunique() == 5


def test_calculate_metrics() -> None:
    metrics = calculate_metrics(
        pd.Series([100.0, 200.0]),
        np.array([110.0, 180.0]),
    )

    assert metrics["mae"] == 15
    assert metrics["median_absolute_percentage_error"] == 10
    assert metrics["mean_absolute_percentage_error"] == 10


# PREDICTOR


def test_predictor_supported_listing_types(
    predictor: RealEstatePredictor,
) -> None:
    assert set(predictor.supported_listing_types(ALMETYEVSK.id)) == set(ListingType)
    assert predictor.supported_listing_types(KAZAN.id) == [ListingType.APARTMENT]
    assert predictor.supported_listing_types(1) == []


@pytest.mark.parametrize(
    ("radius_km", "limit_km"),
    [
        (6.0, 11.0),
        (30.0, 45.0),
    ],
)
def test_coverage_limit_km(
    predictor: RealEstatePredictor,
    monkeypatch: pytest.MonkeyPatch,
    radius_km: float,
    limit_km: float,
) -> None:
    monkeypatch.setitem(predictor.coverage[ListingType.APARTMENT], ALMETYEVSK.id, radius_km)

    assert predictor.coverage_limit_km(ListingType.APARTMENT, ALMETYEVSK.id) == limit_km


def test_coverage_limit_km_without_model(
    predictor: RealEstatePredictor,
) -> None:
    assert predictor.coverage_limit_km(ListingType.HOUSE, KAZAN.id) is None


def test_predict_apartment_is_reasonable(
    predictor: RealEstatePredictor,
) -> None:
    small = predictor.predict_apartment(**apartment(area_m2=35.0, rooms=1))
    large = predictor.predict_apartment(**apartment(area_m2=90.0, rooms=3))

    assert 1_000_000 < small < large < 50_000_000


def test_predict_house_and_land(
    predictor: RealEstatePredictor,
) -> None:
    house = predictor.predict_house(
        city_id=ALMETYEVSK.id,
        lat=54.91,
        lon=52.33,
        house_kind=HouseKind.HOUSE,
        house_area_m2=120.0,
        land_area_m2=800.0,
    )
    land = predictor.predict_land(
        city_id=ALMETYEVSK.id,
        lat=54.91,
        lon=52.33,
        land_area_m2=800.0,
        land_type=LandType.IZHS,
    )

    assert house > 0
    assert land > 0


def copy_models(
    target: Path,
) -> Path:
    shutil.copytree(MODELS_DIR, target)

    return target


def test_predictor_requires_coverage_in_metadata(
    tmp_path: Path,
) -> None:
    models_dir = copy_models(tmp_path / "models")
    path = metadata_path(ListingType.LAND, models_dir)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    del metadata["coverage_radius_km"]
    path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(RuntimeError):
        RealEstatePredictor(models_dir)


def test_predictor_rejects_model_with_other_features(
    tmp_path: Path,
) -> None:
    models_dir = copy_models(tmp_path / "models")
    shutil.copy(
        models_dir / "land_price.cbm",
        models_dir / "house_price.cbm",
    )

    with pytest.raises(RuntimeError):
        RealEstatePredictor(models_dir)


def test_predictor_requires_model_file(
    tmp_path: Path,
) -> None:
    models_dir = copy_models(tmp_path / "models")
    (models_dir / "apartment_price.cbm").unlink()

    with pytest.raises(FileNotFoundError):
        RealEstatePredictor(models_dir)
