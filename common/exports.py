"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import typing

import msgspec


class GachaItemv1(msgspec.Struct):
    name: str
    description: str
    amount: int
    image: str | None = None


class GachaItemv2(msgspec.Struct):
    name: str
    description: str
    rarity: int
    amount: int
    image: str | None = None


class GachaItemDict(typing.TypedDict):
    name: str
    description: str
    rarity: int
    amount: int
    image: str | None


class GachaItemv1Container(msgspec.Struct, tag=1, tag_field="version"):
    items: list[GachaItemv1]


class GachaItemv2Container(msgspec.Struct, tag=2, tag_field="version"):
    items: list[GachaItemv2]


GachaItemContainer = GachaItemv1Container | GachaItemv2Container
dec = msgspec.json.Decoder(GachaItemContainer)


def handle_gacha_item_data(json_data: str | bytes) -> list[GachaItemv2]:
    container: GachaItemContainer = dec.decode(json_data)

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
