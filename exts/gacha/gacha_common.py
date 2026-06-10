"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections

import discord

import common.classes as classes
import common.models as models
import common.utils as utils

_item_creation_locks: collections.defaultdict[str, asyncio.Lock] = (
    collections.defaultdict(asyncio.Lock)
)

__all__ = ("CreateGachaItemModal", "EditGachaItemModal", "gacha_item_button")


class CreateGachaItemModal(discord.ui.DesignerModal):
    def __init__(self) -> None:
        super().__init__(
            discord.ui.Label(
                label="Item Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="item_name",
                    max_length=64,
                ),
            ),
            discord.ui.Label(
                label="Item Description",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.paragraph,
                    custom_id="item_description",
                    max_length=3500,
                ),
            ),
            discord.ui.Label(
                label="Item Rarity",
                item=discord.ui.Select(
                    discord.ComponentType.string_select,
                    options=[
                        discord.SelectOption(
                            label="Common", value="Common", default=True
                        ),
                        discord.SelectOption(label="Uncommon", value="Uncommon"),
                        discord.SelectOption(label="Rare", value="Rare"),
                        discord.SelectOption(label="Epic", value="Epic"),
                        discord.SelectOption(label="Legendary", value="Legendary"),
                    ],
                    custom_id="item_rarity",
                    placeholder="Select the item rarity.",
                    min_values=1,
                    max_values=1,
                ),
            ),
            discord.ui.Label(
                label="Item Quantity",
                description="Defaults to being unlimited if left empty.",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="item_amount",
                    max_length=10,
                    required=False,
                    placeholder="Unlimited",
                ),
            ),
            discord.ui.Label(
                label="Item Image",
                description="The image URL of the item.",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="item_image",
                    required=False,
                ),
            ),
            title="Add Gacha Item",
            custom_id="add_gacha_item",
        )

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        responses = utils.parse_modal_responses(self)

        name: str = utils.replace_smart_punc(responses["item_name"])
        description: str = responses["item_description"]
        str_amount: str = (
            responses["item_amount"].strip() if responses.get("item_amount") else "-1"
        )
        image: str | None = (
            responses["item_image"].strip() if responses.get("item_image") else None
        )

        if isinstance(responses["item_rarity"], list):
            str_rarity: str = responses["item_rarity"][0]
        else:
            str_rarity: str = responses["item_rarity"]

        async with _item_creation_locks[f"{inter.guild_id}-{name.lower()}"]:
            if await models.GachaItem.exists(
                guild_id=inter.guild_id, name__iexact=name
            ):
                raise utils.BadArgument("An item with that name already exists.")

            try:
                rarity = models.Rarity[str_rarity.upper()]
            except (KeyError, ValueError):
                raise utils.BadArgument(
                    "Invalid rarity. Rarity must be one of: common, uncommon, rare,"
                    " epic, legendary."
                ) from None

            try:
                amount = int(str_amount)
                if amount < -1:
                    raise ValueError
            except ValueError:
                raise utils.BadArgument("Quantity must be a positive number.") from None

            if amount > 999:
                raise utils.BadArgument(
                    "This amount is too high. Please set an amount at or lower than"
                    " 999, or leave the value empty to have an unlimited amount."
                )

            if image and not utils.HTTP_URL_REGEX.fullmatch(image):
                raise utils.BadArgument("The image given must be a valid URL.")

            # some configs needs to exist, lets make sure they do
            await models.GuildConfig.fetch_create(inter.guild_id, {"gacha": True})

            created_item = await models.GachaItem.create(
                guild_id=inter.guild_id,
                name=name,
                description=description,
                rarity=rarity,
                amount=amount,
                image=image,
            )

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(f"Added item `{name}` to the gacha."),
                accessory=discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label="View Item",
                    custom_id=f"gacha-item-{created_item.id}-admin",
                ),
            ),
            color=inter.client.color,
        )
        await inter.respond(view=utils.quick_view(container))


class EditGachaItemModal(discord.ui.DesignerModal):
    def __init__(self, item: models.GachaItem) -> None:
        string_select_options: list[discord.SelectOption] = []
        for rarity_name in models.Rarity.__members__.keys():
            option = discord.SelectOption(
                label=rarity_name.title(),
                value=rarity_name.title(),
            )
            if rarity_name.upper() == item.rarity.name:
                option.default = True
            string_select_options.append(option)

        super().__init__(
            discord.ui.Label(
                label="Item Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="item_name",
                    max_length=64,
                    value=item.name,
                ),
            ),
            discord.ui.Label(
                label="Item Description",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.paragraph,
                    custom_id="item_description",
                    max_length=3500,
                    value=item.description,
                ),
            ),
            discord.ui.Label(
                label="Item Rarity",
                item=discord.ui.Select(
                    discord.ComponentType.string_select,
                    options=string_select_options,
                    custom_id="item_rarity",
                    placeholder="Select the item rarity.",
                    min_values=1,
                    max_values=1,
                ),
            ),
            discord.ui.Label(
                label="Item Quantity",
                description="Defaults to being unlimited if left empty.",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="item_amount",
                    max_length=10,
                    required=False,
                    placeholder="Unlimited",
                ),
            ),
            discord.ui.Label(
                label="Item Image",
                description="The image URL of the item.",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="item_image",
                    required=False,
                    value=item.image,
                ),
            ),
            title="Edit Gacha Item",
            custom_id=f"edit_gacha_item-{item.id}",
        )

        self.item = item

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        responses = utils.parse_modal_responses(self)

        name: str = utils.replace_smart_punc(responses["item_name"])
        description: str = responses["item_description"]
        str_amount: str = (
            responses["item_amount"].strip() if responses.get("item_amount") else "-1"
        )
        image: str | None = (
            responses["item_image"].strip() if responses.get("item_image") else None
        )

        if isinstance(responses["item_rarity"], list):
            str_rarity: str = responses["item_rarity"][0]
        else:
            str_rarity: str = responses["item_rarity"]

        # quick check to make sure item still exists
        item = await models.GachaItem.get_or_none(
            id=self.item.id, guild_id=inter.guild_id
        )
        if not item:
            raise utils.BadArgument("This item no longer exists.")

        if name.lower() != item.name.lower() and await models.GachaItem.exists(
            guild_id=int(inter.guild_id), name__iexact=name
        ):
            raise utils.BadArgument(
                f"An item named `{name}` already exists in this server."
            )

        try:
            rarity = models.Rarity[str_rarity.upper()]
        except (KeyError, ValueError):
            raise utils.BadArgument(
                "Invalid rarity. Rarity must be one of: common, uncommon, rare, epic,"
                " legendary."
            ) from None

        try:
            amount = int(str_amount)
            if amount < -1:
                raise ValueError
        except ValueError:
            raise utils.BadArgument("Quantity must be a positive number.") from None

        if amount > 999:
            raise utils.BadArgument(
                "This amount is too high. Please set an amount at or lower than 999, or"
                " leave the value empty to have an unlimited amount."
            )

        if image and not utils.HTTP_URL_REGEX.fullmatch(image):
            raise utils.BadArgument("The image given must be a valid URL.")

        await models.GachaItem.filter(id=item.id).update(
            name=name,
            description=description,
            rarity=rarity,
            amount=amount,
            image=image,
        )

        if name != item.name:
            text = discord.ui.TextDisplay(
                f"Edited item `{discord.utils.escape_markdown(item.name)}`, now renamed"
                f" to `{discord.utils.escape_markdown(name)}`."
            )
        else:
            text = discord.ui.TextDisplay(
                f"Edited item `{discord.utils.escape_markdown(name)}`."
            )

        container = discord.ui.Container(
            discord.ui.Section(
                text,
                accessory=discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label="View Item",
                    custom_id=f"gacha-item-{item.id}-admin",
                ),
            ),
            color=inter.client.color,
        )
        await inter.respond(view=utils.quick_view(container))


def gacha_item_button(custom_id: str) -> classes.ButtonToModal:
    return classes.ButtonToModal(
        text="Add gacha items with this button!",
        button=discord.ui.Button(
            style=discord.ButtonStyle.green,
            label="Create item",
            custom_id=custom_id,
        ),
        modal=CreateGachaItemModal,
    )
