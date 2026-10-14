import pytest

from estima_backend.ingestion.models import (
    ApartmentData,
    HouseData,
    HouseKind,
    LandType,
    SkipRecord,
)
from estima_backend.ingestion.titles import (
    parse_apartment_title,
    parse_house_title,
    parse_land_title,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        (
            "2-к. квартира, 45 м², 3/9 эт.",
            ApartmentData(
                area_m2=45.0,
                rooms=2,
                is_studio=False,
                floor=3,
                floors_total=9,
            ),
        ),
        (
            "1-к. квартира, 32,5 м², 1/5 эт.",
            ApartmentData(
                area_m2=32.5,
                rooms=1,
                is_studio=False,
                floor=1,
                floors_total=5,
            ),
        ),
        (
            "Квартира-студия, 24 м², 12/17 эт.",
            ApartmentData(
                area_m2=24.0,
                rooms=None,
                is_studio=True,
                floor=12,
                floors_total=17,
            ),
        ),
        (
            " 3-к.\xa0квартира,  78 м², 9/9 эт. ",
            ApartmentData(
                area_m2=78.0,
                rooms=3,
                is_studio=False,
                floor=9,
                floors_total=9,
            ),
        ),
    ],
)
def test_parse_apartment_title(
    title: str,
    expected: ApartmentData,
) -> None:
    assert parse_apartment_title(title) == expected


@pytest.mark.parametrize(
    "title",
    [
        "Квартира-студия, 8 м², 1/5 эт.",
        "5-к. квартира, 500 м², 1/5 эт.",
        "2-к. квартира, 10 м², 1/5 эт.",
    ],
)
def test_parse_apartment_title_accepts_boundaries(
    title: str,
) -> None:
    parse_apartment_title(title)


@pytest.mark.parametrize(
    "title",
    [
        "Апартаменты-студия, 25 м², 3/10 эт.",
        "Квартира свободной планировки, 50 м², 2/5 эт.",
        "Доля в 2-к. квартире, 15 м², 1/5 эт.",
        "10 и более-к. квартира, 300 м², 5/5 эт.",
        "2-к. квартира, 45 м², 3/9 эт. (аукцион)",
        "0-к. квартира, 30 м², 1/5 эт.",
        "1-к. квартира, 7,9 м², 1/5 эт.",
        "5-к. квартира, 501 м², 1/5 эт.",
        "4-к. квартира, 18 м², 1/5 эт.",
        "2-к. квартира, 45 м², 10/9 эт.",
        "2-к. квартира, 45 м², 0/9 эт.",
        "",
    ],
)
def test_parse_apartment_title_skips_unsupported(
    title: str,
) -> None:
    with pytest.raises(SkipRecord):
        parse_apartment_title(title)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        (
            "Дом 120 м² на участке 6 сот.",
            HouseData(
                house_kind=HouseKind.HOUSE,
                house_area_m2=120.0,
                land_area_m2=600.0,
            ),
        ),
        (
            "Коттедж 250,5 м² на участке 15,5 сот.",
            HouseData(
                house_kind=HouseKind.COTTAGE,
                house_area_m2=250.5,
                land_area_m2=1550.0,
            ),
        ),
        (
            "Дача 30 м² на участке 4 сот.",
            HouseData(
                house_kind=HouseKind.DACHA,
                house_area_m2=30.0,
                land_area_m2=400.0,
            ),
        ),
        (
            "Таунхаус 90 м² на участке 2 сот.",
            HouseData(
                house_kind=HouseKind.TOWNHOUSE,
                house_area_m2=90.0,
                land_area_m2=200.0,
            ),
        ),
    ],
)
def test_parse_house_title(
    title: str,
    expected: HouseData,
) -> None:
    assert parse_house_title(title) == expected


@pytest.mark.parametrize(
    "title",
    [
        "Дом 120 м² на участке 1 га",
        "Дом 0 м² на участке 6 сот.",
        "Дом 120 м² на участке 0 сот.",
        "Дом 120 м²",
        "Недострой 120 м² на участке 6 сот.",
    ],
)
def test_parse_house_title_skips_unsupported(
    title: str,
) -> None:
    with pytest.raises(SkipRecord):
        parse_house_title(title)


@pytest.mark.parametrize(
    ("title", "land_area_m2", "land_type"),
    [
        ("Участок 6 сот. (ИЖС)", 600.0, LandType.IZHS),
        ("Участок 8,3 сот. (ИЖС)", 830.0, LandType.IZHS),
        ("Участок 4 сот. (СНТ, ДНП)", 400.0, LandType.SNT_DNP),
        ("Участок 10 сот. (личное подсобное хозяйство (лпх))", 1000.0, LandType.LPH),
        ("Участок 10,8 сот. (промназначения)", 1080.0, LandType.INDUSTRIAL),
    ],
)
def test_parse_land_title(
    title: str,
    land_area_m2: float,
    land_type: LandType,
) -> None:
    land = parse_land_title(title)

    assert land.land_area_m2 == pytest.approx(land_area_m2)
    assert land.land_type is land_type


@pytest.mark.parametrize(
    "title",
    [
        "Участок 1 га (ИЖС)",
        "Участок 0 сот. (ИЖС)",
        "Участок 10 сот. (сельхозназначения)",
        "Участок 10 сот.",
    ],
)
def test_parse_land_title_skips_unsupported(
    title: str,
) -> None:
    with pytest.raises(SkipRecord):
        parse_land_title(title)
