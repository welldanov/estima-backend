from pydantic import BaseModel, ConfigDict


class AddressSuggestion(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    title: str
    subtitle: str | None = None

    formatted_address: str | None = None

    uri: str


class AddressSearchResponse(BaseModel):
    items: list[AddressSuggestion]
