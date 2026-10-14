import numpy as np
from numpy.typing import ArrayLike
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


def calculate_metrics(
    y_true: ArrayLike,
    y_pred: ArrayLike,
) -> dict[str, float]:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    absolute_errors = np.abs(y_true - y_pred)

    percentage_errors = absolute_errors / y_true * 100

    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "median_absolute_percentage_error": float(np.median(percentage_errors)),
        "mean_absolute_percentage_error": float(np.mean(percentage_errors)),
    }


def print_metrics(
    metrics: dict[str, float],
) -> None:
    print(f"MAE:   {metrics['mae']:,.0f}")
    print(f"RMSE:  {metrics['rmse']:,.0f}")
    print(f"R²:    {metrics['r2']:.4f}")
    print(f"MdAPE: {metrics['median_absolute_percentage_error']:.2f}%")
    print(f"MAPE:  {metrics['mean_absolute_percentage_error']:.2f}%")
