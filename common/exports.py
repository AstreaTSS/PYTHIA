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
    image: typing.Optional[str] = None


class GachaItemv1Dict(typing.TypedDict):
    name: str
    description: str
    amount: int
    image: typing.Optional[str]


class GachaItemv1Container(msgspec.Struct, tag=1, tag_field="version"):
    items: list[GachaItemv1]


GachaItemContainer = GachaItemv1Container  # will become a union with additions
dec = msgspec.json.Decoder(GachaItemContainer)


def handle_gacha_item_data(json_data: str | bytes) -> list[GachaItemv1]:
    container = dec.decode(json_data)
    return container.items
