from estima_backend.ml.predictor import (
    RealEstatePredictor,
)


def main() -> None:
    predictor = RealEstatePredictor()

    price = predictor.predict_apartment(
        city_id=650210,
        lat=54.890438,
        lon=52.268565,
        area_m2=42,
        rooms=1,
        is_studio=False,
        floor=8,
        floors_total=18,
    )

    print()
    print("=" * 50)
    print("APARTMENT PRICE PREDICTION")
    print("=" * 50)
    print(f"Predicted price: {price:,.0f} RUB")
    print("=" * 50)


if __name__ == "__main__":
    main()
