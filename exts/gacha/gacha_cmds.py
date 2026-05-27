"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import discord
import ragwort
import typing_extensions as typing
from tortoise.expressions import F
from tortoise.query_utils import Prefetch
from tortoise.transactions import in_transaction

import common.classes as classes
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils


async def gacha_roll_actual(
    ctx: utils.THIASlashContext | utils.Interaction,
    *,
    name_for_action: str,
    button_press: bool = False,
) -> None:
    if isinstance(ctx, utils.Interaction):
        await ctx.response.defer()
    if isinstance(ctx, utils.THIASlashContext):
        ctx = typing.cast("utils.Interaction", ctx.interaction)

    config = await models.GuildConfig.fetch_create(
        ctx.guild_id, {"gacha": True, "names": True}
    )
    if typing.TYPE_CHECKING:
        assert config.gacha and isinstance(config.gacha, models.GachaConfig)
        assert config.names and isinstance(config.names, models.Names)

    if not config.player_role or not config.gacha.enabled:
        raise utils.CustomCheckFailure("Gacha is not enabled in this server.")

    if not ctx.user.get_role(config.player_role):
        player_role = await ctx.guild.fetch_role(config.player_role)
        player_role_name = player_role.name if player_role else "Player"
        raise utils.CustomCheckFailure(f"You do not have the {player_role_name} role.")

    async with ctx.client.gacha_locks[f"{ctx.guild_id}-{ctx.user.id}"]:
        player = await models.GachaPlayer.get_or_none(
            guild_id=ctx.guild_id, user_id=ctx.user.id
        ).prefetch_related("items")

        if not player or player.currency_amount < config.gacha.currency_cost:
            raise utils.CustomCheckFailure(
                f"You do not have enough {config.names.plural_currency_name} to"
                f" {name_for_action} the gacha. You need at least"
                f" {config.gacha.currency_cost}"
                f" {config.names.currency_name(config.gacha.currency_cost)} to do"
                f" so, but you have {player.currency_amount if player else 0}"
                f" {config.names.currency_name(config.gacha.currency_cost)}."
            )

        item_ids = {entry.item_id for entry in player.items}

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)
        rarity = rarities.roll_rarity()

        if config.gacha.draw_duplicates:
            items = await models.GachaItem.roll(ctx.guild_id, rarity)

            # we don't want to prevent duplicates, but making them less likely
            # sounds nice, doesn't it?
            # we try up to 3 times to find an item that the user doesn't have

            if not items:
                item = None
            elif len(items) <= 1 or items[0].id not in item_ids:
                item = items[0]
            elif len(items) <= 2 or items[1].id not in item_ids:
                item = items[1]
            else:
                item = items[2]

        else:
            item = await models.GachaItem.roll_no_duplicates(
                ctx.guild_id, item_ids, rarity
            )

        if not item:
            raise utils.CustomCheckFailure(
                f"There are no items available to {name_for_action}."
            )

        # if there are no items of other rarities, there's no point in showing rarity
        # in the embed
        show_rarity = await models.GachaItem.filter(
            guild_id=ctx.guild_id,
            rarity__not=item.rarity,
        ).exists()

        new_count = player.currency_amount - config.gacha.currency_cost

        container = item.container(config.names, rarities, show_rarity=show_rarity)
        container.add_separator(
            divider=True, spacing=discord.SeparatorSpacingSize.large
        )

        buttons: list[discord.ui.Button] = [
            discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label=f"{new_count} {config.names.currency_name(new_count)} Left",
                disabled=True,
            )
        ]
        if new_count >= config.gacha.currency_cost:
            buttons.insert(
                0,
                discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    label=f"{name_for_action.capitalize()} Again",
                    custom_id=f"gacha-roll-{name_for_action}",
                ),
            )

        container.add_row(*buttons)

        await ctx.respond(
            view=(
                utils.quick_view(discord.ui.TextDisplay(ctx.user.mention), container)
                if button_press
                else utils.quick_view(container)
            ),
            allowed_mentions=discord.AllowedMentions(
                users=[discord.Object(ctx.user.id)]
            ),
        )

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


class GachaRollButtonView(discord.ui.View):
    def __init__(self, name_for_action: str) -> None:
        super().__init__(timeout=None)
        self.name_for_action = name_for_action
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                label=f"{name_for_action.capitalize()} Again",
                custom_id=f"gacha-roll-{name_for_action}",
            )
        )

    async def interaction_check(self, inter: utils.Interaction) -> bool:
        if (
            inter.message
            and inter.message.interaction_metadata
            and int(inter.user.id) != int(inter.message.interaction_metadata.user.id)
        ):
            raise utils.CustomCheckFailure(
                "You cannot use this button as you did not initiate the"
                f" {self.name_for_action}."
            )

        return True

    async def on_error(
        self, error: Exception, item: discord.ui.ViewItem, inter: utils.Interaction
    ) -> None:
        if isinstance(error, utils.CustomCheckFailure):
            await inter.response.send_message(
                view=utils.error_view(str(error)),
                ephemeral=True,
            )
        else:
            await super().on_error(error, item, inter)

    async def callback(self, inter: utils.Interaction) -> None:
        await gacha_roll_actual(
            inter, name_for_action=self.name_for_action, button_press=True
        )


class GachaCommands(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Gacha"

        self.bot.add_view(GachaRollButtonView("roll"))
        self.bot.add_view(GachaRollButtonView("pull"))
        self.bot.add_view(GachaRollButtonView("draw"))

    gacha = ragwort.SlashCommandGroup(
        name="gacha",
        description="Hosts public-facing gacha commands.",
        contexts={discord.InteractionContextType.guild},
    )

    @gacha.command(
        name="roll",
        description="Rolls for an item in the gacha.",
    )
    async def gacha_roll(self, ctx: utils.THIASlashContext) -> None:
        await gacha_roll_actual(ctx, name_for_action=ctx.command.name)

    gacha_pull = utils.alias(
        gacha_roll,
        name="pull",
        description="Pulls for an item in the gacha. Alias of /gacha roll.",
    )
    gacha_draw = utils.alias(
        gacha_roll,
        name="draw",
        description="Draws for an item in the gacha. Alias of /gacha draw.",
    )

    @gacha.command(
        name="profile",
        description="Shows your gacha currency and items.",
    )
    @ragwort.auto_defer(ephemeral=True)
    async def gacha_profile(
        self,
        ctx: utils.THIASlashContext,
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

        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha and isinstance(config.gacha, models.GachaConfig)
            assert config.names and isinstance(config.names, models.Names)

        if not config.player_role or not config.gacha.enabled:
            raise utils.CustomCheckFailure("Gacha is not enabled in this server.")

        player = await models.GachaPlayer.get_or_none(
            guild_id=ctx.guild_id, user_id=ctx.author.id
        ).prefetch_related(
            Prefetch("items", models.ItemToPlayer.filter().prefetch_related("item"))
        )
        if player is None:
            if not ctx.author.get_role(config.player_role):
                raise utils.BadArgument("You have no data for gacha.")
            player = await models.GachaPlayer.create(
                guild_id=ctx.guild_id, user_id=ctx.author.id
            )
            await player.fetch_related("items__item")

        if mode == "spacious":
            chunks = player.create_profile_spacious(config.names, sort_by=sort_by)
        elif mode == "modern":
            chunks = player.create_profile_modern(config.names, sort_by=sort_by)
        else:
            chunks = player.create_profile_compact(config.names, sort_by=sort_by)

        pag = classes.ContainerPaginator(
            *chunks,
            title=f"{ctx.author.display_name}'s Gacha Profile",
            author_id=ctx.author.id,
        )
        await ctx.respond(view=pag, ephemeral=True)

    gacha_inventory = utils.alias(
        gacha_profile,
        name="inventory",
        description="Shows your gacha currency and items. Alias of /gacha profile.",
    )

    @gacha.command(
        name="give-currency",
        description="Gives currency to a user.",
    )
    async def gacha_give_currency(
        self,
        ctx: utils.THIASlashContext,
        recipient: discord.Member = ragwort.Option("The recipient."),
        amount: int = ragwort.Option("The amount to give.", min_value=1, max_value=999),
    ) -> None:
        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha and isinstance(config.gacha, models.GachaConfig)
            assert config.names and isinstance(config.names, models.Names)

        if int(ctx.author.id) == int(recipient.id):
            raise utils.BadArgument(
                f"You cannot give {config.names.plural_currency_name} to yourself."
            )

        if not config.player_role or not config.gacha.enabled:
            raise utils.CustomCheckFailure("Gacha is not enabled in this server.")

        try:
            await self.bot.gacha_locks[f"{ctx.guild_id}-{ctx.author.id}"].acquire()
            await self.bot.gacha_locks[f"{ctx.guild_id}-{recipient.id}"].acquire()

            player = await models.GachaPlayer.get_or_none(
                guild_id=ctx.guild_id, user_id=ctx.author.id
            )
            if player is None:
                if not ctx.author.get_role(config.player_role):
                    raise utils.BadArgument("You have no data for gacha.")
                player = await models.GachaPlayer.create(
                    guild_id=ctx.guild_id, user_id=ctx.author.id
                )

            if player.currency_amount < amount:
                raise utils.CustomCheckFailure(
                    "You do not have enough currency to give."
                )

            recipient_player = await models.GachaPlayer.get_or_none(
                guild_id=ctx.guild_id, user_id=recipient.id
            )
            if recipient_player is None:
                if not recipient.get_role(config.player_role):
                    raise utils.BadArgument("The recipient has no data for gacha.")
                recipient_player = await models.GachaPlayer.create(
                    guild_id=ctx.guild_id, user_id=recipient.id
                )

            recipient_player.currency_amount += amount
            player.currency_amount -= amount
            await recipient_player.save()
            await player.save()

            await ctx.respond(
                view=utils.make_view(
                    f"Gave {amount} {config.names.currency_name(amount)} to"
                    f" {recipient.mention}. You now have {player.currency_amount}"
                    f" {config.names.currency_name(player.currency_amount)}."
                )
            )
        finally:
            if self.bot.gacha_locks[f"{ctx.guild_id}-{ctx.author.id}"].locked():
                self.bot.gacha_locks[f"{ctx.guild_id}-{ctx.author.id}"].release()
            if self.bot.gacha_locks[f"{ctx.guild_id}-{recipient.id}"].locked():
                self.bot.gacha_locks[f"{ctx.guild_id}-{recipient.id}"].release()

    @gacha.command(
        name="view-item",
        description="Shows information about an item you have.",
    )
    @ragwort.auto_defer(ephemeral=True)
    async def gacha_user_view_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to view.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        item = await models.GachaItem.filter(
            guild_id=ctx.guild_id,
            name=name,
            players__player__guild_id=ctx.guild_id,
            players__player__user_id=ctx.author.id,
        ).first()
        if item is None:
            raise utils.BadArgument("Item either does not exist or you do not have it.")

        await self.gacha_view_item_actual(ctx, item)

    @utils.button_handler(custom_id_prefix="gacha-item-")
    async def gacha_view_item_button(
        self, inter: utils.Interaction, custom_id: str
    ) -> None:
        admin = custom_id.endswith("-admin")
        await inter.response.defer(ephemeral=not admin)

        item = await models.GachaItem.get_or_none(
            id=custom_id.removeprefix("gacha-item-").removesuffix("-admin"),
            guild_id=inter.guild_id,
        )
        if item is None:
            raise utils.CustomCheckFailure("This item no longer exists.")

        await self.gacha_view_item_actual(inter, item, show_amount=admin)

    async def gacha_view_item_actual(
        self,
        ctx: utils.THIASlashContext | utils.Interaction,
        item: models.GachaItem,
        show_amount: bool = False,
    ) -> None:
        if isinstance(ctx, utils.THIASlashContext):
            ctx = typing.cast("utils.Interaction", ctx.interaction)

        show_rarity = await models.GachaItem.filter(
            guild_id=ctx.guild_id,
            rarity__not=item.rarity,
        ).exists()

        config = await models.GuildConfig.fetch_create(
            ctx.guild_id, {"gacha": True, "names": True}
        )
        if typing.TYPE_CHECKING:
            assert config.gacha and isinstance(config.gacha, models.GachaConfig)
            assert config.names and isinstance(config.names, models.Names)

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)
        await ctx.respond(
            view=utils.quick_view(
                item.container(
                    config.names,
                    rarities,
                    show_rarity=show_rarity,
                    show_amount=show_amount,
                )
            ),
            ephemeral=not show_amount,
        )

    @gacha_user_view_item.autocomplete("name")
    async def _autocomplete_gacha_user_item(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_gacha_user_item(ctx, **ctx.options)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(classes)
    importlib.reload(models)
    bot.add_cog(GachaCommands(bot))
