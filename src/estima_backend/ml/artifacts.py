import json
from pathlib import Path

from catboost import CatBoostRegressor


def save_model(
        model: CatBoostRegressor,
        path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    model.save_model(path)


def save_metadata(
        metadata: dict,
        path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
            "w",
            encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=2,
        )
