from fastapi import APIRouter

from ..dependencies import PredictionServiceDep
from ..schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
)

router = APIRouter(
    prefix="/api/predict",
    tags=["prediction"],
)


@router.post("")
async def predict(
        service: PredictionServiceDep,
        prediction_request: PredictionRequest,
) -> PredictionResponse:
    return await service.predict(prediction_request)
