from typing import Any

from fastapi import APIRouter

from ..dependencies import YandexQuotaDep

router = APIRouter(
    prefix="/api/health",
    tags=["health"],
)


@router.get("")
async def health(
        quota: YandexQuotaDep,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "yandex_usage": quota.usage(),
    }
