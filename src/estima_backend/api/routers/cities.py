from fastapi import APIRouter

from ..dependencies import CityServiceDep
from ..schemas.city import CityResponse

router = APIRouter(
    prefix="/api/cities",
    tags=["cities"],
)


@router.get("")
async def get_cities(
        service: CityServiceDep,
) -> list[CityResponse]:
    return service.list_cities()
