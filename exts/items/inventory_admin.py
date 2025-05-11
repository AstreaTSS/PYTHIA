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

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.text_utils as text_utils
import common.utils as utils


class InventoryManagement(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Inventory Management"

    manage = tansy.SlashCommand(
        name="inventory-manage",
        description="Handles management of inventories.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @manage.subcommand(
        "user-inventory",
        sub_cmd_description="Views a user's inventory.",
    )
    async def user_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to view the inventory of.",
        ),
    ) -> None:
        user_items = await models.ItemRelation.filter(
            object_id=user.id,
        ).prefetch_related("item")
        if not user_items:
            raise utils.CustomCheckFailure("This user has no items in their inventory.")

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
            page.title = f"{user.display_name}'s Inventory"

        if len(pag.pages) == 1:
            embed = pag.pages[0].to_embed()  # type: ignore
            embed.timestamp = ipy.Timestamp.utcnow()
            embed.color = ctx.bot.color
            await ctx.send(embeds=embed)
            return

        pag.show_callback_button = False
        pag.default_color = ctx.bot.color
        await pag.send(ctx)

    @manage.subcommand(
        "put-in-inventory",
        sub_cmd_description="Places an item in a user's inventory.",
    )
    async def put_in_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to place the item in the inventory of.",
        ),
        name: str = tansy.Option(
            "The name of the item to place.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        amount: int = tansy.Option(
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
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
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

        await ctx.send(
            embed=utils.make_embed(
                f"Placed {amount} of item `{text_utils.escape_markdown(name)}` in"
                f" {user.mention}'s inventory."
            )
        )

    @manage.subcommand(
        "remove-from-inventory",
        sub_cmd_description="Removes an item from a player's inventory.",
    )
    async def remove_from_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to remove the item from.",
        ),
        name: str = tansy.Option(
            "The name of the item to remove.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        amount: int = tansy.Option(
            "The amount of the item to remove. Defaults to 1.",
            min_value=1,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id, name=name
        )
        if not item:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
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

        await ctx.send(
            embed=utils.make_embed(
                f"Removed {amount} of item `{text_utils.escape_markdown(name)}` from"
                f" {user.mention}'s inventory."
            )
        )

    @manage.subcommand(
        "drop-from-inventory",
        sub_cmd_description=(
            "Drops items from a player's inventory into a specified channel."
        ),
    )
    async def drop_from_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to drop the item from.",
        ),
        name: str = tansy.Option(
            "The name of the item to drop.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel to drop the items in.",
        ),
        amount: int = tansy.Option(
            "The amount of the item to drop. Defaults to 1.",
            min_value=1,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id, name=name
        )
        if not item:
            raise ipy.errors.BadArgument(
                f"Item `{text_utils.escape_markdown(name)}` does not exist in this"
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

        await ctx.send(
            embed=utils.make_embed(
                f"Dropped {amount} of item `{text_utils.escape_markdown(name)}` from"
                f" {user.mention}'s inventory into {channel.mention}."
            )
        )

    @manage.subcommand(
        "clear-inventory",
        sub_cmd_description="Clears a user's inventory.",
    )
    async def clear_inventory(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to clear the inventory of.",
        ),
    ) -> None:
        count = await models.ItemRelation.filter(
            object_id=user.id,
        ).delete()
        if count == 0:
            raise utils.CustomCheckFailure("There are no items to clear for this user.")

        await ctx.send(
            embed=utils.make_embed(f"Cleared the inventory of {user.mention}.")
        )

    @put_in_inventory.autocomplete("name")
    async def _item_name_autocomplete(self, ctx: ipy.AutocompleteContext) -> None:
        return await fuzzy.autocomplete_item(
            ctx,
            **ctx.kwargs,
        )

    @remove_from_inventory.autocomplete("name")
    @drop_from_inventory.autocomplete("name")
    async def _user_item_name_autocomplete(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        await fuzzy.autocomplete_item_user(
            ctx,
            **ctx.kwargs,
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(text_utils)
    importlib.reload(help_tools)
    importlib.reload(fuzzy)
    InventoryManagement(bot)
