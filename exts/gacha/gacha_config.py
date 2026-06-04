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

import discord
import ragwort
import typing_extensions as typing

import common.models as models
import common.utils as utils

VALID_DECIMAL_REGEX = re.compile(
    r"^(\d{1,2}(?:[\.,]\d{1,2})?%)|(0(?:[\.,]\d{1,4})?)|(?:100(?:[\.,]\d{1,2})?%)|(?:1(?:\.0{1,4})?)$"
)
VALID_COLOR = re.compile(r"^#?[\da-fA-F]{6}$")


def convert_to_decimal(value: str) -> Decimal:
    if not VALID_DECIMAL_REGEX.fullmatch(value):
        raise utils.BadArgument(f"Invalid decimal value: `{value}`.")

    value = value.replace(",", ".")  # we love localization

    if value.endswith("%"):
        value = value[:-1]
        if not value:
            raise utils.BadArgument(f"Invalid decimal value: `{value}`.")

        try:
            decimal_value = (Decimal(value) / 100).normalize()
        except (ValueError, TypeError):
            raise utils.BadArgument(f"Invalid decimal value: `{value}`.") from None
    else:
        try:
            decimal_value = Decimal(value).normalize()
        except (ValueError, TypeError):
            raise utils.BadArgument(f"Invalid decimal value: `{value}`.") from None

    if decimal_value < 0:
        raise utils.BadArgument("Decimal value must be non-negative.")
    if decimal_value > 1:
        raise utils.BadArgument("Decimal value cannot be greater than one.")

    return decimal_value


def convert_to_color(value: str) -> str:
    if not VALID_COLOR.fullmatch(value):
        raise utils.BadArgument(f"Invalid color value: `{value}`.")

    if not value.startswith("#"):
        value = f"#{value}"

    return value.lower()


def to_percent(d: Decimal) -> str:
    d *= 100
    d = d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
    return f"{d}%"


class CurrencyNamesModal(discord.ui.DesignerModal):
    def __init__(self, names: models.Names) -> None:
        super().__init__(
            discord.ui.Label(
                label="Singular Currency Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="singular_currency_name",
                    value=names.singular_currency_name,
                    max_length=40,
                ),
            ),
            discord.ui.Label(
                label="Plural Currency Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="plural_currency_name",
                    value=names.plural_currency_name,
                    max_length=40,
                ),
            ),
            title="Edit Currency Names",
            custom_id="currency_names",
        )

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        config = await models.GuildConfig.fetch_create(
            int(inter.guild_id), {"names": True}
        )
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        names = config.names

        names.singular_currency_name = self.children[0].item.value
        names.plural_currency_name = self.children[1].item.value
        await names.save()

        await inter.respond(
            view=utils.make_view(
                "Updated! Please note this will only affect public-facing"
                f" aspects.\nSingular: {names.singular_currency_name}\nPlural:"
                f" {names.plural_currency_name}"
            )
        )


class RarityNamesModal(discord.ui.DesignerModal):
    def __init__(self, names: models.Names) -> None:
        super().__init__(
            discord.ui.Label(
                label="Common Rarity Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="gacha_common_name",
                    value=names.gacha_common_name,
                    max_length=40,
                ),
            ),
            discord.ui.Label(
                label="Uncommon Rarity Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="gacha_uncommon_name",
                    value=names.gacha_uncommon_name,
                    max_length=40,
                ),
            ),
            discord.ui.Label(
                label="Rare Rarity Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="gacha_rare_name",
                    value=names.gacha_rare_name,
                    max_length=40,
                ),
            ),
            discord.ui.Label(
                label="Epic Rarity Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="gacha_epic_name",
                    value=names.gacha_epic_name,
                    max_length=40,
                ),
            ),
            discord.ui.Label(
                label="Legendary Rarity Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="gacha_legendary_name",
                    value=names.gacha_legendary_name,
                    max_length=40,
                ),
            ),
            title="Edit Rarity Names",
            custom_id="rarity_names",
        )

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        config = await models.GuildConfig.fetch_create(
            int(inter.guild_id), {"names": True}
        )
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        names = config.names
        responses = utils.parse_modal_responses(self)

        names.gacha_common_name = responses["gacha_common_name"]
        names.gacha_uncommon_name = responses["gacha_uncommon_name"]
        names.gacha_rare_name = responses["gacha_rare_name"]
        names.gacha_epic_name = responses["gacha_epic_name"]
        names.gacha_legendary_name = responses["gacha_legendary_name"]
        await names.save()

        await inter.respond(
            view=utils.make_view(
                "Updated! Please note this will only affect public-facing"
                f" aspects.\n\nCommon: {names.gacha_common_name}\nUncommon:"
                f" {names.gacha_uncommon_name}\nRare: {names.gacha_rare_name}"
                f"\nEpic: {names.gacha_epic_name}\nLegendary:"
                f" {names.gacha_legendary_name}"
            )
        )


class RarityOddsModal(discord.ui.DesignerModal):
    def __init__(self, rarities: models.GachaRarities) -> None:
        super().__init__(
            discord.ui.Label(
                label="Common Odds",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="common_odds",
                    value=to_percent(rarities.common_odds),
                    max_length=10,
                ),
            ),
            discord.ui.Label(
                label="Uncommon Odds",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="uncommon_odds",
                    value=to_percent(rarities.uncommon_odds),
                    max_length=10,
                ),
            ),
            discord.ui.Label(
                label="Rare Odds",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="rare_odds",
                    value=to_percent(rarities.rare_odds),
                    max_length=10,
                ),
            ),
            discord.ui.Label(
                label="Epic Odds",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="epic_odds",
                    value=to_percent(rarities.epic_odds),
                    max_length=10,
                ),
            ),
            discord.ui.Label(
                label="Legendary Odds",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="legendary_odds",
                    value=to_percent(rarities.legendary_odds),
                    max_length=10,
                ),
            ),
            title="Edit Rarity Odds",
            custom_id="rarity_odds",
        )

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        config = await models.GuildConfig.fetch_create(
            int(inter.guild_id), {"gacha": True}
        )
        if typing.TYPE_CHECKING:
            assert config.gacha and isinstance(config.gacha, models.GachaConfig)

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=inter.guild_id)
        responses = utils.parse_modal_responses(self)

        common = convert_to_decimal(responses["common_odds"])
        uncommon = convert_to_decimal(responses["uncommon_odds"])
        rare = convert_to_decimal(responses["rare_odds"])
        epic = convert_to_decimal(responses["epic_odds"])
        legendary = convert_to_decimal(responses["legendary_odds"])

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

        await inter.respond(
            view=utils.make_view(
                f"Updated!\n\nCommon: {to_percent(common)}\nUncommon:"
                f" {to_percent(uncommon)}\nRare: {to_percent(rare)}"
                f"\nEpic: {to_percent(epic)}\nLegendary:"
                f" {to_percent(legendary)}"
            )
        )


class RarityColorsModal(discord.ui.DesignerModal):
    def __init__(self, rarities: models.GachaRarities) -> None:
        super().__init__(
            discord.ui.Label(
                label="Common Color",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="common_color",
                    value=rarities.common_color,
                    max_length=7,
                ),
            ),
            discord.ui.Label(
                label="Uncommon Color",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="uncommon_color",
                    value=rarities.uncommon_color,
                    max_length=7,
                ),
            ),
            discord.ui.Label(
                label="Rare Color",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="rare_color",
                    value=rarities.rare_color,
                    max_length=7,
                ),
            ),
            discord.ui.Label(
                label="Epic Color",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="epic_color",
                    value=rarities.epic_color,
                    max_length=7,
                ),
            ),
            discord.ui.Label(
                label="Legendary Color",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="legendary_color",
                    value=rarities.legendary_color,
                    max_length=7,
                ),
            ),
            title="Edit Rarity Colors",
            custom_id="rarity_colors",
        )

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        config = await models.GuildConfig.fetch_create(
            int(inter.guild_id), {"gacha": True}
        )
        if typing.TYPE_CHECKING:
            assert config.gacha and isinstance(config.gacha, models.GachaConfig)

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=inter.guild_id)
        responses = utils.parse_modal_responses(self)

        rarities.common_color = convert_to_color(responses["common_color"])
        rarities.uncommon_color = convert_to_color(responses["uncommon_color"])
        rarities.rare_color = convert_to_color(responses["rare_color"])
        rarities.epic_color = convert_to_color(responses["epic_color"])
        rarities.legendary_color = convert_to_color(responses["legendary_color"])
        await rarities.save()

        await inter.respond(
            view=utils.make_view(
                f"Updated!\n\nCommon: {rarities.common_color}\nUncommon:"
                f" {rarities.uncommon_color}\nRare: {rarities.rare_color}"
                f"\nEpic: {rarities.epic_color}\nLegendary:"
                f" {rarities.legendary_color}"
            )
        )


class GachaConfig(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Gacha Config"

    config = ragwort.SlashCommandGroup(
        name="gacha-config",
        description="Handles configuration of gacha mechanics.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={
            discord.InteractionContextType.guild,
        },
    )

    @config.command(
        name="info",
        description="Lists out the gacha configuration settings for the server.",
    )
    async def gacha_info(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"gacha": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.gacha and isinstance(config.gacha, models.GachaConfig)
            assert config.names and isinstance(config.names, models.Names)

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

        embed = discord.Embed(
            description="# Gacha Configuration\n" + "\n".join(str_builder),
            color=self.bot.color,
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
        embed.add_field(name="Names", value="\n".join(names_str_builder), inline=True)

        rarity_color_builder = [
            f"Common Color: {rarities.common_color}",
            f"Uncommon Color: {rarities.uncommon_color}",
            f"Rare Color: {rarities.rare_color}",
            f"Epic Color: {rarities.epic_color}",
            f"Legendary Color: {rarities.legendary_color}",
        ]
        embed.add_field(
            name="Rarity Colors", value="\n".join(rarity_color_builder), inline=True
        )

        rarity_odds_builder = [
            f"Common Odds: {to_percent(rarities.common_odds)}",
            f"Uncommon Odds: {to_percent(rarities.uncommon_odds)}",
            f"Rare Odds: {to_percent(rarities.rare_odds)}",
            f"Epic Odds: {to_percent(rarities.epic_odds)}",
            f"Legendary Odds: {to_percent(rarities.legendary_odds)}",
        ]
        embed.add_field(
            name="Rarity Odds", value="\n".join(rarity_odds_builder), inline=True
        )

        await ctx.respond(embed=embed)

    @config.command(
        name="toggle", description="Enables or disables the entire gacha system."
    )
    async def gacha_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should the gacha system be turned on or off?",
            name="toggle",
            choices=[
                discord.OptionChoice("on", "on"),
                discord.OptionChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        config = await ctx.fetch_config({"gacha": True})

        if toggle and not config.player_role:
            raise utils.CustomCheckFailure(
                "Player role not set. Please set it with"
                f" {self.bot.mention_command('config player set')} first."
            )

        await models.GachaConfig.filter(guild_id=ctx.guild_id).update(enabled=toggle)

        await ctx.respond(
            view=utils.make_view(
                f"Gacha system turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.command(
        name="names",
        description="Edit the displayed names used for various parts of the gacha.",
    )
    @ragwort.auto_defer(enabled=False)
    async def gacha_name(
        self,
        ctx: utils.THIASlashContext,
        to_change: str = ragwort.Option(
            "The names to change.",
            choices=[
                discord.OptionChoice("Currency Names", "currency_names"),
                discord.OptionChoice("Rarity Names", "rarity_names"),
            ],
        ),
    ) -> None:
        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)

        if to_change == "currency_names":
            modal = CurrencyNamesModal(config.names)
        elif to_change == "rarity_names":
            modal = RarityNamesModal(config.names)
        else:
            raise utils.BadArgument("Invalid choice.")

        await ctx.send_modal(modal)

    @config.command(name="cost", description="Sets the cost of a single gacha use.")
    async def gacha_cost(
        self,
        ctx: utils.THIASlashContext,
        cost: int = ragwort.Option(
            "The cost of a single gacha use.", min_value=1, max_value=2147483647
        ),
    ) -> None:
        if cost > 2147483647:  # just in case
            raise utils.BadArgument(
                "This amount is too high. Please set an amount at or lower than"
                " 2,147,483,647 (signed 32-bit integer limit)."
            )

        await ctx.fetch_config({"gacha": True})
        await models.GachaConfig.filter(guild_id=ctx.guild_id).update(
            currency_cost=cost
        )

        await ctx.respond(
            view=utils.make_view(
                f"Updated! The cost of a single gacha use is now {cost}."
            )
        )

    @config.command(
        name="draw-duplicates",
        description="Toggles the ability for players draw items they already own.",
    )
    async def gacha_draw_duplicates(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should players be allowed to draw items they already own?",
            name="toggle",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "yes"

        await ctx.fetch_config({"gacha": True})
        await models.GachaConfig.filter(guild_id=ctx.guild_id).update(
            draw_duplicates=toggle
        )

        await ctx.respond(
            view=utils.make_view(
                f"Drawing duplicates turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.command(
        name="rarities",
        description="Allows you to edit the rarity colors and odds.",
    )
    @ragwort.auto_defer(enabled=False)
    async def gacha_rarities(
        self,
        ctx: utils.THIASlashContext,
        to_change: str = ragwort.Option(
            "The aspect of the rarities to change.",
            choices=[
                discord.OptionChoice("Rarity Colors", "colors"),
                discord.OptionChoice("Rarity Odds", "odds"),
                discord.OptionChoice("Reset Rarity Colors", "reset_colors"),
                discord.OptionChoice("Reset Rarity Odds", "reset_odds"),
            ],
        ),
    ) -> None:
        config = await ctx.fetch_config({"gacha": True})
        if typing.TYPE_CHECKING:
            assert config.gacha and isinstance(config.gacha, models.GachaConfig)

        rarities, _ = await models.GachaRarities.get_or_create(guild_id=ctx.guild_id)

        if to_change == "odds":
            modal = RarityOddsModal(rarities)
        elif to_change == "colors":
            modal = RarityColorsModal(rarities)
        elif to_change == "reset_colors":
            await ctx.defer()

            for name, field in rarities._meta.fields_map.items():
                if name.endswith("_color"):
                    setattr(rarities, name, field.default)

            await rarities.save()
            await ctx.respond(
                view=utils.make_view(
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
            await ctx.respond(
                view=utils.make_view(
                    "Updated! The odds have been reset to the defaults."
                )
            )
            return
        else:
            raise utils.BadArgument("Invalid choice.")

        await ctx.send_modal(modal)

    @config.command(
        name="help", description="Tells you how to set up the gacha system."
    )
    async def gacha_help(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            "To set up the gacha system, follow the gacha setup guide below.",
            title="Set Up Gacha System",
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Gacha Setup Guide",
                url="https://pythia.astrea.cc/setup/gacha_setup",
            )
        )
        await ctx.respond(view=utils.quick_view(container))


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    bot.add_cog(GachaConfig(bot))
