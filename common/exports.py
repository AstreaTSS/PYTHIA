"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import typing

from pydantic import BaseModel


class GachaItemv1(BaseModel):
    name: str
    description: str
    amount: int
    image: typing.Optional[str] = None


class GachaItemv1Container(BaseModel):
    version: typing.Literal[1]
    items: list[GachaItemv1]


class GachaItemContainer(BaseModel):
    data: GachaItemv1Container  # make this a union of all versions when more are added


def handle_gacha_item_data(json_data: str | bytes) -> list[GachaItemv1]:
    container = GachaItemContainer.model_validate_json(json_data)
    return container.data.items
