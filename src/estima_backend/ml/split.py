import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

# ~10 м: объявления одного здания имеют одинаковые координаты.
BUILDING_COORDINATE_DECIMALS = 4


def building_groups(
        df: pd.DataFrame,
) -> pd.Series:
    return (
            df["lat"].round(BUILDING_COORDINATE_DECIMALS).astype(str)
            + ","
            + df["lon"].round(BUILDING_COORDINATE_DECIMALS).astype(str)
    )


def split_by_groups(
        groups: pd.Series,
        test_size: float,
        random_state: int,
) -> tuple[pd.Index, pd.Index]:
    # Все объявления одного здания попадают в одну часть,
    # иначе похожие квартиры из train «подсказывают» ответ в test.
    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=test_size,
        random_state=random_state,
    )

    train_positions, test_positions = next(
        splitter.split(
            groups,
            groups=groups,
        )
    )

    return (
        groups.index[train_positions],
        groups.index[test_positions],
    )
