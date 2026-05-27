"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import collections
import importlib

import discord
import ragwort
import typing_extensions as typing

import common.classes as classes
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils


class ItemsCommands(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Items Commands"

    items = ragwort.SlashCommandGroup(
        name="items",
        description="Hosts public-facing items commands.",
        contexts={discord.InteractionContextType.guild},
    )

    @items.command(
        name="here",
        description="Views an item in the current channel.",
    )
    @ragwort.auto_defer(enabled=False)
    async def items_here(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to view.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        hidden: str = ragwort.Option(
            "Should the result be shown only to you? Defaults to no.",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        await ctx.defer(ephemeral=hidden == "yes")

        config = await ctx.fetch_config({"items": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.items and isinstance(config.items, models.ItemsConfig)
            assert config.names and isinstance(config.names, models.Names)

        if not config.player_role or not config.items.enabled:
            raise utils.CustomCheckFailure("Items are not enabled in this server.")

        if not ctx.author.get_role(config.player_role):
            try:
                player_role = await ctx.guild.fetch_role(config.player_role)
            except discord.HTTPException:
                player_role = None

            player_role_name = player_role.name if player_role else "Player"
            raise utils.CustomCheckFailure(
                f"You do not have the {player_role_name} role."
            )

        item = await models.ItemsSystemItem.filter(
            name=name,
            relations__object_id=int(ctx.channel_id),
        ).first()
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " channel."
            )

        count = await models.ItemRelation.filter(
            object_id=int(ctx.channel_id), item_id=item.id
        ).count()

        embeds = item.embeds(count=count)
        await ctx.respond(embeds=embeds, ephemeral=hidden == "yes")

    @items.command(
        name="take",
        description="Takes an item from the current channel.",
    )
    @ragwort.auto_defer(enabled=False)
    async def items_take(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to take.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        amount: int = ragwort.Option(
            "The amount of the item to take. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
        hidden: str = ragwort.Option(
            "Should the result be shown only to you? Defaults to no.",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        await ctx.defer(ephemeral=hidden == "yes")

        config = await ctx.fetch_config({"items": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.items and isinstance(config.items, models.ItemsConfig)
            assert config.names and isinstance(config.names, models.Names)

        if not config.player_role or not config.items.enabled:
            raise utils.CustomCheckFailure("Items are not enabled in this server.")

        if not ctx.author.get_role(config.player_role):
            try:
                player_role = await ctx.guild.fetch_role(config.player_role)
            except discord.HTTPException:
                player_role = None

            player_role_name = player_role.name if player_role else "Player"
            raise utils.CustomCheckFailure(
                f"You do not have the {player_role_name} role."
            )

        item_relations = await models.ItemRelation.filter(
            object_id=int(ctx.channel_id),
            item__name=name,
        ).prefetch_related("item")
        if not item_relations:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " channel."
            )

        item = item_relations[0].item
        if typing.TYPE_CHECKING:
            assert item is not None

        if not item.takeable:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` cannot be taken."
            )

        if amount == len(item_relations):
            await models.ItemRelation.filter(
                item_id=item.id, object_id=int(ctx.channel_id)
            ).update(
                object_id=ctx.author.id,
                object_type=models.ItemsRelationType.USER,
            )
        elif amount > len(item_relations):
            raise utils.CustomCheckFailure(
                "You cannot take more items than there are in the channel."
            )
        else:
            to_update = (
                await models.ItemRelation.filter(
                    item_id=item.id, object_id=int(ctx.channel_id)
                )
                .limit(amount)
                .values_list("id", flat=True)
            )
            await models.ItemRelation.filter(id__in=to_update).update(
                object_id=ctx.author.id,
                object_type=models.ItemsRelationType.USER,
            )

        await ctx.respond(
            view=utils.make_view(
                f"Successfully took {amount} of"
                f" `{discord.utils.escape_markdown(item.name)}` from the channel."
            ),
            ephemeral=hidden == "yes",
        )

    @items.command(
        name="view-inventory",
        description="Views your inventory.",
    )
    @ragwort.auto_defer(ephemeral=True)
    async def view_inventory(
        self,
        ctx: utils.THIASlashContext,
        mode: str = ragwort.Option(
            "The mode to show the inventory in.",
            choices=[
                discord.OptionChoice("Cozy", "cozy"),
                discord.OptionChoice("Compact", "compact"),
            ],
            default="cozy",
        ),
    ) -> None:
        if mode not in ("cozy", "compact"):
            raise utils.BadArgument("Invalid mode.")

        user_items = await models.ItemRelation.filter(
            guild_id=ctx.guild_id,
            object_id=ctx.author.id,
        ).prefetch_related("item")
        if not user_items:
            if ctx.command.qualified_name == "inventory view":
                raise utils.CustomCheckFailure(
                    "You have no items in your inventory. If you want to look at your"
                    " items from the gacha, please use `/gacha profile`."
                )

            raise utils.CustomCheckFailure("You have no items in your inventory.")

        items_counter: collections.Counter[models.ItemHash] = collections.Counter()

        for item in user_items:
            items_counter[models.ItemHash(item.item)] += 1

        str_builder: list[str] = []

        for k, v in sorted(items_counter.items(), key=lambda i: i[0].item.name.lower()):
            if mode == "compact":
                str_builder.append(
                    f"**{discord.utils.escape_markdown(k.item.name)}**{f' (x{v})' if v > 1 else ''}:"
                    f" {models.short_desc(k.item.description)}"
                )
            else:
                str_builder.append(
                    f"**{discord.utils.escape_markdown(k.item.name)}**{f' (x{v})' if v > 1 else ''}\n-#"
                    f" {models.short_desc(k.item.description, 70)}"
                )

        limit = 15 if mode == "cozy" else 30

        if len(str_builder) > limit:
            chunks = [
                str_builder[x : x + limit] for x in range(0, len(str_builder), limit)
            ]
            items = [[discord.ui.TextDisplay("\n".join(entry))] for entry in chunks]
        else:
            await ctx.respond(
                view=utils.make_view(
                    title="Your Inventory",
                    description="\n".join(str_builder),
                ),
                ephemeral=True,
            )
            return

        pag = classes.ContainerPaginator(
            *items, title="Your Inventory", author_id=ctx.author.id
        )
        await ctx.respond(view=pag, ephemeral=True)

    @items.command(
        name="view-item",
        description="Views an item in your inventory.",
    )
    @ragwort.auto_defer(ephemeral=True)
    async def view_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to view.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.filter(
            name=name,
            guild_id=ctx.guild_id,
            relations__object_id=ctx.author.id,
        ).first()
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` is not in your"
                " inventory."
            )

        count = await models.ItemRelation.filter(
            object_id=ctx.author.id, item_id=item.id
        ).count()

        embeds = item.embeds(count=count)
        embeds[0].footer = None
        await ctx.respond(embeds=embeds, ephemeral=True)

    @items.command(
        name="drop",
        description="Drops an item from your inventory into the current channel.",
    )
    async def item_drop(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to drop.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        amount: int = ragwort.Option(
            "The amount of the item to drop. Defaults to 1.",
            min_value=1,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id,
            name=name,
        )
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        total = await models.ItemRelation.filter(
            item_id=item.id,
            object_id=ctx.author.id,
        ).count()

        if amount >= total:
            amount = total
            await models.ItemRelation.filter(
                item_id=item.id, object_id=ctx.author.id
            ).delete()
        elif total == 0:
            raise utils.CustomCheckFailure(
                "There are no items of this type in your inventory."
            )
        else:
            to_delete = (
                await models.ItemRelation.filter(
                    item_id=item.id, object_id=ctx.author.id
                )
                .limit(amount)
                .values_list("id", flat=True)
            )
            await models.ItemRelation.filter(id__in=to_delete).delete()

        await ctx.respond(
            view=utils.make_view(
                f"Dropped {amount} of item `{discord.utils.escape_markdown(name)}` from"
                f" {ctx.author.mention}'s inventory into this channel."
            )
        )

    investigate = ragwort.SlashCommandGroup(
        name="investigate",
        description="Hosts aliases for general investigation of items.",
        contexts={discord.InteractionContextType.guild},
    )

    investigate_here = utils.alias(
        items_here,
        name="here",
        description="Views an item in the current channel. Alias for /items here.",
        parent=investigate,
    )

    investigate_take = utils.alias(
        items_take,
        name="take",
        description="Takes an item from the current channel. Alias for /items take.",
        parent=investigate,
    )

    inventory = ragwort.SlashCommandGroup(
        name="inventory",
        description="Hosts aliases for inventory of items.",
        contexts={discord.InteractionContextType.guild},
    )

    alias_view_inventory = utils.alias(
        view_inventory,
        name="view",
        description=(
            "Views your inventory for the items system. Alias for /items"
            " view-inventory."
        ),
        parent=inventory,
    )

    alias_view_item = utils.alias(
        view_item,
        name="view-item",
        description="Views an item in your inventory. Alias for /items view-item.",
        parent=inventory,
    )

    alias_item_drop = utils.alias(
        item_drop,
        name="drop",
        description=(
            "Drops an item from your inventory into the current channel. Alias for"
            " /items drop."
        ),
        parent=inventory,
    )

    @items_here.autocomplete("name")
    @investigate_here.autocomplete("name")
    async def _channel_item_name_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_item_channel(
            ctx,
            channel=str(ctx.interaction.channel_id),
            investigate_variant=True,
            **ctx.options,
        )

    @items_take.autocomplete("name")
    @investigate_take.autocomplete("name")
    async def _channel_item_name_takeable_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_item_channel(
            ctx,
            channel=str(ctx.interaction.channel_id),
            check_takeable=True,
            investigate_variant=True,
            **ctx.options,
        )

    @view_item.autocomplete("name")
    @alias_view_item.autocomplete("name")
    @item_drop.autocomplete("name")
    @alias_item_drop.autocomplete("name")
    async def _user_item_name_autocomplete(
        self,
        ctx: discord.AutocompleteContext,
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_item_user(
            ctx,
            user=str(ctx.interaction.user.id),
            **ctx.options,
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(classes)
    importlib.reload(fuzzy)
    bot.add_cog(ItemsCommands(bot))
