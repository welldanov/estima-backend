import numpy as np
import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


def calculate_metrics(
        y_true: pd.Series,
        y_pred: np.ndarray,
) -> dict[str, float]:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    absolute_errors = np.abs(y_true - y_pred)

    percentage_errors = absolute_errors / y_true * 100

    return {
        "mae": float(
            mean_absolute_error(y_true, y_pred)
        ),

        "rmse": float(
            np.sqrt(
                mean_squared_error(y_true, y_pred)
            )
        ),

        "r2": float(
            r2_score(y_true, y_pred)
        ),

        "median_absolute_percentage_error": float(
            np.median(percentage_errors)
        ),

        "mean_absolute_percentage_error": float(
            np.mean(percentage_errors)
        ),
    }


def print_metrics(
        metrics: dict[str, float],
) -> None:
    print(f"MAE:   {metrics['mae']:,.0f}")
    print(f"RMSE:  {metrics['rmse']:,.0f}")
    print(f"R²:    {metrics['r2']:.4f}")
    print(
        "MdAPE: "
        f"{metrics['median_absolute_percentage_error']:.2f}%"
    )
    print(
        "MAPE:  "
        f"{metrics['mean_absolute_percentage_error']:.2f}%"
    )
