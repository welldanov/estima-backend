import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from estima_backend.config import ANALYSIS_DIR, DB_PATH
from estima_backend.database.connection import create_connection
from estima_backend.ingestion.models import ListingType
from estima_backend.ml.artifacts import save_metadata, save_model
from estima_backend.ml.cleaning import (
    drop_duplicate_listings,
    drop_price_outliers,
)
from estima_backend.ml.config import TrainingConfig
from estima_backend.ml.dataset import (
    load_apartments,
    load_houses,
    load_lands,
)
from estima_backend.ml.evaluator import (
    calculate_metrics,
    print_metrics,
)
from estima_backend.ml.features import (
    prepare_apartment_features,
    prepare_house_features,
    prepare_land_features,
)
from estima_backend.ml.predictor import (
    MODEL_FEATURES,
    metadata_path,
    model_path,
)
from estima_backend.ml.split import building_groups, split_by_groups
from estima_backend.ml.trainer import (
    predict_price,
    train_final_model,
    train_model,
)

REPORT_COLUMNS = [
    "listing_id",
    "url",
    "address",
]


@dataclass(frozen=True)
class TrainingTask:
    listing_type: ListingType
    load: Callable[[sqlite3.Connection], pd.DataFrame]
    prepare: Callable[[pd.DataFrame], tuple[pd.DataFrame, pd.Series]]
    area_column: str
    # Поля, совпадение которых означает один и тот же объект.
    key_columns: list[str]


TASKS = [
    TrainingTask(
        listing_type=ListingType.APARTMENT,
        load=load_apartments,
        prepare=prepare_apartment_features,
        area_column="area_m2",
        key_columns=[
            "city_id",
            "lat",
            "lon",
            "area_m2",
            "rooms",
            "floor",
            "floors_total",
        ],
    ),
    TrainingTask(
        listing_type=ListingType.HOUSE,
        load=load_houses,
        prepare=prepare_house_features,
        area_column="house_area_m2",
        key_columns=[
            "city_id",
            "lat",
            "lon",
            "house_kind",
            "house_area_m2",
            "land_area_m2",
        ],
    ),
    TrainingTask(
        listing_type=ListingType.LAND,
        load=load_lands,
        prepare=prepare_land_features,
        area_column="land_area_m2",
        key_columns=[
            "city_id",
            "lat",
            "lon",
            "land_area_m2",
            "land_type",
        ],
    ),
]


# ============================================================
# BASELINES
# ============================================================

def median_price_baseline(
        train: pd.DataFrame,
        test: pd.DataFrame,
) -> np.ndarray:
    medians = train.groupby("city_id")["price"].median()

    return test["city_id"].map(medians).to_numpy()


def price_per_area_baseline(
        train: pd.DataFrame,
        test: pd.DataFrame,
        area_column: str,
) -> np.ndarray:
    medians = (
        (train["price"] / train[area_column])
        .groupby(train["city_id"])
        .median()
    )

    return (
            test["city_id"].map(medians)
            * test[area_column]
    ).to_numpy()


# ============================================================
# REPORTS
# ============================================================

def print_header(
        title: str,
) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_price_statistics(
        price: pd.Series,
) -> None:
    print_header("PRICE STATISTICS")

    print(f"Count:  {len(price)}")
    print(f"Mean:   {price.mean():,.0f}")

    for quantile, value in price.quantile([0, 0.05, 0.5, 0.95, 1]).items():
        print(f"{quantile * 100:>4.0f}%:  {value:,.0f}")


def build_error_analysis(
        data: pd.DataFrame,
        x: pd.DataFrame,
        y_pred: np.ndarray,
) -> pd.DataFrame:
    result = pd.concat(
        [
            data[REPORT_COLUMNS],
            x,
        ],
        axis=1,
    )

    result["actual_price"] = data["price"]
    result["predicted_price"] = y_pred
    result["error"] = result["predicted_price"] - result["actual_price"]
    result["percentage_error"] = (
            result["error"]
            / result["actual_price"]
            * 100
    )

    return result.sort_values(
        "percentage_error",
        key=np.abs,
        ascending=False,
    )


def save_feature_importance(
        model: CatBoostRegressor,
        path,
) -> None:
    pd.DataFrame({
        "feature": model.feature_names_,
        "importance": model.get_feature_importance(),
    }).sort_values(
        "importance",
        ascending=False,
    ).to_csv(
        path,
        index=False,
    )


# ============================================================
# TRAINING
# ============================================================

def coverage_radius_km(
        data: pd.DataFrame,
        x: pd.DataFrame,
        config: TrainingConfig,
) -> dict[str, float]:
    radius = (
        x["distance_to_center_km"]
        .groupby(data["city_id"])
        .quantile(config.coverage_quantile)
        * config.coverage_margin
    )

    return {
        str(city_id): round(float(value), 1)
        for city_id, value in radius.items()
    }


def train_one_model(
        task: TrainingTask,
        data: pd.DataFrame,
        config: TrainingConfig,
) -> None:
    name = f"{task.listing_type}_price"
    features, categorical_features = MODEL_FEATURES[task.listing_type]

    print("\n" + "#" * 70)
    print(f"# TRAINING: {name}")
    print("#" * 70)

    rows = {"loaded": len(data)}

    data = drop_duplicate_listings(
        data,
        task.key_columns,
    )
    rows["after_duplicates"] = len(data)

    data = drop_price_outliers(
        data,
        task.area_column,
        config.outlier_quantile,
    )
    rows["after_outliers"] = len(data)

    print_price_statistics(data["price"])

    x, y = task.prepare(data)
    groups = building_groups(data)

    train_index, test_index = split_by_groups(
        groups,
        config.test_size,
        config.random_seed,
    )
    fit_index, valid_index = split_by_groups(
        groups.loc[train_index],
        config.valid_size,
        config.random_seed,
    )

    rows |= {
        "train": len(fit_index),
        "valid": len(valid_index),
        "test": len(test_index),
    }

    print_header("ROWS")
    for key, value in rows.items():
        print(f"{key + ':':<18}{value}")

    result = train_model(
        x.loc[fit_index],
        y.loc[fit_index],
        x.loc[valid_index],
        y.loc[valid_index],
        categorical_features,
        config,
    )

    y_test = y.loc[test_index]
    y_pred = predict_price(
        result.model,
        x.loc[test_index],
    )

    metrics = {
        "median_price_baseline": calculate_metrics(
            y_test,
            median_price_baseline(
                data.loc[train_index],
                data.loc[test_index],
            ),
        ),
        "price_per_area_baseline": calculate_metrics(
            y_test,
            price_per_area_baseline(
                data.loc[train_index],
                data.loc[test_index],
                task.area_column,
            ),
        ),
        "model": calculate_metrics(
            y_test,
            y_pred,
        ),
    }

    for title, values in metrics.items():
        print_header(title.upper())
        print_metrics(values)

    print(f"\nBest iteration: {result.best_iteration}")

    errors = build_error_analysis(
        data.loc[test_index],
        x.loc[test_index],
        y_pred,
    )

    print_header("WORST PREDICTIONS BY PERCENTAGE ERROR")
    print(
        errors[["listing_id", "actual_price", "predicted_price", "percentage_error"]]
        .head(10)
        .to_string(index=False)
    )

    model = train_final_model(
        x,
        y,
        categorical_features,
        config,
        iterations=result.best_iteration + 1,
    )

    errors_path = ANALYSIS_DIR / f"{name}_errors.csv"
    importance_path = ANALYSIS_DIR / f"{name}_feature_importance.csv"
    path = model_path(task.listing_type)
    metadata_file = metadata_path(task.listing_type)

    ANALYSIS_DIR.mkdir(exist_ok=True)
    errors.to_csv(
        errors_path,
        index=False,
    )
    save_feature_importance(
        model,
        importance_path,
    )
    save_model(
        model,
        path,
    )
    save_metadata(
        {
            "listing_type": str(task.listing_type),
            "target_transform": "log1p",
            "features": features,
            "categorical_features": categorical_features,
            "city_ids": sorted(int(city_id) for city_id in data["city_id"].unique()),
            "coverage_radius_km": coverage_radius_km(
                data,
                x,
                config,
            ),
            "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "data_last_seen_at": data["last_seen_at"].max(),
            "rows": rows,
            "best_iteration": result.best_iteration,
            "config": asdict(config),
            "metrics": metrics,
        },
        metadata_file,
    )

    print("\nSaved:")
    for saved_path in (path, metadata_file, errors_path, importance_path):
        print(f"  {saved_path}")


def main() -> None:
    config = TrainingConfig()

    with closing(create_connection(DB_PATH)) as conn:
        datasets = [
            (task, task.load(conn))
            for task in TASKS
        ]

    for task, data in datasets:
        train_one_model(
            task,
            data,
            config,
        )


if __name__ == "__main__":
    main()
