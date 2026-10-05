from contextlib import closing

from estima_backend.config import DB_PATH

from estima_backend.database.connection import create_connection

from estima_backend.ml.dataset import (
    load_apartments,
    load_houses,
    load_lands,
)


def main():
    with closing(create_connection(DB_PATH)) as conn:
        apartments = load_apartments(conn)
        houses = load_houses(conn)
        lands = load_lands(conn)

    print("APARTMENTS")
    print(apartments.shape)
    print(apartments.head())
    print()

    print("HOUSES")
    print(houses.shape)
    print(houses.head())
    print()

    print("LANDS")
    print(lands.shape)
    print(lands.head())


if __name__ == "__main__":
    main()
