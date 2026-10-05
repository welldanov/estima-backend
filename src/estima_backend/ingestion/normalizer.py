from ..config import BASE_URL, CATEGORY_TYPES, CITIES
from .models import (
    ListingData,
    ListingType,
    NormalizedListing,
    SkipRecord,
)
from .titles import (
    parse_apartment_title,
    parse_house_title,
    parse_land_title,
)
from .validator import AvitoListingSchema


def classify_listing(
        category_id: int,
) -> ListingType:
    try:
        return ListingType(CATEGORY_TYPES[category_id])

    except KeyError as exc:
        raise SkipRecord(
            "Unsupported Avito category"
        ) from exc


def build_url(
        url_path: str,
) -> str:
    if url_path.startswith(("http://", "https://")):
        return url_path

    return f"{BASE_URL}{url_path}"


def normalize(
        item: AvitoListingSchema,
) -> NormalizedListing:
    if item.location.id not in CITIES:
        raise SkipRecord(
            "Unknown city"
        )

    listing_type = classify_listing(item.category.id)

    match listing_type:
        case ListingType.APARTMENT:
            details = parse_apartment_title(item.title)

        case ListingType.HOUSE:
            details = parse_house_title(item.title)

        case ListingType.LAND:
            details = parse_land_title(item.title)

        case _:
            raise ValueError(
                f"Unsupported listing type: {listing_type}"
            )

    address = item.geo.formattedAddress.strip()

    if not address:
        raise SkipRecord(
            "Address is missing"
        )

    listing = ListingData(
        id=item.id,
        city_id=item.location.id,
        property_type=listing_type,
        title=item.title,
        description=item.description,
        price=item.priceDetailed.value,
        address=address,
        lat=item.coords.lat,
        lon=item.coords.lng,
        url=build_url(item.urlPath),
        seen_at=item.parsed_at,
    )

    return NormalizedListing(
        listing=listing,
        details=details,
    )
