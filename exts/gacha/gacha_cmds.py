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
from prisma.types import PrismaGachaItemScalarFieldKeys

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.utils as utils

QUERY_GACHA_ROLL = (
    f"SELECT {', '.join(typing.get_args(PrismaGachaItemScalarFieldKeys))} FROM"  # noqa: S608
    " thiagachaitems WHERE guild_id = $1 AND amount != 0 ORDER BY RANDOM() LIMIT 1;"
)
QUERY_GACHA_ROLL_NO_DUPS = (
    f"SELECT {', '.join(typing.get_args(PrismaGachaItemScalarFieldKeys))} FROM"  # noqa: S608
    " thiagachaitems WHERE guild_id = $1 AND amount != 0 AND id NOT IN (SELECT item_id"
    " FROM thiagachaitemtoplayer WHERE player_id = $2) ORDER BY RANDOM() LIMIT 1;"
)


class GachaCommands(utils.Extension):
    def __init__(self, bot: utils.THIABase) -> None:
        self.name = "Gacha Commands"
        self.bot: utils.THIABase = bot
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

        async with self.gacha_roll_locks[str(ctx.author_id)]:
            player = await models.GachaPlayer.get_or_create(ctx.guild.id, ctx.author.id)

            if player.currency_amount < config.gacha.currency_cost:
                raise utils.CustomCheckFailure(
                    f"You do not have enough {config.names.plural_currency_name} to"
                    " roll the gacha. You need at least"
                    f" {config.gacha.currency_cost} {config.names.currency_name(config.gacha.currency_cost)} to"
                    " do so."
                )

            if config.gacha.draw_duplicates:
                item = await models.GachaItem.prisma().query_first(
                    QUERY_GACHA_ROLL, ctx.guild.id
                )
            else:
                item = await models.GachaItem.prisma().query_first(
                    QUERY_GACHA_ROLL_NO_DUPS, ctx.guild.id, player.id
                )

            if item is None:
                raise utils.CustomCheckFailure("There are no items available to roll.")

            new_count = player.currency_amount - config.gacha.currency_cost
            embed = item.embed()
            embed.set_footer(
                f"{new_count} {config.names.currency_name(new_count)} left"
            )

            await ctx.send(embed=embed)

            async with self.bot.db.batch_() as batch:
                if item.amount != -1:
                    batch.prismagachaitem.update(
                        data={"amount": {"decrement": 1}}, where={"id": item.id}
                    )

                batch.prismagachaplayer.update(
                    data={"currency_amount": {"decrement": config.gacha.currency_cost}},
                    where={"id": player.id},
                )
                batch.prismaitemtoplayer.create(
                    data={
                        "item": {"connect": {"id": item.id}},
                        "player": {"connect": {"id": player.id}},
                    }
                )

    @gacha.subcommand(
        "pull",
        sub_cmd_description="Pulls for an item in the gacha. Alias of /gacha roll.",
    )
    async def gacha_pull(self, ctx: utils.THIASlashContext) -> None:
        await self.gacha_roll.call_with_binding(self.gacha_roll.callback, ctx)

    @gacha.subcommand(
        "draw",
        sub_cmd_description="Draws for an item in the gacha. Alias of /gacha draw.",
    )
    async def gacha_draw(self, ctx: utils.THIASlashContext) -> None:
        await self.gacha_roll.call_with_binding(self.gacha_roll.callback, ctx)

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
            ctx.guild_id, ctx.author.id, include={"items": {"include": {"item": True}}}
        )
        if player is None:
            if not ctx.author.has_role(config.player_role):
                raise ipy.errors.BadArgument("You have no data for gacha.")
            player = await models.GachaPlayer.prisma().create(
                data={"guild_id": ctx.guild_id, "user_id": ctx.author.id},
            )

        embeds = player.create_profile(ctx.author.display_name, config.names)

        if len(embeds) > 1:
            pag = help_tools.HelpPaginator.create_from_embeds(
                self.bot, *embeds, timeout=120
            )
            pag.show_callback_button = False
            await pag.send(ctx, ephemeral=True)
        else:
            await ctx.send(embeds=embeds, ephemeral=True)

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

        player = await models.GachaPlayer.get_or_none(ctx.guild_id, ctx.author.id)
        if player is None:
            if not ctx.author.has_role(config.player_role):
                raise ipy.errors.BadArgument("You have no data for gacha.")
            player = await models.GachaPlayer.prisma().create(
                data={"guild_id": ctx.guild_id, "user_id": ctx.author.id}
            )

        if player.currency_amount < amount:
            raise utils.CustomCheckFailure("You do not have enough currency to give.")

        recipient_player = await models.GachaPlayer.get_or_none(
            ctx.guild_id, recipient.id
        )
        if recipient_player is None:
            if not recipient.has_role(config.player_role):
                raise ipy.errors.BadArgument("The recipient has no data for gacha.")
            recipient_player = await models.GachaPlayer.prisma().create(
                data={"guild_id": ctx.guild_id, "user_id": ctx.author.id}
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
        item = await models.GachaItem.prisma().find_first(
            where={
                "guild_id": ctx.guild_id,
                "name": name,
                "players": {
                    "some": {
                        "player": {
                            "is": {"guild_id": ctx.guild_id, "user_id": ctx.author.id}
                        }
                    }
                },
            },
        )
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
