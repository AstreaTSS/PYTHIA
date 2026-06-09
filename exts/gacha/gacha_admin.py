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
import discord
import orjson
import pydantic
import ragwort
import typing_extensions as typing
from discord.ext import commands
from tortoise.expressions import F
from tortoise.query_utils import Prefetch
from tortoise.transactions import in_transaction

import common.classes as classes
import common.exports as exports
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils

from . import gacha_common

if typing.TYPE_CHECKING:
    from discord.types.member import MemberWithUser


class GuildMemberEntry(typing.TypedDict):
    member: "MemberWithUser"


class GuildMembersSearchResult(typing.TypedDict):
    guild_id: str
    members: list[GuildMemberEntry]
    page_result_count: int
    total_result_count: int


class GachaManagement(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Gacha Management"

        self.bot.add_view(gacha_common.gacha_item_button("thia-button:add_gacha_item"))
        self.bot.add_view(gacha_common.gacha_item_button("thia:add-gacha-new"))

    manage = ragwort.SlashCommandGroup(
        name="gacha-manage",
        description="Handles management of gacha mechanics.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={
            discord.InteractionContextType.guild,
        },
    )

    @manage.command(
        name="add-item",
        description="Adds an item to the gacha.",
    )
    @ragwort.auto_defer(enabled=False)
    async def gacha_item_add(
        self,
        ctx: utils.THIASlashContext,
        _send_button: str = ragwort.Option(
            "Should a button be sent that allows for repeatedly adding items?",
            name="send_button",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="yes",
        ),
    ) -> None:
        send_button = _send_button == "yes"

        if send_button:
            await ctx.respond(view=gacha_common.gacha_item_button("thia:add-gacha-new"))
            return

        await ctx.send_modal(gacha_common.CreateGachaItemModal())

    @manage.command(
        name="edit-item",
        description="Edits an item in the gacha.",
    )
    @ragwort.auto_defer(enabled=False)
    async def gacha_item_edit(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to edit.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise utils.BadArgument("No item with that name exists.")

        await ctx.send_modal(gacha_common.EditGachaItemModal(item))

    @manage.command(
        name="delete-item",
        description="Deletes an item from the gacha.",
    )
    async def gacha_item_delete(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to delete.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        amount = await models.GachaItem.filter(
            guild_id=ctx.guild_id, name=name
        ).delete()

        if amount <= 0:
            raise utils.BadArgument("No item with that name exists.")

        await ctx.respond(view=utils.make_view(f"Deleted {name}."))

    gacha_item_remove = utils.alias(
        gacha_item_delete,
        name="remove-item",
        description=(
            "Removes an item from the gacha. Alias of /gacha-manage delete-item."
        ),
    )

    @manage.command(name="view-item", description="Views an item in the gacha.")
    async def gacha_view_single_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to view.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise utils.BadArgument("No item with that name exists.")

        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha and isinstance(config.gacha, models.GachaConfig)
            assert config.names and isinstance(config.names, models.Names)

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)

        await ctx.respond(
            view=utils.quick_view(
                item.container(config.names, rarities, show_amount=True)
            )
        )

    @manage.command(
        name="list-items", description="Lists all gacha items for this server."
    )
    async def gacha_view_items(
        self,
        ctx: utils.THIASlashContext,
        sort_by: str = ragwort.Option(
            "What should the items be sorted by?",
            choices=[
                discord.OptionChoice("Name", "name"),
                discord.OptionChoice("Rarity", "rarity"),
                discord.OptionChoice("Time Created", "time_created"),
            ],
            default="name",
        ),
        mode: str = ragwort.Option(
            "The mode to show the items in.",
            choices=[
                discord.OptionChoice("Modern", "modern"),
                discord.OptionChoice("Spacious", "spacious"),
                discord.OptionChoice("Compact", "compact"),
            ],
            default="modern",
        ),
    ) -> None:
        if mode not in ("cozy", "compact", "modern", "spacious"):
            raise utils.BadArgument("Invalid mode.")
        if sort_by not in ("name", "rarity", "time_created"):
            raise utils.BadArgument("Invalid option for sorting.")

        if mode == "cozy":  # basically the same thing
            mode = "modern"

        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        items = await models.GachaItem.filter(guild_id=ctx.guild_id)
        if not items:
            raise utils.CustomCheckFailure("This server has no items to show.")

        if sort_by == "name":
            sorted_items = sorted(items, key=lambda i: i.name.lower())
        elif sort_by == "rarity":
            sorted_items = sorted(items, key=lambda i: (i.rarity.value, i.name.lower()))
        else:
            sorted_items = sorted(items, key=lambda i: (i.id))

        components: list[discord.ui.ViewItem] = []
        split_components: list[list[discord.ui.ViewItem]] = []
        max_num = 0

        if mode == "spacious":
            components = [
                discord.ui.Section(
                    discord.ui.TextDisplay(
                        f"**{discord.utils.escape_markdown(item.name)}**{f' ({item.amount} remaining)' if item.amount != -1 else ''}\n-#"
                        f" {config.names.rarity_name(item.rarity)} ●"
                        f" {models.short_desc(item.description, length=50)}"
                    ),
                    accessory=discord.ui.Button(
                        style=discord.ButtonStyle.gray,
                        label="View",
                        custom_id=f"gacha-item-{item.id}-admin",
                    ),
                )
                for item in sorted_items
            ]
            max_num = 10
        elif mode == "modern":
            components = [
                discord.ui.TextDisplay(
                    f"**{discord.utils.escape_markdown(item.name)}**{f' ({item.amount} remaining)' if item.amount != -1 else ''}\n-#"
                    f" {config.names.rarity_name(item.rarity)} ●"
                    f" {models.short_desc(item.description, length=50)}"
                )
                for item in sorted_items
            ]
            max_num = 15
        else:
            items_list = [
                f"**{discord.utils.escape_markdown(i.name)}**{f' ({i.amount} remaining)' if i.amount != -1 else ''}:"
                f" {models.short_desc(i.description)}"
                for i in sorted_items
            ]

            chunks = [items_list[x : x + 30] for x in range(0, len(items_list), 30)]
            for chunk in chunks:
                split_components.append([discord.ui.TextDisplay("\n".join(chunk))])

        if components and not split_components:
            split_components = [
                components[x : x + max_num] for x in range(0, len(components), max_num)
            ]

        pag = classes.ContainerPaginator(
            *split_components,
            title="Gacha Items",
            author_id=ctx.author.id,
        )
        await ctx.respond(view=pag)

    @manage.command(
        name="export-items", description="Exports all gacha items to a JSON file."
    )
    @commands.cooldown(1, 60, commands.BucketType.guild)
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
        items_file = discord.File(
            items_io,
            filename=f"gacha_items_{ctx.guild_id}_{int(ctx.interaction.created_at.timestamp())}.json",
        )

        container = utils.make_container(
            "Exported items to JSON file.", title="Gacha Items Export"
        )
        container.add_separator(divider=False)
        container.add_file(url=f"attachment://{items_file.filename}")

        try:
            await ctx.respond(
                view=utils.quick_view(container),
                file=items_file,
                ephemeral=True,
            )
        finally:
            items_io.close()

    @manage.command(
        name="import-items", description="Imports gacha items from a JSON file."
    )
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def gacha_import_items(
        self,
        ctx: utils.THIASlashContext,
        json_file: discord.Attachment = ragwort.Option("The JSON file to import."),
        _override: str = ragwort.Option(
            "Should pre-existing items with the same name be overriden?",
            name="override",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        override = _override == "yes"

        if not json_file.content_type or not json_file.content_type.startswith(
            "application/json"
        ):
            raise utils.BadArgument("The file must be a JSON file.")

        async with aiohttp.ClientSession() as session:
            async with session.get(json_file.url) as response:
                if response.status != 200:
                    raise utils.BadArgument("Failed to fetch the file.")

                try:
                    await response.content.readexactly(10485760 + 1)
                    raise utils.CustomCheckFailure(
                        "This file is over 10 MiB, which is not supported by this bot."
                    )
                except asyncio.IncompleteReadError as e:
                    items_json = e.partial

        try:
            items = exports.handle_gacha_item_data(items_json)
        except pydantic.ValidationError as e:
            # let's remove the first line that tells what class the error is for
            error_str = "\n".join(str(e).splitlines()[1:])
            raise utils.BadArgument(
                f"The file is not in the correct format.\n```\n{error_str}\n```"
            ) from None

        await ctx.fetch_config({"gacha": True})

        async with in_transaction():
            # TODO: this is flawed - how do we do case insensitive unique checks without doing multiple queries?
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
                    raise utils.BadArgument(
                        "One or more items in the file has a name with an item already"
                        " in this server."
                    )

            to_create: list[models.GachaItem] = [
                models.GachaItem(
                    guild_id=ctx.guild_id,
                    name=item.name,
                    description=item.description,
                    rarity=item.rarity,
                    amount=item.amount,
                    image=item.image,
                )
                for item in items
            ]
            await models.GachaItem.bulk_create(to_create)

        await ctx.respond(
            view=utils.make_view(
                "Imported items from JSON file.", title="Gacha Items Import"
            ),
        )

    @manage.command(
        name="add-currency",
        description="Adds an amount of currency to a user.",
    )
    async def gacha_give_currency(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to add currency to."),
        amount: int = ragwort.Option(
            "The amount of currency to add.", min_value=1, max_value=2147483647
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True, "gacha": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        async with self.bot.gacha_locks[f"{ctx.guild_id}-{user.id}"]:
            async with asyncio.timeout(60):
                player, _ = await models.GachaPlayer.get_or_create(
                    guild_id=ctx.guild_id, user_id=user.id
                )
                player.currency_amount += amount

                if player.currency_amount > 2147483647:
                    raise utils.BadArgument(
                        '"Frankly, the fact that you wish to make a person have'
                        " more than 2,147,483,647"
                        f" {config.names.currency_name(amount)} is absurd. I seek"
                        " to assist, but I will refuse to handle amounts like"
                        ' this." - PYTHIA'
                    )

                await player.save()

        await ctx.respond(
            view=utils.make_view(
                f"Added {amount} {config.names.currency_name(amount)} to"
                f" {user.mention}. They now have {player.currency_amount}"
                f" {config.names.currency_name(player.currency_amount)}."
            )
        )

    @manage.command(
        name="remove-currency",
        description="Removes a certain amount of currency from a user.",
    )
    async def gacha_remove_currency(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to remove currency from.",
        ),
        amount: int = ragwort.Option(
            "The amount of currency to remove.", min_value=1, max_value=2147483647
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True, "gacha": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        async with self.bot.gacha_locks[f"{ctx.guild_id}-{user.id}"]:
            async with asyncio.timeout(60):
                player, _ = await models.GachaPlayer.get_or_create(
                    guild_id=ctx.guild_id, user_id=user.id
                )
                player.currency_amount -= amount

                if player.currency_amount < -2147483647:
                    raise utils.BadArgument(
                        '"Frankly, the fact that you make a person have less than'
                        f" than -2,147,483,647 {config.names.currency_name(amount)}"
                        " is absurd. Surely, you only did so to test my"
                        ' capabilities, correct?" - PYTHIA'
                    )

                await player.save()

        await ctx.respond(
            view=utils.make_view(
                f"Removed {amount} {config.names.currency_name(amount)} from"
                f" {user.mention}. They now have {player.currency_amount}"
                f" {config.names.currency_name(player.currency_amount)}."
            )
        )

    @manage.command(
        name="reset-currency",
        description="Resets currency amount for a user.",
    )
    async def gacha_reset_currency(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to reset currency for.",
        ),
    ) -> None:
        async with self.bot.gacha_locks[f"{ctx.guild_id}-{user.id}"]:
            amount = await models.GachaPlayer.filter(
                guild_id=ctx.guild_id, user_id=user.id, currency_amount__not=0
            ).update(currency_amount=0)

            if amount == 0:
                raise utils.BadArgument("The user has no currency to reset.")

            await ctx.respond(
                view=utils.make_view(f"Reset currency for {user.mention}.")
            )

    @manage.command(
        name="reset-items",
        description="Resets items for a user.",
    )
    async def gacha_reset_items(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to reset items for.",
        ),
    ) -> None:
        to_delete = await models.ItemToPlayer.filter(
            player__user_id=user.id, player__guild_id=ctx.guild_id
        ).values_list("id", flat=True)

        if not to_delete:
            raise utils.BadArgument("The user has no items to reset.")

        await models.ItemToPlayer.filter(id__in=to_delete).delete()

        await ctx.respond(view=utils.make_view(f"Reset items for {user.mention}."))

    @manage.command(
        name="clear-user",
        description=(
            "Clears/removes gacha data, including currency and items, for a user."
        ),
    )
    async def gacha_clear_user(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to clear data for.",
        ),
    ) -> None:
        amount = await models.GachaPlayer.filter(
            guild_id=ctx.guild_id, user_id=user.id
        ).delete()

        if not amount:
            raise utils.BadArgument("The user has no data to clear.")

        await ctx.respond(
            view=utils.make_view(f"Cleared/removed data for {user.mention}.")
        )

    @manage.command(
        name="clear-items",
        description="Clears/removes all items for this server. Use with caution!",
    )
    async def gacha_clear_items(
        self,
        ctx: utils.THIASlashContext,
        confirm: bool = ragwort.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise utils.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        items_amount = await models.GachaItem.filter(guild_id=ctx.guild_id).delete()

        if items_amount <= 0:
            raise utils.CustomCheckFailure("There's no gacha item data to clear!")

        await ctx.respond(view=utils.make_view("All gacha items data cleared."))

    @manage.command(
        name="clear-everything",
        description="Clears ALL gacha user and items data. Use with caution!",
    )
    async def gacha_clear(
        self,
        ctx: utils.THIASlashContext,
        confirm: bool = ragwort.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise utils.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        players_amount = await models.GachaPlayer.filter(guild_id=ctx.guild_id).delete()
        items_amount = await models.GachaItem.filter(guild_id=ctx.guild_id).delete()

        if players_amount + items_amount <= 0:
            raise utils.CustomCheckFailure("There's no gacha data to clear!")

        await ctx.respond(
            view=utils.make_view("All gacha user and items data cleared.")
        )

    @manage.command(
        name="add-currency-role",
        description=(
            "Adds a certain amount of currency to all users with a specific role."
        ),
    )
    async def gacha_give_role(
        self,
        ctx: utils.THIASlashContext,
        role: discord.Role = ragwort.Option("The role to add currency to."),
        amount: int = ragwort.Option(
            "The amount of currency to add.", min_value=1, max_value=10000
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True, "gacha": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        members: list[int] = []

        if (
            "COMMUNITY" in ctx.guild.features
            or "ENABLED_MODERATION_EXPERIENCE_FOR_NON_COMMUNITY" in ctx.guild.features
        ) and ctx.app_permissions.is_superset(discord.Permissions(manage_guild=True)):
            # fast path - can use an undocumented endpoint
            retry = 0

            while True:
                # https://docs.discord.food/resources/guild#search-guild-members
                data = await ctx.bot.http.request(
                    discord.Route("POST", f"/guilds/{ctx.guild_id}/members-search"),
                    json={
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
            if not ctx.guild.chunked:
                async with asyncio.timeout(60 * 2):
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
                raise utils.BadArgument(
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

        await ctx.respond(
            view=utils.make_view(
                f"Added {amount} {config.names.currency_name(amount)} to all users with"
                f" the {role.name} role."
            )
        )

    @manage.command(
        name="add-currency-players",
        description=(
            "Adds a certain amount of currency to all users with the Player role."
        ),
    )
    async def gacha_give_all(
        self,
        ctx: utils.THIASlashContext,
        amount: int = ragwort.Option(
            "The amount of currency to add.", min_value=1, max_value=10000
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True, "gacha": True})

        if not config.player_role:
            raise utils.CustomCheckFailure(
                "Player role not set. Please set it with"
                f" {self.bot.mention_command('config player set')} first."
            )

        actual_role = await ctx.guild.get_or_fetch(discord.Role, config.player_role)
        if actual_role is None:
            raise utils.CustomCheckFailure("The Player role was not found.")

        await self.gacha_give_role(
            ctx,
            actual_role,
            amount,
        )

    @manage.command(
        name="list-currency-amounts",
        description="Lists the currency amounts of all users.",
    )
    async def gacha_view_all_currencies(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        players = await models.GachaPlayer.filter(guild_id=ctx.guild_id).order_by(
            "-currency_amount"
        )

        if not players:
            raise utils.BadArgument("No users have data for gacha.")

        str_build: list[str] = []
        str_build.extend(
            f"<@{player.user_id}> - {player.currency_amount}"
            f" {config.names.currency_name(player.currency_amount)}"
            for player in players
        )

        await ctx.respond(
            view=utils.make_view("\n".join(str_build), title="Gacha Currency Amounts")
        )

    @manage.command(
        name="user-profile",
        description="Views the currency amount and items of a user.",
    )
    async def gacha_view(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option(
            "The user to view currency amount and items for.",
        ),
        sort_by: str = ragwort.Option(
            "What should the items be sorted by?",
            choices=[
                discord.OptionChoice("Name", "name"),
                discord.OptionChoice("Rarity", "rarity"),
                discord.OptionChoice("Time First Gotten", "time_gotten"),
            ],
            default="name",
        ),
        mode: str = ragwort.Option(
            "The mode to show the profile in.",
            choices=[
                discord.OptionChoice("Modern", "modern"),
                discord.OptionChoice("Spacious", "spacious"),
                discord.OptionChoice("Compact", "compact"),
            ],
            default="modern",
        ),
    ) -> None:
        if mode not in ("cozy", "compact", "modern", "spacious"):
            raise utils.BadArgument("Invalid mode.")
        if sort_by not in ("name", "rarity", "time_gotten"):
            raise utils.BadArgument("Invalid option for sorting.")

        if mode == "cozy":  # basically the same thing
            mode = "modern"

        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        player = await models.GachaPlayer.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        ).prefetch_related(
            Prefetch("items", models.ItemToPlayer.filter().prefetch_related("item"))
        )

        if player is None:
            raise utils.BadArgument("The user has no data for gacha.")

        if mode == "spacious":
            chunks = player.create_profile_spacious(
                config.names, sort_by=sort_by, admin=True
            )
        elif mode == "modern":
            chunks = player.create_profile_modern(config.names, sort_by=sort_by)
        else:
            chunks = player.create_profile_compact(config.names, sort_by=sort_by)

        pag = classes.ContainerPaginator(
            *chunks,
            title=f"{ctx.author.display_name}'s Gacha Profile",
            author_id=ctx.author.id,
        )
        await ctx.respond(view=pag)

    gacha_inventory = utils.alias(
        gacha_view,
        name="user-inventory",
        description=(
            "Views the currency amount and items of a user. Alias of /gacha-manage"
            " user-profile."
        ),
    )

    @manage.command(name="remove-item-from", description="Removes an item from a user.")
    async def gacha_remove_item_from(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to remove an item from."),
        name: str = ragwort.Option(
            "The name of the item to remove.",
        ),
        amount: int | None = ragwort.Option(
            "The amount to remove. Defaults to the amount of that item they have.",
            min_value=1,
            default=None,
        ),
        _replenish_gacha: str = ragwort.Option(
            "Should said amount of the item be added back into the gacha pool? Defaults"
            " to no.",
            name="replenish_gacha",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        replenish_gacha = _replenish_gacha == "yes"

        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise utils.BadArgument("No item with that name exists.")

        items = await models.ItemToPlayer.filter(
            player__user_id=user.id, player__guild_id=ctx.guild_id, item_id=item.id
        )
        if not items:
            raise utils.BadArgument("The user does not have that item.")
        items_count = len(items)

        if amount is None:
            amount = items_count

        if items_count < amount:
            raise utils.BadArgument("The user does not have that many items to remove.")

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

        await ctx.respond(view=utils.make_view(reply_str))

    @manage.command(name="add-item-to", description="Adds an item to a user.")
    async def gacha_add_item_to(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to add an item to."),
        name: str = ragwort.Option("The name of the item to add."),
        amount: int = ragwort.Option(
            "The amount to add. Defaults to 1.",
            min_value=1,
            max_value=500,
            default=1,
        ),
        _remove_amount_from_gacha: str = ragwort.Option(
            "Should said amount of the item be removed from the gacha pool? Defaults"
            " to no.",
            name="remove_amount_from_gacha",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        remove_amount_from_gacha = _remove_amount_from_gacha == "yes"

        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise utils.BadArgument("No item with that name exists.")

        if remove_amount_from_gacha and item.amount != -1 and item.amount < amount:
            raise utils.BadArgument("The item does not have enough quantity to give.")

        player_gacha, _ = await models.GachaPlayer.get_or_create(
            guild_id=ctx.guild_id, user_id=user.id
        )

        if (
            await models.ItemToPlayer.filter(
                player_id=player_gacha.id, item_id=item.id
            ).count()
            >= 500
        ):
            raise utils.BadArgument("The user can have a maximum of 500 of this item.")

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

        await ctx.respond(view=utils.make_view(reply_str))

    @gacha_item_edit.autocomplete("name")
    @gacha_item_delete.autocomplete("name")
    @gacha_item_remove.autocomplete("name")
    @gacha_view_single_item.autocomplete("name")
    @gacha_add_item_to.autocomplete("name")
    async def _autocomplete_gacha_items(
        self,
        ctx: discord.AutocompleteContext,
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_gacha_item(ctx, **ctx.options)

    @gacha_remove_item_from.autocomplete("name")
    async def _autocomplete_gacha_user_item(
        self,
        ctx: discord.AutocompleteContext,
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_gacha_optional_user_item(ctx, **ctx.options)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(classes)
    importlib.reload(exports)
    importlib.reload(gacha_common)
    bot.add_cog(GachaManagement(bot))
