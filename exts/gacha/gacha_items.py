"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import importlib
import io

import aiohttp
import interactions as ipy
import modal_backport as modalb
import msgspec
import orjson
import tansy
import typing_extensions as typing
from tortoise.transactions import in_transaction

import common.classes as classes
import common.exports as exports
import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.text_utils as text_utils
import common.utils as utils


class GachaItems(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Gacha Items"

        self.gacha_item_create_modal = ipy.Modal(
            ipy.InputText(
                label="Item Name",
                style=ipy.TextStyles.SHORT,
                custom_id="item_name",
                max_length=64,
            ),
            ipy.InputText(
                label="Item Description",
                style=ipy.TextStyles.PARAGRAPH,
                custom_id="item_description",
                max_length=3500,
            ),
            ipy.InputText(
                label="Item Rarity",
                style=ipy.TextStyles.SHORT,
                custom_id="item_rarity",
                max_length=10,
                value="Common",
                placeholder="Common, uncommon, rare, epic, legendary.",
            ),
            ipy.InputText(
                label="Item Quantity",
                style=ipy.TextStyles.SHORT,
                custom_id="item_amount",
                max_length=10,
                placeholder="Defaults to being unlimited.",
                required=False,
            ),
            ipy.InputText(
                label="Item Image",
                style=ipy.TextStyles.SHORT,
                custom_id="item_image",
                placeholder="The image URL of the item.",
                required=False,
            ),
            title="Add Gacha Item",
            custom_id="add_gacha_item",
        )

        self.beta_gacha_item_create_modal = modalb.Modal(
            ipy.InputText(
                label="Item Name",
                style=ipy.TextStyles.SHORT,
                custom_id="item_name",
                max_length=64,
            ),
            ipy.InputText(
                label="Item Description",
                style=ipy.TextStyles.PARAGRAPH,
                custom_id="item_description",
                max_length=3500,
            ),
            modalb.LabelComponent(
                label="Item Rarity",
                component=modalb.StringSelectMenu(
                    ipy.StringSelectOption(
                        label="Common", value="Common", default=True
                    ),
                    ipy.StringSelectOption(label="Uncommon", value="Uncommon"),
                    ipy.StringSelectOption(label="Rare", value="Rare"),
                    ipy.StringSelectOption(label="Epic", value="Epic"),
                    ipy.StringSelectOption(label="Legendary", value="Legendary"),
                    custom_id="item_rarity",
                    placeholder="Select the item rarity.",
                    min_values=1,
                    max_values=1,
                ),
            ),
            modalb.LabelComponent(
                label="Item Quantity",
                description="Defaults to being unlimited if left empty.",
                component=modalb.InputText(
                    style=ipy.TextStyles.SHORT,
                    custom_id="item_amount",
                    max_length=10,
                    required=False,
                    placeholder="Unlimited",
                ),
            ),
            modalb.LabelComponent(
                label="Item Image",
                description="The image URL of the item.",
                component=modalb.InputText(
                    style=ipy.TextStyles.SHORT,
                    custom_id="item_image",
                    required=False,
                ),
            ),
            title="Add Gacha Item",
            custom_id="add_gacha_item",
        )

    manage = tansy.SlashCommand(
        name="gacha-manage",
        description="Handles management of gacha mechanics.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @manage.subcommand(
        "add-item",
        sub_cmd_description="Adds an item to the gacha.",
    )
    @ipy.auto_defer(enabled=False)
    async def gacha_item_add(
        self,
        ctx: utils.THIASlashContext,
        _send_button: str = tansy.Option(
            "Should a button be sent that allows for repeatedly adding items?",
            name="send_button",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="yes",
        ),
    ) -> None:
        send_button = _send_button == "yes"

        config = await ctx.fetch_config()

        if send_button:
            await ctx.defer()

            if config.enabled_beta:
                await ctx.send(
                    components=classes.ContainerComponent(
                        ipy.SectionComponent(
                            components=[
                                ipy.TextDisplayComponent(
                                    "Add gacha items with this button!"
                                )
                            ],
                            accessory=ipy.Button(
                                style=ipy.ButtonStyle.GREEN,
                                label="Add Item",
                                custom_id="thia:add-gacha-new",
                            ),
                        ),
                        accent_color=self.bot.color.value,
                    )
                )
            else:
                await ctx.send(
                    embed=utils.make_embed("Add gacha items via the button below!"),
                    components=ipy.Button(
                        style=ipy.ButtonStyle.GREEN,
                        label="Add Gacha Item",
                        custom_id="thia-button:add_gacha_item",
                    ),
                )
            return

        if config.enabled_beta:
            await ctx.send_modal(self.beta_gacha_item_create_modal)
        else:
            await ctx.send_modal(self.gacha_item_create_modal)

    @ipy.component_callback("thia-button:add_gacha_item")
    async def add_gacha_item_button(self, ctx: ipy.ComponentContext) -> None:
        await ctx.send_modal(self.gacha_item_create_modal)

    @ipy.component_callback("thia:add-gacha-new")
    async def add_gacha_item_beta_button(self, ctx: ipy.ComponentContext) -> None:
        await ctx.send_modal(self.beta_gacha_item_create_modal)

    @ipy.modal_callback("add_gacha_item")
    async def add_gacha_item_modal(self, ctx: utils.THIAModalContext) -> None:
        name: str = ctx.responses["item_name"]
        description: str = ctx.responses["item_description"]
        str_amount: str = ctx.responses.get("item_amount", "-1").strip() or "-1"
        image: str | None = ctx.responses.get("item_image", "").strip() or None

        if isinstance(ctx.responses["item_rarity"], list):
            str_rarity: str = ctx.responses["item_rarity"][0]
        else:
            str_rarity: str = ctx.responses["item_rarity"]

        if await models.GachaItem.exists(guild_id=ctx.guild_id, name=name):
            raise ipy.errors.BadArgument("An item with that name already exists.")

        try:
            rarity = models.Rarity[str_rarity.upper()]
        except (KeyError, ValueError):
            raise ipy.errors.BadArgument(
                "Invalid rarity. Rarity must be one of: common, uncommon, rare, epic,"
                " legendary."
            ) from None

        try:
            amount = int(str_amount)
            if amount < -1:
                raise ValueError
        except ValueError:
            raise ipy.errors.BadArgument(
                "Quantity must be a positive number."
            ) from None

        if amount > 999:
            raise ipy.errors.BadArgument(
                "This amount is too high. Please set an amount at or lower than 999, or"
                " leave the value empty to have an unlimited amount."
            )

        if image and not text_utils.HTTP_URL_REGEX.fullmatch(image):
            raise ipy.errors.BadArgument("The image given must be a valid URL.")

        # some configs needs to exist, lets make sure they do
        await ctx.fetch_config({"gacha": True})

        await models.GachaItem.create(
            guild_id=ctx.guild_id,
            name=name,
            description=description,
            rarity=rarity,
            amount=amount,
            image=image,
        )

        await ctx.send(embed=utils.make_embed(f"Added item {name} to the gacha."))

    @manage.subcommand(
        "edit-item",
        sub_cmd_description="Edits an item in the gacha.",
    )
    @ipy.auto_defer(enabled=False)
    async def gacha_item_edit(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option("The name of the item to edit.", autocomplete=True),
    ) -> None:
        config = await ctx.fetch_config()

        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise ipy.errors.BadArgument("No item with that name exists.")

        if config.enabled_beta:
            string_select_options: list[ipy.StringSelectOption] = []
            for rarity_name in models.Rarity.__members__.keys():
                option = ipy.StringSelectOption(
                    label=rarity_name.title(),
                    value=rarity_name.title(),
                )
                if rarity_name.upper() == item.rarity.name:
                    option.default = True
                string_select_options.append(option)

            modal = modalb.Modal(
                ipy.InputText(
                    label="Item Name",
                    style=ipy.TextStyles.SHORT,
                    custom_id="item_name",
                    max_length=64,
                    value=item.name,
                ),
                ipy.InputText(
                    label="Item Description",
                    style=ipy.TextStyles.PARAGRAPH,
                    custom_id="item_description",
                    max_length=3500,
                    value=item.description,
                ),
                modalb.LabelComponent(
                    label="Item Rarity",
                    component=modalb.StringSelectMenu(
                        *string_select_options,
                        custom_id="item_rarity",
                        placeholder="Select the item rarity.",
                        min_values=1,
                        max_values=1,
                    ),
                ),
                modalb.LabelComponent(
                    label="Item Quantity",
                    description="Defaults to being unlimited if left empty.",
                    component=modalb.InputText(
                        style=ipy.TextStyles.SHORT,
                        custom_id="item_amount",
                        max_length=10,
                        required=False,
                        placeholder="Unlimited",
                        value=str(item.amount) if item.amount != -1 else ipy.MISSING,
                    ),
                ),
                modalb.LabelComponent(
                    label="Item Image",
                    description="The image URL of the item.",
                    component=modalb.InputText(
                        style=ipy.TextStyles.SHORT,
                        custom_id="item_image",
                        required=False,
                        value=item.image if item.image else ipy.MISSING,
                    ),
                ),
                title="Edit Gacha Item",
                custom_id=f"edit_gacha_item-{item.id}",
            )
        else:
            modal = ipy.Modal(
                ipy.InputText(
                    label="Item Name",
                    style=ipy.TextStyles.SHORT,
                    custom_id="item_name",
                    max_length=64,
                    value=item.name,
                ),
                ipy.InputText(
                    label="Item Description",
                    style=ipy.TextStyles.PARAGRAPH,
                    custom_id="item_description",
                    max_length=3500,
                    value=item.description,
                ),
                ipy.InputText(
                    label="Item Rarity",
                    style=ipy.TextStyles.SHORT,
                    custom_id="item_rarity",
                    max_length=10,
                    value=item.rarity.name.title(),
                    placeholder="Common, uncommon, rare, epic, legendary.",
                ),
                ipy.InputText(
                    label="Item Quantity",
                    style=ipy.TextStyles.SHORT,
                    custom_id="item_amount",
                    max_length=10,
                    placeholder="Defaults to being unlimited.",
                    required=False,
                    value=str(item.amount) if item.amount != -1 else ipy.MISSING,
                ),
                ipy.InputText(
                    label="Item Image",
                    style=ipy.TextStyles.SHORT,
                    custom_id="item_image",
                    placeholder="The image URL of the item.",
                    required=False,
                    value=item.image if item.image else ipy.MISSING,
                ),
                title="Edit Gacha Item",
                custom_id=f"edit_gacha_item-{item.id}",
            )
        await ctx.send_modal(modal)

    @ipy.listen("modal_completion")
    @utils.modal_event_error_handler
    async def on_modal_edit_gacha_item(self, event: ipy.events.ModalCompletion) -> None:
        ctx = event.ctx

        if not ctx.custom_id.startswith("edit_gacha_item-"):
            return

        item_id = int(ctx.custom_id.split("-")[1])
        name: str = ctx.kwargs["item_name"]
        description: str = ctx.kwargs["item_description"]
        str_amount: str = ctx.kwargs.get("item_amount", "-1").strip() or "-1"
        image: str | None = ctx.kwargs.get("item_image", "").strip() or None

        if isinstance(ctx.responses["item_rarity"], list):
            str_rarity: str = ctx.responses["item_rarity"][0]
        else:
            str_rarity: str = ctx.responses["item_rarity"]

        if not await models.GachaItem.exists(id=item_id, guild_id=ctx.guild_id):
            raise ipy.errors.BadArgument("The item no longer exists.")

        try:
            rarity = models.Rarity[str_rarity.upper()]
        except (KeyError, ValueError):
            raise ipy.errors.BadArgument(
                "Invalid rarity. Rarity must be one of: common, uncommon, rare, epic,"
                " legendary."
            ) from None

        try:
            amount = int(str_amount)
            if amount < -1:
                raise ValueError
        except ValueError:
            raise ipy.errors.BadArgument(
                "Quantity must be a positive number."
            ) from None

        if amount > 999:
            raise ipy.errors.BadArgument(
                "This amount is too high. Please set an amount at or lower than 999, or"
                " leave the value empty to have an unlimited amount."
            )

        if image and not text_utils.HTTP_URL_REGEX.fullmatch(image):
            raise ipy.errors.BadArgument("The image given must be a valid URL.")

        await models.GachaItem.filter(id=item_id).update(
            name=name,
            description=description,
            rarity=rarity,
            amount=amount,
            image=image,
        )

        await ctx.send(embed=utils.make_embed(f"Edited item {name}."))

    @manage.subcommand(
        "delete-item",
        sub_cmd_description="Deletes an item from the gacha.",
    )
    async def gacha_item_delete(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option("The name of the item to delete.", autocomplete=True),
    ) -> None:
        amount = await models.GachaItem.filter(
            guild_id=ctx.guild_id, name=name
        ).delete()

        if amount <= 0:
            raise ipy.errors.BadArgument("No item with that name exists.")

        await ctx.send(embed=utils.make_embed(f"Deleted {name}."))

    gacha_item_remove = utils.alias(
        gacha_item_delete,
        "gacha-manage remove-item",
        "Removes an item from the gacha. Alias of /gacha-manage delete-item.",
    )

    @manage.subcommand("view-item", sub_cmd_description="Views an item in the gacha.")
    async def gacha_view_single_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option("The name of the item to view.", autocomplete=True),
    ) -> None:
        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise ipy.errors.BadArgument("No item with that name exists.")

        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None
            assert config.names is not None

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)

        await ctx.send(embed=item.embed(config.names, rarities, show_amount=True))

    @manage.subcommand(
        "list-items", sub_cmd_description="Lists all gacha items for this server."
    )
    async def gacha_view_items(
        self,
        ctx: utils.THIASlashContext,
        sort_by: str = tansy.Option(
            "What should the items be sorted by?",
            choices=[
                ipy.SlashCommandChoice("Name", "name"),
                ipy.SlashCommandChoice("Rarity", "rarity"),
                ipy.SlashCommandChoice("Time Created", "time_created"),
            ],
            default="name",
        ),
        mode: str = tansy.Option(
            "The mode to show the items in.",
            choices=[
                ipy.SlashCommandChoice("Modern", "modern"),
                ipy.SlashCommandChoice("Spacious (Modern)", "spacious"),
                ipy.SlashCommandChoice("Cozy", "cozy"),
                ipy.SlashCommandChoice("Compact", "compact"),
            ],
            default="modern",
        ),
    ) -> None:
        if mode not in ("cozy", "compact", "modern", "spacious"):
            raise ipy.errors.BadArgument("Invalid mode.")
        if sort_by not in ("name", "rarity", "time_created"):
            raise ipy.errors.BadArgument("Invalid option for sorting.")

        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        items = await models.GachaItem.filter(guild_id=ctx.guild_id)
        if not items:
            raise utils.CustomCheckFailure("This server has no items to show.")

        if sort_by == "name":
            sorted_items = sorted(items, key=lambda i: i.name.lower())
        elif sort_by == "rarity":
            sorted_items = sorted(items, key=lambda i: (i.rarity.value, i.name.lower()))
        else:
            sorted_items = sorted(items, key=lambda i: (i.id))

        if mode == "modern" or mode == "spacious":
            if mode == "spacious":
                components: list[ipy.BaseComponent] = [
                    ipy.SectionComponent(
                        components=[
                            ipy.TextDisplayComponent(
                                f"**{text_utils.escape_markdown(item.name)}**{f' ({item.amount} remaining)' if item.amount != -1 else ''}\n-#"
                                f" {config.names.rarity_name(item.rarity)} ●"
                                f" {models.short_desc(item.description, length=50)}"
                            )
                        ],
                        accessory=ipy.Button(
                            style=ipy.ButtonStyle.GRAY,
                            label="View",
                            custom_id=f"gacha-item-{item.id}-admin",
                        ),
                    )
                    for item in sorted_items
                ]
                max_num = 10
            else:
                components: list[ipy.BaseComponent] = [
                    ipy.TextDisplayComponent(
                        f"**{text_utils.escape_markdown(item.name)}**{f' ({item.amount} remaining)' if item.amount != -1 else ''}\n-#"
                        f" {config.names.rarity_name(item.rarity)} ●"
                        f" {models.short_desc(item.description, length=50)}"
                    )
                    for item in sorted_items
                ]
                max_num = 15

            if len(components) > max_num:
                chunks = [
                    components[x : x + max_num]
                    for x in range(0, len(components), max_num)
                ]

                pag = classes.ContainerPaginator(
                    self.bot,
                    title="Gacha Items",
                    pages_data=chunks,
                )
                await pag.send(ctx)
                return

            await ctx.send(
                components=ipy.ContainerComponent(
                    ipy.TextDisplayComponent("Gacha Items"),
                    *components,
                    accent_color=self.bot.color.value,
                ),
                ephemeral=True,
            )
            return

        if mode == "cozy":
            items_list = [
                f"**{text_utils.escape_markdown(i.name)}**{f' ({i.amount} remaining)' if i.amount != -1 else ''}\n-#"
                f" {config.names.rarity_name(i.rarity)} ●"
                f" {models.short_desc(i.description, length=50)}"
                for i in sorted_items
            ]
            max_num = 15
        else:
            items_list = [
                f"**{text_utils.escape_markdown(i.name)}**{f' ({i.amount} remaining)' if i.amount != -1 else ''}:"
                f" {models.short_desc(i.description)}"
                for i in sorted_items
            ]
            max_num = 30

        if len(items_list) > max_num:
            chunks = [
                items_list[x : x + max_num] for x in range(0, len(items_list), max_num)
            ]
            embeds = [
                utils.make_embed(
                    "\n".join(chunk),
                    title="Gacha Items",
                )
                for chunk in chunks
            ]

            pag = help_tools.HelpPaginator.create_from_embeds(
                self.bot, *embeds, timeout=120
            )
            pag.show_callback_button = False
            await pag.send(ctx)
        else:
            await ctx.send(
                embed=utils.make_embed(
                    "\n".join(items_list),
                    title="Gacha Items",
                )
            )

    @manage.subcommand(
        "export-items", sub_cmd_description="Exports all gacha items to a JSON file."
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 60)
    async def gacha_export_items(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        items = await models.GachaItem.filter(guild_id=ctx.guild_id)
        if not items:
            raise utils.CustomCheckFailure("This server has no items to export.")

        items_dict: list[exports.GachaItemDict] = [
            {
                "name": item.name,
                "description": item.description,
                "rarity": item.rarity.value,
                "amount": item.amount,
                "image": item.image,
            }
            for item in items
        ]
        items_json = orjson.dumps(
            {"version": 2, "items": items_dict}, option=orjson.OPT_INDENT_2
        )

        if len(items_json) > 10000000:
            raise utils.CustomCheckFailure(
                "The file is too large to send. Please try again with fewer items."
            )

        items_io = io.BytesIO(items_json)
        items_file = ipy.File(
            items_io,
            file_name=(
                f"gacha_items_{ctx.guild_id}_{int(ctx.id.created_at.timestamp())}.json"
            ),
        )

        try:
            await ctx.send(
                embed=utils.make_embed("Exported items to JSON file."),
                file=items_file,
            )
        finally:
            items_io.close()

    @manage.subcommand(
        "import-items", sub_cmd_description="Imports gacha items from a JSON file."
    )
    async def gacha_import_items(
        self,
        ctx: utils.THIASlashContext,
        json_file: ipy.Attachment = tansy.Option("The JSON file to import."),
        _override: str = tansy.Option(
            "Should pre-existing items with the same name be overriden?",
            name="override",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        override = _override == "yes"

        if not json_file.content_type or not json_file.content_type.startswith(
            "application/json"
        ):
            raise ipy.errors.BadArgument("The file must be a JSON file.")

        async with aiohttp.ClientSession() as session:
            async with session.get(json_file.url) as response:
                if response.status != 200:
                    raise ipy.errors.BadArgument("Failed to fetch the file.")

                try:
                    await response.content.readexactly(10485760 + 1)
                    raise utils.CustomCheckFailure(
                        "This file is over 10 MiB, which is not supported by this bot."
                    )
                except asyncio.IncompleteReadError as e:
                    items_json = e.partial

        try:
            items = exports.handle_gacha_item_data(items_json)
        except msgspec.DecodeError:
            raise ipy.errors.BadArgument(
                "The file is not in the correct format."
            ) from None

        await ctx.fetch_config({"gacha": True})

        async with in_transaction():
            if await models.GachaItem.exists(
                guild_id=ctx.guild_id,
                name__in=[item.name for item in items],
            ):
                if override:
                    await models.GachaItem.filter(
                        guild_id=ctx.guild_id,
                        name__in=[item.name for item in items],
                    ).delete()
                else:
                    raise ipy.errors.BadArgument(
                        "One or more items in the file has a name with an item already"
                        " in this server."
                    )

            to_create: list[models.GachaItem] = []

            for item in items:
                if item.amount < -1:
                    raise ipy.errors.BadArgument(
                        f"The amount for `{text_utils.escape_markdown(item.name)}` must"
                        " be a positive number."
                    )

                if item.amount > 999:
                    raise ipy.errors.BadArgument(
                        f"The amount for `{text_utils.escape_markdown(item.name)}` is"
                        " too high. Please set an amount at or lower than 999, or mark"
                        " the value as -1 to make it unlimited."
                    )

                if item.rarity < 1 or item.rarity > 5:
                    raise ipy.errors.BadArgument(
                        f"The rarity for `{text_utils.escape_markdown(item.name)}` must"
                        " be a number between 1 and 5."
                    )

                if item.image and not text_utils.HTTP_URL_REGEX.fullmatch(item.image):
                    raise ipy.errors.BadArgument(
                        f"The image given for `{text_utils.escape_markdown(item.name)}`"
                        " must be a valid URL."
                    )

                to_create.append(
                    models.GachaItem(
                        guild_id=ctx.guild_id,
                        name=item.name,
                        description=item.description,
                        rarity=item.rarity,
                        amount=item.amount,
                        image=item.image,
                    )
                )

            await models.GachaItem.bulk_create(to_create)

        await ctx.send(embed=utils.make_embed("Imported items from JSON file."))

    @gacha_item_edit.autocomplete("name")
    @gacha_item_delete.autocomplete("name")
    @gacha_view_single_item.autocomplete("name")
    async def _autocomplete_gacha_items(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        return await fuzzy.autocomplete_gacha_item(ctx, **ctx.kwargs)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(text_utils)
    importlib.reload(help_tools)
    importlib.reload(exports)
    importlib.reload(classes)
    GachaItems(bot)
