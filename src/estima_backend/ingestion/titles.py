import re

from .models import (
    ApartmentData,
    HouseData,
    HouseKind,
    LandData,
    LandType,
    SkipRecord,
)

NUMBER = r"\d+(?:,\d+)?"

APARTMENT_PATTERN = re.compile(
    rf"(?P<rooms>\d+)-к\. квартира, "
    rf"(?P<area>{NUMBER}) м², "
    rf"(?P<floor>\d+)/(?P<floors_total>\d+) эт\."
)

STUDIO_PATTERN = re.compile(
    rf"Квартира-студия, "
    rf"(?P<area>{NUMBER}) м², "
    rf"(?P<floor>\d+)/(?P<floors_total>\d+) эт\."
)

HOUSE_PATTERN = re.compile(
    rf"(?P<kind>Дом|Дача|Коттедж|Таунхаус) "
    rf"(?P<house_area>{NUMBER}) м² на участке "
    rf"(?P<land_area>{NUMBER}) (?P<unit>сот\.|га)"
)

LAND_PATTERN = re.compile(
    rf"Участок (?P<area>{NUMBER}) (?P<unit>сот\.|га) "
    rf"\((?P<land_type>.+)\)"
)

HOUSE_KINDS: dict[str, HouseKind] = {
    "Дом": HouseKind.HOUSE,
    "Дача": HouseKind.DACHA,
    "Коттедж": HouseKind.COTTAGE,
    "Таунхаус": HouseKind.TOWNHOUSE,
}

LAND_TYPES: dict[str, LandType] = {
    "ижс": LandType.IZHS,
    "снт, днп": LandType.SNT_DNP,
    "личное подсобное хозяйство (лпх)": LandType.LPH,
    "промназначения": LandType.INDUSTRIAL,
}

SOTKA_M2 = 100.0

MIN_APARTMENT_AREA_M2 = 8.0
MAX_APARTMENT_AREA_M2 = 500.0
MIN_AREA_PER_ROOM_M2 = 5.0


def clean_title(
        title: str,
) -> str:
    return " ".join(
        title.replace("\xa0", " ").split()
    )


def _to_float(
        value: str,
) -> float:
    return float(value.replace(",", "."))


def _reject_hectares(
        unit: str,
) -> None:
    if unit == "га":
        raise SkipRecord(
            "Land area in hectares is unreliable"
        )


def parse_apartment_title(
        title: str,
) -> ApartmentData:
    title = clean_title(title)

    if match := APARTMENT_PATTERN.fullmatch(title):
        rooms = int(match["rooms"])
        is_studio = False

    elif match := STUDIO_PATTERN.fullmatch(title):
        rooms = None
        is_studio = True

    else:
        raise SkipRecord(
            "Unsupported apartment title"
        )

    area_m2 = _to_float(match["area"])
    floor = int(match["floor"])
    floors_total = int(match["floors_total"])

    if rooms == 0:
        raise SkipRecord(
            "Apartment rooms count is zero"
        )

    if not MIN_APARTMENT_AREA_M2 <= area_m2 <= MAX_APARTMENT_AREA_M2:
        raise SkipRecord(
            "Apartment area out of range"
        )

    if rooms is not None and area_m2 / rooms < MIN_AREA_PER_ROOM_M2:
        raise SkipRecord(
            "Apartment area too small for room count"
        )

    if floor == 0 or floors_total == 0 or floor > floors_total:
        raise SkipRecord(
            "Apartment floor is inconsistent"
        )

    return ApartmentData(
        area_m2=area_m2,
        rooms=rooms,
        is_studio=is_studio,
        floor=floor,
        floors_total=floors_total,
    )


def parse_house_title(
        title: str,
) -> HouseData:
    match = HOUSE_PATTERN.fullmatch(
        clean_title(title)
    )

    if match is None:
        raise SkipRecord(
            "Unsupported house title"
        )

    _reject_hectares(match["unit"])

    house_area_m2 = _to_float(match["house_area"])
    land_area_m2 = _to_float(match["land_area"]) * SOTKA_M2

    if house_area_m2 <= 0 or land_area_m2 <= 0:
        raise SkipRecord(
            "House area is not positive"
        )

    return HouseData(
        house_kind=HOUSE_KINDS[match["kind"]],
        house_area_m2=house_area_m2,
        land_area_m2=land_area_m2,
    )


def parse_land_title(
        title: str,
) -> LandData:
    match = LAND_PATTERN.fullmatch(
        clean_title(title)
    )

    if match is None:
        raise SkipRecord(
            "Unsupported land title"
        )

    land_type = LAND_TYPES.get(
        match["land_type"].strip().lower()
    )

    if land_type is None:
        raise SkipRecord(
            "Unknown land type"
        )

    _reject_hectares(match["unit"])

    land_area_m2 = _to_float(match["area"]) * SOTKA_M2

    if land_area_m2 <= 0:
        raise SkipRecord(
            "Land area is not positive"
        )

    return LandData(
        land_area_m2=land_area_m2,
        land_type=land_type,
    )
