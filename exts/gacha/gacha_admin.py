"""
Copyright 2021-2025 AstreaTSS.
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
import msgspec
import orjson
import tansy
import typing_extensions as typing
from interactions.api.http.route import Route
from interactions.models.misc.iterator import AsyncIterator
from tortoise.expressions import F
from tortoise.query_utils import Prefetch
from tortoise.transactions import in_transaction

import common.exports as exports
import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.text_utils as text_utils
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


class MemberIterator(AsyncIterator):
    def __init__(self, guild: "ipy.Guild", limit: int = 0) -> None:
        super().__init__(limit)
        self.guild = guild
        self._more = True

    async def fetch(self) -> list:
        if self._more:
            expected = self.get_limit

            rcv = await self.guild._client.http.list_members(
                self.guild.id,
                limit=expected,
                after=self.last["user"]["id"] if self.last else ipy.MISSING,
            )
            if not rcv:
                raise asyncio.QueueEmpty
            self._more = len(rcv) == expected
            return rcv
        raise asyncio.QueueEmpty


class GachaManagement(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Gacha Management"

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
                max_length=1024,
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

    config = tansy.SlashCommand(
        name="gacha-config",
        description="Handles configuration of gacha mechanics.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        "info",
        sub_cmd_description=(
            "Lists out the gacha configuration settings for the server."
        ),
    )
    async def gacha_info(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None
            assert config.names is not None

        str_builder = [
            (
                "Player role:"
                f" {f'<@&{config.player_role}>' if config.player_role else 'N/A'}"
            ),
            f"Gacha status: {utils.toggle_friendly_str(config.gacha.enabled)}",
            f"Gacha use cost: {config.gacha.currency_cost}",
            (
                "Draw duplicates:"
                f" {utils.toggle_friendly_str(config.gacha.draw_duplicates)}"
            ),
        ]

        embed = utils.make_embed(
            "\n".join(str_builder),
            title=f"Gacha config for {ctx.guild.name}",
        )

        names = (
            f"Singular Currency Name: {config.names.singular_currency_name}\nPlural"
            f" Currency Name: {config.names.plural_currency_name}"
        )

        embed.add_field("Names", names, inline=True)
        await ctx.send(embed=embed)

    @config.subcommand(
        "toggle", sub_cmd_description="Enables or disables the entire gacha system."
    )
    async def gacha_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = tansy.Option(
            "Should the gacha system be turned on or off?",
            name="toggle",
            choices=[
                ipy.SlashCommandChoice("on", "on"),
                ipy.SlashCommandChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        config = await ctx.fetch_config({"gacha": True})

        if toggle and not config.player_role:
            raise utils.CustomCheckFailure(
                "Player role not set. Please set it with"
                f" {self.bot.mention_command('config player')} first."
            )

        await models.GachaConfig.filter(guild_id=ctx.guild_id).update(enabled=toggle)

        await ctx.send(
            embed=utils.make_embed(
                f"Gacha system turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.subcommand(
        "names",
        sub_cmd_description="Sets the name of the currency to be used.",
    )
    @ipy.auto_defer(enabled=False)
    async def gacha_name(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        modal = ipy.Modal(
            ipy.InputText(
                label="Singular Currency Name",
                style=ipy.TextStyles.SHORT,
                custom_id="singular_currency_name",
                value=config.names.singular_currency_name,
                max_length=40,
            ),
            ipy.InputText(
                label="Plural Currency Name",
                style=ipy.TextStyles.SHORT,
                custom_id="plural_currency_name",
                value=config.names.plural_currency_name,
                max_length=40,
            ),
            title="Edit Currency Names",
            custom_id="currency_names",
        )

        await ctx.send_modal(modal)

    @ipy.modal_callback("currency_names")
    async def currency_names_edit(self, ctx: utils.THIAModalContext) -> None:
        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        names = config.names

        names.singular_currency_name = ctx.kwargs["singular_currency_name"]
        names.plural_currency_name = ctx.kwargs["plural_currency_name"]
        await names.save()

        await ctx.send(
            embed=utils.make_embed(
                "Updated! Please note this will only affect public-facing"
                f" aspects.\nSingular: {names.singular_currency_name}\nPlural:"
                f" {names.plural_currency_name}"
            )
        )

    @config.subcommand(
        "cost", sub_cmd_description="Sets the cost of a single gacha use."
    )
    async def gacha_cost(
        self,
        ctx: utils.THIASlashContext,
        cost: int = tansy.Option(
            "The cost of a single gacha use.", min_value=1, max_value=2147483647
        ),
    ) -> None:
        if cost > 2147483647:  # just in case
            raise ipy.errors.BadArgument(
                "This amount is too high. Please set an amount at or lower than"
                " 2,147,483,647 (signed 32-bit integer limit)."
            )

        await ctx.fetch_config({"gacha": True})
        await models.GachaConfig.filter(guild_id=ctx.guild_id).update(
            currency_cost=cost
        )

        await ctx.send(
            embed=utils.make_embed(
                f"Updated! The cost of a single gacha use is now {cost}."
            )
        )

    @config.subcommand(
        "draw-duplicates",
        sub_cmd_description=(
            "Toggles the ability for players draw items they already own."
        ),
    )
    async def gacha_draw_duplicates(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = tansy.Option(
            "Should players be allowed to draw items they already own?",
            name="toggle",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "yes"

        await ctx.fetch_config({"gacha": True})
        await models.GachaConfig.filter(guild_id=ctx.guild_id).update(
            draw_duplicates=toggle
        )

        await ctx.send(
            embed=utils.make_embed(
                f"Drawing duplicates turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.subcommand(
        "help", sub_cmd_description="Tells you how to set up the gacha system."
    )
    async def gacha_help(self, ctx: utils.THIASlashContext) -> None:
        embed = utils.make_embed(
            "To set up the gacha system, follow the gacha setup guide below.",
            title="Setup Bot",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.LINK,
            label="Gacha Setup Guide",
            url="https://pythia.astrea.cc/setup/gacha_setup",
        )
        await ctx.send(embeds=embed, components=button)

    manage = tansy.SlashCommand(
        name="gacha-manage",
        description="Handles management of gacha mechanics.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @manage.subcommand(
        "add-currency",
        sub_cmd_description="Adds an amount of currency to a user.",
    )
    async def gacha_give_currency(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to add currency to."),
        amount: int = tansy.Option(
            "The amount of currency to add.", min_value=1, max_value=2147483647
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True, "gacha": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        player, _ = await models.GachaPlayer.get_or_create(
            guild_id=ctx.guild_id, user_id=user.id
        )
        player.currency_amount += amount

        if player.currency_amount > 2147483647:
            raise ipy.errors.BadArgument(
                '"Frankly, the fact that you wish to make a person have more than'
                f" 2,147,483,647 {config.names.currency_name(amount)} is absurd. I seek"
                ' to assist, but I will refuse to handle amounts like this." - PYTHIA'
            )

        await player.save()

        await ctx.send(
            embed=utils.make_embed(
                f"Added {amount} {config.names.currency_name(amount)} to"
                f" {user.mention}. New total: {player.currency_amount}."
            )
        )

    @manage.subcommand(
        "remove-currency",
        sub_cmd_description="Removes a certain amount of currency from a user.",
    )
    async def gacha_remove_currency(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option(
            "The user to remove currency from.",
        ),
        amount: int = tansy.Option(
            "The amount of currency to remove.", min_value=1, max_value=2147483647
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True, "gacha": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        player, _ = await models.GachaPlayer.get_or_create(
            guild_id=ctx.guild_id, user_id=user.id
        )
        player.currency_amount -= amount

        if player.currency_amount < -2147483647:
            raise ipy.errors.BadArgument(
                '"Frankly, the fact that you make a person have less than than'
                f" -2,147,483,647 {config.names.currency_name(amount)} is absurd."
                ' Surely, you only did so to test my capabilities, correct?" - PYTHIA'
            )

        await player.save()

        await ctx.send(
            embed=utils.make_embed(
                f"Removed {amount} {config.names.currency_name(amount)} from"
                f" {user.mention}. New total: {player.currency_amount}."
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
        amount = await models.GachaPlayer.filter(
            guild_id=ctx.guild_id, user_id=user.id, currency_amount__not=0
        ).update(currency_amount=0)

        if amount == 0:
            raise ipy.errors.BadArgument("The user has no currency to reset.")

        await ctx.send(embed=utils.make_embed(f"Reset currency for {user.mention}."))

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
        amount = await models.ItemToPlayer.filter(
            player__user_id=user.id, player__guild_id=ctx.guild_id
        ).delete()

        if not amount:
            raise ipy.errors.BadArgument("The user has no items to reset.")

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
        if typing.TYPE_CHECKING:
            assert config.names is not None

        if not config.player_role:
            raise utils.CustomCheckFailure(
                "Player role not set. Please set it with"
                f" {self.bot.mention_command('config player')} first."
            )

        actual_role = await ctx.guild.fetch_role(config.player_role)
        if actual_role is None:
            raise utils.CustomCheckFailure("The Player role was not found.")

        members: list[GuildMemberEntry] = []

        if "COMMUNITY" in ctx.guild.features:
            # fast path - can use an undocumented endpoint
            retry = 0

            while True:
                # https://docs.discord.sex/resources/guild#search-guild-members
                data = await ctx.bot.http.request(
                    route=Route("POST", f"/guilds/{ctx.guild_id}/members-search"),
                    payload={
                        "and_query": {"role_ids": {"and_query": [str(actual_role.id)]}},
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

                members = data["members"]
                break
        else:
            # slow path, we just have to iterate over all members
            iterator = MemberIterator(ctx.guild)
            async for member in iterator:
                if str(actual_role.id) in member["roles"]:
                    members.append({"member": member})

        if not members:
            raise utils.CustomCheckFailure(
                "No members with the Player role were found."
            )

        existing_players = await models.GachaPlayer.filter(
            guild_id=ctx.guild_id,
            user_id__in=[int(m["member"]["user"]["id"]) for m in members],
        )
        if any(p.currency_amount + amount > 2147483647 for p in existing_players):
            raise ipy.errors.BadArgument(
                "One or more users would have more than the maximum amount of currency,"
                " 2,147,483,647, after this operation."
            )

        existing_players_set = {p.user_id for p in existing_players}
        non_existing_players = {
            int(m["member"]["user"]["id"]) for m in members
        }.difference(existing_players_set)

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

        await ctx.send(
            embed=utils.make_embed(
                f"Added {amount} {config.names.currency_name(amount)} to all players."
            )
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
            f"<@{player.user_id}> -"
            f" {player.currency_amount} {config.names.currency_name(player.currency_amount)}"
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
    ) -> None:
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

        embeds = player.create_profile(user.display_name, config.names)

        if len(embeds) > 1:
            pag = help_tools.HelpPaginator.create_from_embeds(
                self.bot, *embeds, timeout=120
            )
            pag.show_callback_button = False
            await pag.send(ctx)
        else:
            await ctx.send(embeds=embeds)

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

        if send_button:
            await ctx.defer()
            await ctx.send(
                embed=utils.make_embed("Add gacha items via the button below!"),
                components=ipy.Button(
                    style=ipy.ButtonStyle.GREEN,
                    label="Add Gacha Item",
                    custom_id="thia-button:add_gacha_item",
                ),
            )
            return
        await ctx.send_modal(self.gacha_item_create_modal)

    @ipy.component_callback("thia-button:add_gacha_item")
    async def add_gacha_item_button(self, ctx: ipy.ComponentContext) -> None:
        await ctx.send_modal(self.gacha_item_create_modal)

    @ipy.modal_callback("add_gacha_item")
    async def add_gacha_item_modal(self, ctx: utils.THIAModalContext) -> None:
        name: str = ctx.kwargs["item_name"]
        description: str = ctx.kwargs["item_description"]
        str_amount: str = ctx.kwargs.get("item_amount", "-1").strip() or "-1"
        image: typing.Optional[str] = ctx.kwargs.get("item_image", "").strip() or None

        if await models.GachaItem.exists(guild_id=ctx.guild_id, name=name):
            raise ipy.errors.BadArgument("An item with that name already exists.")

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
        item = await models.GachaItem.get_or_none(guild_id=ctx.guild_id, name=name)
        if item is None:
            raise ipy.errors.BadArgument("No item with that name exists.")

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
    async def on_modal_edit_gacha_item(self, event: ipy.events.ModalCompletion) -> None:
        ctx = event.ctx

        if not ctx.custom_id.startswith("edit_gacha_item-"):
            return

        item_id = int(ctx.custom_id.split("-")[1])
        name: str = ctx.kwargs["item_name"]
        description: str = ctx.kwargs["item_description"]
        str_amount: str = ctx.kwargs.get("item_amount", "-1").strip() or "-1"
        image: typing.Optional[str] = ctx.kwargs.get("item_image", "").strip() or None

        if not await models.GachaItem.exists(id=item_id, guild_id=ctx.guild_id):
            raise ipy.errors.BadArgument("The item no longer exists.")

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

        await ctx.send(embed=item.embed(show_amount=True))

    @manage.subcommand(
        "list-items", sub_cmd_description="Lists all gacha items for this server."
    )
    async def gacha_view_items(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        items = await models.GachaItem.filter(guild_id=ctx.guild_id)

        if not items:
            raise utils.CustomCheckFailure("This server has no items to show.")

        items_list = [
            f"**{i.name}**{f' ({i.amount} remaining)' if i.amount != -1 else ''}:"
            f" {models.short_desc(i.description)}"
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
        "remove-item-from", sub_cmd_description="Removes an item from a user."
    )
    async def gacha_remove_item_from(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to remove an item from."),
        name: str = tansy.Option("The name of the item to remove.", autocomplete=True),
        amount: typing.Optional[int] = tansy.Option(
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
        amount: typing.Optional[int] = tansy.Option(
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

        items_dict: list[exports.GachaItemv1Dict] = [
            {
                "name": item.name,
                "description": item.description,
                "amount": item.amount,
                "image": item.image,
            }
            for item in items
        ]
        items_json = orjson.dumps(
            {"version": 1, "items": items_dict}, option=orjson.OPT_INDENT_2
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
                        amount=item.amount,
                        image=item.image,
                        rarity=models.Rarity.COMMON,
                    )
                )

            await models.GachaItem.bulk_create(to_create)

        await ctx.send(embed=utils.make_embed("Imported items from JSON file."))

    @gacha_item_edit.autocomplete("name")
    @gacha_item_delete.autocomplete("name")
    @gacha_view_single_item.autocomplete("name")
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
    importlib.reload(text_utils)
    importlib.reload(help_tools)
    importlib.reload(exports)
    GachaManagement(bot)
