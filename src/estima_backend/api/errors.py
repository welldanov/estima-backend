class ServiceError(Exception):
    """Ошибка запроса, которую клиент может исправить: detail уходит в ответ."""

    status_code = 400
    detail = "Некорректный запрос."

    def __init__(
            self,
            detail: str | None = None,
    ) -> None:
        if detail is not None:
            self.detail = detail

        super().__init__(self.detail)


class CityNotFoundError(ServiceError):
    status_code = 404
    detail = "Город не найден."


class PropertyTypeNotSupportedError(ServiceError):
    status_code = 422
    detail = "Для этого города прогноз такого типа недвижимости пока недоступен."


class AddressNotFoundError(ServiceError):
    status_code = 422
    detail = "Адрес не найден. Выберите его из подсказок заново."


class AddressNotPreciseError(ServiceError):
    status_code = 422
    detail = "Адрес указан неточно."


class AddressOutOfCoverageError(ServiceError):
    status_code = 422
    detail = "Адрес слишком далеко от города: прогноз для него ненадёжен."
