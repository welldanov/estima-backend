import json
from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor

from ..config import MODELS_DIR
from ..ingestion.models import HouseKind, LandType, ListingType
from .features import (
    APARTMENT_CATEGORICAL_FEATURES,
    APARTMENT_FEATURES,
    HOUSE_CATEGORICAL_FEATURES,
    HOUSE_FEATURES,
    LAND_CATEGORICAL_FEATURES,
    LAND_FEATURES,
    build_apartment_features,
    build_house_features,
    build_land_features,
)
from .trainer import predict_price

MODEL_FEATURES: dict[ListingType, tuple[list[str], list[str]]] = {
    ListingType.APARTMENT: (
        APARTMENT_FEATURES,
        APARTMENT_CATEGORICAL_FEATURES,
    ),
    ListingType.HOUSE: (
        HOUSE_FEATURES,
        HOUSE_CATEGORICAL_FEATURES,
    ),
    ListingType.LAND: (
        LAND_FEATURES,
        LAND_CATEGORICAL_FEATURES,
    ),
}


def model_path(
        listing_type: ListingType,
        models_dir: Path = MODELS_DIR,
) -> Path:
    return models_dir / f"{listing_type}_price.cbm"


def metadata_path(
        listing_type: ListingType,
        models_dir: Path = MODELS_DIR,
) -> Path:
    return model_path(listing_type, models_dir).with_suffix(".json")


class RealEstatePredictor:
    def __init__(
            self,
            models_dir: Path = MODELS_DIR,
    ) -> None:
        self.models = {
            listing_type: self._load_model(
                model_path(listing_type, models_dir),
                *MODEL_FEATURES[listing_type],
            )
            for listing_type in ListingType
        }
        self.coverage = {
            listing_type: self._load_coverage(
                metadata_path(listing_type, models_dir),
            )
            for listing_type in ListingType
        }

    @staticmethod
    def _load_coverage(
            path: Path,
    ) -> dict[int, float]:
        if not path.exists():
            raise FileNotFoundError(
                f"Model metadata file not found: {path}"
            )

        metadata = json.loads(
            path.read_text(encoding="utf-8")
        )

        if "coverage_radius_km" not in metadata:
            raise RuntimeError(
                f"Model metadata {path.name} has no coverage radius, "
                "retrain it (scripts/train.py)"
            )

        return {
            int(city_id): float(radius)
            for city_id, radius in metadata["coverage_radius_km"].items()
        }

    @staticmethod
    def _load_model(
            path: Path,
            features: list[str],
            categorical_features: list[str],
    ) -> CatBoostRegressor:
        if not path.exists():
            raise FileNotFoundError(
                f"Model file not found: {path}"
            )

        model = CatBoostRegressor()
        model.load_model(str(path))

        expected_categorical = sorted(
            features.index(feature)
            for feature in categorical_features
        )

        if (
                model.feature_names_ != features
                or sorted(model.get_cat_feature_indices()) != expected_categorical
        ):
            raise RuntimeError(
                f"Model {path.name} was trained on different features, "
                "retrain it (scripts/train.py)"
            )

        return model

    def coverage_radius_km(
            self,
            listing_type: ListingType,
            city_id: int,
    ) -> float | None:
        return self.coverage[listing_type].get(city_id)

    def supported_listing_types(
            self,
            city_id: int,
    ) -> list[ListingType]:
        return [
            listing_type
            for listing_type, radius_by_city in self.coverage.items()
            if city_id in radius_by_city
        ]

    def _predict_price(
            self,
            listing_type: ListingType,
            features: pd.DataFrame,
    ) -> float:
        return float(
            predict_price(
                self.models[listing_type],
                features,
            )[0]
        )

    def predict_apartment(
            self,
            *,
            city_id: int,
            lat: float,
            lon: float,
            area_m2: float,
            rooms: int | None,
            is_studio: bool,
            floor: int,
            floors_total: int,
    ) -> float:
        features = build_apartment_features({
            "city_id": city_id,
            "lat": lat,
            "lon": lon,
            "area_m2": area_m2,
            "rooms": rooms,
            "is_studio": is_studio,
            "floor": floor,
            "floors_total": floors_total,
        })

        return self._predict_price(
            ListingType.APARTMENT,
            features,
        )

    def predict_house(
            self,
            *,
            city_id: int,
            lat: float,
            lon: float,
            house_kind: HouseKind,
            house_area_m2: float,
            land_area_m2: float,
    ) -> float:
        features = build_house_features({
            "city_id": city_id,
            "lat": lat,
            "lon": lon,
            "house_kind": house_kind,
            "house_area_m2": house_area_m2,
            "land_area_m2": land_area_m2,
        })

        return self._predict_price(
            ListingType.HOUSE,
            features,
        )

    def predict_land(
            self,
            *,
            city_id: int,
            lat: float,
            lon: float,
            land_area_m2: float,
            land_type: LandType,
    ) -> float:
        features = build_land_features({
            "city_id": city_id,
            "lat": lat,
            "lon": lon,
            "land_area_m2": land_area_m2,
            "land_type": land_type,
        })

        return self._predict_price(
            ListingType.LAND,
            features,
        )
