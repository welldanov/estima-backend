import pandas as pd


def drop_duplicate_listings(
        df: pd.DataFrame,
        key_columns: list[str],
) -> pd.DataFrame:
    return (
        df
        .sort_values("last_seen_at")
        .drop_duplicates(
            key_columns,
            keep="last",
        )
        .sort_index()
    )


def drop_price_outliers(
        df: pd.DataFrame,
        area_column: str,
        quantile: float,
) -> pd.DataFrame:
    price_per_area = df["price"] / df[area_column]
    by_city = price_per_area.groupby(df["city_id"])

    lower = by_city.transform("quantile", quantile)
    upper = by_city.transform("quantile", 1 - quantile)

    return df[price_per_area.between(lower, upper)]
