"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import interactions as ipy
import tansy
import typing_extensions as typing
from tortoise.expressions import F
from tortoise.query_utils import Prefetch
from tortoise.transactions import in_transaction

import common.classes as classes
import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.utils as utils


class GachaCommands(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Gacha Commands"

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
        await self.gacha_roll_actual(
            ctx, name_for_action=ctx._command_name.split(" ")[1]
        )

    @ipy.listen(ipy.events.ButtonPressed)
    async def gacha_roll_button(self, event: ipy.events.ButtonPressed) -> None:
        if not event.ctx.custom_id.startswith("gacha-roll-"):
            return

        if event.ctx.message.interaction_metadata and int(event.ctx.author_id) != int(
            event.ctx.message.interaction_metadata._user_id
        ):
            await event.ctx.send(
                embeds=utils.error_embed_generate(
                    "You cannot use this button as you did not initiate the"
                    f" {event.ctx.custom_id.removeprefix('gacha-roll-')}."
                ),
                ephemeral=True,
            )
            return

        try:
            await self.gacha_roll_actual(
                event.ctx,
                name_for_action=event.ctx.custom_id.removeprefix("gacha-roll-"),
                button_press=True,
            )
        except Exception as e:
            if isinstance(e, utils.CustomCheckFailure | ipy.errors.BadArgument):
                embed = utils.error_embed_generate(str(e))
                await event.ctx.send(
                    event.ctx.author.mention,
                    embeds=embed,
                    allowed_mentions=ipy.AllowedMentions.none(),
                )
            else:
                await utils.error_handle(e, ctx=event.ctx)

    async def gacha_roll_actual(
        self,
        ctx: utils.THIASlashContext | utils.THIAComponentContext,
        *,
        name_for_action: str,
        button_press: bool = False,
    ) -> None:
        if isinstance(ctx, utils.THIAComponentContext):
            await ctx.defer()

        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None
            assert config.names is not None

        if not config.player_role or not config.gacha.enabled:
            raise utils.CustomCheckFailure("Gacha is not enabled in this server.")

        if not ctx.author.has_role(config.player_role):
            player_role = await ctx.guild.fetch_role(config.player_role)
            player_role_name = player_role.name if player_role else "Player"
            raise utils.CustomCheckFailure(
                f"You do not have the {player_role_name} role."
            )

        async with self.bot.gacha_locks[f"{ctx.guild_id}-{ctx.author.id}"]:
            player, _ = await models.GachaPlayer.get_or_create(
                guild_id=ctx.guild_id, user_id=ctx.author.id
            )

            if player.currency_amount < config.gacha.currency_cost:
                raise utils.CustomCheckFailure(
                    f"You do not have enough {config.names.plural_currency_name} to"
                    f" {name_for_action} the gacha. You need at least"
                    f" {config.gacha.currency_cost}"
                    f" {config.names.currency_name(config.gacha.currency_cost)} to"
                    " do so."
                )

            rarities, _ = await models.GachaRarities.get_or_create(
                guild_id=ctx.guild_id
            )
            rarity = rarities.roll_rarity()

            if config.gacha.draw_duplicates:
                item = await models.GachaItem.roll(ctx.guild_id, rarity)
            else:
                item = await models.GachaItem.roll_no_duplicates(
                    ctx.guild_id, player.id, rarity
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
            embed = item.embed(config.names, rarities, show_rarity=show_rarity)
            embed.set_footer(
                f"{new_count} {config.names.currency_name(new_count)} left"
            )

            button: ipy.Button | None = None
            if new_count >= config.gacha.currency_cost:
                button = ipy.Button(
                    style=ipy.ButtonStyle.PRIMARY,
                    label=f"{name_for_action.capitalize()} Again",
                    custom_id=f"gacha-roll-{name_for_action}",
                )

            await ctx.send(
                content=ctx.author.mention if button_press else None,
                embed=embed,
                components=button,
                allowed_mentions=ipy.AllowedMentions.none(),
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
    async def gacha_profile(
        self,
        ctx: utils.THIASlashContext,
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

        if mode == "modern" or mode == "spacious":
            if mode == "spacious":
                chunks = player.create_profile_spacious(config.names, sort_by=sort_by)
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
                    ),
                    ephemeral=True,
                )
                return

            pag = classes.ContainerPaginator(
                self.bot,
                title=f"{ctx.author.display_name}'s Gacha Profile",
                pages_data=chunks,
            )
            await pag.send(ctx, ephemeral=True)
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

        if int(ctx.author.id) == int(recipient.id):
            raise ipy.errors.BadArgument(
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
                if not ctx.author.has_role(config.player_role):
                    raise ipy.errors.BadArgument("You have no data for gacha.")
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
                    f" {recipient.mention}. You now have {player.currency_amount}"
                    f" {config.names.currency_name(player.currency_amount)}."
                )
            )
        finally:
            if self.bot.gacha_locks[f"{ctx.guild_id}-{ctx.author.id}"].locked():
                self.bot.gacha_locks[f"{ctx.guild_id}-{ctx.author.id}"].release()
            if self.bot.gacha_locks[f"{ctx.guild_id}-{recipient.id}"].locked():
                self.bot.gacha_locks[f"{ctx.guild_id}-{recipient.id}"].release()

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

        await self.gacha_view_item_actual(ctx, item)

    @ipy.listen(ipy.events.ButtonPressed)
    async def gacha_view_item_button(self, event: ipy.events.ButtonPressed) -> None:
        if not event.ctx.custom_id.startswith("gacha-item-"):
            return

        await event.ctx.defer(ephemeral=True)

        item = await models.GachaItem.get_or_none(
            id=event.ctx.custom_id.removeprefix("gacha-item-").removesuffix("-admin"),
            guild_id=event.ctx.guild_id,
        )
        if item is None:
            await event.ctx.send(
                embeds=utils.error_embed_generate("This item no longer exists."),
                ephemeral=True,
            )
            return

        await self.gacha_view_item_actual(
            event.ctx, item, show_amount=event.ctx.custom_id.endswith("-admin")
        )

    async def gacha_view_item_actual(
        self,
        ctx: utils.THIASlashContext | utils.THIAComponentContext,
        item: models.GachaItem,
        show_amount: bool = False,
    ) -> None:
        show_rarity = await models.GachaItem.filter(
            guild_id=ctx.guild_id,
            rarity__not=item.rarity,
        ).exists()

        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None
            assert config.names is not None

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)
        await ctx.send(
            embed=item.embed(
                config.names, rarities, show_rarity=show_rarity, show_amount=show_amount
            ),
            ephemeral=True,
        )

    @gacha_user_view_item.autocomplete("name")
    async def _autocomplete_gacha_user_item(self, ctx: ipy.AutocompleteContext) -> None:
        await fuzzy.autocomplete_gacha_user_item(ctx, **ctx.kwargs)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(help_tools)
    importlib.reload(fuzzy)
    importlib.reload(classes)
    GachaCommands(bot)
