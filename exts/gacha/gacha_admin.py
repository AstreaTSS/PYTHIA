"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import importlib

import interactions as ipy
import tansy
import typing_extensions as typing
from interactions.api.http.route import Route
from tortoise.expressions import F
from tortoise.query_utils import Prefetch
from tortoise.transactions import in_transaction

import common.classes as classes
import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.utils as utils

if typing.TYPE_CHECKING:
    import discord_typings


class GuildMemberEntry(typing.TypedDict):
    member: "discord_typings.GuildMemberAddData"


class GuildMembersSearchResult(typing.TypedDict):
    guild_id: str
    members: list[GuildMemberEntry]
    page_result_count: int
    total_result_count: int


class GachaManagement(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Gacha Management"

    manage = tansy.SlashCommand(
        name="gacha-manage",
        description="Handles management of gacha mechanics.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    manage_hybrid = tansy.HybridSlashCommand(
        name="gacha-manage",
        description="Handles management of gacha mechanics.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @manage_hybrid.subcommand(
        "add-currency",
        sub_cmd_description="Adds an amount of currency to a user.",
    )
    @ipy.auto_defer(enabled=False)
    @help_tools.prefixed_check()
    async def gacha_give_currency(
        self,
        ctx: utils.THIAHybridContext,
        user: ipy.Member = tansy.Option("The user to add currency to."),
        amount: int = tansy.Option(
            "The amount of currency to add.", min_value=1, max_value=2147483647
        ),
    ) -> None:
        async with ctx.typing:
            config = await ctx.fetch_config({"names": True, "gacha": True})
            if typing.TYPE_CHECKING:
                assert config.names is not None

            async with self.bot.gacha_locks[f"{ctx.guild_id}-{user.id}"]:
                async with asyncio.timeout(60):
                    player, _ = await models.GachaPlayer.get_or_create(
                        guild_id=ctx.guild_id, user_id=user.id
                    )
                    player.currency_amount += amount

                    if player.currency_amount > 2147483647:
                        raise ipy.errors.BadArgument(
                            '"Frankly, the fact that you wish to make a person have'
                            " more than 2,147,483,647"
                            f" {config.names.currency_name(amount)} is absurd. I seek"
                            " to assist, but I will refuse to handle amounts like"
                            ' this." - PYTHIA'
                        )

                    await player.save()

        await ctx.reply(
            embed=utils.make_embed(
                f"Added {amount} {config.names.currency_name(amount)} to"
                f" {user.mention}. They now have {player.currency_amount}"
                f" {config.names.currency_name(player.currency_amount)}."
            )
        )

    @manage_hybrid.subcommand(
        "remove-currency",
        sub_cmd_description="Removes a certain amount of currency from a user.",
    )
    @ipy.auto_defer(enabled=False)
    @help_tools.prefixed_check()
    async def gacha_remove_currency(
        self,
        ctx: utils.THIAHybridContext,
        user: ipy.Member = tansy.Option(
            "The user to remove currency from.",
        ),
        amount: int = tansy.Option(
            "The amount of currency to remove.", min_value=1, max_value=2147483647
        ),
    ) -> None:
        async with ctx.typing:
            config = await ctx.fetch_config({"names": True, "gacha": True})
            if typing.TYPE_CHECKING:
                assert config.names is not None

            async with self.bot.gacha_locks[f"{ctx.guild_id}-{user.id}"]:
                async with asyncio.timeout(60):
                    player, _ = await models.GachaPlayer.get_or_create(
                        guild_id=ctx.guild_id, user_id=user.id
                    )
                    player.currency_amount -= amount

                    if player.currency_amount < -2147483647:
                        raise ipy.errors.BadArgument(
                            '"Frankly, the fact that you make a person have less than'
                            f" than -2,147,483,647 {config.names.currency_name(amount)}"
                            " is absurd. Surely, you only did so to test my"
                            ' capabilities, correct?" - PYTHIA'
                        )

                    await player.save()

        await ctx.reply(
            embed=utils.make_embed(
                f"Removed {amount} {config.names.currency_name(amount)} from"
                f" {user.mention}. They now have {player.currency_amount}"
                f" {config.names.currency_name(player.currency_amount)}."
            )
        )

    @manage.subcommand(
        "reset-currency",
        sub_cmd_description="Resets currency amount for a user.",
    )
    async def gacha_reset_currency(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to reset currency for.",
            type=ipy.User,
        ),
    ) -> None:
        async with self.bot.gacha_locks[f"{ctx.guild_id}-{user.id}"]:
            amount = await models.GachaPlayer.filter(
                guild_id=ctx.guild_id, user_id=user.id, currency_amount__not=0
            ).update(currency_amount=0)

            if amount == 0:
                raise ipy.errors.BadArgument("The user has no currency to reset.")

            await ctx.send(
                embed=utils.make_embed(f"Reset currency for {user.mention}.")
            )

    @manage.subcommand(
        "reset-items",
        sub_cmd_description="Resets items for a user.",
    )
    async def gacha_reset_items(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to reset items for.",
            type=ipy.User,
        ),
    ) -> None:
        to_delete = await models.ItemToPlayer.filter(
            player__user_id=user.id, player__guild_id=ctx.guild_id
        ).values_list("id", flat=True)

        if not to_delete:
            raise ipy.errors.BadArgument("The user has no items to reset.")

        await models.ItemToPlayer.filter(id__in=to_delete).delete()

        await ctx.send(embed=utils.make_embed(f"Reset items for {user.mention}."))

    @manage.subcommand(
        "clear-user",
        sub_cmd_description=(
            "Clears/removes gacha data, including currency and items, for a user."
        ),
    )
    async def gacha_clear_user(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to clear data for.",
            type=ipy.User,
        ),
    ) -> None:
        amount = await models.GachaPlayer.filter(
            guild_id=ctx.guild_id, user_id=user.id
        ).delete()

        if not amount:
            raise ipy.errors.BadArgument("The user has no data to clear.")

        await ctx.send(
            embed=utils.make_embed(f"Cleared/removed data for {user.mention}.")
        )

    @manage.subcommand(
        "clear-items",
        sub_cmd_description=(
            "Clears/removes all items for this server. Use with caution!"
        ),
    )
    async def gacha_clear_items(
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

        items_amount = await models.GachaItem.filter(guild_id=ctx.guild_id).delete()

        if items_amount <= 0:
            raise utils.CustomCheckFailure("There's no gacha item data to clear!")

        await ctx.send(embed=utils.make_embed("All gacha items data cleared."))

    @manage.subcommand(
        "clear-everything",
        sub_cmd_description="Clears ALL gacha user and items data. Use with caution!",
    )
    async def gacha_clear(
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

        players_amount = await models.GachaPlayer.filter(guild_id=ctx.guild_id).delete()
        items_amount = await models.GachaItem.filter(guild_id=ctx.guild_id).delete()

        if players_amount + items_amount <= 0:
            raise utils.CustomCheckFailure("There's no gacha data to clear!")

        await ctx.send(embed=utils.make_embed("All gacha user and items data cleared."))

    @manage.subcommand(
        "add-currency-role",
        sub_cmd_description=(
            "Adds a certain amount of currency to all users with a specific role."
        ),
    )
    async def gacha_give_role(
        self,
        ctx: utils.THIASlashContext,
        role: ipy.Role = tansy.Option("The role to add currency to."),
        amount: int = tansy.Option(
            "The amount of currency to add.", min_value=1, max_value=10000
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True, "gacha": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        if isinstance(role, str):
            role = await ctx.guild.fetch_role(int(role))

        members: list[int] = []

        if (
            "COMMUNITY" in ctx.guild.features
            or "ENABLED_MODERATION_EXPERIENCE_FOR_NON_COMMUNITY" in ctx.guild.features
        ) and ipy.Permissions.MANAGE_GUILD in ctx.app_permissions:
            # fast path - can use an undocumented endpoint
            retry = 0

            while True:
                # https://docs.discord.food/resources/guild#search-guild-members
                data = await ctx.bot.http.request(
                    route=Route("POST", f"/guilds/{ctx.guild_id}/members-search"),
                    payload={
                        "and_query": {"role_ids": {"and_query": [str(role.id)]}},
                        "limit": 250,  # surely this is a reasonable limit
                    },
                )

                # index is likely being build, let's wait
                if retry_after := data.get("retry_after"):
                    if retry_after == 0:
                        retry_after = 0.5
                    await asyncio.sleep(retry_after)

                    if retry >= 5:  # reasonable limit
                        raise utils.CustomCheckFailure("Failed to fetch members.")

                    retry += 1
                    continue

                if typing.TYPE_CHECKING:
                    data: GuildMembersSearchResult

                members = [int(m["member"]["user"]["id"]) for m in data["members"]]
                break
        else:
            # slow path, we just have to iterate over all members
            if not ctx.guild.chunked.is_set():
                await ctx.guild.chunk()

            members = [int(m.id) for m in role.members]

        if not members:
            raise utils.CustomCheckFailure(
                f"No members with the {role.name} role were found."
            )

        try:
            for member in members:
                await self.bot.gacha_locks[f"{ctx.guild_id}-{member}"].acquire()

            existing_players = await models.GachaPlayer.filter(
                guild_id=ctx.guild_id,
                user_id__in=members,
            )
            if any(p.currency_amount + amount > 2147483647 for p in existing_players):
                raise ipy.errors.BadArgument(
                    "One or more users would have more than the maximum amount of"
                    " currency, 2,147,483,647, after this operation."
                )

            existing_players_set = {p.user_id for p in existing_players}
            non_existing_players = set(members).difference(existing_players_set)

            async with in_transaction():
                await models.GachaPlayer.filter(
                    guild_id=ctx.guild_id, user_id__in=list(existing_players_set)
                ).update(currency_amount=F("currency_amount") + amount)

                await models.GachaPlayer.bulk_create(
                    models.GachaPlayer(
                        guild_id=ctx.guild_id, user_id=user_id, currency_amount=amount
                    )
                    for user_id in non_existing_players
                )
        finally:
            for member in members:
                if self.bot.gacha_locks[f"{ctx.guild_id}-{member}"].locked():
                    self.bot.gacha_locks[f"{ctx.guild_id}-{member}"].release()

        await ctx.send(
            embed=utils.make_embed(
                f"Added {amount} {config.names.currency_name(amount)} to all users with"
                f" the {role.name} role."
            )
        )

    @manage.subcommand(
        "add-currency-players",
        sub_cmd_description=(
            "Adds a certain amount of currency to all users with the Player role."
        ),
    )
    async def gacha_give_all(
        self,
        ctx: utils.THIASlashContext,
        amount: int = tansy.Option(
            "The amount of currency to add.", min_value=1, max_value=10000
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True, "gacha": True})

        if not config.player_role:
            raise utils.CustomCheckFailure(
                "Player role not set. Please set it with"
                f" {self.bot.mention_command('config player set')} first."
            )

        actual_role = await ctx.guild.fetch_role(config.player_role)
        if actual_role is None:
            raise utils.CustomCheckFailure("The Player role was not found.")

        await self.gacha_give_role.call_with_binding(
            self.gacha_give_role.callback,
            ctx,
            actual_role,
            amount,
        )

    @manage.subcommand(
        "list-currency-amounts",
        sub_cmd_description="Lists the currency amounts of all users.",
    )
    async def gacha_view_all_currencies(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        players = await models.GachaPlayer.filter(guild_id=ctx.guild_id).order_by(
            "-currency_amount"
        )

        if not players:
            raise ipy.errors.BadArgument("No users have data for gacha.")

        str_build: list[str] = []
        str_build.extend(
            f"<@{player.user_id}> - {player.currency_amount}"
            f" {config.names.currency_name(player.currency_amount)}"
            for player in players
        )

        await ctx.send(
            embed=utils.make_embed("\n".join(str_build), title="Gacha Currency Amounts")
        )

    @manage.subcommand(
        "user-profile",
        sub_cmd_description="Views the currency amount and items of a user.",
    )
    async def gacha_view(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to view currency amount and items for.",
            type=ipy.User,
        ),
        sort_by: str = tansy.Option(
            "What should the items be sorted by?",
            choices=[
                ipy.SlashCommandChoice("Name", "name"),
                ipy.SlashCommandChoice("Rarity", "rarity"),
                ipy.SlashCommandChoice("Time First Gotten", "time_gotten"),
            ],
            default="name",
        ),
        mode: str = tansy.Option(
            "The mode to show the profile in.",
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
        if sort_by not in ("name", "rarity", "time_gotten"):
            raise ipy.errors.BadArgument("Invalid option for sorting.")

        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        player = await models.GachaPlayer.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        ).prefetch_related(
            Prefetch("items", models.ItemToPlayer.filter().prefetch_related("item"))
        )

        if player is None:
            raise ipy.errors.BadArgument("The user has no data for gacha.")

        if mode == "modern" or mode == "spacious":
            if mode == "spacious":
                chunks = player.create_profile_spacious(
                    config.names, sort_by=sort_by, admin=True
                )
            else:
                chunks = player.create_profile_modern(config.names, sort_by=sort_by)

            if len(chunks) == 1:
                await ctx.send(
                    components=ipy.ContainerComponent(
                        ipy.TextDisplayComponent(
                            f"# {ctx.author.display_name}'s Gacha Profile"
                        ),
                        *chunks[0],
                        accent_color=self.bot.color.value,
                    )
                )
                return

            pag = classes.ContainerPaginator(
                self.bot,
                title=f"{ctx.author.display_name}'s Gacha Profile",
                pages_data=chunks,
            )
            await pag.send(ctx)
            return

        if mode == "cozy":
            embeds = player.create_profile_cozy(
                ctx.author.display_name, config.names, sort_by=sort_by
            )
        else:
            embeds = player.create_profile_compact(
                ctx.author.display_name, config.names, sort_by=sort_by
            )

        if len(embeds) > 1:
            pag = help_tools.HelpPaginator.create_from_embeds(
                self.bot, *embeds, timeout=120
            )
            pag.show_callback_button = False
            await pag.send(ctx)
        else:
            await ctx.send(embeds=embeds)

    gacha_inventory = utils.alias(
        gacha_view,
        "gacha-manage user-inventory",
        "Views the currency amount and items of a user. Alias of /gacha-manage"
        " user-profile.",
    )

    @manage.subcommand(
        "remove-item-from", sub_cmd_description="Removes an item from a user."
    )
    async def gacha_remove_item_from(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to remove an item from."),
        name: str = tansy.Option("The name of the item to remove.", autocomplete=True),
        amount: int | None = tansy.Option(
            "The amount to remove. Defaults to the amount of that item they have.",
            min_value=1,
        ),
        _replenish_gacha: str = tansy.Option(
            "Should said amount of the item be added back into the gacha pool? Defaults"
            " to no.",
            name="replenish_gacha",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        replenish_gacha = _replenish_gacha == "yes"

        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise ipy.errors.BadArgument("No item with that name exists.")

        items = await models.ItemToPlayer.filter(
            player__user_id=user.id, player__guild_id=ctx.guild_id, item_id=item.id
        )
        if not items:
            raise ipy.errors.BadArgument("The user does not have that item.")
        items_count = len(items)

        if amount is None:
            amount = items_count

        if items_count < amount:
            raise ipy.errors.BadArgument(
                "The user does not have that many items to remove."
            )

        await models.ItemToPlayer.filter(
            id__in=[item.id for item in items[:amount]]
        ).delete()

        if replenish_gacha and item.amount != -1:
            await models.GachaItem.filter(id=item.id).update(
                amount=F("amount") + amount
            )

        reply_str = f"Removed {amount} of {item.name} from {user.mention}."
        if replenish_gacha and item.amount != -1:
            reply_str += f" Added {amount} back into the gacha pool."

        await ctx.send(embed=utils.make_embed(reply_str))

    @manage.subcommand("add-item-to", sub_cmd_description="Adds an item to a user.")
    async def gacha_add_item_to(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to add an item to."),
        name: str = tansy.Option("The name of the item to add.", autocomplete=True),
        amount: int | None = tansy.Option(
            "The amount to add. Defaults to 1.",
            min_value=1,
            max_value=500,
        ),
        _remove_amount_from_gacha: str = tansy.Option(
            "Should said amount of the item be removed from the gacha pool? Defaults"
            " to no.",
            name="remove_amount_from_gacha",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        remove_amount_from_gacha = _remove_amount_from_gacha == "yes"

        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise ipy.errors.BadArgument("No item with that name exists.")

        if amount is None:
            amount = 1

        if remove_amount_from_gacha and item.amount != -1 and item.amount < amount:
            raise ipy.errors.BadArgument(
                "The item does not have enough quantity to give."
            )

        player_gacha, _ = await models.GachaPlayer.get_or_create(
            guild_id=ctx.guild_id, user_id=user.id
        )

        if (
            await models.ItemToPlayer.filter(
                player_id=player_gacha.id, item_id=item.id
            ).count()
            >= 500
        ):
            raise ipy.errors.BadArgument(
                "The user can have a maximum of 500 of this item."
            )

        await models.ItemToPlayer.bulk_create(
            models.ItemToPlayer(
                player_id=player_gacha.id,
                item_id=item.id,
            )
            for _ in range(amount)
        )

        if remove_amount_from_gacha and item.amount != -1:
            await models.GachaItem.filter(id=item.id).update(
                amount=F("amount") - amount
            )

        reply_str = f"Added {amount} of {item.name} to {user.mention}."
        if remove_amount_from_gacha:
            reply_str += f" Removed {amount} from the gacha pool."

        await ctx.send(embed=utils.make_embed(reply_str))

    @gacha_add_item_to.autocomplete("name")
    async def _autocomplete_gacha_items(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        return await fuzzy.autocomplete_gacha_item(ctx, **ctx.kwargs)

    @gacha_remove_item_from.autocomplete("name")
    async def _autocomplete_gacha_user_item(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        return await fuzzy.autocomplete_gacha_optional_user_item(ctx, **ctx.kwargs)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(help_tools)
    importlib.reload(classes)
    GachaManagement(bot)
