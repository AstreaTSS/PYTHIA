"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import importlib
from collections import defaultdict

import interactions as ipy
import tansy
import typing_extensions as typing
from tortoise.expressions import F
from tortoise.query_utils import Prefetch
from tortoise.transactions import in_transaction

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.utils as utils

QUERY_GACHA_ROLL = (
    f"SELECT {', '.join(models.GachaItem._meta.fields_db_projection)} FROM"  # noqa: S608
    " thiagachaitems WHERE guild_id = $1 AND amount != 0 ORDER BY RANDOM() LIMIT 1;"
)
QUERY_GACHA_ROLL_NO_DUPS = (
    f"SELECT {', '.join(models.GachaItem._meta.fields_db_projection)} FROM"  # noqa: S608
    " thiagachaitems WHERE guild_id = $1 AND amount != 0 AND id NOT IN (SELECT item_id"
    " FROM thiagachaitemtoplayer WHERE player_id = $2) ORDER BY RANDOM() LIMIT 1;"
)


class GachaCommands(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Gacha Commands"

        self.gacha_roll_locks: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )

    gacha = tansy.SlashCommand(
        name="gacha",
        description="Hosts public-facing gacha commands.",
        dm_permission=False,
    )

    @gacha.subcommand(
        "roll",
        sub_cmd_description="Rolls for an item in the gacha.",
    )
    async def gacha_roll(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None
            assert config.names is not None

        if not config.player_role or not config.gacha.enabled:
            raise utils.CustomCheckFailure("Gacha is not enabled in this server.")

        if not ctx.author.has_role(config.player_role):
            raise utils.CustomCheckFailure("You do not have the Player role.")

        name_for_action = ctx._command_name.split(" ")[1]

        async with self.gacha_roll_locks[str(ctx.author_id)]:
            player, _ = await models.GachaPlayer.get_or_create(
                guild_id=ctx.guild_id, user_id=ctx.author.id
            )

            if player.currency_amount < config.gacha.currency_cost:
                raise utils.CustomCheckFailure(
                    f"You do not have enough {config.names.plural_currency_name} to"
                    f" {name_for_action} the gacha. You need at least"
                    f" {config.gacha.currency_cost} {config.names.currency_name(config.gacha.currency_cost)} to"
                    " do so."
                )

            # technically, this is sql injection
            # but our input is safe
            if config.gacha.draw_duplicates:
                items = await models.GachaItem.raw(
                    QUERY_GACHA_ROLL.replace("$1", str(ctx.guild.id))
                )
            else:
                items = await models.GachaItem.raw(
                    QUERY_GACHA_ROLL_NO_DUPS.replace("$1", str(ctx.guild.id)).replace(
                        "$2", str(player.id)
                    )
                )

            if not items:
                raise utils.CustomCheckFailure(
                    f"There are no items available to {name_for_action}."
                )
            item: models.GachaItem = items[0]

            new_count = player.currency_amount - config.gacha.currency_cost
            embed = item.embed()
            embed.set_footer(
                f"{new_count} {config.names.currency_name(new_count)} left"
            )

            await ctx.send(embed=embed)

            async with in_transaction():
                if item.amount != -1:
                    item.amount -= 1
                    await item.save(force_update=True)

                await models.GachaPlayer.filter(id=player.id).update(
                    currency_amount=F("currency_amount") - config.gacha.currency_cost
                )

                await models.ItemToPlayer.create(
                    item_id=item.id,
                    player_id=player.id,
                )

    gacha_pull = utils.alias(
        gacha_roll,
        "gacha pull",
        "Pulls for an item in the gacha. Alias of /gacha roll.",
    )
    gacha_draw = utils.alias(
        gacha_roll,
        "gacha draw",
        "Draws for an item in the gacha. Alias of /gacha draw.",
    )

    @gacha.subcommand(
        "profile",
        sub_cmd_description="Shows your gacha currency and items.",
    )
    @ipy.auto_defer(ephemeral=True)
    async def gacha_profile(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None
            assert config.names is not None

        if not config.player_role or not config.gacha.enabled:
            raise utils.CustomCheckFailure("Gacha is not enabled in this server.")

        player = await models.GachaPlayer.get_or_none(
            guild_id=ctx.guild_id, user_id=ctx.author.id
        ).prefetch_related(
            Prefetch("items", models.ItemToPlayer.filter().prefetch_related("item"))
        )
        if player is None:
            if not ctx.author.has_role(config.player_role):
                raise ipy.errors.BadArgument("You have no data for gacha.")
            player = await models.GachaPlayer.create(
                guild_id=ctx.guild_id, user_id=ctx.author.id
            )
            await player.fetch_related("items__item")

        embeds = player.create_profile(ctx.author.display_name, config.names)

        if len(embeds) > 1:
            pag = help_tools.HelpPaginator.create_from_embeds(
                self.bot, *embeds, timeout=120
            )
            pag.show_callback_button = False
            await pag.send(ctx, ephemeral=True)
        else:
            await ctx.send(embeds=embeds, ephemeral=True)

    gacha_inventory = utils.alias(
        gacha_profile,
        "gacha inventory",
        "Shows your gacha currency and items. Alias of /gacha profile.",
    )

    @gacha.subcommand(
        "give-currency",
        sub_cmd_description="Gives currency to a user.",
    )
    async def gacha_give_currency(
        self,
        ctx: utils.THIASlashContext,
        recipient: ipy.Member = tansy.Option("The recipient."),
        amount: int = tansy.Option("The amount to give.", min_value=1, max_value=999),
    ) -> None:
        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None
            assert config.names is not None

        if not config.player_role or not config.gacha.enabled:
            raise utils.CustomCheckFailure("Gacha is not enabled in this server.")

        player = await models.GachaPlayer.get_or_none(
            guild_id=ctx.guild_id, user_id=ctx.author.id
        )
        if player is None:
            if not ctx.author.has_role(config.player_role):
                raise ipy.errors.BadArgument("You have no data for gacha.")
            player = await models.GachaPlayer.create(
                guild_id=ctx.guild_id, user_id=ctx.author.id
            )

        if player.currency_amount < amount:
            raise utils.CustomCheckFailure("You do not have enough currency to give.")

        recipient_player = await models.GachaPlayer.get_or_none(
            guild_id=ctx.guild_id, user_id=recipient.id
        )
        if recipient_player is None:
            if not recipient.has_role(config.player_role):
                raise ipy.errors.BadArgument("The recipient has no data for gacha.")
            recipient_player = await models.GachaPlayer.create(
                guild_id=ctx.guild_id, user_id=recipient.id
            )

        recipient_player.currency_amount += amount
        player.currency_amount -= amount
        await recipient_player.save()
        await player.save()

        await ctx.send(
            embed=utils.make_embed(
                f"Gave {amount} {config.names.currency_name(amount)} to"
                f" {recipient.mention}. New balance: {player.currency_amount}."
            )
        )

    @gacha.subcommand(
        "view-item",
        sub_cmd_description="Shows information about an item you have.",
    )
    @ipy.auto_defer(ephemeral=True)
    async def gacha_user_view_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option("The name of the item to view.", autocomplete=True),
    ) -> None:
        item = await models.GachaItem.filter(
            guild_id=ctx.guild_id,
            name=name,
            players__player__guild_id=ctx.guild_id,
            players__player__user_id=ctx.author.id,
        ).first()
        if item is None:
            raise ipy.errors.BadArgument(
                "Item either does not exist or you do not have it."
            )

        await ctx.send(embed=item.embed(), ephemeral=True)

    @gacha_user_view_item.autocomplete("name")
    async def _autocomplete_gacha_user_item(self, ctx: ipy.AutocompleteContext) -> None:
        await fuzzy.autocomplete_gacha_user_item(ctx, **ctx.kwargs)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(help_tools)
    importlib.reload(fuzzy)
    GachaCommands(bot)
