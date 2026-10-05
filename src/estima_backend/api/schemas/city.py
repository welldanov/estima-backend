from pydantic import BaseModel

from ...ingestion.models import ListingType


class CityResponse(BaseModel):
    id: int
    name: str
    property_types: list[ListingType]
