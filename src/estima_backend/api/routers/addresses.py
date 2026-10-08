from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import StringConstraints

from ...ingestion.models import ListingType
from ..dependencies import AddressServiceDep
from ..schemas.address import AddressSearchResponse

router = APIRouter(
    prefix="/api/addresses",
    tags=["addresses"],
)

SearchQuery = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=200,
    ),
    Query(),
]


@router.get("/search")
async def search_addresses(
        service: AddressServiceDep,
        city_id: Annotated[int, Query(gt=0)],
        query: SearchQuery,
        property_type: Annotated[ListingType | None, Query()] = None,
) -> AddressSearchResponse:
    return AddressSearchResponse(
        items=await service.search(
            city_id=city_id,
            query=query,
            listing_type=property_type,
        ),
    )
