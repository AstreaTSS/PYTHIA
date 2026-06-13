"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import d20
import pydantic
import typing_extensions as typing

import common.utils as utils

_d20_roll = d20.Roller(d20.RollContext(100)).roll


def _replace_smart_punc(text: typing.Any) -> typing.Any:
    if not isinstance(text, str):
        return text

    return utils.replace_smart_punc(text)


def _validate_http_url(url: str) -> str:
    if not url:
        return url

    if not utils.HTTP_URL_REGEX.fullmatch(url):
        raise ValueError("Invalid URL.")
    return url


def _validate_dice_value(value: str) -> str:
    try:
        _d20_roll(value)
    except d20.errors.RollSyntaxError as e:
        raise ValueError(f"Invalid dice roll syntax: {e!s}") from None
    except d20.errors.TooManyRolls:
        raise ValueError("Too many dice rolls in this expression.") from None
    except d20.errors.RollValueError:
        raise ValueError("Invalid dice roll value.") from None

    return value


RemoveSmartPunc = pydantic.BeforeValidator(_replace_smart_punc)
HTTPURLValidator = pydantic.AfterValidator(_validate_http_url)
DiceValueValidator = pydantic.AfterValidator(_validate_dice_value)
StripWhitespace = pydantic.StringConstraints(strip_whitespace=True)


class GachaItemv1(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, strict=True)

    name: typing.Annotated[str, RemoveSmartPunc, StripWhitespace] = pydantic.Field(
        min_length=1, max_length=64
    )
    description: typing.Annotated[str, StripWhitespace] = pydantic.Field(
        min_length=1, max_length=3500
    )
    amount: int = pydantic.Field(ge=-1, le=999)
    image: typing.Annotated[str | None, StripWhitespace, HTTPURLValidator] = (
        pydantic.Field(max_length=2000, default=None)
    )


class GachaItemv2(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, strict=True)

    name: typing.Annotated[str, RemoveSmartPunc, StripWhitespace] = pydantic.Field(
        min_length=1, max_length=64
    )
    description: typing.Annotated[str, StripWhitespace] = pydantic.Field(
        min_length=1, max_length=3500
    )
    rarity: int = pydantic.Field(ge=1, le=5)
    amount: int = pydantic.Field(ge=-1, le=999)
    image: typing.Annotated[str | None, StripWhitespace, HTTPURLValidator] = (
        pydantic.Field(max_length=2000, default=None)
    )


class GachaItemDict(typing.TypedDict):
    name: str
    description: str
    rarity: int
    amount: int
    image: str | None


class DiceEntryv1(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, strict=True)

    name: typing.Annotated[str, RemoveSmartPunc, StripWhitespace] = pydantic.Field(
        min_length=1, max_length=100
    )
    value: typing.Annotated[str, StripWhitespace, DiceValueValidator] = pydantic.Field(
        min_length=1, max_length=100
    )


class DiceEntryDict(typing.TypedDict):
    name: str
    value: str


class ItemsSystemItemv1(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, strict=True)

    name: typing.Annotated[str, RemoveSmartPunc, StripWhitespace] = pydantic.Field(
        min_length=1, max_length=64
    )
    description: typing.Annotated[str, StripWhitespace] = pydantic.Field(
        min_length=1, max_length=3500
    )
    takeable: bool = pydantic.Field()
    image: typing.Annotated[str | None, StripWhitespace, HTTPURLValidator] = (
        pydantic.Field(max_length=2000, default=None)
    )


class ItemsSystemItemDict(typing.TypedDict):
    name: str
    description: str
    takeable: bool
    image: str | None


class GachaItemv1Container(pydantic.BaseModel):
    version: typing.Literal[1] = 1
    items: list[GachaItemv1]


class GachaItemv2Container(pydantic.BaseModel):
    version: typing.Literal[2] = 2
    items: list[GachaItemv2]


class DiceEntryv1Container(pydantic.BaseModel):
    version: typing.Literal[1] = 1
    entries: list[DiceEntryv1]


class ItemsSystemItemv1Container(pydantic.BaseModel):
    version: typing.Literal[1] = 1
    items: list[ItemsSystemItemv1]


GachaItemContainer = pydantic.RootModel[
    typing.Annotated[
        GachaItemv1Container | GachaItemv2Container,
        pydantic.Field(discriminator="version"),
    ]
]


def handle_gacha_item_data(json_data: str | bytes) -> list[GachaItemv2]:
    container = GachaItemContainer.model_validate_json(json_data).root

    if isinstance(container, GachaItemv1Container):
        items = [
            GachaItemv2(
                name=item.name,
                description=item.description,
                rarity=1,  # default rarity for v1 items - common
                amount=item.amount,
                image=item.image,
            )
            for item in container.items
        ]
        container = GachaItemv2Container(items=items)

    return container.items


def handle_dice_entry_data(json_data: str | bytes) -> list[DiceEntryv1]:
    container = DiceEntryv1Container.model_validate_json(json_data)
    return container.entries


def handle_items_system_item_data(json_data: str | bytes) -> list[ItemsSystemItemv1]:
    container = ItemsSystemItemv1Container.model_validate_json(json_data)
    return container.items
