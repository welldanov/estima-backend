from contextlib import closing

from estima_backend.config import DB_PATH

from estima_backend.database.connection import create_connection

from estima_backend.ml.dataset import (
    load_apartments,
    load_houses,
    load_lands,
)

from estima_backend.ml.features import (
    prepare_apartment_features,
    prepare_house_features,
    prepare_land_features,
)


def main():
    with closing(create_connection(DB_PATH)) as conn:
        apartments = load_apartments(conn)
        houses = load_houses(conn)
        lands = load_lands(conn)

    x_apartment, y_apartment = (
        prepare_apartment_features(apartments)
    )

    x_house, y_house = (
        prepare_house_features(houses)
    )

    x_land, y_land = (
        prepare_land_features(lands)
    )

    print("APARTMENTS")
    print("X:", x_apartment.shape)
    print("y:", y_apartment.shape)
    print(x_apartment.head())
    print()

    print("HOUSES")
    print("X:", x_house.shape)
    print("y:", y_house.shape)
    print(x_house.head())
    print()

    print("LANDS")
    print("X:", x_land.shape)
    print("y:", y_land.shape)
    print(x_land.head())


if __name__ == "__main__":
    main()
