from dataclasses import dataclass

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from .config import TrainingConfig


@dataclass(frozen=True)
class TrainingResult:
    model: CatBoostRegressor
    best_iteration: int


def _create_model(
        config: TrainingConfig,
        iterations: int,
        **params,
) -> CatBoostRegressor:
    return CatBoostRegressor(
        iterations=iterations,
        learning_rate=config.learning_rate,
        depth=config.depth,

        loss_function=config.loss_function,
        eval_metric=config.eval_metric,

        l2_leaf_reg=config.l2_leaf_reg,
        random_strength=config.random_strength,

        random_seed=config.random_seed,

        verbose=False,
        allow_writing_files=False,

        **params,
    )


def train_model(
        x_train: pd.DataFrame,
        y_train: pd.Series,
        x_valid: pd.DataFrame,
        y_valid: pd.Series,
        cat_features: list[str],
        config: TrainingConfig,
) -> TrainingResult:
    model = _create_model(
        config,
        config.iterations,
        od_type="Iter",
        od_wait=config.early_stopping_rounds,
    )

    model.fit(
        x_train,
        np.log1p(y_train),

        cat_features=cat_features,

        eval_set=(x_valid, np.log1p(y_valid)),

        use_best_model=True,
    )

    return TrainingResult(
        model=model,
        best_iteration=model.get_best_iteration(),
    )


def train_final_model(
        x: pd.DataFrame,
        y: pd.Series,
        cat_features: list[str],
        config: TrainingConfig,
        iterations: int,
) -> CatBoostRegressor:
    model = _create_model(
        config,
        iterations,
    )

    model.fit(
        x,
        np.log1p(y),
        cat_features=cat_features,
    )

    return model


def predict_price(
        model: CatBoostRegressor,
        x: pd.DataFrame,
) -> np.ndarray:
    return np.expm1(model.predict(x))
