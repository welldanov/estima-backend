from pydantic import BaseModel, ConfigDict, Field


class AddressSuggestion(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    title: str
    subtitle: str | None = None

    formatted_address: str | None = None

    uri: str

    kind: str | None = Field(
        default=None,
        description="Тип объекта по Yandex: house, street, district, locality",
    )


class AddressSearchResponse(BaseModel):
    items: list[AddressSuggestion]
