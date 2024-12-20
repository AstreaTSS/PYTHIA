"""
Copyright 2021-2024 AstreaTSS.
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


class ItemsCommands(utils.Extension):
    def __init__(self, bot: utils.THIABase) -> None:
        self.name = "Items Commands"
        self.bot: utils.THIABase = bot

    items = tansy.SlashCommand(
        name="items",
        description="Hosts public-facing items commands.",
        dm_permission=False,
    )

    @items.subcommand(
        "here",
        sub_cmd_description="Views an item in the current channel.",
    )
    async def items_here(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to view.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        hidden: bool = tansy.Option(
            "Should the result be shown only to you? Defaults to no.",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        config = await ctx.fetch_config({"items": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.items is not None
            assert config.names is not None

        if not config.player_role or not config.items.enabled:
            raise utils.CustomCheckFailure("Items are not enabled in this server.")

        if not ctx.author.has_role(config.player_role):
            raise utils.CustomCheckFailure("You do not have the Player role.")

        item = await models.ItemsSystemItem.prisma().find_first(
            where={
                "name": name,
                "relations": {"some": {"object_id": int(ctx.channel_id)}},
            },
        )
        if not item:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
                " channel."
            )

        count = await models.ItemRelation.prisma().count(
            where={"object_id": int(ctx.channel_id), "item_id": item.id},
        )

        embeds = item.embeds(count=count)
        await ctx.send(embeds=embeds, ephemeral=hidden == "yes")

    @items.subcommand(
        "take",
        sub_cmd_description="Takes an item from the current channel.",
    )
    async def items_take(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to take.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        amount: int = tansy.Option(
            "The amount of the item to take. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
        hidden: bool = tansy.Option(
            "Should the result be shown only to you? Defaults to no.",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        config = await ctx.fetch_config({"items": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.items is not None
            assert config.names is not None

        if not config.player_role or not config.items.enabled:
            raise utils.CustomCheckFailure("Items are not enabled in this server.")

        if not ctx.author.has_role(config.player_role):
            raise utils.CustomCheckFailure("You do not have the Player role.")

        item_relations = await models.ItemRelation.prisma().find_many(
            where={"object_id": int(ctx.channel_id), "item": {"is": {"name": name}}},
            include={"item": True},
        )
        if not item_relations:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
                " channel."
            )

        item = item_relations[0].item
        if typing.TYPE_CHECKING:
            assert item is not None

        if not item.takeable:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` cannot be taken."
            )

        if amount == len(item_relations):
            # fast path
            await models.ItemRelation.prisma().update_many(
                where={"item_id": item.id, "object_id": int(ctx.channel_id)},
                data={
                    "object_id": ctx.author.id,
                    "object_type": models.ItemsRelationType.USER,
                },
            )
        elif amount > len(item_relations):
            raise utils.CustomCheckFailure(
                "You cannot take more items than there are in the channel."
            )
        else:
            to_take = await models.ItemRelation.prisma().find_many(
                where={"item_id": item.id, "object_id": int(ctx.channel_id)},
                take=amount,
            )
            await models.ItemRelation.prisma().update_many(
                where={"id": {"in": [i.id for i in to_take]}},
                data={
                    "object_id": ctx.author.id,
                    "object_type": models.ItemsRelationType.USER,
                },
            )

        await ctx.send(
            embed=utils.make_embed(
                f"Successfully took {amount} of"
                f" `{text_utils.escape_markdown(item.name)}` from the channel."
            ),
            ephemeral=hidden == "yes",
        )

    @items.subcommand(
        "view-inventory",
        sub_cmd_description="Views your inventory.",
    )
    async def view_inventory(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        user_items = await models.ItemRelation.prisma().find_many(
            where={"object_id": ctx.author.id},
            include={"item": True},
        )
        if not user_items:
            raise utils.CustomCheckFailure("You have no items in your inventory.")

        items_counter: collections.Counter[str] = collections.Counter()

        for item in user_items:
            items_counter[item.item.name] += 1

        str_builder: collections.deque[str] = collections.deque()

        for k, v in sorted(items_counter.items(), key=lambda i: i[0].lower()):
            str_builder.append(
                f"**{k}**{f' (x{v})' if v > 1 else ''}:"
                f" {models.short_desc(item.item.description)}"
            )

        pag = help_tools.HelpPaginator.create_from_list(
            ctx.bot, list(str_builder), timeout=300
        )
        for page in pag.pages:
            page.title = "Your Inventory"

        if len(pag.pages) == 1:
            embed = pag.pages[0].to_embed()  # type: ignore
            embed.timestamp = ipy.Timestamp.utcnow()
            embed.color = ctx.bot.color
            await ctx.send(embeds=embed, ephemeral=True)
            return

        pag.show_callback_button = False
        pag.default_color = ctx.bot.color
        await pag.send(ctx, ephemeral=True)

    @items.subcommand(
        "view-item",
        sub_cmd_description="Views an item in your inventory.",
    )
    async def view_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to view.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.prisma().find_first(
            where={"name": name, "relations": {"some": {"object_id": ctx.author.id}}},
        )
        if not item:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` is not in your inventory."
            )

        count = await models.ItemRelation.prisma().count(
            where={"object_id": ctx.author.id, "item_id": item.id},
        )

        embeds = item.embeds(count=count)
        embeds[0].footer = None
        await ctx.send(embeds=embeds, ephemeral=True)

    @items.subcommand(
        "drop",
        sub_cmd_description=(
            "Drops an item from your inventory into the current channel."
        ),
    )
    async def item_drop(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to drop.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        amount: typing.Optional[int] = tansy.Option(
            "The amount of the item to drop. Defaults to 1.",
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
            where={"item_id": item.id, "object_id": ctx.author.id}
        )

        if not amount:
            amount = total
            # fast path
            await models.ItemRelation.prisma().update_many(
                where={"item_id": item.id, "object_id": ctx.author.id},
                data={
                    "object_id": ctx.channel.id,
                    "object_type": models.ItemsRelationType.CHANNEL,
                },
            )
        elif total == 0:
            raise utils.CustomCheckFailure(
                "There are no items of this type in your inventory."
            )
        elif amount > total:
            raise utils.CustomCheckFailure(
                "You cannot drop more items than are in your inventory."
            )
        else:
            to_delete = await models.ItemRelation.prisma().find_many(
                where={"item_id": item.id, "object_id": ctx.author.id},
                take=amount,
            )
            await models.ItemRelation.prisma().update_many(
                where={"id": {"in": [i.id for i in to_delete]}},
                data={
                    "object_id": ctx.channel.id,
                    "object_type": models.ItemsRelationType.CHANNEL,
                },
            )

        await ctx.send(
            embed=utils.make_embed(
                f"Dropped {amount} of item `{text_utils.escape_markdown(name)}` from "
                f"{ctx.author.mention}'s inventory into this channel."
            )
        )

    investigate = tansy.SlashCommand(
        name="investigate",
        description="Hosts aliases for general investigation of items.",
        dm_permission=False,
    )

    @investigate.subcommand(
        "here",
        sub_cmd_description=(
            "Views an item in the current channel. Alias for /items here."
        ),
    )
    async def investigate_here(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to view.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        hidden: bool = tansy.Option(
            "Should the result be shown only to you? Defaults to no.",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        await self.items_here.call_with_binding(
            self.items_here.callback, ctx, name, hidden
        )

    @investigate.subcommand(
        "take",
        sub_cmd_description=(
            "Takes an item from the current channel. Alias for /items take."
        ),
    )
    async def investigate_take(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to take.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        amount: int = tansy.Option(
            "The amount of the item to take. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
        hidden: bool = tansy.Option(
            "Should the result be shown only to you? Defaults to no.",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        await self.items_take.call_with_binding(
            self.items_take.callback, ctx, name, amount, hidden
        )

    inventory = tansy.SlashCommand(
        name="inventory",
        description="Hosts aliases for inventory of items.",
        dm_permission=False,
    )

    @inventory.subcommand(
        "view",
        sub_cmd_description="Views your inventory. Alias for /items view-inventory.",
    )
    async def alias_view_inventory(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        await self.view_inventory.call_with_binding(self.view_inventory.callback, ctx)

    @inventory.subcommand(
        "view-item",
        sub_cmd_description=(
            "Views an item in your inventory. Alias for /items view-item."
        ),
    )
    async def alias_view_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to view.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        await self.view_item.call_with_binding(self.view_item.callback, ctx, name)

    @inventory.subcommand(
        "drop",
        sub_cmd_description=(
            "Drops an item from your inventory into the current channel. Alias for"
            " /items drop."
        ),
    )
    async def alias_item_drop(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the item to drop.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        amount: typing.Optional[int] = tansy.Option(
            "The amount of the item to drop. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
    ) -> None:
        await self.item_drop.call_with_binding(
            self.item_drop.callback, ctx, name, amount
        )

    @items_here.autocomplete("name")
    @investigate_here.autocomplete("name")
    async def _channel_item_name_autocomplete(
        self, ctx: ipy.AutocompleteContext
    ) -> None:
        return await fuzzy.autocomplete_item_channel(
            ctx,
            channel=str(ctx.channel_id),
            **ctx.kwargs,
        )

    @items_take.autocomplete("name")
    @investigate_take.autocomplete("name")
    async def _channel_item_name_takeable_autocomplete(
        self, ctx: ipy.AutocompleteContext
    ) -> None:
        return await fuzzy.autocomplete_item_channel(
            ctx,
            channel=str(ctx.channel_id),
            check_takeable=True,
            **ctx.kwargs,
        )

    @view_item.autocomplete("name")
    @item_drop.autocomplete("name")
    @alias_view_item.autocomplete("name")
    @alias_item_drop.autocomplete("name")
    async def _user_item_name_autocomplete(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        await fuzzy.autocomplete_item_user(
            ctx,
            user=str(ctx.author.id),
            **ctx.kwargs,
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(text_utils)
    importlib.reload(help_tools)
    importlib.reload(fuzzy)
    ItemsCommands(bot)
