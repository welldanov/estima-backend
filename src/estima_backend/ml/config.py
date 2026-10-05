from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingConfig:
    random_seed: int = 42

    test_size: float = 0.20
    valid_size: float = 0.20

    outlier_quantile: float = 0.005

    # Радиус от центра города, в котором модель даёт прогноз:
    # квантиль расстояний обучающей выборки с запасом.
    coverage_quantile: float = 0.99
    coverage_margin: float = 1.25

    iterations: int = 3000
    learning_rate: float = 0.03
    depth: int = 6

    l2_leaf_reg: float = 5.0
    random_strength: float = 1.0

    loss_function: str = "RMSE"
    eval_metric: str = "RMSE"

    early_stopping_rounds: int = 200
