"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import collections
import importlib

import interactions as ipy
import tansy
import typing_extensions as typing

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.text_utils as text_utils
import common.utils as utils


class ItemsManagement(utils.Extension):
    def __init__(self, bot: utils.THIABase) -> None:
        self.name = "Items Management"
        self.bot: utils.THIABase = bot

    @staticmethod
    def create_item_create_modal() -> ipy.Modal:
        return ipy.Modal(
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
                max_length=1024,
            ),
            ipy.InputText(
                label="Item Image",
                style=ipy.TextStyles.SHORT,
                custom_id="item_image",
                placeholder="The image URL of the item.",
                required=False,
            ),
            ipy.ShortText(
                label="Is this item takeable?",
                custom_id="item_takeable",
                value="yes",
                max_length=10,
            ),
            title="Create Item",
            custom_id="thia-modal:create_item",
        )

    config = tansy.SlashCommand(
        name="items-config",
        description="Handles configuration of items.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        "info",
        sub_cmd_description=(
            "Lists out the items configuration settings for the server."
        ),
    )
    async def items_info(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"items": True})
        if typing.TYPE_CHECKING:
            assert config.items is not None

        options = (
            f"Enabled: {utils.yesno_friendly_str(config.items.enabled)}",
            f"Auto-Suggestions: {utils.toggle_friendly_str(config.items.autosuggest)}",
        )
        await ctx.send(
            embed=utils.make_embed("\n".join(options), title="Items Configuration")
        )

    @config.subcommand(
        "toggle",
        sub_cmd_description="Enables or disables the items system.",
    )
    async def items_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = tansy.Option(
            "Should the items system be turned on or off?",
            name="toggle",
            choices=[
                ipy.SlashCommandChoice("on", "on"),
                ipy.SlashCommandChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        config = await ctx.fetch_config({"items": True})
        if typing.TYPE_CHECKING:
            assert config.items is not None

        if toggle and not config.player_role:
            raise utils.CustomCheckFailure(
                "Player role not set. Please set it with"
                f" {self.bot.mention_command('config player')} first."
            )

        await models.ItemsConfig.prisma().update(
            data={"enabled": toggle},
            where={"guild_id": ctx.guild.id},
        )

        await ctx.send(
            embed=utils.make_embed(
                f"Items system turned {utils.toggle_friendly_str(toggle)}."
            )
        )

    @config.subcommand(
        "auto-suggestions",
        sub_cmd_description=(
            "Enables or disables auto-suggestions when investigating items."
        ),
    )
    async def auto_suggestions_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = tansy.Option(
            "Should auto-suggestions be turned on or off?",
            name="toggle",
            choices=[
                ipy.SlashCommandChoice("on", "on"),
                ipy.SlashCommandChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        config = await ctx.fetch_config({"items": True})
        if typing.TYPE_CHECKING:
            assert config.items is not None

        await models.ItemsConfig.prisma().update(
            data={"autosuggest": toggle},
            where={"guild_id": ctx.guild.id},
        )

        await ctx.send(
            embed=utils.make_embed(
                f"Auto-suggestions turned {utils.toggle_friendly_str(toggle)}."
            )
        )

    @config.subcommand(
        "help", sub_cmd_description="Tells you how to set up the items system."
    )
    async def items_help(self, ctx: utils.THIASlashContext) -> None:
        embed = utils.make_embed(
            "To set up the items system, follow the items setup guide below.",
            title="Setup Bot",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.LINK,
            label="Items Setup Guide",
            url="https://pythia.astrea.cc/setup/items_setup",
        )
        await ctx.send(embeds=embed, components=button)

    manage = tansy.SlashCommand(
        name="items-manage",
        description="Handles management of items.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @manage.subcommand(
        "create-item",
        sub_cmd_description="Creates an investigable item.",
    )
    @ipy.auto_defer(enabled=False)
    async def item_create(
        self,
        ctx: utils.THIASlashContext,
        _send_button: str = tansy.Option(
            "Should a button be sent that allows for repeatedly creating items?",
            name="send_button",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="yes",
        ),
    ) -> None:
        send_button = _send_button == "yes"

        if send_button:
            await ctx.defer()

            button = ipy.Button(
                style=ipy.ButtonStyle.GREEN,
                label="Create item",
                custom_id="thia-button:create_item",
            )
            await ctx.send(
                embed=utils.make_embed("Create items via the button below!"),
                components=button,
            )
            return

        await ctx.send_modal(self.create_item_create_modal())

    @ipy.component_callback("thia-button:create_item")
    async def on_create_item_button(self, ctx: ipy.ComponentContext) -> None:
        await ctx.send_modal(self.create_item_create_modal())

    @ipy.modal_callback("thia-modal:create_item")
    async def on_create_item_modal(self, ctx: ipy.ModalContext) -> None:
        name = text_utils.replace_smart_punc(ctx.responses["item_name"])

        if (
            await models.ItemsSystemItem.prisma().count(
                where={"guild_id": int(ctx.guild_id), "name": name}
            )
            > 0
        ):
            await ctx.send(
                embed=utils.error_embed_generate(
                    f"An item named `{text_utils.escape_markdown(name)}` already"
                    " exists in this server."
                )
            )
            return

        try:
            takeable = utils.convert_to_bool(ctx.responses["item_takeable"])
        except ipy.errors.BadArgument:
            await ctx.send(
                embed=utils.error_embed_generate(
                    "Invalid value for if the item is takeable. Giving a simple"
                    " 'yes' or 'no' will work."
                )
            )
            return

        image: typing.Optional[str] = (
            ctx.responses.get("item_image", "").strip() or None
        )
        if image and not text_utils.HTTP_URL_REGEX.fullmatch(image):
            raise ipy.errors.BadArgument("The image given must be a valid URL.")

        await models.ItemsConfig.get_or_create(ctx.guild_id)  # needs to exist

        await models.ItemsSystemItem.prisma().create(
            data={
                "name": name,
                "description": ctx.responses["item_description"],
                "image": image,
                "takeable": takeable,
                "guild_id": ctx.guild_id,
            }
        )

        await ctx.send(
            embed=utils.make_embed(
                f"Created item `{text_utils.escape_markdown(name)}`."
            ),
        )

    @manage.subcommand(
        "edit-item", sub_cmd_description="Sends a prompt to edit an item."
    )
    @ipy.auto_defer(enabled=False)
    async def edit_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to edit.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.prisma().find_first(
            where={"guild_id": ctx.guild_id, "name": name}
        )
        if not item:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

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
                max_length=1024,
                value=item.description,
            ),
            ipy.InputText(
                label="Item Image",
                style=ipy.TextStyles.SHORT,
                custom_id="item_image",
                placeholder="The image URL of the item.",
                required=False,
                value=item.image,
            ),
            ipy.ShortText(
                label="Is this item takeable?",
                custom_id="item_takeable",
                value=utils.yesno_friendly_str(item.takeable),
                max_length=10,
            ),
            title="Edit Item",
            custom_id=f"thia:edit_item-{item.id}",
        )
        await ctx.send_modal(modal)

    @ipy.listen("modal_completion")
    async def on_modal_edit_item(self, event: ipy.events.ModalCompletion) -> None:
        ctx = event.ctx

        if ctx.custom_id.startswith("thia:edit_item-"):
            item_id = int(ctx.custom_id.removeprefix("thia:edit_item-"))

            item = await models.ItemsSystemItem.prisma().find_unique(
                where={"id": int(item_id)}
            )
            if not item:
                raise ipy.errors.BadArgument("This item no longer exists.")

            old_name = item.name
            name = text_utils.replace_smart_punc(ctx.responses["item_name"])

            if (
                name != old_name
                and await models.ItemsSystemItem.prisma().count(
                    where={"guild_id": int(ctx.guild_id), "name": name}
                )
                > 0
            ):
                await ctx.send(
                    embed=utils.error_embed_generate(
                        f"An item named `{name}` already exists in this server."
                    )
                )
                return

            try:
                takeable = utils.convert_to_bool(ctx.responses["item_takeable"])
            except ipy.errors.BadArgument:
                await ctx.send(
                    embed=utils.error_embed_generate(
                        "Invalid value for if the item is takeable. Giving a simple"
                        " 'yes' or 'no' will work."
                    )
                )
                return

            image: typing.Optional[str] = (
                ctx.responses.get("item_image", "").strip() or None
            )
            if image and not text_utils.HTTP_URL_REGEX.fullmatch(image):
                raise ipy.errors.BadArgument("The image given must be a valid URL.")

            item.name = name
            item.description = ctx.responses["item_description"]
            item.image = image
            item.takeable = takeable
            await item.save()

            if name != old_name:
                await ctx.send(
                    embed=utils.make_embed(
                        f"Edited item `{text_utils.escape_markdown(old_name)}`, renamed"
                        f" to `{text_utils.escape_markdown(name)}`."
                    )
                )
            else:
                await ctx.send(
                    embed=utils.make_embed(
                        f"Edited item `{text_utils.escape_markdown(name)}`."
                    )
                )

    @manage.subcommand(
        "list-items",
        sub_cmd_description="Lists all items in the server.",
    )
    async def list_items(self, ctx: utils.THIASlashContext) -> None:
        items = await models.ItemsSystemItem.prisma().find_many(
            where={"guild_id": ctx.guild_id}
        )

        if not items:
            raise utils.CustomCheckFailure("This server has no items to show.")

        items_list = [
            f"**{i.name}**: {models.short_desc(i.description)}"
            for i in sorted(items, key=lambda i: i.name.lower())
        ]
        if len(items_list) > 30:
            chunks = [items_list[x : x + 30] for x in range(0, len(items_list), 30)]
            embeds = [
                utils.make_embed(
                    "\n".join(chunk),
                    title="Items",
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
                    title="Items",
                )
            )

    @manage.subcommand(
        "list-placed-items",
        sub_cmd_description="Lists all items currently placed in channels.",
    )
    async def list_placed_items(self, ctx: utils.THIASlashContext) -> None:
        placed_items = await models.ItemRelation.prisma().find_many(
            where={
                "guild_id": ctx.guild_id,
                "object_type": models.ItemsRelationType.CHANNEL,
            },
            include={"item": True},
        )

        if not placed_items:
            raise utils.CustomCheckFailure(
                "This server has no items placed in channels."
            )

        items_dict: collections.defaultdict[int, collections.Counter[str]] = (
            collections.defaultdict(collections.Counter)
        )

        for item in placed_items:
            items_dict[item.object_id][item.item.name] += 1

        str_builder: collections.deque[str] = collections.deque()

        for channel_id in items_dict.keys():
            str_builder.append(f"<#{channel_id}>:")

            for k, v in sorted(
                items_dict[channel_id].items(), key=lambda i: i[0].lower()
            ):
                str_builder.append(f"- **{k}** x{v}")

            str_builder.append("")

        pag = help_tools.HelpPaginator.create_from_list(
            ctx.bot, list(str_builder), timeout=300
        )
        if len(pag.pages) == 1:
            embed = pag.pages[0].to_embed()  # type: ignore
            embed.timestamp = ipy.Timestamp.utcnow()
            embed.color = ctx.bot.color
            embed.title = None
            await ctx.send(embeds=embed)
            return

        pag.show_callback_button = False
        pag.show_select_menu = False
        pag.default_color = ctx.bot.color
        await pag.send(ctx)

    @manage.subcommand(
        "list-items-in-channel",
        sub_cmd_description="Lists all items in a channel.",
    )
    async def list_items_in_channel(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel to list items for.",
        ),
    ) -> None:
        channel_items = await models.ItemRelation.prisma().find_many(
            where={"object_id": channel.id},
            include={"item": True},
        )
        if not channel_items:
            raise utils.CustomCheckFailure("This channel has no items placed in it.")

        items_counter: collections.Counter[str] = collections.Counter()

        for item in channel_items:
            items_counter[item.item.name] += 1

        str_builder: collections.deque[str] = collections.deque()

        for k, v in sorted(items_counter.items(), key=lambda i: i[0].lower()):
            str_builder.append(
                f"**{k}** x{v}: {models.short_desc(item.item.description)}"
            )

        pag = help_tools.HelpPaginator.create_from_list(
            ctx.bot, list(str_builder), timeout=300
        )
        for page in pag.pages:
            page.title = f"Items in #{channel.name}"

        if len(pag.pages) == 1:
            embed = pag.pages[0].to_embed()  # type: ignore
            embed.timestamp = ipy.Timestamp.utcnow()
            embed.color = ctx.bot.color
            await ctx.send(embeds=embed)
            return

        pag.show_callback_button = False
        pag.show_select_menu = False
        pag.default_color = ctx.bot.color
        await pag.send(ctx)

    @manage.subcommand(
        "place-item-in-channel",
        sub_cmd_description="Places an item in a channel.",
    )
    async def place_item_in_channel(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to place.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel to place the item in.",
        ),
        amount: int = tansy.Option(
            "The amount of the item to place. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.prisma().find_first(
            where={"guild_id": ctx.guild_id, "name": name}
        )
        if not item:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        if not item.takeable and amount > 1:
            raise utils.CustomCheckFailure(
                "This item is not takeable, so you can only place one of it per"
                " channel."
            )

        if await models.ItemRelation.prisma().count(
            where={"item_id": item.id, "object_id": channel.id}
        ) >= (50 if item.takeable else 1):
            if item.takeable:
                raise utils.CustomCheckFailure(
                    "You cannot place more than 50 of the same item in a channel."
                )
            raise utils.CustomCheckFailure(
                "You cannot place more than 1 of a non-takeable item in a channel."
            )

        async with self.bot.db.batch_() as batch:
            for _ in range(amount):
                batch.prismaitemrelation.create(
                    data={
                        "item": {"connect": {"id": item.id}},
                        "guild_id": ctx.guild_id,
                        "object_id": int(channel.id),
                        "object_type": models.ItemsRelationType.CHANNEL,
                    }
                )

        await ctx.send(
            embed=utils.make_embed(
                f"Placed {amount} of item `{text_utils.escape_markdown(name)}` in"
                f" <#{channel.id}>."
            )
        )

    @manage.subcommand(
        "remove-item-from-channel",
        sub_cmd_description="Removes an item from a channel.",
    )
    async def remove_item_from_channel(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel to remove the item from.",
        ),
        name: str = tansy.Option(
            "The name of the item to remove.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        amount: int = tansy.Option(
            "The amount of the item to remove. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.prisma().find_first(
            where={"guild_id": ctx.guild_id, "name": name}
        )
        if not item:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        total = await models.ItemRelation.prisma().count(
            where={"item_id": item.id, "object_id": channel.id}
        )

        if amount >= total:
            amount = total
            # fast path
            await models.ItemRelation.prisma().delete_many(
                where={"item_id": item.id, "object_id": channel.id}
            )
        elif total == 0:
            raise utils.CustomCheckFailure(
                "There are no items of this type in the channel."
            )
        else:
            to_drop = await models.ItemRelation.prisma().find_many(
                where={"item_id": item.id, "object_id": channel.id},
                take=amount,
            )
            await models.ItemRelation.prisma().delete_many(
                where={"id": {"in": [i.id for i in to_drop]}}
            )

        await ctx.send(
            embed=utils.make_embed(
                f"Removed {amount} of item `{text_utils.escape_markdown(name)}` from"
                f" <#{channel.id}>."
            )
        )

    @manage.subcommand(
        "view-item",
        sub_cmd_description="Shows information about an item.",
    )
    async def view_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to view.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        _view_possessors: str = tansy.Option(
            "Should the possessors of this item (channels and users) be shown?",
            name="view_possessors",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        view_possessors = _view_possessors == "yes"

        item = await models.ItemsSystemItem.prisma().find_first(
            where={"guild_id": ctx.guild_id, "name": name},
            include={"relations": view_possessors},
        )
        if not item:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        embeds = item.embeds()

        if len(embeds) > 1:
            pag = help_tools.HelpPaginator.create_from_embeds(
                self.bot, *embeds, timeout=120
            )
            pag.show_callback_button = False
            await pag.send(ctx)
        else:
            await ctx.send(embeds=embeds)

    @manage.subcommand(
        "delete-item",
        sub_cmd_description="Deletes an item.",
    )
    async def delete_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to delete.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        count = await models.ItemsSystemItem.prisma().delete_many(
            where={"guild_id": ctx.guild_id, "name": name}
        )
        if count == 0:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        await ctx.send(
            embed=utils.make_embed(
                f"Deleted item `{text_utils.escape_markdown(name)}`."
            )
        )

    @manage.subcommand(
        "clear-items-in-channel",
        sub_cmd_description="Clears all items in a channel.",
    )
    async def clear_items_in_channel(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel to clear items from.",
        ),
    ) -> None:
        count = await models.ItemRelation.prisma().delete_many(
            where={"object_id": channel.id}
        )
        if count == 0:
            raise utils.CustomCheckFailure(
                "There are no items to clear from this channel."
            )

        await ctx.send(
            embed=utils.make_embed(f"Cleared all items from <#{channel.id}>.")
        )

    @manage.subcommand(
        "clear-everything",
        sub_cmd_description=(
            "Clears ALL items data (except config data) in this server."
            " Use with caution!"
        ),
    )
    async def clear_everything(
        self,
        ctx: utils.THIASlashContext,
        confirm: bool = tansy.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise ipy.errors.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        items_amount = await models.ItemsSystemItem.prisma().delete_many(
            where={"guild_id": ctx.guild_id}
        )

        if items_amount <= 0:
            raise utils.CustomCheckFailure("There's no items data to clear!")

        await ctx.send(embed=utils.make_embed("All items data cleared."))

    @edit_item.autocomplete("name")
    @place_item_in_channel.autocomplete("name")
    @view_item.autocomplete("name")
    @delete_item.autocomplete("name")
    async def _item_name_autocomplete(self, ctx: ipy.AutocompleteContext) -> None:
        return await fuzzy.autocomplete_item(
            ctx,
            **ctx.kwargs,
        )

    @remove_item_from_channel.autocomplete("name")
    async def _channel_item_name_autocomplete(
        self, ctx: ipy.AutocompleteContext
    ) -> None:
        return await fuzzy.autocomplete_item_channel(
            ctx,
            **ctx.kwargs,
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(text_utils)
    importlib.reload(help_tools)
    importlib.reload(fuzzy)
    ItemsManagement(bot)
