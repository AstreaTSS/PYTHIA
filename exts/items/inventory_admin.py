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

import common.classes as classes
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils


class InventoryManagement(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Inventory Management"

    manage = ragwort.SlashCommandGroup(
        name="inventory-manage",
        description="Handles management of inventories.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={
            discord.InteractionContextType.guild,
        },
    )

    @manage.command(
        name="user-inventory",
        description="Views a user's inventory.",
    )
    async def user_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to view the inventory of.",
        ),
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
            object_id=user.id,
        ).prefetch_related("item")
        if not user_items:
            raise utils.CustomCheckFailure("This user has no items in their inventory.")

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
                    title=f"{user.display_name}'s Inventory",
                    description="\n".join(str_builder),
                )
            )
            return

        pag = classes.ContainerPaginator(
            *items, title=f"{user.display_name}'s Inventory", author_id=ctx.author.id
        )
        await ctx.respond(view=pag)

    @manage.command(
        name="put-in-inventory",
        description="Places an item in a user's inventory.",
    )
    async def put_in_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to place the item in the inventory of.",
        ),
        name: str = ragwort.Option(
            "The name of the item to place.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        amount: int = ragwort.Option(
            "The amount of the item to place. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id, name=name
        )
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        if not item.takeable:
            raise utils.CustomCheckFailure(
                "You cannot place non-takeable items in a user's inventory."
            )

        if (
            await models.ItemRelation.filter(item_id=item.id, object_id=user.id).count()
            >= 50
        ):
            raise utils.CustomCheckFailure(
                "You cannot place more than 50 of the same item in a user's inventory."
            )

        await models.ItemRelation.bulk_create(
            models.ItemRelation(
                item_id=item.id,
                guild_id=ctx.guild_id,
                object_id=int(user.id),
                object_type=models.ItemsRelationType.USER,
            )
            for _ in range(amount)
        )

        await ctx.respond(
            view=utils.make_view(
                f"Placed {amount} of item `{discord.utils.escape_markdown(name)}` in"
                f" {user.mention}'s inventory."
            )
        )

    @manage.command(
        name="remove-from-inventory",
        description="Removes an item from a player's inventory.",
    )
    async def remove_from_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to remove the item from.",
        ),
        name: str = ragwort.Option(
            "The name of the item to remove.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        amount: int = ragwort.Option(
            "The amount of the item to remove. Defaults to 1.",
            min_value=1,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id, name=name
        )
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        total = await models.ItemRelation.filter(
            item_id=item.id, object_id=user.id
        ).count()

        if amount >= total:
            amount = total
            await models.ItemRelation.filter(
                item_id=item.id, object_id=user.id
            ).delete()
        elif total == 0:
            raise utils.CustomCheckFailure(
                "There are no items of this type in this user's inventory."
            )
        else:
            to_delete = (
                await models.ItemRelation.filter(item_id=item.id, object_id=user.id)
                .limit(amount)
                .values_list("id", flat=True)
            )
            await models.ItemRelation.filter(id__in=to_delete).delete()

        await ctx.respond(
            view=utils.make_view(
                f"Removed {amount} of item `{discord.utils.escape_markdown(name)}` from"
                f" {user.mention}'s inventory."
            )
        )

    @manage.command(
        name="drop-from-inventory",
        description="Drops items from a player's inventory into a specified channel.",
    )
    async def drop_from_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to drop the item from.",
        ),
        name: str = ragwort.Option(
            "The name of the item to drop.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel to drop the items in.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        amount: int = ragwort.Option(
            "The amount of the item to drop. Defaults to 1.",
            min_value=1,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id, name=name
        )
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        total = await models.ItemRelation.filter(
            item_id=item.id, object_id=user.id
        ).count()

        if amount >= total:
            amount = total
            await models.ItemRelation.filter(item_id=item.id, object_id=user.id).update(
                object_id=channel.id,
                object_type=models.ItemsRelationType.CHANNEL,
            )
        elif total == 0:
            raise utils.CustomCheckFailure(
                "There are no items of this type in this user's inventory."
            )
        else:
            to_update = (
                await models.ItemRelation.filter(item_id=item.id, object_id=user.id)
                .limit(amount)
                .values_list("id", flat=True)
            )
            await models.ItemRelation.filter(id__in=to_update).update(
                object_id=channel.id,
                object_type=models.ItemsRelationType.CHANNEL,
            )

        await ctx.respond(
            view=utils.make_view(
                f"Dropped {amount} of item `{discord.utils.escape_markdown(name)}` from"
                f" {user.mention}'s inventory into {channel.mention}."
            )
        )

    @manage.command(
        name="clear-inventory",
        description="Clears a user's inventory.",
    )
    async def clear_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to clear the inventory of.",
        ),
    ) -> None:
        count = await models.ItemRelation.filter(
            guild_id=ctx.guild_id,
            object_id=user.id,
        ).delete()
        if count == 0:
            raise utils.CustomCheckFailure("There are no items to clear for this user.")

        await ctx.respond(
            view=utils.make_view(f"Cleared the inventory of {user.mention}.")
        )

    @put_in_inventory.autocomplete("name")
    async def _item_name_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_item(
            ctx,
            **ctx.options,
        )

    @remove_from_inventory.autocomplete("name")
    @drop_from_inventory.autocomplete("name")
    async def _user_item_name_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_item_user(
            ctx,
            **ctx.options,
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(classes)
    importlib.reload(fuzzy)
    bot.add_cog(InventoryManagement(bot))
