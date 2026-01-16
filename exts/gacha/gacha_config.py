"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib
import re
from decimal import Decimal

import interactions as ipy
import tansy
import typing_extensions as typing

import common.models as models
import common.utils as utils

VALID_DECIMAL_REGEX = re.compile(
    r"^(\d{1,2}(?:[\.,]\d{1,2})?%)|(0(?:[\.,]\d{1,4})?)|(?:100(?:[\.,]\d{1,2})?%)|(?:1(?:\.0{1,4})?)$"
)
VALID_COLOR = re.compile(r"^#?[\da-fA-F]{6}$")


def convert_to_decimal(value: str) -> Decimal:
    if not VALID_DECIMAL_REGEX.fullmatch(value):
        raise ipy.errors.BadArgument(f"Invalid decimal value: `{value}`.")

    value = value.replace(",", ".")  # we love localization

    if value.endswith("%"):
        value = value[:-1]
        if not value:
            raise ipy.errors.BadArgument(f"Invalid decimal value: `{value}`.")

        try:
            decimal_value = (Decimal(value) / 100).normalize()
        except (ValueError, TypeError):
            raise ipy.errors.BadArgument(f"Invalid decimal value: `{value}`.") from None
    else:
        try:
            decimal_value = Decimal(value).normalize()
        except (ValueError, TypeError):
            raise ipy.errors.BadArgument(f"Invalid decimal value: `{value}`.") from None

    if decimal_value < 0:
        raise ipy.errors.BadArgument("Decimal value must be non-negative.")
    if decimal_value > 1:
        raise ipy.errors.BadArgument("Decimal value cannot be greater than one.")

    return decimal_value


def convert_to_color(value: str) -> str:
    if not VALID_COLOR.fullmatch(value):
        raise ipy.errors.BadArgument(f"Invalid color value: `{value}`.")

    if not value.startswith("#"):
        value = f"#{value}"

    return value.lower()


def to_percent(d: Decimal) -> str:
    d *= 100
    d = d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
    return f"{d}%"


class GachaConfig(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Gacha Config"

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

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)

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

        names_str_builder = [
            f"Singular Currency Name: {config.names.singular_currency_name}",
            f"Currency Name: {config.names.plural_currency_name}",
            "",
            f"Common Rarity: {config.names.gacha_common_name}",
            f"Uncommon Rarity: {config.names.gacha_uncommon_name}",
            f"Rare Rarity: {config.names.gacha_rare_name}",
            f"Epic Rarity: {config.names.gacha_epic_name}",
            f"Legendary Rarity: {config.names.gacha_legendary_name}",
        ]
        embed.add_field("Names", "\n".join(names_str_builder), inline=True)

        rarity_color_builder = [
            f"Common Color: {rarities.common_color}",
            f"Uncommon Color: {rarities.uncommon_color}",
            f"Rare Color: {rarities.rare_color}",
            f"Epic Color: {rarities.epic_color}",
            f"Legendary Color: {rarities.legendary_color}",
        ]
        embed.add_field("Rarity Colors", "\n".join(rarity_color_builder), inline=True)

        rarity_odds_builder = [
            f"Common Odds: {to_percent(rarities.common_odds)}",
            f"Uncommon Odds: {to_percent(rarities.uncommon_odds)}",
            f"Rare Odds: {to_percent(rarities.rare_odds)}",
            f"Epic Odds: {to_percent(rarities.epic_odds)}",
            f"Legendary Odds: {to_percent(rarities.legendary_odds)}",
        ]
        embed.add_field("Rarity Odds", "\n".join(rarity_odds_builder), inline=True)

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
        sub_cmd_description=(
            "Edit the displayed names used for various parts of the gacha."
        ),
    )
    @ipy.auto_defer(enabled=False)
    async def gacha_name(
        self,
        ctx: utils.THIASlashContext,
        to_change: str = tansy.Option(
            "The names to change.",
            choices=[
                ipy.SlashCommandChoice("Currency Names", "currency_names"),
                ipy.SlashCommandChoice("Rarity Names", "rarity_names"),
            ],
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        if to_change == "currency_names":
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
        elif to_change == "rarity_names":
            modal = ipy.Modal(
                ipy.InputText(
                    label="Common Rarity Name",
                    style=ipy.TextStyles.SHORT,
                    custom_id="gacha_common_name",
                    value=config.names.gacha_common_name,
                    max_length=40,
                ),
                ipy.InputText(
                    label="Uncommon Rarity Name",
                    style=ipy.TextStyles.SHORT,
                    custom_id="gacha_uncommon_name",
                    value=config.names.gacha_uncommon_name,
                    max_length=40,
                ),
                ipy.InputText(
                    label="Rare Rarity Name",
                    style=ipy.TextStyles.SHORT,
                    custom_id="gacha_rare_name",
                    value=config.names.gacha_rare_name,
                    max_length=40,
                ),
                ipy.InputText(
                    label="Epic Rarity Name",
                    style=ipy.TextStyles.SHORT,
                    custom_id="gacha_epic_name",
                    value=config.names.gacha_epic_name,
                    max_length=40,
                ),
                ipy.InputText(
                    label="Legendary Rarity Name",
                    style=ipy.TextStyles.SHORT,
                    custom_id="gacha_legendary_name",
                    value=config.names.gacha_legendary_name,
                    max_length=40,
                ),
                title="Edit Rarity Names",
                custom_id="rarity_names",
            )
        else:
            raise ipy.errors.BadArgument("Invalid choice.")

        await ctx.send_modal(modal)

    @ipy.modal_callback("currency_names")
    async def currency_names_edit(self, ctx: utils.THIAModalContext) -> None:
        await ctx.defer()

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

    @ipy.modal_callback("rarity_names")
    async def rarity_names_edit(self, ctx: utils.THIAModalContext) -> None:
        await ctx.defer()

        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names is not None

        names = config.names

        names.gacha_common_name = ctx.kwargs["gacha_common_name"]
        names.gacha_uncommon_name = ctx.kwargs["gacha_uncommon_name"]
        names.gacha_rare_name = ctx.kwargs["gacha_rare_name"]
        names.gacha_epic_name = ctx.kwargs["gacha_epic_name"]
        names.gacha_legendary_name = ctx.kwargs["gacha_legendary_name"]
        await names.save()

        await ctx.send(
            embed=utils.make_embed(
                "Updated! Please note this will only affect public-facing"
                f" aspects.\n\nCommon: {names.gacha_common_name}\nUncommon:"
                f" {names.gacha_uncommon_name}\nRare: {names.gacha_rare_name}"
                f"\nEpic: {names.gacha_epic_name}\nLegendary:"
                f" {names.gacha_legendary_name}"
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
        "rarities",
        sub_cmd_description="Allows you to edit the rarity colors and odds.",
    )
    @ipy.auto_defer(enabled=False)
    async def gacha_rarities(
        self,
        ctx: utils.THIASlashContext,
        to_change: str = tansy.Option(
            "The aspect of the rarities to change.",
            choices=[
                ipy.SlashCommandChoice("Rarity Colors", "colors"),
                ipy.SlashCommandChoice("Rarity Odds", "odds"),
                ipy.SlashCommandChoice("Reset Rarity Colors", "reset_colors"),
                ipy.SlashCommandChoice("Reset Rarity Odds", "reset_odds"),
            ],
        ),
    ) -> None:
        config = await ctx.fetch_config({"gacha": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)

        if to_change == "odds":
            modal = ipy.Modal(
                ipy.InputText(
                    label="Common Odds",
                    style=ipy.TextStyles.SHORT,
                    custom_id="common_odds",
                    max_length=10,
                    value=to_percent(rarities.common_odds),
                ),
                ipy.InputText(
                    label="Uncommon Odds",
                    style=ipy.TextStyles.SHORT,
                    custom_id="uncommon_odds",
                    max_length=10,
                    value=to_percent(rarities.uncommon_odds),
                ),
                ipy.InputText(
                    label="Rare Odds",
                    style=ipy.TextStyles.SHORT,
                    custom_id="rare_odds",
                    max_length=10,
                    value=to_percent(rarities.rare_odds),
                ),
                ipy.InputText(
                    label="Epic Odds",
                    style=ipy.TextStyles.SHORT,
                    custom_id="epic_odds",
                    max_length=10,
                    value=to_percent(rarities.epic_odds),
                ),
                ipy.InputText(
                    label="Legendary Odds",
                    style=ipy.TextStyles.SHORT,
                    custom_id="legendary_odds",
                    max_length=10,
                    value=to_percent(rarities.legendary_odds),
                ),
                title="Edit Rarity Odds",
                custom_id="rarity_odds",
            )
        elif to_change == "colors":
            modal = ipy.Modal(
                ipy.InputText(
                    label="Common Color",
                    style=ipy.TextStyles.SHORT,
                    custom_id="common_color",
                    max_length=7,
                    value=rarities.common_color,
                ),
                ipy.InputText(
                    label="Uncommon Color",
                    style=ipy.TextStyles.SHORT,
                    custom_id="uncommon_color",
                    max_length=7,
                    value=rarities.uncommon_color,
                ),
                ipy.InputText(
                    label="Rare Color",
                    style=ipy.TextStyles.SHORT,
                    custom_id="rare_color",
                    max_length=7,
                    value=rarities.rare_color,
                ),
                ipy.InputText(
                    label="Epic Color",
                    style=ipy.TextStyles.SHORT,
                    custom_id="epic_color",
                    max_length=7,
                    value=rarities.epic_color,
                ),
                ipy.InputText(
                    label="Legendary Color",
                    style=ipy.TextStyles.SHORT,
                    custom_id="legendary_color",
                    max_length=7,
                    value=rarities.legendary_color,
                ),
                title="Edit Rarity Colors",
                custom_id="rarity_colors",
            )
        elif to_change == "reset_colors":
            await ctx.defer()

            for name, field in rarities._meta.fields_map.items():
                if name.endswith("_color"):
                    setattr(rarities, name, field.default)

            await rarities.save()
            await ctx.send(
                embed=utils.make_embed(
                    "Updated! The colors have been reset to the defaults."
                )
            )
            return
        elif to_change == "reset_odds":
            await ctx.defer()

            for name, field in rarities._meta.fields_map.items():
                if name.endswith("_odds"):
                    setattr(rarities, name, field.default)

            await rarities.save()
            await ctx.send(
                embed=utils.make_embed(
                    "Updated! The odds have been reset to the defaults."
                )
            )
            return
        else:
            raise ipy.errors.BadArgument("Invalid choice.")

        await ctx.send_modal(modal)

    @ipy.modal_callback("rarity_odds")
    async def rarity_odds_edit(self, ctx: utils.THIAModalContext) -> None:
        await ctx.defer()

        config = await ctx.fetch_config({"gacha": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)

        common = convert_to_decimal(ctx.kwargs["common_odds"])
        uncommon = convert_to_decimal(ctx.kwargs["uncommon_odds"])
        rare = convert_to_decimal(ctx.kwargs["rare_odds"])
        epic = convert_to_decimal(ctx.kwargs["epic_odds"])
        legendary = convert_to_decimal(ctx.kwargs["legendary_odds"])

        if common + uncommon + rare + epic + legendary != 1:
            raise utils.CustomCheckFailure(
                "The odds must add up to 100%/1. Please try again."
            )

        rarities.common_odds = common
        rarities.uncommon_odds = uncommon
        rarities.rare_odds = rare
        rarities.epic_odds = epic
        rarities.legendary_odds = legendary
        await rarities.save()

        await ctx.send(
            embed=utils.make_embed(
                f"Updated!\n\nCommon: {to_percent(common)}\nUncommon:"
                f" {to_percent(uncommon)}\nRare: {to_percent(rare)}"
                f"\nEpic: {to_percent(epic)}\nLegendary:"
                f" {to_percent(legendary)}"
            )
        )

    @ipy.modal_callback("rarity_colors")
    async def rarity_colors_edit(self, ctx: utils.THIAModalContext) -> None:
        await ctx.defer()

        config = await ctx.fetch_config({"gacha": True})
        if typing.TYPE_CHECKING:
            assert config.gacha is not None

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)

        rarities.common_color = convert_to_color(ctx.kwargs["common_color"])
        rarities.uncommon_color = convert_to_color(ctx.kwargs["uncommon_color"])
        rarities.rare_color = convert_to_color(ctx.kwargs["rare_color"])
        rarities.epic_color = convert_to_color(ctx.kwargs["epic_color"])
        rarities.legendary_color = convert_to_color(ctx.kwargs["legendary_color"])
        await rarities.save()

        await ctx.send(
            embed=utils.make_embed(
                f"Updated!\n\nCommon: {rarities.common_color}\nUncommon:"
                f" {rarities.uncommon_color}\nRare: {rarities.rare_color}"
                f"\nEpic: {rarities.epic_color}\nLegendary:"
                f" {rarities.legendary_color}"
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


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    GachaConfig(bot)
